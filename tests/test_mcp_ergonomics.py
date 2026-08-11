from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tmf.mcp_server import McpService, tools_list
from tmf.ids import stable_function_claim_id


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-b", "master"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(["git", "config", "user.email", "tmf@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "tmf"], cwd=root, check=True)
    (root / "a.py").write_text(
        "VALUE = 1\n\ndef helper():\n    return VALUE\n\ndef caller():\n    return helper()\n",
        encoding="utf-8",
    )
    (root / "b.py").write_text(
        "def helper():\n    return 2\n\ndef other():\n    return helper()\n",
        encoding="utf-8",
    )
    (root / "Child.java").write_text(
        "class Base {}\ninterface Marker {}\nclass Child extends Base implements Marker {}\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "a.py", "b.py", "Child.java"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(["git", "commit", "-m", "fixture"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


class McpErgonomicsTests(unittest.TestCase):
    def test_tool_descriptions_carry_framework_and_payloads_are_slim(self):
        listed = {tool["name"]: tool for tool in tools_list()}
        self.assertIn("tmf_context", listed)
        self.assertTrue(listed["tmf_context"]["description"].startswith("Investigating a codebase: start here"))
        self.assertIn("Partial coverage", listed["tmf_retrieve"]["description"])
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            _init_repo(repo)
            svc = McpService(repo)
            svc.tmf_warm()
            payload = svc.tmf_retrieve("helper caller", limit=2)
            self.assertNotIn("framework", payload)
            self.assertEqual(payload["coverage"], "complete")
            self.assertTrue(payload["claims"])

    def test_name_addressing_unique_ambiguous_and_claim_id_compat(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            _init_repo(repo)
            svc = McpService(repo)
            svc.tmf_warm()
            unique = svc.tmf_callers(qualname="caller", path="a.py")
            self.assertEqual(unique["addressing"]["mode"], "qualname")
            self.assertIn("callers", unique)
            ambiguous = svc.tmf_callers(qualname="helper")
            self.assertEqual(ambiguous["status"], "ambiguous")
            self.assertGreaterEqual(len(ambiguous["candidates"]), 2)
            self.assertNotIn("callers", ambiguous)
            compat = svc.tmf_callers(claim_id=stable_function_claim_id("a.py", "helper"))
            self.assertEqual(compat["addressing"]["mode"], "claim_id")
            self.assertIn("callers", compat)

    def test_tmf_context_is_deterministic_thin_and_budgeted(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            _init_repo(repo)
            svc = McpService(repo)
            svc.tmf_warm()
            first = svc.tmf_context("who calls helper and reads VALUE", max_chars=900)
            second = svc.tmf_context("who calls helper and reads VALUE", max_chars=900)
            self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
            text = json.dumps(first, sort_keys=True)
            self.assertLessEqual(len(text), 900)
            self.assertNotIn('"body"', text)
            self.assertIn("claims", first)
            self.assertIn("relations", first)
            self.assertIn("coverage", first)
            tiny = svc.tmf_context("who calls helper and reads VALUE", max_chars=220)
            self.assertTrue(tiny["truncated"])
            self.assertLessEqual(len(json.dumps(tiny, sort_keys=True)), 220)

    def test_context_expands_only_fresh_one_hop_relations_with_budget(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            _init_repo(repo)
            svc = McpService(repo)
            svc.tmf_warm()
            payload = svc.tmf_context("helper caller", max_chars=5000)
            self.assertLessEqual(len(payload["relations"]), 8)
            self.assertTrue(any(r["kind"] == "calls" for r in payload["relations"]))
            self.assertTrue(all(r["coverage"] == "partial" and r["unresolved"] >= 0 for r in payload["relations"]))
            call_relations = [r for r in payload["relations"] if r["kind"] == "calls"]
            self.assertTrue(all(set(r["endpoints"]) == {"caller_id", "callee_id"} for r in call_relations))
            self.assertTrue(all(set(r["endpoint_hints"]) == {"caller_id", "callee_id"} for r in call_relations))
            self.assertTrue(all(r["endpoint_hints"]["caller_id"]["qualname"] for r in call_relations))
            self.assertTrue(all(r["endpoint_hints"]["callee_id"]["path"] for r in call_relations))

    def test_truncated_context_keeps_relation_endpoint_hints(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            _init_repo(repo)
            svc = McpService(repo)
            svc.tmf_warm()
            payload = svc.tmf_context("helper caller", max_chars=1800)
            self.assertTrue(payload["truncated"])
            self.assertTrue(payload["relations"])
            self.assertIn("endpoint_hints", payload["relations"][0])
            hint = next(iter(payload["relations"][0]["endpoint_hints"].values()))
            self.assertIn("qualname", hint)
            self.assertIn("path", hint)

    def test_relation_endpoint_hints_require_fresh_endpoint_claims(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            _init_repo(repo)
            svc = McpService(repo)
            svc.tmf_warm()
            caller_id = stable_function_claim_id("a.py", "caller")
            helper_id = stable_function_claim_id("a.py", "helper")
            caller = svc.store.get_claim(caller_id)
            helper_path = svc.store.claim_path(helper_id)
            helper = json.loads(helper_path.read_text(encoding="utf-8"))
            helper["bindings"][0]["file_blob"] = "stale-endpoint-blob"
            helper["bindings"][0]["fn_hash"] = "stale-endpoint-function"
            helper_path.write_text(json.dumps(helper), encoding="utf-8")

            self.assertIsNotNone(caller)
            relations = svc._bounded_relations([caller], edge_budget=8)
            self.assertFalse(any(r["kind"] == "calls" and r["endpoints"].get("callee_id") == helper_id for r in relations))

    def test_context_ambiguity_does_not_guess_relation_chain(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            _init_repo(repo)
            svc = McpService(repo)
            svc.tmf_warm()
            ambiguous = svc.tmf_callers(qualname="helper")
            self.assertEqual(ambiguous["status"], "ambiguous")
            context = svc.tmf_context("helper", max_chars=5000)
            self.assertFalse(any("chain" in r or "runtime" in r for r in context["relations"]))


if __name__ == "__main__":
    unittest.main()
