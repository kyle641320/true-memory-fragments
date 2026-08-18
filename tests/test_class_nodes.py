from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.ids import stable_class_claim_id
from tmf.retrieve import refresh_path
from tmf.store import Store

ROOT = Path(__file__).resolve().parents[1]


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def init_repo(tmp_path: Path, content: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init", "-b", "master"], repo)
    run(["git", "config", "user.email", "tmf@example.com"], repo)
    run(["git", "config", "user.name", "tmf"], repo)
    (repo / "m.py").write_text(content, encoding="utf-8")
    run(["git", "add", "m.py"], repo)
    run(["git", "commit", "-m", "init"], repo)
    return repo


class ClassNodeTests(unittest.TestCase):
    def test_class_claim_is_derived_and_fresh(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), "class C:\n    def m(self):\n        return 1\n")
            data = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "m.py", "--refresh", "--repo", str(repo)], ROOT).stdout)
            classes = [c for c in data["claims"] if c["scope"] == "class"]
            self.assertEqual(len(classes), 1)
            self.assertEqual(classes[0]["qualname"], "C")
            claim = Store(repo).get_claim(stable_class_claim_id("m.py", "C"))
            self.assertIsNotNone(claim)
            self.assertTrue(check_freshness(GitRepo(repo), claim).fresh)

    def test_class_body_change_stales_class_and_method_change_over_invalidates_class(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), "class C:\n    def m(self):\n        return 1\n")
            refresh_path(repo, "m.py")
            claim = Store(repo).get_claim(stable_class_claim_id("m.py", "C"))
            self.assertIsNotNone(claim)
            (repo / "m.py").write_text("class C:\n    def m(self):\n        return 2\n", encoding="utf-8")
            freshness = check_freshness(GitRepo(repo), claim)
            self.assertFalse(freshness.fresh)
            self.assertTrue(any("class_hash mismatch" in item for item in freshness.stale_bindings), freshness.stale_bindings)

    def test_class_delete_reconciles_tombstone(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), "class C:\n    def m(self):\n        return 1\n")
            refresh_path(repo, "m.py")
            claim_id = stable_class_claim_id("m.py", "C")
            self.assertIsNotNone(Store(repo).get_claim(claim_id))
            (repo / "m.py").write_text("def f():\n    return 1\n", encoding="utf-8")
            refresh_path(repo, "m.py")
            self.assertIsNone(Store(repo).get_claim(claim_id))


if __name__ == "__main__":
    unittest.main()
