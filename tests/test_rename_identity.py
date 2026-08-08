from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.ids import stable_call_edge_claim_id, stable_contract_claim_id, stable_function_claim_id
from tmf.store import Store
from tmf.warm import warm_repo


def init_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    import subprocess
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "tmf@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "tmf"], cwd=repo, check=True)
    for path, content in files.items():
        full = repo / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", *files.keys()], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return repo


class RenameIdentityTests(unittest.TestCase):
    def test_pure_rename_migrates_contract_and_edge_fresh(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "a.py": "from b import helper\n\ndef main():\n    x = helper()\n    return x\n",
                "b.py": "def helper():\n    y = 1\n    if y:\n        return y\n    return 0\n",
            })
            warm_repo(repo)
            old_contract = stable_contract_claim_id("b.py", "helper")
            old_helper = stable_function_claim_id("b.py", "helper")
            main = stable_function_claim_id("a.py", "main")
            self.assertIsNotNone(Store(repo).get_claim(old_contract))
            (repo / "c.py").write_text((repo / "b.py").read_text(encoding="utf-8"), encoding="utf-8")
            (repo / "b.py").unlink()
            result = warm_repo(repo)
            self.assertGreater(result["renamed_claims"], 0)
            store = Store(repo)
            new_contract = stable_contract_claim_id("c.py", "helper")
            new_helper = stable_function_claim_id("c.py", "helper")
            self.assertIsNone(store.get_claim(old_contract))
            migrated = store.get_claim(new_contract)
            self.assertIsNotNone(migrated)
            self.assertTrue(check_freshness(GitRepo(repo), migrated).fresh)
            edge = store.get_claim(stable_call_edge_claim_id(main, new_helper))
            self.assertIsNotNone(edge)
            assert edge is not None
            self.assertTrue(check_freshness(GitRepo(repo), edge).fresh)
            self.assertIsNone(store.get_claim(stable_call_edge_claim_id(main, old_helper)))
            self.assertEqual(edge.body["callee_id"], new_helper)
            self.assertEqual(edge.body["callee_path"], "c.py")
            self.assertTrue(any(b.path == "c.py" for b in edge.bindings))
            self.assertFalse(any(b.path == "b.py" for b in edge.bindings))

    def test_rename_plus_edit_does_not_migrate(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"b.py": "def helper():\n    y = 1\n    if y:\n        return y\n    return 0\n"})
            warm_repo(repo)
            old_contract = stable_contract_claim_id("b.py", "helper")
            (repo / "c.py").write_text("def helper():\n    y = 2\n    if y:\n        return y\n    return 0\n", encoding="utf-8")
            (repo / "b.py").unlink()
            result = warm_repo(repo)
            self.assertEqual(result["renamed_claims"], 0)
            self.assertIsNone(Store(repo).get_claim(old_contract))
            self.assertIsNotNone(Store(repo).get_claim(stable_contract_claim_id("c.py", "helper")))

    def test_ambiguous_same_blob_new_paths_do_not_migrate(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"b.py": "def helper():\n    y = 1\n    if y:\n        return y\n    return 0\n"})
            warm_repo(repo)
            old_contract = stable_contract_claim_id("b.py", "helper")
            text = (repo / "b.py").read_text(encoding="utf-8")
            (repo / "c.py").write_text(text, encoding="utf-8")
            (repo / "d.py").write_text(text, encoding="utf-8")
            (repo / "b.py").unlink()
            result = warm_repo(repo)
            self.assertEqual(result["renamed_claims"], 0)
            self.assertIsNone(Store(repo).get_claim(old_contract))


if __name__ == "__main__":
    unittest.main()
