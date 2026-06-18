from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.ids import stable_declaration_claim_id
from tmf.retrieve import retrieve_path
from tmf.store import Store

ROOT = Path(__file__).resolve().parents[1]


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


class DeclarationNodeTests(unittest.TestCase):
    def test_module_constant_declaration_is_derived_and_fresh(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), "TIMEOUT = 30\n\ndef f():\n    return TIMEOUT\n")
            data = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "m.py", "--repo", str(repo)], ROOT).stdout)
            declarations = [c for c in data["claims"] if c["scope"] == "declaration"]
            self.assertEqual(len(declarations), 1)
            self.assertEqual(declarations[0]["qualname"], "TIMEOUT")
            claim = Store(repo).get_claim(stable_declaration_claim_id("m.py", "TIMEOUT"))
            self.assertIsNotNone(claim)
            self.assertTrue(check_freshness(GitRepo(repo), claim).fresh)

    def test_module_declaration_change_stales_and_delete_reconciles(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), "TIMEOUT = 30\n")
            retrieve_path(repo, "m.py")
            claim_id = stable_declaration_claim_id("m.py", "TIMEOUT")
            claim = Store(repo).get_claim(claim_id)
            self.assertIsNotNone(claim)
            (repo / "m.py").write_text("TIMEOUT = 60\n", encoding="utf-8")
            freshness = check_freshness(GitRepo(repo), claim)
            self.assertFalse(freshness.fresh)
            self.assertTrue(any("declaration_hash mismatch" in item for item in freshness.stale_bindings), freshness.stale_bindings)
            (repo / "m.py").write_text("def f():\n    return 1\n", encoding="utf-8")
            retrieve_path(repo, "m.py")
            self.assertIsNone(Store(repo).get_claim(claim_id))


if __name__ == "__main__":
    unittest.main()
