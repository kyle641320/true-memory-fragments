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
    (repo / "app.py").write_text(
        "def add(a, b):\n"
        "    label = 'a b'\n"
        "    return a + b\n\n"
        "def untouched(x):\n"
        "    return x\n",
        encoding="utf-8",
    )
    run(["git", "add", "app.py"], repo)
    run(["git", "commit", "-m", "init"], repo)
    return repo


class TmfV1Tests(unittest.TestCase):
    def test_path_retrieve_derives_file_and_function_claims(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td))
            proc = run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "app.py", "--repo", str(repo)], ROOT)
            data = json.loads(proc.stdout)
            scopes = {c.get("qualname") or c["scope"] for c in data["claims"]}
            self.assertIn("file", scopes)
            self.assertIn("add", scopes)
            self.assertIn("untouched", scopes)
            function_claims = [c for c in data["claims"] if c["scope"] == "function" and c["freshness_binding_refs"][0].get("fn_hash_prefix")]
            self.assertEqual(len(function_claims), 2)

    def test_fn_hash_uses_worktree_and_token_stream_not_regex_whitespace(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td))
            run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "app.py", "--repo", str(repo)], ROOT)
            claim_files = sorted((repo / ".tmf" / "claims").glob("*.json"))
            before = {json.loads(p.read_text())["body"].get("qualname"): json.loads(p.read_text()) for p in claim_files}
            before_add_hash = before["add"]["bindings"][0]["fn_hash"][:12]
            before_untouched_hash = before["untouched"]["bindings"][0]["fn_hash"][:12]

            # Uncommitted edit changes a string literal from 'a b' to 'ab'. A
            # regex whitespace stripper would miss this; token stream must not.
            (repo / "app.py").write_text(
                "def add(a, b):\n"
                "    label = 'ab'\n"
                "    return a + b\n\n"
                "def untouched(x):\n"
                "    return x\n",
                encoding="utf-8",
            )
            proc = run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "app.py", "--repo", str(repo)], ROOT)
            data = json.loads(proc.stdout)
            after = {c.get("qualname"): c for c in data["claims"] if c.get("qualname")}
            self.assertNotEqual(after["add"]["freshness_binding_refs"][0]["fn_hash_prefix"], before_add_hash)
            self.assertEqual(after["untouched"]["freshness_binding_refs"][0]["fn_hash_prefix"], before_untouched_hash)
            self.assertTrue(after["add"]["fresh"])

    def test_feedback_usage_does_not_raise_confidence(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td))
            proc = run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "app.py", "--repo", str(repo)], ROOT)
            claim = json.loads(proc.stdout)["claims"][0]
            before = claim["confidence"]
            proc = run([sys.executable, "-m", "tmf.cli", "feedback", claim["id"], "usage", "--repo", str(repo), "--note", "read during coding"], ROOT)
            data = json.loads(proc.stdout)
            self.assertEqual(data["confidence"], before)
            self.assertFalse(data["changed"])

    def test_feedback_hunch_does_not_overwrite_fact(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td))
            proc = run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "app.py", "--repo", str(repo)], ROOT)
            claim = json.loads(proc.stdout)["claims"][0]
            old_text = claim["claim"]
            proc = run([sys.executable, "-m", "tmf.cli", "feedback", claim["id"], "hunch", "--repo", str(repo), "--note", "maybe related to billing"], ROOT)
            data = json.loads(proc.stdout)
            self.assertEqual(data["claim"], old_text)
            self.assertLessEqual(data["confidence"], 0.3)
            explained = json.loads(run([sys.executable, "-m", "tmf.cli", "explain", claim["id"], "--repo", str(repo), "--json"], ROOT).stdout)
            self.assertIn("maybe related to billing", str(explained.get("hunches")))

    def test_feedback_verified_can_raise_confidence(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td))
            proc = run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "app.py", "--repo", str(repo)], ROOT)
            claim = json.loads(proc.stdout)["claims"][0]
            proc = run([sys.executable, "-m", "tmf.cli", "feedback", claim["id"], "verified", "--repo", str(repo), "--note", "unit test observed"], ROOT)
            data = json.loads(proc.stdout)
            self.assertGreaterEqual(data["confidence"], 0.75)
            self.assertEqual(data["evidence"], "verified")


