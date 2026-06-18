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


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init"], repo)
    run(["git", "config", "user.email", "tmf@example.com"], repo)
    run(["git", "config", "user.name", "tmf"], repo)
    (repo / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    run(["git", "add", "app.py"], repo)
    run(["git", "commit", "-m", "init"], repo)
    return repo


class TmfV0Tests(unittest.TestCase):
    def test_retrieve_path_creates_fresh_claim(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td))
            proc = run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "app.py", "--repo", str(repo)], ROOT)
            data = json.loads(proc.stdout)
            self.assertTrue(data["claims"])
            self.assertTrue(data["claims"][0]["fresh"])
            self.assertTrue((repo / ".tmf" / "claims").exists())

    def test_retrieve_path_rederives_in_place_after_committed_blob_change(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td))
            run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "app.py", "--repo", str(repo)], ROOT)
            before_files = sorted((repo / ".tmf" / "claims").glob("*.json"))
            file_claims = [p for p in before_files if json.loads(p.read_text())["scope"] == "file"]
            self.assertEqual(len(file_claims), 1)
            before_name = file_claims[0].name
            before_blob = json.loads(file_claims[0].read_text())["bindings"][0]["file_blob"]

            (repo / "app.py").write_text("def add(a, b):\n    return a + b + 1\n", encoding="utf-8")
            run(["git", "add", "app.py"], repo)
            run(["git", "commit", "-m", "change"], repo)
            proc = run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "app.py", "--repo", str(repo)], ROOT)
            data = json.loads(proc.stdout)
            self.assertTrue(data["claims"][0]["fresh"])

            after_files = sorted((repo / ".tmf" / "claims").glob("*.json"))
            after_file_claims = [p for p in after_files if json.loads(p.read_text())["scope"] == "file"]
            self.assertEqual(len(after_file_claims), 1)
            self.assertEqual(after_file_claims[0].name, before_name)
            after_blob = json.loads(after_file_claims[0].read_text())["bindings"][0]["file_blob"]
            self.assertNotEqual(after_blob, before_blob)

    def test_uncommitted_worktree_change_is_not_misreported_fresh(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td))
            run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "app.py", "--repo", str(repo)], ROOT)
            before_files = sorted((repo / ".tmf" / "claims").glob("*.json"))
            before_file = [p for p in before_files if json.loads(p.read_text())["scope"] == "file"][0]
            before_blob = json.loads(before_file.read_text())["bindings"][0]["file_blob"]

            # No commit: the coding-agent common case. Freshness must track the
            # working tree, not HEAD:path.
            (repo / "app.py").write_text("def add(a, b):\n    return a + b + 2\n", encoding="utf-8")
            proc = run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "app.py", "--repo", str(repo)], ROOT)
            data = json.loads(proc.stdout)
            self.assertTrue(data["claims"][0]["fresh"])
            after_files = sorted((repo / ".tmf" / "claims").glob("*.json"))
            after_file = [p for p in after_files if json.loads(p.read_text())["scope"] == "file"][0]
            after = json.loads(after_file.read_text())
            self.assertNotEqual(after["bindings"][0]["file_blob"], before_blob)
            self.assertEqual(after["bindings"][0]["commit"], run(["git", "rev-parse", "HEAD"], repo).stdout.strip())

    def test_retrieve_text_repairs_stale_top_match(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td))
            run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "app.py", "--repo", str(repo)], ROOT)
            (repo / "app.py").write_text("def add(a, b):\n    patched_value = a + b + 3\n    return patched_value\n", encoding="utf-8")
            proc = run([sys.executable, "-m", "tmf.cli", "retrieve", "add", "--repo", str(repo)], ROOT)
            data = json.loads(proc.stdout)
            self.assertTrue(data["claims"])
            self.assertTrue(data["claims"][0]["fresh"])
            self.assertTrue(data["claims"][0]["fresh"])

    def test_summary_does_not_store_source_lines(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td))
            run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "app.py", "--repo", str(repo)], ROOT)
            claim_files = sorted((repo / ".tmf" / "claims").glob("*.json"))
            claim_file = [p for p in claim_files if json.loads(p.read_text())["scope"] == "file"][0]
            summary = json.loads(claim_file.read_text())["body"]["summary"]
            self.assertNotIn("def add", summary)
            self.assertNotIn("return a + b", summary)


if __name__ == "__main__":
    unittest.main()
