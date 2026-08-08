from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from tmf.derive import derive_call_edge_claim


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def init_repo(tmp_path: Path, content: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init"], repo)
    run(["git", "config", "user.email", "tmf@example.com"], repo)
    run(["git", "config", "user.name", "tmf"], repo)
    (repo / "m.py").write_text(content, encoding="utf-8")
    run(["git", "add", "m.py"], repo)
    run(["git", "commit", "-m", "init"], repo)
    return repo


class CallsEdgeTests(unittest.TestCase):
    def test_module_local_name_call_and_reverse_caller(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), "def helper():\n    return 1\n\ndef main():\n    return helper()\n")
            data = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "m.py", "--repo", str(repo)], ROOT).stdout)
            by_name = {c.get("qualname"): c for c in data["claims"] if c["scope"] == "function"}
            self.assertEqual(by_name["main"]["callees"][0]["target_qualname"], "helper")
            self.assertEqual(by_name["main"]["callees"][0]["evidence"], "observed")
            self.assertTrue(by_name["helper"]["callers"])
            self.assertFalse(by_name["main"]["unresolved_calls"])

    def test_self_method_call_resolves_only_same_class(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), "class C:\n    def a(self):\n        return self.b()\n    def b(self):\n        return 2\n")
            data = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "m.py", "--repo", str(repo)], ROOT).stdout)
            by_name = {c.get("qualname"): c for c in data["claims"] if c["scope"] == "function"}
            self.assertEqual(by_name["C.a"]["callees"][0]["target_qualname"], "C.b")
            self.assertTrue(by_name["C.b"]["callers"])

    def test_unknown_attribute_and_external_name_are_unresolved_not_edges(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), "def main(obj):\n    print(obj.run())\n    return missing()\n")
            data = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "m.py", "--repo", str(repo)], ROOT).stdout)
            main = [c for c in data["claims"] if c.get("qualname") == "main"][0]
            self.assertFalse(main["callees"])
            exprs = {item["expr"] for item in main["unresolved_calls"]}
            self.assertIn("print", exprs)
            self.assertIn("obj.run", exprs)
            self.assertIn("missing", exprs)


    def test_call_edge_claim_uses_precomputed_anchors_without_reading_source(self):
        edge = SimpleNamespace(
            caller_path="m.py",
            callee_path="m.py",
            caller_fn_hash="callerhash",
            callee_fn_hash="calleehash",
            caller_id="fn:m.py:main",
            callee_id="fn:m.py:helper",
            caller_qualname="main",
            callee_qualname="helper",
            resolution="module_local_name",
        )

        class Repo:
            def blob_sha(self, path):
                return "blob"

            def head(self):
                return "HEAD"

            def read_file(self, path):
                raise AssertionError("precomputed anchors should avoid source reads")

        claim = derive_call_edge_claim(
            Repo(),
            edge,
            {
                "fn:m.py:main": {"path": "m.py", "line_start": 3, "line_end": 4, "qualname": "main"},
                "fn:m.py:helper": {"path": "m.py", "line_start": 1, "line_end": 2, "qualname": "helper"},
            },
        )
        self.assertEqual(claim.body["caller_anchor"]["line_start"], 3)
        self.assertEqual(claim.body["callee_anchor"]["line_start"], 1)

    def test_rename_delete_recomputes_edges_and_removes_dead_endpoint(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), "def helper():\n    return 1\n\ndef main():\n    return helper()\n")
            run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "m.py", "--repo", str(repo)], ROOT)
            (repo / "m.py").write_text("def renamed():\n    return 1\n\ndef main():\n    return renamed()\n", encoding="utf-8")
            data = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "m.py", "--repo", str(repo)], ROOT).stdout)
            by_name = {c.get("qualname"): c for c in data["claims"] if c["scope"] == "function"}
            self.assertNotIn("helper", by_name)
            self.assertEqual(by_name["main"]["callees"][0]["target_qualname"], "renamed")
            disk_claims = [json.loads(p.read_text()) for p in sorted((repo / ".tmf" / "claims").glob("*.json"))]
            disk_names = {c["body"].get("qualname") for c in disk_claims if c["scope"] == "function"}
            self.assertEqual(disk_names, {"main", "renamed"})


if __name__ == "__main__":
    unittest.main()

class CallsNestedAttributionTests(unittest.TestCase):
    def test_nested_function_call_is_not_attributed_to_outer(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), "def helper():\n    return 1\n\ndef outer():\n    def inner():\n        return helper()\n    return inner\n")
            data = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "m.py", "--repo", str(repo)], ROOT).stdout)
            by_name = {c.get("qualname"): c for c in data["claims"] if c["scope"] == "function"}
            self.assertFalse(by_name["outer"]["callees"])
            self.assertEqual(by_name["outer.inner"]["callees"][0]["target_qualname"], "helper")

