from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tmf.backends import SemanticExtractorBackend
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo


class StubSemanticBackend(SemanticExtractorBackend):
    def __init__(self) -> None:
        self.queued: list[tuple[str, str]] = []

    def available(self) -> bool:
        return True

    def enqueue_background_refresh(self, repo_root: str, path: str) -> None:
        self.queued.append((repo_root, path))


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


class SemanticBackendStubTests(unittest.TestCase):
    def test_available_semantic_backend_queues_background_refresh_without_sync_claims(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            run(["git", "init"], repo)
            run(["git", "config", "user.email", "tmf@example.com"], repo)
            run(["git", "config", "user.name", "tmf"], repo)
            (repo / "sample.py").write_text("def f():\n    return 1\n", encoding="utf-8")
            run(["git", "add", "sample.py"], repo)
            run(["git", "commit", "-m", "init"], repo)

            backend = StubSemanticBackend()
            claims = derive_claims_for_path(GitRepo(repo), "sample.py", semantic_backend=backend)

            self.assertEqual(backend.queued, [(str(repo), "sample.py")])
            self.assertTrue(all(c.body.get("extraction_tier") != "semantic-resolved" for c in claims if c.scope != "file"))
            semantic = claims[0].body.get("semantic_extraction")
            self.assertEqual(semantic, {
                "available": True,
                "degraded": True,
                "queued_background_refresh": True,
                "extraction_tier": "semantic-resolved",
            })


if __name__ == "__main__":
    unittest.main()
