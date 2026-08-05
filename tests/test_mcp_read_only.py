from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tmf.git import GitRepo
from tmf.explain import explain_claim
from tmf.mcp_server import McpService, tools_list
from tmf.retrieve import retrieve_path, retrieve_text
from tmf.store import StoreNotInitializedError, configure_state_root


def tree_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return "MISSING"
    for path in sorted(root.rglob("*")):
        stat = path.lstat()
        digest.update(f"{path.relative_to(root)}\0{stat.st_mode}\0{stat.st_size}\0{stat.st_mtime_ns}\0".encode())
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


class McpReadOnlyTests(unittest.TestCase):
    def tearDown(self):
        configure_state_root(None)

    def make_repo(self, root: Path) -> Path:
        repo = root / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "tmf@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "tmf"], cwd=repo, check=True)
        (repo / "sample.py").write_text("def target():\n    return 1\n", encoding="utf-8")
        subprocess.run(["git", "add", "sample.py"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=repo, check=True)
        return repo

    def test_surface_excludes_warm(self):
        names = {tool["name"] for tool in tools_list()}
        self.assertEqual(names, {"tmf_context", "tmf_retrieve", "tmf_explain", "tmf_callers", "tmf_readers", "tmf_writers", "tmf_subtypes", "tmf_status"})

    def test_uninitialized_store_fails_without_creating_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root)
            state = root / "missing-state"
            with self.assertRaises(StoreNotInitializedError):
                McpService(repo, state)
            self.assertFalse(state.exists())
            self.assertFalse((repo / ".tmf").exists())

    def test_stale_queries_do_not_modify_repo_or_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root)
            state = root / "state"
            configure_state_root(state)
            retrieve_path(repo, "sample.py")
            (repo / "sample.py").write_text("def target():\n    return 2\n", encoding="utf-8")
            service = McpService(repo, state)
            before_repo, before_state = tree_fingerprint(repo), tree_fingerprint(state)
            result = service.tmf_retrieve("target", 5)
            claim_id = result["claims"][0]["id"]
            service.tmf_context("target", 3000)
            service.tmf_explain(claim_id, True)
            service.tmf_callers(claim_id=claim_id)
            service.tmf_status()
            self.assertFalse(result["claims"][0]["fresh"])
            self.assertEqual(tree_fingerprint(repo), before_repo)
            self.assertEqual(tree_fingerprint(state), before_state)
            self.assertFalse((repo / ".tmf").exists())

    def test_read_only_retrieve_does_not_expand_after_partial_lexical_hit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root)
            state = root / "state"
            configure_state_root(state)
            retrieve_path(repo, "sample.py")
            with (
                patch("tmf.retrieve._add_router_seeds", side_effect=AssertionError("router expansion called")),
                patch("tmf.retrieve._add_embedding_seed_expansion", side_effect=AssertionError("embedding expansion called")),
            ):
                result = retrieve_text(repo, "target", limit=50, read_only=True)

            self.assertTrue(result.claims)
            self.assertLess(len(result.claims), 50)

    def test_mcp_retrieve_returns_nodes_not_edge_records(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root)
            state = root / "state"
            configure_state_root(state)
            retrieve_path(repo, "sample.py")

            service = McpService(repo, state)
            result = service.tmf_retrieve("target", limit=50)

            self.assertTrue(result["claims"])
            self.assertTrue(all(item.get("scope") != "cross-repo" for item in result["claims"]))

    def test_read_only_explain_uses_stored_graph_without_warm_scan(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root)
            state = root / "state"
            configure_state_root(state)
            claim = retrieve_path(repo, "sample.py").claims[0].claim
            with (
                patch("tmf.explain._graph_with_fresh_edges", side_effect=AssertionError("graph scan called")),
                patch("tmf.explain.warm_is_complete", side_effect=AssertionError("warm scan called")),
            ):
                result = explain_claim(GitRepo(repo), claim, read_only=True)

            self.assertEqual(result["graph"], claim.body.get("graph", {}))
            self.assertEqual(result["graph_coverage"], "partial")

    def test_locator_view_caps_graph_lists_and_keeps_counts(self):
        explained = {
            "id": "claim_fn_test",
            "claim": "test",
            "kind": "structure",
            "scope": "function",
            "qualname": "target",
            "trust": {"level": "observed", "label": "source"},
            "fresh": True,
            "stale_reasons": [],
            "confidence": 0.4,
            "confidence_cap_applied": False,
            "anchors": [],
            "action_hint": "inspect",
            "belief_provenance": [],
            "freshness_bindings": [],
            "graph": {"callees": [{"target_id": str(index)} for index in range(8)], "unresolved_calls": [{"expr": "x"}] * 20},
            "graph_coverage": "partial",
        }

        result = McpService._locator_view(explained)

        self.assertEqual(result["callees_count"], 8)
        self.assertEqual(len(result["callees"]), 5)
        self.assertEqual(result["unresolved_call_count"], 20)
        self.assertNotIn("unresolved_calls", result)


if __name__ == "__main__":
    unittest.main()
