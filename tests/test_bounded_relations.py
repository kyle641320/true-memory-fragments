from __future__ import annotations

import subprocess
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from tmf.git import GitRepo
from tmf.ids import stable_function_claim_id
from tmf.mcp_server import McpService, tools_list
from tmf.relations import RequestFreshnessCache, bounded_fragment
from tmf.store import Store
from tmf.warm import warm_repo
from tmf.retrieve import refresh_path, retrieve_path, retrieve_text, reverse_callers


def init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "master"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "x@example.test"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "x"], cwd=root, check=True)
    (root / "a.py").write_text(
        "def helper():\n    return 1\n\ndef caller():\n    return helper()\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "a.py"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)


class BoundedRelationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        init_repo(self.repo)
        warm_repo(self.repo)
        self.entry = stable_function_claim_id("a.py", "caller")

    def tearDown(self):
        self.tmp.cleanup()

    def test_endpoint_and_relation_kind_query_never_scans_claim_store(self):
        store = Store(self.repo)
        with patch.object(Store, "iter_claims", side_effect=AssertionError("full scan forbidden")):
            fragment = bounded_fragment(
                GitRepo(self.repo), store, entry=self.entry, relations=["calls"],
                hop_limit=1, boundary_types=["function"], max_nodes=4, max_edges=2,
            )
        self.assertEqual(["calls"], [edge["relation_kind"] for edge in fragment["verified_hops"]])
        self.assertLessEqual(len(fragment["verified_hops"]), 2)

    def test_required_constraints_and_hard_limits(self):
        schema = next(tool for tool in tools_list() if tool["name"] == "tmf_fragment")["inputSchema"]
        self.assertEqual(
            {"entry", "relations", "hop_limit", "boundary_types"},
            set(schema["required"]),
        )
        service = McpService(self.repo)
        with self.assertRaises(ValueError):
            service.tmf_fragment(self.entry, ["calls"], 5, ["function"])
        with self.assertRaises(ValueError):
            service.tmf_fragment(self.entry, ["calls"], 1, ["function"], max_nodes=65)

    def test_fragment_contract_and_missing_index_gap(self):
        service = McpService(self.repo)
        fragment = service.tmf_fragment(self.entry, ["calls"], 1, ["function"], 4, 2)
        self.assertEqual(
            {"entry", "verified_hops", "boundaries", "gaps", "stale_or_unknown", "stop_reason", "coverage", "routing_shape"},
            set(fragment),
        )
        service.store.index.close()
        service.store.index.path.unlink()
        with patch.object(Store, "iter_claims", side_effect=AssertionError("missing index must not scan")):
            gap = service.tmf_fragment(self.entry, ["calls"], 1, ["function"], 4, 2)
        self.assertEqual("partial", gap["coverage"])
        self.assertEqual("endpoint_edge_index_missing", gap["gaps"][0]["reason"])

    def test_request_freshness_cache_invalidates_on_source_change(self):
        repo = GitRepo(self.repo)
        claim = Store(self.repo).get_claim(self.entry)
        self.assertIsNotNone(claim)
        cache = RequestFreshnessCache(repo)
        self.assertTrue(cache.check(claim).fresh)
        (self.repo / "a.py").write_text(
            "def helper():\n    return 1\n\ndef caller():\n    return helper() + 1\n",
            encoding="utf-8",
        )
        self.assertFalse(cache.check(claim).fresh)

    def test_context_and_thin_explain_do_not_scan_claim_store(self):
        service = McpService(self.repo)
        caller = service.store.get_claim(self.entry)
        self.assertIsNotNone(caller)
        with patch.object(Store, "iter_claims", side_effect=AssertionError("thin graph fallback forbidden")):
            relations = service._bounded_relations([caller], edge_budget=2)
            explained = service.tmf_explain(self.entry, full=False)
        self.assertTrue(relations)
        self.assertEqual("thin", explained["view"])

    def test_missing_index_retrieve_does_not_scan_or_rebuild(self):
        store = Store(self.repo)
        store.index.close()
        store.index.path.unlink()
        with patch.object(Store, "iter_claims", side_effect=AssertionError("ordinary retrieve must not scan")):
            result = retrieve_text(self.repo, "caller", limit=3)
        self.assertEqual([], result.claims)
        self.assertEqual(["inverted_index_missing_no_full_store_fallback"], result.gaps)
        self.assertFalse(Store(self.repo).index.valid())

    def test_path_miss_is_read_only_and_reports_refresh_gap(self):
        repo = self.repo / "miss.py"
        repo.write_text("def new_function():\n    return 1\n", encoding="utf-8")
        with (
            patch("tmf.retrieve.derive_claims_for_path", side_effect=AssertionError("derive forbidden")),
            patch.object(Store, "write_lock", side_effect=AssertionError("write lock forbidden")),
            patch.object(Store, "iter_claims", side_effect=AssertionError("full scan forbidden")),
        ):
            result = retrieve_path(self.repo, "miss.py")
        self.assertEqual([], result.claims)
        self.assertEqual(["path_claims_missing_refresh_required"], result.gaps)
        self.assertEqual(["miss.py"], list(result.source_fallback))

    def test_stale_path_and_lexical_hits_are_omitted_without_writes(self):
        (self.repo / "a.py").write_text(
            "def helper():\n    return 2\n\ndef caller():\n    return helper() + 1\n",
            encoding="utf-8",
        )
        with (
            patch("tmf.retrieve.derive_claims_for_path", side_effect=AssertionError("derive forbidden")),
            patch.object(Store, "write_lock", side_effect=AssertionError("write lock forbidden")),
            patch.object(Store, "iter_claims", side_effect=AssertionError("full scan forbidden")),
        ):
            path_result = retrieve_path(self.repo, "a.py")
            text_result = retrieve_text(self.repo, "caller", limit=3)
        self.assertEqual([], path_result.claims)
        self.assertIn("stale_path_claims_omitted_refresh_required", path_result.gaps)
        self.assertEqual([], text_result.claims)
        self.assertIn("stale_lexical_claim_omitted_refresh_required", text_result.gaps)
        self.assertEqual(["a.py"], list(text_result.source_fallback))

    def test_explicit_refresh_is_the_only_write_path(self):
        (self.repo / "a.py").write_text(
            "def helper():\n    return 2\n\ndef caller():\n    return helper() + 1\n",
            encoding="utf-8",
        )
        with patch.object(Store, "iter_claims", side_effect=AssertionError("path refresh must stay local")):
            refreshed = refresh_path(self.repo, "a.py")
        self.assertTrue(refreshed.claims)
        self.assertEqual([], refreshed.gaps)
        self.assertTrue(all(item.fresh for item in refreshed.claims))

    def test_stale_reverse_callers_query_is_read_only(self):
        helper = stable_function_claim_id("a.py", "helper")
        (self.repo / "a.py").write_text(
            "def helper():\n    return 2\n\ndef caller():\n    return helper() + 1\n",
            encoding="utf-8",
        )
        with (
            patch("tmf.retrieve.derive_claims_for_path", side_effect=AssertionError("derive forbidden")),
            patch.object(Store, "write_lock", side_effect=AssertionError("write lock forbidden")),
            patch.object(Store, "iter_claims", side_effect=AssertionError("full scan forbidden")),
        ):
            result = reverse_callers(self.repo, helper)
        self.assertEqual([], result["callers"])
        self.assertGreater(result["stale_skipped"], 0)

    def test_configured_semantic_retrieval_and_status_never_scan_claim_store(self):
        service = McpService(self.repo)
        with (
            patch.dict("os.environ", {"TMF_ROUTER_COMMAND": "false"}, clear=False),
            patch.object(Store, "iter_claims", side_effect=AssertionError("full scan forbidden")),
        ):
            result = retrieve_text(self.repo, "semantic-miss", limit=3)
            status = service.tmf_status()
        self.assertLessEqual(len(result.claims), 3)
        self.assertEqual(status["claims"], status["freshness_sample"]["checked"])
        self.assertLessEqual(status["freshness_sample"]["checked"], 20)
        self.assertIn("index_schema_version", status)

    def test_status_missing_index_returns_gap_without_scan(self):
        service = McpService(self.repo)
        service.store.index.close()
        service.store.index.path.unlink()
        with patch.object(Store, "iter_claims", side_effect=AssertionError("full scan forbidden")):
            status = service.tmf_status()
        self.assertEqual("partial", status["coverage"])
        self.assertEqual(["inverted_index_missing_no_full_store_fallback"], status["gaps"])


if __name__ == "__main__":
    unittest.main()
