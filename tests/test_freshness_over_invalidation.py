from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tmf import extract as extract_mod
from tmf.extract import extract_functions, fn_hash_for_span
from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.ids import stable_call_edge_claim_id, stable_file_claim_id, stable_function_claim_id
from tmf.retrieve import retrieve_path
from tmf.store import Store


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


class FreshnessOverInvalidationTests(unittest.TestCase):
    def test_class_first_method_stays_fresh_when_class_member_inserted_above(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(
                Path(td),
                {"m.py": "class C:\n    def target(self):\n        return 1\n"},
            )
            retrieve_path(repo, "m.py")
            claim = Store(repo).get_claim(stable_function_claim_id("m.py", "C.target"))
            self.assertIsNotNone(claim)
            (repo / "m.py").write_text(
                "class C:\n    inserted = 1\n\n    def target(self):\n        return 1\n",
                encoding="utf-8",
            )
            freshness = check_freshness(GitRepo(repo), claim)
            self.assertTrue(freshness.fresh, freshness.stale_bindings)

    def test_nested_first_inner_function_stays_fresh_when_statement_inserted_above(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(
                Path(td),
                {"m.py": "def outer():\n    def inner():\n        return 1\n    return inner()\n"},
            )
            retrieve_path(repo, "m.py")
            claim = Store(repo).get_claim(stable_function_claim_id("m.py", "outer.inner"))
            self.assertIsNotNone(claim)
            (repo / "m.py").write_text(
                "def outer():\n    marker = 1\n\n    def inner():\n        return 1\n    return inner()\n",
                encoding="utf-8",
            )
            freshness = check_freshness(GitRepo(repo), claim)
            self.assertTrue(freshness.fresh, freshness.stale_bindings)

    def test_module_first_function_hash_is_unaffected_by_preceding_comment(self):
        before = "def target():\n    return 1\n"
        after = "# module comment\n\ndef target():\n    return 1\n"
        before_node = {node.qualname: node for node in extract_functions("m.py", before)}["target"]
        after_node = {node.qualname: node for node in extract_functions("m.py", after)}["target"]
        self.assertEqual(before_node.fn_hash, after_node.fn_hash)


    def test_extract_functions_reuses_single_file_token_stream_for_many_spans(self):
        source = "".join(f"def f{i}():\n    return {i}\n\n" for i in range(12))
        extract_mod._token_items_for_source.cache_clear()
        before = extract_mod._token_items_for_source.cache_info()
        nodes = extract_functions("m.py", source)
        after = extract_mod._token_items_for_source.cache_info()
        self.assertEqual(len(nodes), 12)
        self.assertEqual(after.misses - before.misses, 1)
        self.assertGreaterEqual(after.hits - before.hits, 11)

    def test_method_body_change_stales_method(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"m.py": "class C:\n    def target(self):\n        return 1\n"})
            retrieve_path(repo, "m.py")
            claim = Store(repo).get_claim(stable_function_claim_id("m.py", "C.target"))
            self.assertIsNotNone(claim)
            (repo / "m.py").write_text("class C:\n    def target(self):\n        return 2\n", encoding="utf-8")
            freshness = check_freshness(GitRepo(repo), claim)
            self.assertFalse(freshness.fresh)

    def test_method_internal_block_structure_change_stales_method(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"m.py": "class C:\n    def target(self):\n        return 1\n"})
            retrieve_path(repo, "m.py")
            claim = Store(repo).get_claim(stable_function_claim_id("m.py", "C.target"))
            self.assertIsNotNone(claim)
            (repo / "m.py").write_text(
                "class C:\n    def target(self):\n        if True:\n            return 1\n",
                encoding="utf-8",
            )
            freshness = check_freshness(GitRepo(repo), claim)
            self.assertFalse(freshness.fresh)

    def test_boundary_indent_normalization_preserves_structure_distinction(self):
        one_line = "def f():\n    return 1\n"
        block = "def f():\n    if True:\n        return 1\n"
        self.assertNotEqual(
            fn_hash_for_span(one_line, 1, 2),
            fn_hash_for_span(block, 1, 3),
        )

    def test_same_file_changed_function_stales_only_that_function_not_sibling(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"m.py": "def f1():\n    return 1\n\ndef f2():\n    return 2\n"})
            retrieve_path(repo, "m.py")
            store = Store(repo)
            f1 = store.get_claim(stable_function_claim_id("m.py", "f1"))
            f2 = store.get_claim(stable_function_claim_id("m.py", "f2"))
            self.assertIsNotNone(f1)
            self.assertIsNotNone(f2)
            (repo / "m.py").write_text("def f1():\n    return 10\n\ndef f2():\n    return 2\n", encoding="utf-8")
            git_repo = GitRepo(repo)
            self.assertFalse(check_freshness(git_repo, f1).fresh)
            self.assertTrue(check_freshness(git_repo, f2).fresh, check_freshness(git_repo, f2).stale_bindings)

    def test_comment_only_and_indent_width_changes_keep_function_fresh(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"m.py": "def f():\n    if True:\n        return 1\n"})
            retrieve_path(repo, "m.py")
            claim = Store(repo).get_claim(stable_function_claim_id("m.py", "f"))
            self.assertIsNotNone(claim)
            (repo / "m.py").write_text("# comment only\ndef f():\n  if True:\n    return 1\n", encoding="utf-8")
            freshness = check_freshness(GitRepo(repo), claim)
            self.assertTrue(freshness.fresh, freshness.stale_bindings)

    def test_changed_function_body_stales_function(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"m.py": "def f():\n    return 1\n"})
            retrieve_path(repo, "m.py")
            claim = Store(repo).get_claim(stable_function_claim_id("m.py", "f"))
            self.assertIsNotNone(claim)
            (repo / "m.py").write_text("def f():\n    return 2\n", encoding="utf-8")
            freshness = check_freshness(GitRepo(repo), claim)
            self.assertFalse(freshness.fresh)
            self.assertTrue(any("fn_hash mismatch" in item for item in freshness.stale_bindings), freshness.stale_bindings)

    def test_file_claim_still_stales_on_any_file_blob_change(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"m.py": "def f():\n    return 1\n"})
            retrieve_path(repo, "m.py")
            claim = Store(repo).get_claim(stable_file_claim_id("m.py"))
            self.assertIsNotNone(claim)
            (repo / "m.py").write_text("# changed\ndef f():\n    return 1\n", encoding="utf-8")
            freshness = check_freshness(GitRepo(repo), claim)
            self.assertFalse(freshness.fresh)
            self.assertTrue(any("blob mismatch" in item for item in freshness.stale_bindings), freshness.stale_bindings)

    def test_cross_file_edge_stales_only_when_endpoint_hash_changes_not_unrelated_function(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "a.py": "from b import helper\n\ndef main():\n    return helper()\n",
                "b.py": "def helper():\n    return 1\n\ndef spare():\n    return 2\n",
            })
            retrieve_path(repo, "a.py")
            edge = next(claim for claim in Store(repo).iter_claims() if claim.body.get("edge_kind") == "calls")
            (repo / "b.py").write_text("def helper():\n    return 1\n\ndef spare():\n    return 20\n", encoding="utf-8")
            self.assertTrue(check_freshness(GitRepo(repo), edge).fresh, check_freshness(GitRepo(repo), edge).stale_bindings)
            (repo / "b.py").write_text("def helper():\n    return 10\n\ndef spare():\n    return 20\n", encoding="utf-8")
            freshness = check_freshness(GitRepo(repo), edge)
            self.assertFalse(freshness.fresh)
            self.assertTrue(all(item.startswith("b.py:helper") for item in freshness.stale_bindings), freshness.stale_bindings)


if __name__ == "__main__":
    unittest.main()
