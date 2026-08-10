from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tmf.git import GitRepo
from tmf.derive import derive_claims_for_path
from tmf.freshness import check_freshness


class YamlSqlNodeChecks(unittest.TestCase):
    def _repo(self, root: Path, files: dict[str, str]) -> Path:
        repo = root / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-b", "master"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        subprocess.run(["git", "config", "user.email", "tmf@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "tmf"], cwd=repo, check=True)
        for rel, text in files.items():
            path = repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        subprocess.run(["git", "commit", "-m", "fixture"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return repo

    def test_yaml_config_nodes_and_value_staleness(self):
        with tempfile.TemporaryDirectory() as td:
            repo_path = self._repo(Path(td), {"app.yaml": "service:\n  port: 8080\n  name: api\nfeature: true\n"})
            repo = GitRepo(repo_path)
            claims = derive_claims_for_path(repo, "app.yaml")
            configs = [c for c in claims if c.scope == "config"]
            keys = {c.body.get("qualname"): c for c in configs}
            self.assertIn("service.port", keys)
            self.assertIn("feature", keys)
            self.assertEqual(keys["service.port"].body.get("config_kind"), "yaml")
            self.assertEqual(keys["service.port"].body["anchors"][0]["line_start"], 2)
            self.assertTrue(check_freshness(repo, keys["service.port"]).fresh)
            (repo_path / "app.yaml").write_text("service:\n  port: 9090\n  name: api\nfeature: true\n", encoding="utf-8")
            self.assertFalse(check_freshness(repo, keys["service.port"]).fresh)

    def test_complex_yaml_degrades_to_no_config_nodes(self):
        with tempfile.TemporaryDirectory() as td:
            repo_path = self._repo(Path(td), {"app.yml": "items:\n  - one\n  - two\n"})
            repo = GitRepo(repo_path)
            claims = derive_claims_for_path(repo, "app.yml")
            self.assertFalse([c for c in claims if c.scope == "config"])

    def test_sql_create_table_and_view_nodes(self):
        with tempfile.TemporaryDirectory() as td:
            repo_path = self._repo(Path(td), {"schema.sql": "CREATE TABLE users (id int);\ncreate view active_users as select * from users;\n"})
            repo = GitRepo(repo_path)
            claims = derive_claims_for_path(repo, "schema.sql")
            decls = [c for c in claims if c.scope == "declaration"]
            by_name = {c.body.get("qualname"): c for c in decls}
            self.assertEqual(by_name["users"].body.get("declaration_kind"), "sql_table")
            self.assertEqual(by_name["active_users"].body.get("declaration_kind"), "sql_view")
            self.assertEqual(by_name["users"].body.get("language"), "sql")

    def test_dynamic_sql_string_in_python_is_not_parsed(self):
        with tempfile.TemporaryDirectory() as td:
            repo_path = self._repo(Path(td), {"dao.py": "table = 'users'\nsql = 'CREATE TABLE ' + table\n"})
            repo = GitRepo(repo_path)
            claims = derive_claims_for_path(repo, "dao.py")
            self.assertFalse([c for c in claims if c.body.get("declaration_kind", "").startswith("sql_")])


if __name__ == "__main__":
    unittest.main()
