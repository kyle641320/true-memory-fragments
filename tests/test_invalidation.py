import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tmf.invalidation import diff_revisions


class InvalidationDiffTests(unittest.TestCase):
    def test_rev_pair_diff_is_store_independent_and_has_manifest_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "TMF"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "tmf@example.invalid"], cwd=root, check=True)
            (root / "app.py").write_text("def f():\n    return 1\n")
            subprocess.run(["git", "add", "app.py"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "old"], cwd=root, check=True)
            old = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            (root / "app.py").write_text("def f():\n    return 2\n")
            subprocess.run(["git", "add", "app.py"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "new"], cwd=root, check=True)
            new = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            result = diff_revisions(root, old, new, per_file_timeout=60)
            self.assertEqual(result["mode"], "dry_run")
            self.assertEqual(result["old_rev"], old)
            self.assertEqual(result["new_rev"], new)
            self.assertEqual(result["summary"]["files_scanned"], 1)
            self.assertEqual(result["summary"]["changed"], 1)
            self.assertEqual(result["skipped"], [])
            json.dumps(result)


if __name__ == "__main__":
    unittest.main()
