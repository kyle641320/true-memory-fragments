from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tmf.retrieve import retrieve_path
from tmf.store import Store
from tmf.validation import _expected_stale_ids_for_sample, run_self_validation


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


class SelfValidationTests(unittest.TestCase):
    def test_expected_stale_set_includes_enclosing_span_for_nested_sample(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "m.py": "def outer():\n    class Inner:\n        pass\n    return 1\n"
            })
            retrieve_path(repo, "m.py")
            claims = list(Store(repo).iter_claims())
            by_qualname = {claim.body.get("qualname"): claim for claim in claims if isinstance(claim.body, dict)}
            inner = by_qualname["outer.Inner"]
            outer = by_qualname["outer"]
            expected = _expected_stale_ids_for_sample(inner, claims, insertion_after_line=2)
            self.assertIn(inner.id, expected)
            self.assertIn(outer.id, expected)

    def test_expected_stale_set_is_tight_for_same_file_unrelated_spans(self):
        def claim(cid, scope, qualname, start, end):
            return SimpleNamespace(
                id=cid,
                scope=scope,
                body={"qualname": qualname, "anchors": [{"path": "m.py", "line_start": start, "line_end": end}]},
                bindings=[SimpleNamespace(path="m.py", qualname=qualname)],
            )

        x = claim("x", "function", "x", 1, 3)
        y = claim("y", "function", "y", 5, 7)
        edge_to_y = SimpleNamespace(
            id="edge-y",
            scope="function",
            body={"edge_kind": "calls"},
            bindings=[SimpleNamespace(path="m.py", qualname="y")],
        )
        expected = _expected_stale_ids_for_sample(x, [x, y, edge_to_y], insertion_after_line=2)
        self.assertIn("x", expected)
        self.assertNotIn("y", expected)
        self.assertNotIn("edge-y", expected)

    def test_expected_stale_set_for_top_level_sample_excludes_unrelated_node(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "m.py": "def target():\n    return 1\n\ndef unrelated():\n    return 2\n"
            })
            retrieve_path(repo, "m.py")
            claims = list(Store(repo).iter_claims())
            by_qualname = {claim.body.get("qualname"): claim for claim in claims if isinstance(claim.body, dict)}
            target = by_qualname["target"]
            unrelated = by_qualname["unrelated"]
            expected = _expected_stale_ids_for_sample(target, claims, insertion_after_line=1)
            self.assertIn(target.id, expected)
            self.assertNotIn(unrelated.id, expected)

    def test_self_validation_reports_real_repo_checks_and_sampling_metrics(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "app.py": "from settings import helper\n\ndef main():\n    return helper()\n",
                "settings.py": "def helper():\n    return 1\n\ndef spare():\n    return 2\n",
                "config.json": '{"timeout": 30, "name": "svc"}\n',
            })
            out = Path(td) / "out"
            report = run_self_validation(repo, out, sample_limit=3)
            self.assertTrue((out / "self-validation.json").exists())
            self.assertTrue((out / "self-validation.md").exists())
            self.assertIn("summary", report)
            self.assertIn("freshness_sampling", report)
            self.assertGreater(report["freshness_sampling"]["samples"], 0)
            self.assertEqual(report["summary"]["status"], "pass")
            self.assertEqual(report["freshness_sampling"]["fp"], 0)
            self.assertEqual(report["freshness_sampling"]["fn"], 0)
            loaded = json.loads((out / "self-validation.json").read_text(encoding="utf-8"))
            self.assertEqual(loaded["summary"]["status"], "pass")


if __name__ == "__main__":
    unittest.main()
