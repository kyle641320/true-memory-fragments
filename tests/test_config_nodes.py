from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.ids import stable_config_claim_id
from tmf.retrieve import retrieve_path
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


class ConfigNodeTests(unittest.TestCase):
    def test_json_top_level_key_config_node_fresh_format_immune_and_value_sensitive(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"config.json": '{"timeout": 30, "name": "svc"}\n'})
            data = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "config.json", "--repo", str(repo)], ROOT).stdout)
            configs = [c for c in data["claims"] if c["scope"] == "config"]
            self.assertEqual({c["qualname"] for c in configs}, {"timeout", "name"})
            timeout = Store(repo).get_claim(stable_config_claim_id("config.json", "timeout"))
            self.assertIsNotNone(timeout)
            self.assertTrue(check_freshness(GitRepo(repo), timeout).fresh)

            (repo / "config.json").write_text('{\n  "name": "svc",\n  "timeout": 30\n}\n', encoding="utf-8")
            self.assertTrue(check_freshness(GitRepo(repo), timeout).fresh, check_freshness(GitRepo(repo), timeout).stale_bindings)

            (repo / "config.json").write_text('{"timeout": 60, "name": "svc"}\n', encoding="utf-8")
            freshness = check_freshness(GitRepo(repo), timeout)
            self.assertFalse(freshness.fresh)
            self.assertTrue(any("config_hash mismatch" in item for item in freshness.stale_bindings), freshness.stale_bindings)

    def test_json_unrelated_key_change_does_not_stale_and_delete_reconciles(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"config.json": '{"timeout": 30, "name": "svc"}\n'})
            retrieve_path(repo, "config.json")
            timeout_id = stable_config_claim_id("config.json", "timeout")
            timeout = Store(repo).get_claim(timeout_id)
            self.assertIsNotNone(timeout)
            (repo / "config.json").write_text('{"timeout": 30, "name": "api"}\n', encoding="utf-8")
            self.assertTrue(check_freshness(GitRepo(repo), timeout).fresh)
            (repo / "config.json").write_text('{"name": "api"}\n', encoding="utf-8")
            retrieve_path(repo, "config.json")
            self.assertIsNone(Store(repo).get_claim(timeout_id))

    def test_invalid_json_degrades_to_no_config_nodes_without_crash(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"broken.json": '{"timeout": '})
            data = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "broken.json", "--repo", str(repo)], ROOT).stdout)
            self.assertFalse([c for c in data["claims"] if c["scope"] == "config"])

    @unittest.skipIf(sys.version_info < (3, 11), "tomllib unavailable")
    def test_toml_top_level_key_config_node_fresh_format_immune_and_value_sensitive(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"pyproject.toml": 'name = "svc"\ntimeout = 30\n'})
            retrieve_path(repo, "pyproject.toml")
            timeout = Store(repo).get_claim(stable_config_claim_id("pyproject.toml", "timeout"))
            self.assertIsNotNone(timeout)
            self.assertTrue(check_freshness(GitRepo(repo), timeout).fresh)
            (repo / "pyproject.toml").write_text('timeout = 30\nname = "svc"\n', encoding="utf-8")
            self.assertTrue(check_freshness(GitRepo(repo), timeout).fresh)
            (repo / "pyproject.toml").write_text('name = "svc"\ntimeout = 60\n', encoding="utf-8")
            self.assertFalse(check_freshness(GitRepo(repo), timeout).fresh)


if __name__ == "__main__":
    unittest.main()