if __name__ == "__main__":
    unittest.main()

class TmfV1PrecisionTests(unittest.TestCase):
    def test_indent_width_change_does_not_change_fn_hash(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            run(["git", "init"], repo)
            run(["git", "config", "user.email", "tmf@example.com"], repo)
            run(["git", "config", "user.name", "tmf"], repo)
            (repo / "m.py").write_text(
                "def foo(x):\n"
                "    if x:\n"
                "        return 'yes'\n"
                "    return 'no'\n",
                encoding="utf-8",
            )
            run(["git", "add", "m.py"], repo)
            run(["git", "commit", "-m", "init"], repo)
            proc = run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "m.py", "--repo", str(repo)], ROOT)
            before = {c.get("qualname"): c for c in json.loads(proc.stdout)["claims"] if c["scope"] == "function"}
            before_hash = before["foo"]["freshness_binding_refs"][0]["fn_hash_prefix"]

            # Reformat only: 4-space indents become 2-space indents. Block
            # events remain, width trivia must not change fn_hash.
            (repo / "m.py").write_text(
                "def foo(x):\n"
                "  if x:\n"
                "    return 'yes'\n"
                "  return 'no'\n",
                encoding="utf-8",
            )
            proc = run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "m.py", "--repo", str(repo)], ROOT)
            after = {c.get("qualname"): c for c in json.loads(proc.stdout)["claims"] if c["scope"] == "function"}
            self.assertEqual(after["foo"]["freshness_binding_refs"][0]["fn_hash_prefix"], before_hash)

    def test_function_rename_reconciles_tombstone_claim(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            run(["git", "init"], repo)
            run(["git", "config", "user.email", "tmf@example.com"], repo)
            run(["git", "config", "user.name", "tmf"], repo)
            (repo / "m.py").write_text("def foo():\n    return 1\n\ndef keep():\n    return 2\n", encoding="utf-8")
            run(["git", "add", "m.py"], repo)
            run(["git", "commit", "-m", "init"], repo)
            run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "m.py", "--repo", str(repo)], ROOT)

            (repo / "m.py").write_text("def bar():\n    return 1\n\ndef keep():\n    return 2\n", encoding="utf-8")
            proc = run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "m.py", "--repo", str(repo)], ROOT)
            data = json.loads(proc.stdout)
            names = {c.get("qualname") for c in data["claims"] if c["scope"] == "function"}
            self.assertEqual(names, {"bar", "keep"})

            disk_claims = [json.loads(p.read_text()) for p in sorted((repo / ".tmf" / "claims").glob("*.json"))]
            disk_names = {c["body"].get("qualname") for c in disk_claims if c["scope"] == "function"}
            self.assertEqual(disk_names, {"bar", "keep"})
            self.assertFalse(any(c["body"].get("qualname") == "foo" for c in disk_claims))

            # A second read should not be forced stale by a dead foo claim.
            proc2 = run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "m.py", "--repo", str(repo)], ROOT)
            data2 = json.loads(proc2.stdout)
            self.assertTrue(all(c["fresh"] for c in data2["claims"]))

    def test_function_delete_reconciles_tombstone_claim(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            run(["git", "init"], repo)
            run(["git", "config", "user.email", "tmf@example.com"], repo)
            run(["git", "config", "user.name", "tmf"], repo)
            (repo / "m.py").write_text("def foo():\n    return 1\n\ndef keep():\n    return 2\n", encoding="utf-8")
            run(["git", "add", "m.py"], repo)
            run(["git", "commit", "-m", "init"], repo)
            run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "m.py", "--repo", str(repo)], ROOT)

            (repo / "m.py").write_text("def keep():\n    return 2\n", encoding="utf-8")
            proc = run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "m.py", "--repo", str(repo)], ROOT)
            data = json.loads(proc.stdout)
            names = {c.get("qualname") for c in data["claims"] if c["scope"] == "function"}
            self.assertEqual(names, {"keep"})

            disk_claims = [json.loads(p.read_text()) for p in sorted((repo / ".tmf" / "claims").glob("*.json"))]
            disk_names = {c["body"].get("qualname") for c in disk_claims if c["scope"] == "function"}
            self.assertEqual(disk_names, {"keep"})
