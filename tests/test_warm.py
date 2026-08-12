from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tmf.ids import stable_function_claim_id
from tmf.retrieve import reverse_callers
from tmf.store import Store
from tmf.warm import warm_is_complete, warm_repo

ROOT = Path(__file__).resolve().parents[1]


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def init_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init"], repo)
    run(["git", "config", "user.email", "tmf@example.com"], repo)
    run(["git", "config", "user.name", "tmf"], repo)
    for path, content in files.items():
        full = repo / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
    run(["git", "add", *files.keys()], repo)
    run(["git", "commit", "-m", "init"], repo)
    return repo


class WarmReverseIndexTests(unittest.TestCase):
    def test_warm_and_complete_check_share_git_and_tmf_ignore_scope(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = init_repo(root, {
                "src/keep.py": "x = 1\n",
                "outputs/tracked.py": "x = 2\n",
                "reports/tracked.json": "{}\n",
                "ignored.toml": "x = 3\n",
            })
            (repo / ".tmfignore").write_text("outputs/\nreports/\n", encoding="utf-8")
            (repo / ".gitignore").write_text("ignored.toml\n", encoding="utf-8")
            subprocess.run(["git", "add", ".tmfignore", ".gitignore"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "ignores"], cwd=repo, check=True, stdout=subprocess.PIPE)

            result = warm_repo(repo)
            self.assertEqual(result["files"], 1)
            self.assertTrue(warm_is_complete(repo))

            for rel in ("outputs/new.py", "reports/new.json", "ignored.toml"):
                path = repo / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("changed\n", encoding="utf-8")
            self.assertTrue(warm_is_complete(repo))

            (repo / "src/keep.py").write_text("x = 4\n", encoding="utf-8")
            self.assertFalse(warm_is_complete(repo))

    def test_warm_makes_reverse_callers_complete_and_matches_lazy(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "a.py": "from b import helper\n\ndef main():\n    return helper()\n",
                "b.py": "def helper():\n    return 1\n",
            })
            helper_id = stable_function_claim_id("b.py", "helper")
            before = reverse_callers(repo, helper_id)
            self.assertEqual(before["coverage"], "partial")
            self.assertEqual(before["callers"], [])

            result = warm_repo(repo)
            self.assertEqual(result["coverage"], "complete")
            indexed = reverse_callers(repo, helper_id)
            self.assertEqual(indexed["coverage"], "complete")
            self.assertEqual(indexed["callers"], [{
                "caller_id": stable_function_claim_id("a.py", "main"),
                "caller_path": "a.py",
                "callee_qualname": "helper",
                "resolution": "from_import_direct_top_level",
                "evidence": "observed",
                "anchor": {"path": "a.py", "line_start": 3, "line_end": 4, "qualname": "main"},
            }])

            # Deleting the index forces lazy scan, which must return the same fresh callers.
            (repo / ".tmf" / "reverse_callers.json").unlink()
            lazy = reverse_callers(repo, helper_id)
            self.assertEqual(lazy["coverage"], "partial")
            self.assertEqual(lazy["callers"], indexed["callers"])

    def test_warm_second_run_is_noop_and_file_change_is_incremental(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "a.py": "from b import helper\n\ndef main():\n    return helper()\n",
                "b.py": "def helper():\n    return 1\n",
                "c.py": "def spare():\n    return 3\n",
            })
            first = warm_repo(repo)
            self.assertEqual(first["derived"], 3)
            second = warm_repo(repo)
            self.assertEqual(second["derived"], 0)
            self.assertEqual(second["skipped"], 3)

            (repo / "a.py").write_text("from b import helper\n\ndef main():\n    x = 1\n    return helper() + x\n", encoding="utf-8")
            third = warm_repo(repo)
            self.assertEqual(third["derived"], 1)
            self.assertEqual(third["skipped"], 2)
            helper_id = stable_function_claim_id("b.py", "helper")
            self.assertEqual(reverse_callers(repo, helper_id)["coverage"], "complete")

    def test_reverse_callers_falls_back_to_partial_when_warm_index_is_stale(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "a.py": "from b import helper\n\ndef main():\n    return helper()\n",
                "b.py": "def helper():\n    return 1\n",
            })
            warm_repo(repo)
            helper_id = stable_function_claim_id("b.py", "helper")
            self.assertEqual(reverse_callers(repo, helper_id)["coverage"], "complete")

            (repo / "a.py").write_text("def main():\n    return 0\n", encoding="utf-8")
            result = reverse_callers(repo, helper_id)
            self.assertEqual(result["coverage"], "partial")
            self.assertEqual(result["callers"], [])

    def test_warm_cli_outputs_json(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"a.py": "def main():\n    return 1\n"})
            payload = json.loads(run([sys.executable, "-m", "tmf.cli", "warm", "--repo", str(repo)], ROOT).stdout)
            self.assertEqual(payload["coverage"], "complete")
            self.assertEqual(payload["derived"], 1)
            self.assertTrue((repo / ".tmf" / "warm_manifest.json").exists())
            self.assertTrue((repo / ".tmf" / "reverse_callers.json").exists())


if __name__ == "__main__":
    unittest.main()
