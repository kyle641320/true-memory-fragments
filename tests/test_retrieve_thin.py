from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


class RetrieveThinTests(unittest.TestCase):
    def test_default_retrieve_is_thin_and_omits_thick_untrusted_text(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            run(["git", "init", "-b", "master"], repo)
            run(["git", "config", "user.email", "tmf@example.com"], repo)
            run(["git", "config", "user.name", "tmf"], repo)
            (repo / "app.py").write_text('def charge(x):\n    """Reject negative balances because ledger settlement cannot carry debt."""\n    return x >= 0\n', encoding="utf-8")
            run(["git", "add", "app.py"], repo)
            run(["git", "commit", "-m", "Reject negative balances because settlement cannot carry debt"], repo)
            data = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "app.py", "--repo", str(repo), "--model-derive"], ROOT).stdout)
            self.assertEqual(data["view"], "thin")
            claim = data["claims"][0]
            self.assertIn("id", claim)
            self.assertIn("trust", claim)
            self.assertIn("fresh", claim)
            self.assertIn("action_hint", claim)
            self.assertIn("anchors", claim)
            self.assertNotIn("body", claim)
            self.assertNotIn("bindings", claim)
            self.assertNotIn("quoted_text_untrusted_data", json.dumps(claim))
            binding = claim["freshness_binding_refs"][0]
            self.assertLessEqual(len(binding["file_blob_prefix"]), 12)

    def test_retrieve_full_expands_one_claim(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            run(["git", "init", "-b", "master"], repo)
            run(["git", "config", "user.email", "tmf@example.com"], repo)
            run(["git", "config", "user.name", "tmf"], repo)
            (repo / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
            run(["git", "add", "app.py"], repo)
            run(["git", "commit", "-m", "init"], repo)
            data = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "app.py", "--repo", str(repo)], ROOT).stdout)
            claim_id = data["claims"][0]["id"]
            full = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "--full", claim_id, "--repo", str(repo)], ROOT).stdout)
            self.assertEqual(full["id"], claim_id)
            self.assertIn("claim_record", full)
            self.assertIn("body", full["claim_record"])
            self.assertIn("freshness_bindings", full)

    def test_thin_includes_fresh_cross_file_callers_from_edge_claims(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            run(["git", "init", "-b", "master"], repo)
            run(["git", "config", "user.email", "tmf@example.com"], repo)
            run(["git", "config", "user.name", "tmf"], repo)
            (repo / "a.py").write_text("from b import helper\n\ndef main():\n    return helper()\n", encoding="utf-8")
            (repo / "b.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
            run(["git", "add", "a.py", "b.py"], repo)
            run(["git", "commit", "-m", "init"], repo)
            run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "b.py", "--repo", str(repo)], ROOT)
            run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "a.py", "--repo", str(repo)], ROOT)
            data = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "b.py", "--repo", str(repo)], ROOT).stdout)
            helper = [c for c in data["claims"] if c.get("qualname") == "helper"][0]
            self.assertEqual(helper["callers"][0]["source_qualname"], "main")
            self.assertEqual(helper["callers"][0]["resolution"], "from_import_direct_top_level")
            self.assertEqual(helper["graph_coverage"], "partial")
            self.assertEqual(helper["unresolved_call_count"], 0)

            (repo / "b.py").write_text("def helper():\n    x = 1\n    return x\n", encoding="utf-8")
            data = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "b.py", "--repo", str(repo)], ROOT).stdout)
            helper = [c for c in data["claims"] if c.get("qualname") == "helper"][0]
            self.assertEqual(helper["callers"], [])


if __name__ == "__main__":
    unittest.main()
