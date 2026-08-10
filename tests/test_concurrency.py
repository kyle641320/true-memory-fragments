from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from multiprocessing import Process, Queue
from pathlib import Path

from tmf.store import Store
from tmf.warm import warm_repo


def _run_warm(repo: str, q: Queue) -> None:
    try:
        q.put(warm_repo(repo))
    except Exception as exc:  # pragma: no cover - child diagnostic
        q.put({"error": repr(exc)})


class ConcurrentWarmChecks(unittest.TestCase):
    def _repo(self, root: Path) -> Path:
        repo = root / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-b", "master"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        subprocess.run(["git", "config", "user.email", "tmf@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "tmf"], cwd=repo, check=True)
        for i in range(8):
            (repo / f"m{i}.py").write_text(f"def f{i}(x):\n    return x + {i}\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        subprocess.run(["git", "commit", "-m", "fixture"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return repo

    def test_two_process_warm_does_not_corrupt_claim_files(self):
        with tempfile.TemporaryDirectory() as td:
            repo = self._repo(Path(td))
            q: Queue = Queue()
            p1 = Process(target=_run_warm, args=(str(repo), q))
            p2 = Process(target=_run_warm, args=(str(repo), q))
            p1.start(); p2.start()
            p1.join(20); p2.join(20)
            self.assertFalse(p1.is_alive(), "first warm process deadlocked")
            self.assertFalse(p2.is_alive(), "second warm process deadlocked")
            self.assertEqual(p1.exitcode, 0)
            self.assertEqual(p2.exitcode, 0)
            results = [q.get(timeout=2), q.get(timeout=2)]
            self.assertFalse(any("error" in r for r in results), results)

            claim_files = sorted((repo / ".tmf" / "claims").glob("*.json"))
            self.assertGreater(len(claim_files), 0)
            for path in claim_files:
                json.loads(path.read_text(encoding="utf-8"))
            claims = list(Store(repo).iter_claims())
            self.assertGreater(len(claims), 0)
            self.assertTrue((repo / ".tmf" / ".lock").exists())


if __name__ == "__main__":
    unittest.main()
