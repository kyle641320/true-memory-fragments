from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.ids import stable_function_claim_id
from tmf.retrieve import refresh_path, reverse_callers
from tmf.schema import Claim
from tmf.store import Store

ROOT = Path(__file__).resolve().parents[1]


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def init_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
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


class CrossFileEdgesTests(unittest.TestCase):
    def _derive_repo(self, repo: Path) -> tuple[GitRepo, Store]:
        refresh_path(repo, "a.py")
        return GitRepo(repo), Store(repo)

    def _edge_claims(self, repo: Path) -> list[Claim]:
        return [json.loads(p.read_text()) for p in (repo / ".tmf" / "claims").glob("*.json") if p.stem.startswith("claim_edge_")]

    def _edge_claim(self, repo: Path) -> Claim:
        store = Store(repo)
        edge_ids = [p.stem for p in (repo / ".tmf" / "claims").glob("claim_edge_*.json")]
        self.assertEqual(len(edge_ids), 1)
        claim = store.get_claim(edge_ids[0])
        self.assertIsNotNone(claim)
        return claim

    def test_from_import_direct_top_level_creates_multibinding_edge_claim(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "a.py": "from b import helper\n\ndef main():\n    return helper()\n",
                "b.py": "def helper():\n    return 1\n",
            })
            data = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "a.py", "--refresh", "--repo", str(repo)], ROOT).stdout)
            main = [c for c in data["claims"] if c.get("qualname") == "main"][0]
            self.assertEqual(main["callees"][0]["target_qualname"], "helper")
            self.assertEqual(main["callees"][0]["resolution"], "from_import_direct_top_level")
            edge_claims = self._edge_claims(repo)
            self.assertEqual(len(edge_claims), 1)
            self.assertEqual(len(edge_claims[0]["bindings"]), 2)
            self.assertEqual({b["path"] for b in edge_claims[0]["bindings"]}, {"a.py", "b.py"})

    def test_import_module_alias_attr_creates_multibinding_edge_claim(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "a.py": "import b as bee\n\ndef main():\n    return bee.helper()\n",
                "b.py": "def helper():\n    return 1\n",
            })
            data = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "a.py", "--refresh", "--repo", str(repo)], ROOT).stdout)
            main = [c for c in data["claims"] if c.get("qualname") == "main"][0]
            self.assertEqual(main["callees"][0]["resolution"], "import_module_direct_top_level")

    def test_star_import_and_reexport_are_unresolved(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "a.py": "from b import *\n\ndef main():\n    return helper()\n",
                "b.py": "from c import helper\n",
                "c.py": "def helper():\n    return 1\n",
            })
            data = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "a.py", "--refresh", "--repo", str(repo)], ROOT).stdout)
            main = [c for c in data["claims"] if c.get("qualname") == "main"][0]
            self.assertFalse(main["callees"])
            self.assertTrue(main["unresolved_calls"])

    def test_edge_reconcile_for_caller_path_removes_stale_cross_file_edge(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "a.py": "from b import helper\n\ndef main():\n    return helper()\n",
                "b.py": "def helper():\n    return 1\n",
            })
            run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "a.py", "--refresh", "--repo", str(repo)], ROOT)
            self.assertEqual(len(list((repo / ".tmf" / "claims").glob("claim_edge_*.json"))), 1)
            (repo / "a.py").write_text("def main():\n    return 0\n", encoding="utf-8")
            data = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "a.py", "--refresh", "--repo", str(repo)], ROOT).stdout)
            main = [c for c in data["claims"] if c.get("qualname") == "main"][0]
            self.assertFalse(main["callees"])
            self.assertEqual(len(list((repo / ".tmf" / "claims").glob("claim_edge_*.json"))), 0)

    def test_cross_file_edge_freshness_uses_per_binding_qualname(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "a.py": "from b import helper\n\ndef main():\n    return helper()\n",
                "b.py": "def helper():\n    return 1\n",
            })
            git_repo, _store = self._derive_repo(repo)
            edge = self._edge_claim(repo)
            freshness = check_freshness(git_repo, edge)
            self.assertTrue(freshness.fresh, freshness.stale_bindings)
            self.assertTrue(all("function missing" not in item for item in freshness.stale_bindings))

            (repo / "b.py").write_text("def helper():\n    x = 1\n    return x\n", encoding="utf-8")
            freshness = check_freshness(git_repo, edge)
            self.assertFalse(freshness.fresh)
            self.assertTrue(all(item.startswith("b.py:") for item in freshness.stale_bindings), freshness.stale_bindings)

            (repo / "b.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
            (repo / "a.py").write_text("from b import helper\n\ndef main():\n    x = 1\n    return helper() + x\n", encoding="utf-8")
            freshness = check_freshness(git_repo, edge)
            self.assertFalse(freshness.fresh)
            self.assertTrue(all(item.startswith("a.py:") for item in freshness.stale_bindings), freshness.stale_bindings)

    def test_fresh_cross_file_edge_does_not_force_permanent_rederive(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "a.py": "from b import helper\n\ndef main():\n    return helper()\n",
                "b.py": "def helper():\n    return 1\n",
            })
            refresh_path(repo, "a.py")
            edge_path = next((repo / ".tmf" / "claims").glob("claim_edge_*.json"))
            before = edge_path.read_text(encoding="utf-8")
            refresh_path(repo, "a.py")
            after = edge_path.read_text(encoding="utf-8")
            self.assertEqual(before, after)

    def test_legacy_binding_without_qualname_falls_back_to_body_qualname(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"a.py": "def main():\n    return 1\n"})
            refresh_path(repo, "a.py")
            claim_id = stable_function_claim_id("a.py", "main")
            claim_path = repo / ".tmf" / "claims" / f"{claim_id}.json"
            raw = json.loads(claim_path.read_text(encoding="utf-8"))
            raw["bindings"][0].pop("qualname", None)
            claim_path.write_text(json.dumps(raw), encoding="utf-8")
            claim = Store(repo).get_claim(claim_id)
            self.assertIsNotNone(claim)
            freshness = check_freshness(GitRepo(repo), claim)
            self.assertTrue(freshness.fresh, freshness.stale_bindings)

    def test_reverse_callers_is_lazy_fresh_and_partial(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "a.py": "from b import helper\n\ndef main():\n    return helper()\n",
                "b.py": "def helper():\n    return 1\n",
            })
            refresh_path(repo, "a.py")
            helper_id = stable_function_claim_id("b.py", "helper")
            result = reverse_callers(repo, helper_id)
            self.assertEqual(result["coverage"], "partial")
            self.assertEqual(result["note"], "Known callers from already-derived files only; not a complete blast radius.")
            self.assertEqual([c["caller_id"] for c in result["callers"]], [stable_function_claim_id("a.py", "main")])

            (repo / "a.py").write_text("def main():\n    return 0\n", encoding="utf-8")
            refresh_path(repo, "a.py")
            result = reverse_callers(repo, helper_id)
            self.assertEqual(result["callers"], [])
            self.assertEqual(result["coverage"], "partial")

    def test_reverse_callers_skips_stale_until_explicit_refresh(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "a.py": "from b import helper\n\ndef main():\n    return helper()\n",
                "b.py": "def helper():\n    return 1\n",
            })
            refresh_path(repo, "a.py")
            helper_id = stable_function_claim_id("b.py", "helper")
            (repo / "a.py").write_text("from b import helper\n\ndef main():\n    x = 1\n    return helper() + x\n", encoding="utf-8")
            result = reverse_callers(repo, helper_id)
            self.assertEqual(result["callers"], [])
            self.assertEqual(result["stale_skipped"], 1)

            refresh_path(repo, "a.py")
            result = reverse_callers(repo, helper_id)
            self.assertEqual(len(result["callers"]), 1)
            self.assertEqual(result["stale_skipped"], 0)


if __name__ == "__main__":
    unittest.main()
