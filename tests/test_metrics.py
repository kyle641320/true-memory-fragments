from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tmf.metrics import log_event, stats
from tmf.retrieve import refresh_path, retrieve_path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init", "-b", "master"], repo)
    run(["git", "config", "user.email", "tmf@example.com"], repo)
    run(["git", "config", "user.name", "tmf"], repo)
    (repo / "m.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    run(["git", "add", "m.py"], repo)
    run(["git", "commit", "-m", "init"], repo)
    return repo


class MetricsTests(unittest.TestCase):
    def test_metrics_events_and_stats_cli(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td))
            log_event(repo, "cache_hit", node_id="n1", cache_bytes_estimate=10)
            log_event(repo, "stale_detected", node_id="n2", stale_bindings=["m.py:f: fn_hash mismatch"])
            log_event(repo, "rederive", node_id="m.py", duration_ms=5.5, used_model=False)
            log_event(repo, "miss", node_id="m.py")
            log_event(repo, "degrade_to_source", node_id="m.py", read_bytes=20)
            log_event(repo, "rename_migration", node_id="old.py", count=3)
            log_event(repo, "rename_mass_invalidation", node_id="old.py", count=2, reason="blob_not_unique")
            data = stats(repo)
            self.assertEqual(data["counts"]["cache_hit"], 1)
            self.assertEqual(data["stale_detected"], 1)
            self.assertEqual(data["rename_migrations"], 1)
            self.assertEqual(data["rename_mass_invalidations"], 1)
            cli = json.loads(run([sys.executable, "-m", "tmf.cli", "stats", "--repo", str(repo)], ROOT).stdout)
            self.assertEqual(cli["events"], 7)

    def test_retrieve_emits_local_metrics_without_source_content(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td))
            retrieve_path(repo, "m.py")
            refresh_path(repo, "m.py")
            retrieve_path(repo, "m.py")
            events = (repo / ".tmf" / "metrics" / "events.jsonl").read_text(encoding="utf-8")
            self.assertIn('"miss"', events)
            self.assertIn('"cache_hit"', events)
            self.assertNotIn("return 1", events)


if __name__ == "__main__":
    unittest.main()
