from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.ids import stable_api_claim_id
from tmf.retrieve import refresh_path
from tmf.store import Store


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def init_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    repo = tmp_path / "repo"
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


class ApiNodeTests(unittest.TestCase):
    def test_flask_route_api_node_is_derived_and_fresh(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"api.py": "@app.route('/x', methods=['POST'])\ndef handler():\n    return 'ok'\n"})
            refresh_path(repo, "api.py")
            claim = Store(repo).get_claim(stable_api_claim_id("api.py", "POST", "/x", "handler"))
            self.assertIsNotNone(claim)
            self.assertEqual(claim.scope, "api")
            self.assertEqual(claim.body["method"], "POST")
            self.assertEqual(claim.body["route_path"], "/x")
            self.assertTrue(check_freshness(GitRepo(repo), claim).fresh)

    def test_fastapi_route_path_change_stales_api_node(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"api.py": "@router.get('/x')\ndef handler():\n    return 'ok'\n"})
            refresh_path(repo, "api.py")
            claim = Store(repo).get_claim(stable_api_claim_id("api.py", "GET", "/x", "handler"))
            self.assertIsNotNone(claim)
            (repo / "api.py").write_text("@router.get('/y')\ndef handler():\n    return 'ok'\n", encoding="utf-8")
            freshness = check_freshness(GitRepo(repo), claim)
            self.assertFalse(freshness.fresh)

    def test_handler_body_change_stales_api_node(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"api.py": "@router.post('/x')\ndef handler():\n    return 'ok'\n"})
            refresh_path(repo, "api.py")
            claim = Store(repo).get_claim(stable_api_claim_id("api.py", "POST", "/x", "handler"))
            self.assertIsNotNone(claim)
            (repo / "api.py").write_text("@router.post('/x')\ndef handler():\n    return 'changed'\n", encoding="utf-8")
            self.assertFalse(check_freshness(GitRepo(repo), claim).fresh)

    def test_api_node_ignores_comment_and_formatting_changes(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"api.py": "@router.put('/x')\ndef handler():\n    return 'ok'\n"})
            refresh_path(repo, "api.py")
            claim = Store(repo).get_claim(stable_api_claim_id("api.py", "PUT", "/x", "handler"))
            self.assertIsNotNone(claim)
            (repo / "api.py").write_text("# comment\n@router.put('/x')\ndef handler():\n  return 'ok'\n", encoding="utf-8")
            self.assertTrue(check_freshness(GitRepo(repo), claim).fresh, check_freshness(GitRepo(repo), claim).stale_bindings)

    def test_unrelated_function_change_does_not_stale_api_node(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"api.py": "@router.delete('/x')\ndef handler():\n    return 'ok'\n\ndef unrelated():\n    return 1\n"})
            refresh_path(repo, "api.py")
            claim = Store(repo).get_claim(stable_api_claim_id("api.py", "DELETE", "/x", "handler"))
            self.assertIsNotNone(claim)
            (repo / "api.py").write_text("@router.delete('/x')\ndef handler():\n    return 'ok'\n\ndef unrelated():\n    return 2\n", encoding="utf-8")
            self.assertTrue(check_freshness(GitRepo(repo), claim).fresh, check_freshness(GitRepo(repo), claim).stale_bindings)

    def test_dynamic_and_unknown_decorators_are_not_api_nodes(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"api.py": "PATH = '/x'\n@router.get(PATH)\ndef dyn():\n    return 'no'\n\n@bp.route('/known-looking')\ndef unknown():\n    return 'no'\n"})
            refresh_path(repo, "api.py")
            api_claims = [claim for claim in Store(repo).iter_claims() if claim.scope == "api"]
            self.assertEqual(api_claims, [])

    def test_deleted_route_reconciles_api_claim(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"api.py": "@router.patch('/x')\ndef handler():\n    return 'ok'\n"})
            refresh_path(repo, "api.py")
            claim_id = stable_api_claim_id("api.py", "PATCH", "/x", "handler")
            self.assertIsNotNone(Store(repo).get_claim(claim_id))
            (repo / "api.py").write_text("def handler():\n    return 'ok'\n", encoding="utf-8")
            refresh_path(repo, "api.py")
            self.assertIsNone(Store(repo).get_claim(claim_id))


if __name__ == "__main__":
    unittest.main()
