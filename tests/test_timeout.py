import json
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from tmf.git import GitRepo
from tmf.schema import SKIPPED_CLAIM_SCHEMA_VERSION, SkippedClaim
from tmf.timeout import derive_claims_for_path_with_timeout
from tmf.warm import warm_repo
import tmf.timeout as timeout_module


class TimeoutTests(unittest.TestCase):
    def make_repo(self, files):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        for rel, text in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "-c", "user.name=TMF", "-c", "user.email=tmf@example.invalid", "commit", "-qm", "fixture"], cwd=root, check=True)
        return td, root

    def test_skipped_claim_schema(self):
        claim = SkippedClaim("slow.py", "derive_timeout", 3)
        self.assertEqual(claim.to_dict(), {
            "schema_version": SKIPPED_CLAIM_SCHEMA_VERSION,
            "file": "slow.py",
            "reason": "derive_timeout",
            "elapsed_ms": 3,
            "kind": "skipped",
        })

    def test_engine_timeout_returns_skipped_without_hanging(self):
        td, root = self.make_repo({"slow.py": "def f():\n    return 1\n"})
        self.addCleanup(td.cleanup)
        started = time.monotonic()
        outcome = derive_claims_for_path_with_timeout(GitRepo(root), "slow.py", per_file_timeout=0.001)
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 2.0)
        self.assertEqual(outcome.claims, [])
        self.assertIsNotNone(outcome.skipped)
        self.assertEqual(outcome.skipped.reason, "derive_timeout")

    def test_warm_continues_after_timeout(self):
        td, root = self.make_repo({"a.py": "def a():\n    return 1\n", "b.py": "def b():\n    return 2\n"})
        self.addCleanup(td.cleanup)
        result = warm_repo(root, per_file_timeout=0.001)
        self.assertEqual(result["files"], 2)
        self.assertEqual(result["skipped"], 2)
        self.assertEqual(result["coverage"], "partial")
        self.assertEqual(len(result["skipped_claims"]), 2)
        manifest = json.loads((root / ".tmf" / "warm_manifest.json").read_text())
        self.assertEqual(manifest["coverage"], "partial")
        self.assertEqual(len(manifest["skipped_claims"]), 2)

    def test_one_blocked_file_is_skipped_while_next_file_completes(self):
        td, root = self.make_repo({"slow.py": "def slow():\n    return 1\n", "fast.py": "def fast():\n    return 2\n"})
        self.addCleanup(td.cleanup)
        original = timeout_module.derive_claims_for_path

        def fake(repo, path, **kwargs):
            if path == "slow.py":
                time.sleep(0.15)
            return original(repo, path, **kwargs)

        timeout_module.derive_claims_for_path = fake
        try:
            slow = derive_claims_for_path_with_timeout(GitRepo(root), "slow.py", per_file_timeout=0.02)
            fast = derive_claims_for_path_with_timeout(GitRepo(root), "fast.py", per_file_timeout=1.0)
        finally:
            timeout_module.derive_claims_for_path = original
        self.assertEqual(slow.skipped.reason, "derive_timeout")
        self.assertIsNone(fast.skipped)
        self.assertTrue(fast.claims)


if __name__ == "__main__":
    unittest.main()
