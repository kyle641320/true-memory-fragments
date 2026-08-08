from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tmf.metrics import log_event, stats

ROOT = Path(__file__).resolve().parents[1]


class Window1D3Tests(unittest.TestCase):
    def test_stats_reports_delete_missing_and_rename_counts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            log_event(repo, "rename_migration", node_id="old.py", count=2)
            log_event(repo, "rename_mass_invalidation", node_id="dead.py", count=3, reason="old_path_missing_not_unique_pure_rename")
            log_event(repo, "cache_hit", node_id="x", cache_bytes_estimate=10)
            log_event(repo, "miss", node_id="y")
            data = stats(repo)
            self.assertEqual(data["rename_migrations"], 1)
            self.assertEqual(data["rename_mass_invalidations"], 1)
            self.assertEqual(data["hit_rate"], 0.5)

    def test_field_test_harness_writes_plan_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "field-test-plan.json"
            proc = subprocess.run([
                sys.executable,
                "scripts/field_test_harness.py",
                "--out", str(out),
                "--repo-placeholder", "/tmp/repo",
                "--out-placeholder", "/tmp/out",
            ], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            result = json.loads(proc.stdout)
            self.assertEqual(result["status"], "plan_only_not_started")
            plan = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(plan["status"], "plan_only_not_started")
            self.assertTrue(any("offline harness only" in g for g in plan["guardrails"]))
            self.assertTrue(all("/tmp/repo" in cmd or "stats" in cmd for cmd in plan["commands"]))
            encoded = json.dumps(plan, sort_keys=True)
            self.assertNotIn("git clone", encoded)
            self.assertNotIn("http://", encoded)
            self.assertNotIn("https://", encoded)


if __name__ == "__main__":
    unittest.main()
