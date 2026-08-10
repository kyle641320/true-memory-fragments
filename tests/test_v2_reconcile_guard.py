from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


class ReconcileGuardTests(unittest.TestCase):
    def test_path_reconcile_does_not_delete_multi_binding_claim(self):
        from tmf.derive import now_utc
        from tmf.git import GitRepo
        from tmf.schema import Binding, Claim
        from tmf.store import Store

        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            run(["git", "init", "-b", "master"], repo)
            run(["git", "config", "user.email", "tmf@example.com"], repo)
            run(["git", "config", "user.name", "tmf"], repo)
            (repo / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
            (repo / "b.py").write_text("def b():\n    return 2\n", encoding="utf-8")
            run(["git", "add", "a.py", "b.py"], repo)
            run(["git", "commit", "-m", "init"], repo)

            git_repo = GitRepo(repo)
            store = Store(repo)
            multi = Claim(
                id="claim_arch_multi_binding",
                claim="a.py and b.py are related in a cross-file architecture claim.",
                kind="architecture",
                scope="module",
                bindings=[
                    Binding(path="a.py", file_blob=git_repo.blob_sha("a.py"), fn_hash=None, commit=git_repo.head()),
                    Binding(path="b.py", file_blob=git_repo.blob_sha("b.py"), fn_hash=None, commit=git_repo.head()),
                ],
                provenance="model",
                evidence="inferred",
                confidence=0.2,
                endorsed_by=None,
                last_verified=now_utc(),
                model="test",
                body={"anchors": [{"path": "a.py", "line_start": 1, "line_end": 2}, {"path": "b.py", "line_start": 1, "line_end": 2}]},
            )
            store.put_claim(multi)
            self.assertIsNotNone(store.get_claim(multi.id))

            # Re-derive only a.py. The multi-binding architecture claim mentions
            # a.py but must not be deleted by path-local reconciliation.
            run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "a.py", "--repo", str(repo)], ROOT)
            self.assertIsNotNone(store.get_claim(multi.id))

            disk_ids = {p.stem for p in (repo / ".tmf" / "claims").glob("*.json")}
            self.assertIn(multi.id, disk_ids)


if __name__ == "__main__":
    unittest.main()
