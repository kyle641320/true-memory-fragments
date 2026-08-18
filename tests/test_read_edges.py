from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tmf.derive import derive_claims_for_path
from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.ids import stable_declaration_claim_id, stable_function_claim_id, stable_read_edge_claim_id
from tmf.retrieve import refresh_path, reverse_readers, reverse_callers
from tmf.store import Store
from tmf.warm import warm_repo


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def init_repo(root: Path, files: dict[str, str]) -> Path:
    repo = root / "repo"
    repo.mkdir(parents=True)
    run(["git", "init", "-b", "master"], repo)
    run(["git", "config", "user.email", "tmf@example.com"], repo)
    run(["git", "config", "user.name", "tmf"], repo)
    for path, content in files.items():
        full = repo / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
    run(["git", "add", *files.keys()], repo)
    run(["git", "commit", "-m", "init"], repo)
    return repo


class ReadEdgeTests(unittest.TestCase):
    def test_function_reads_module_declaration_and_reverse_partial(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"settings.py": "TIMEOUT = 5\n\ndef load():\n    return TIMEOUT + 1\n"})
            warm_repo(repo)
            store = Store(repo)
            reader_id = stable_function_claim_id("settings.py", "load")
            decl_id = stable_declaration_claim_id("settings.py", "TIMEOUT")
            edge_id = stable_read_edge_claim_id(reader_id, decl_id)
            edge = store.get_claim(edge_id)
            self.assertIsNotNone(edge)
            self.assertEqual(edge.body.get("edge_kind"), "reads")
            self.assertEqual(edge.body.get("reader_id"), reader_id)
            self.assertEqual(edge.body.get("declaration_id"), decl_id)
            fn = store.get_claim(reader_id)
            decl = store.get_claim(decl_id)
            self.assertEqual(fn.body["graph"]["reads"][0]["target_id"], decl_id)
            self.assertEqual(decl.body["graph"]["read_by"][0]["source_id"], reader_id)
            self.assertEqual(decl.body["graph"]["read_by_coverage"], "partial")
            rev = reverse_readers(repo, decl_id)
            self.assertEqual(rev["coverage"], "partial")
            self.assertEqual(rev["readers"][0]["reader_id"], reader_id)
            self.assertEqual(reverse_callers(repo, decl_id)["callers"], [])

    def test_read_edge_freshness_reader_and_declaration_changes_only(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"settings.py": "TIMEOUT = 5\nOTHER = 9\n\ndef load():\n    return TIMEOUT + 1\n"})
            warm_repo(repo)
            store = Store(repo)
            reader_id = stable_function_claim_id("settings.py", "load")
            decl_id = stable_declaration_claim_id("settings.py", "TIMEOUT")
            edge_id = stable_read_edge_claim_id(reader_id, decl_id)
            edge = store.get_claim(edge_id)
            self.assertTrue(check_freshness(GitRepo(repo), edge).fresh)

            (repo / "settings.py").write_text("TIMEOUT = 5\nOTHER = 10\n\ndef load():\n    return TIMEOUT + 1\n", encoding="utf-8")
            self.assertTrue(check_freshness(GitRepo(repo), edge).fresh)

            (repo / "settings.py").write_text("TIMEOUT = 5\nOTHER = 10\n\ndef load():\n    return TIMEOUT + 2\n", encoding="utf-8")
            self.assertFalse(check_freshness(GitRepo(repo), edge).fresh)

            (repo / "settings.py").write_text("TIMEOUT = 7\nOTHER = 10\n\ndef load():\n    return TIMEOUT + 1\n", encoding="utf-8")
            self.assertFalse(check_freshness(GitRepo(repo), edge).fresh)

    def test_local_shadowing_does_not_create_read_edge(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"settings.py": "TIMEOUT = 5\n\ndef load(TIMEOUT):\n    local = TIMEOUT\n    return local\n\ndef other():\n    TIMEOUT = 3\n    return TIMEOUT\n"})
            warm_repo(repo)
            store = Store(repo)
            decl_id = stable_declaration_claim_id("settings.py", "TIMEOUT")
            for fn in ["load", "other"]:
                edge_id = stable_read_edge_claim_id(stable_function_claim_id("settings.py", fn), decl_id)
                self.assertIsNone(store.get_claim(edge_id))
                claim = store.get_claim(stable_function_claim_id("settings.py", fn))
                self.assertGreaterEqual(len(claim.body["graph"].get("reads_unresolved", [])), 1)

    def test_imported_declaration_read_and_unresolved_ambiguity(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "config.py": "TIMEOUT = 5\n",
                "app.py": "from config import TIMEOUT\n\ndef load():\n    return TIMEOUT\n\ndef missing():\n    return UNKNOWN\n",
            })
            warm_repo(repo)
            store = Store(repo)
            reader_id = stable_function_claim_id("app.py", "load")
            decl_id = stable_declaration_claim_id("config.py", "TIMEOUT")
            self.assertIsNotNone(store.get_claim(stable_read_edge_claim_id(reader_id, decl_id)))
            missing = store.get_claim(stable_function_claim_id("app.py", "missing"))
            unresolved = missing.body["graph"].get("reads_unresolved", [])
            self.assertTrue(any(item["expr"] == "UNKNOWN" and item["reason"] == "name_not_tracked_declaration" for item in unresolved))

    def test_reconcile_deletes_read_edge_when_reader_or_declaration_removed(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"settings.py": "TIMEOUT = 5\n\ndef load():\n    return TIMEOUT\n"})
            warm_repo(repo)
            reader_id = stable_function_claim_id("settings.py", "load")
            decl_id = stable_declaration_claim_id("settings.py", "TIMEOUT")
            edge_id = stable_read_edge_claim_id(reader_id, decl_id)
            self.assertIsNotNone(Store(repo).get_claim(edge_id))

            (repo / "settings.py").write_text("TIMEOUT = 5\n\ndef renamed():\n    return TIMEOUT\n", encoding="utf-8")
            refresh_path(repo, "settings.py")
            self.assertIsNone(Store(repo).get_claim(edge_id))

            warm_repo(repo)
            new_reader = stable_function_claim_id("settings.py", "renamed")
            new_edge = stable_read_edge_claim_id(new_reader, decl_id)
            self.assertIsNotNone(Store(repo).get_claim(new_edge))
            (repo / "settings.py").write_text("OTHER = 5\n\ndef renamed():\n    return OTHER\n", encoding="utf-8")
            refresh_path(repo, "settings.py")
            self.assertIsNone(Store(repo).get_claim(new_edge))


if __name__ == "__main__":
    unittest.main()
