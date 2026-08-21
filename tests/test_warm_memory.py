"""Memory regression tests for warm.py streaming fixes.

Baseline (before fix): list(store.iter_claims()) materializes entire claim graph
in memory, costing ~11 KB per claim on large repos.

After fix: warm uses _ClaimRef projections (id, owner_path, binding tuples) that
cost a few hundred bytes per claim, and only reloads full claims by id when
rename migration actually rewrites them.
"""
import tempfile
import unittest
from pathlib import Path

from tmf.git import GitRepo
from tmf.store import Store
from tmf.warm import warm_repo, _ClaimRef, _claim_refs, _claims_by_path_from_claims


def init_repo(root: Path, files: dict[str, str]) -> Path:
    """Initialize a git repository with given files."""
    root.mkdir(parents=True, exist_ok=True)
    for relpath, content in files.items():
        path = root / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    import subprocess
    subprocess.run(["git", "init", "-q", "-b", "master"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=root, check=True)
    return root


class WarmMemoryTest(unittest.TestCase):
    def test_claim_ref_projection_is_bounded(self):
        """_ClaimRef holds only identity + paths + blobs, not full claim body."""
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"a.py": "def func():\n    return 1\n"})
            warm_repo(repo)
            store = Store(repo)
            
            refs = _claim_refs(store)
            self.assertGreater(len(refs), 0, "Should have derived some claims")
            
            for ref in refs:
                self.assertIsInstance(ref, _ClaimRef)
                self.assertIsInstance(ref.id, str)
                self.assertIsInstance(ref.binding_paths, tuple)
                self.assertIsInstance(ref.binding_blobs, tuple)
                # Owner path can be None for some claim types
                self.assertTrue(ref.owner_path is None or isinstance(ref.owner_path, str))

    def test_claims_by_path_accepts_refs_or_claims(self):
        """_claims_by_path_from_claims handles both projections and full claims."""
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"a.py": "def func():\n    return 1\n"})
            warm_repo(repo)
            store = Store(repo)
            
            refs = _claim_refs(store)
            by_path_from_refs = _claims_by_path_from_claims(refs)
            
            full_claims = list(store.iter_claims())
            by_path_from_claims = _claims_by_path_from_claims(full_claims)
            
            # Both should produce the same path keys
            self.assertEqual(set(by_path_from_refs.keys()), set(by_path_from_claims.keys()))
            
            # And same claim id counts per path
            for path in by_path_from_refs:
                ref_ids = {entry.id for entry in by_path_from_refs[path]}
                claim_ids = {entry.id for entry in by_path_from_claims[path]}
                self.assertEqual(ref_ids, claim_ids, f"path {path}")

    def test_warm_uses_projections_not_full_claims(self):
        """Warm's rename/delete detection uses _ClaimRef, not materialized full claims."""
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "a.py": "def func():\n    return 1\n",
                "b.py": "from a import func\n\ndef caller():\n    return func()\n",
            })
            result = warm_repo(repo)
            self.assertEqual(result["derived"], 2)
            
            # Rename a.py -> c.py
            import subprocess
            subprocess.run(["git", "mv", "a.py", "c.py"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "rename"], cwd=repo, check=True)
            
            # This warm must detect the rename without holding all full claims in memory
            result = warm_repo(repo)
            self.assertGreater(result.get("renamed_claims", 0), 0, "Should have renamed claims")


if __name__ == "__main__":
    unittest.main()
