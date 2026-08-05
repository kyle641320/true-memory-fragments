from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.ids import stable_declaration_claim_id, stable_function_claim_id, stable_read_edge_claim_id, stable_write_edge_claim_id
from tmf.retrieve import retrieve_path, reverse_callers, reverse_readers, reverse_writers
from tmf.store import Store
from tmf.warm import warm_repo


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def init_repo(root: Path, files: dict[str, str]) -> Path:
    repo = root / "repo"
    repo.mkdir(parents=True)
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


class WriteEdgeTests(unittest.TestCase):
    def test_global_assignment_creates_write_edge_with_anchors_and_reverse_partial(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"settings.py": "COUNT = 0\nOTHER = 1\n\ndef bump():\n    global COUNT\n    COUNT = COUNT + 1\n"})
            warm_repo(repo)
            store = Store(repo)
            writer_id = stable_function_claim_id("settings.py", "bump")
            decl_id = stable_declaration_claim_id("settings.py", "COUNT")
            write_id = stable_write_edge_claim_id(writer_id, decl_id)
            edge = store.get_claim(write_id)
            self.assertIsNotNone(edge)
            self.assertEqual(edge.body.get("edge_kind"), "writes")
            fn = store.get_claim(writer_id)
            decl = store.get_claim(decl_id)
            self.assertEqual(fn.body["graph"]["writes"][0]["target_id"], decl_id)
            self.assertIn("anchor", fn.body["graph"]["writes"][0])
            self.assertEqual(fn.body["graph"]["writes"][0]["anchor"]["qualname"], "COUNT")
            self.assertEqual(decl.body["graph"]["written_by"][0]["source_id"], writer_id)
            self.assertEqual(decl.body["graph"]["written_by_coverage"], "partial")
            rev = reverse_writers(repo, decl_id)
            self.assertEqual(rev["coverage"], "partial")
            self.assertEqual(rev["writers"][0]["writer_id"], writer_id)
            self.assertIn("anchor", rev["writers"][0])
            self.assertEqual(reverse_callers(repo, decl_id)["callers"], [])
            # COUNT = COUNT + 1 with global is also a read.
            self.assertIsNotNone(store.get_claim(stable_read_edge_claim_id(writer_id, decl_id)))
            self.assertTrue(reverse_readers(repo, decl_id)["readers"])

    def test_assignment_without_global_is_local_not_write_edge(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"settings.py": "COUNT = 0\n\ndef local_set():\n    COUNT = 1\n    return COUNT\n"})
            warm_repo(repo)
            store = Store(repo)
            writer_id = stable_function_claim_id("settings.py", "local_set")
            decl_id = stable_declaration_claim_id("settings.py", "COUNT")
            self.assertIsNone(store.get_claim(stable_write_edge_claim_id(writer_id, decl_id)))
            claim = store.get_claim(writer_id)
            unresolved = claim.body["graph"].get("writes_unresolved", [])
            self.assertTrue(any(item["expr"] == "COUNT" and item["reason"] == "assignment_without_global_is_local" for item in unresolved))

    def test_write_edge_freshness_both_ends_and_unrelated_fresh(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"settings.py": "COUNT = 0\nOTHER = 1\n\ndef set_count():\n    global COUNT\n    COUNT = 2\n"})
            warm_repo(repo)
            store = Store(repo)
            writer_id = stable_function_claim_id("settings.py", "set_count")
            decl_id = stable_declaration_claim_id("settings.py", "COUNT")
            edge = store.get_claim(stable_write_edge_claim_id(writer_id, decl_id))
            self.assertTrue(check_freshness(GitRepo(repo), edge).fresh)
            (repo / "settings.py").write_text("COUNT = 0\nOTHER = 2\n\ndef set_count():\n    global COUNT\n    COUNT = 2\n", encoding="utf-8")
            self.assertTrue(check_freshness(GitRepo(repo), edge).fresh)
            (repo / "settings.py").write_text("COUNT = 0\nOTHER = 2\n\ndef set_count():\n    global COUNT\n    COUNT = 3\n", encoding="utf-8")
            self.assertFalse(check_freshness(GitRepo(repo), edge).fresh)
            (repo / "settings.py").write_text("COUNT = 9\nOTHER = 2\n\ndef set_count():\n    global COUNT\n    COUNT = 2\n", encoding="utf-8")
            self.assertFalse(check_freshness(GitRepo(repo), edge).fresh)

    def test_delete_with_global_writes_and_reconcile_removes_edge(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"settings.py": "COUNT = 0\n\ndef clear():\n    global COUNT\n    del COUNT\n"})
            warm_repo(repo)
            writer_id = stable_function_claim_id("settings.py", "clear")
            decl_id = stable_declaration_claim_id("settings.py", "COUNT")
            edge_id = stable_write_edge_claim_id(writer_id, decl_id)
            self.assertIsNotNone(Store(repo).get_claim(edge_id))
            (repo / "settings.py").write_text("COUNT = 0\n\ndef renamed():\n    global COUNT\n    del COUNT\n", encoding="utf-8")
            retrieve_path(repo, "settings.py")
            self.assertIsNone(Store(repo).get_claim(edge_id))
            warm_repo(repo)
            new_writer = stable_function_claim_id("settings.py", "renamed")
            new_edge = stable_write_edge_claim_id(new_writer, decl_id)
            self.assertIsNotNone(Store(repo).get_claim(new_edge))
            (repo / "settings.py").write_text("OTHER = 0\n\ndef renamed():\n    global OTHER\n    del OTHER\n", encoding="utf-8")
            retrieve_path(repo, "settings.py")
            self.assertIsNone(Store(repo).get_claim(new_edge))


if __name__ == "__main__":
    unittest.main()
