from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tmf.validation import _copy_repo, run_heldout_validation


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def init_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    repo = tmp_path / "repo"
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


class HeldoutValidationTests(unittest.TestCase):
    def test_heldout_validation_reports_metrics_and_zero_invariant_violations(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fixture = init_repo(root / "fixture", {
                "a.py": "from b import helper\n\ndef main():\n    return helper()\n",
                "b.py": "def helper():\n    return 1\n\ndef spare():\n    return 2\n",
            })
            realistic = init_repo(root / "realistic", {
                "service.py": "from dataclasses import dataclass\n\n@dataclass\nclass User:\n    name: str\n\ndef normalize(user):\n    return user.name.strip().lower()\n",
                "api.py": "from service import normalize, User\n\ndef handler(raw):\n    return normalize(User(raw))\n",
            })
            out_dir = root / "reports"
            report = run_heldout_validation([fixture, realistic], out_dir)
            self.assertTrue((out_dir / "heldout-validation.json").exists())
            self.assertTrue((out_dir / "heldout-validation.md").exists())
            self.assertEqual(report["summary"]["status"], "pass")
            self.assertEqual(report["freshness"]["precision"], 1.0)
            self.assertEqual(report["freshness"]["recall"], 1.0)
            self.assertEqual(report["freshness"]["fp"], 0)
            self.assertEqual(report["freshness"]["fn"], 0)
            self.assertEqual(report["invariants"]["total_violations"], 0)
            self.assertEqual(report["claim_support"]["observed_without_current_source_support"], 0)
            self.assertIn("degrade_to_source", report)
            self.assertIn("properties", report)
            self.assertEqual(report["properties"]["total_failures"], 0)
            for item in report["properties"]["by_repo"]:
                for section in [
                    "cross_file_edge_lifecycle",
                    "thin_full_consistency",
                    "verification_boundaries",
                    "provenance_freshness",
                    "embedding_router_additivity",
                    "warm_idempotent_incremental",
                    "reverse_callers_coverage",
                    "config_nodes",
                    "api_nodes",
                    "read_edges",
                    "write_edges",
                    "degrade_all",
                ]:
                    self.assertIn(section, item["checks"])
            loaded = json.loads((out_dir / "heldout-validation.json").read_text(encoding="utf-8"))
            self.assertEqual(loaded["summary"]["status"], "pass")

    def test_copy_repo_excludes_local_validation_noise(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "src"
            src.mkdir()
            (src / "tmf").mkdir()
            (src / "tmf" / "__init__.py").write_text("", encoding="utf-8")
            for noisy in [".tmf", ".ts-venv", "vendor", "reports", "__pycache__"]:
                path = src / noisy
                path.mkdir()
                (path / "noise.py").write_text("def noise():\n    return 1\n", encoding="utf-8")
            (src / ".git").mkdir()
            (src / ".git" / "config").write_text("[core]\n", encoding="utf-8")
            dst = _copy_repo(src, root, "dst")
            self.assertTrue((dst / "tmf" / "__init__.py").exists())
            self.assertTrue((dst / ".git" / "config").exists())
            for noisy in [".tmf", ".ts-venv", "vendor", "reports", "__pycache__"]:
                self.assertFalse((dst / noisy).exists())


if __name__ == "__main__":
    unittest.main()
