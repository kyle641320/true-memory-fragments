from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tmf.backends import SemanticExtractorBackend
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo
from tmf.ids import stable_function_claim_id
from tmf.schema import Claim


class StubSemanticBackend(SemanticExtractorBackend):
    def __init__(self, claims: list[Claim] | None = None) -> None:
        self.queued: list[tuple[str, str]] = []
        self._claims = claims or []

    def available(self) -> bool:
        return True

    def enqueue_background_refresh(self, repo_root: str, path: str) -> None:
        self.queued.append((repo_root, path))

    def semantic_claims_for_path(self, repo, path: str, source: str) -> list[Claim]:
        return self._claims


class UnavailableSemanticBackend(SemanticExtractorBackend):
    def available(self) -> bool:
        return False

    def enqueue_background_refresh(self, repo_root: str, path: str) -> None:
        raise AssertionError("unavailable backend must not enqueue")


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)




class SemanticBackendStubTests(unittest.TestCase):
    def test_available_semantic_backend_queues_background_refresh_without_sync_claims(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            run(["git", "init"], repo); run(["git", "config", "user.email", "tmf@example.com"], repo); run(["git", "config", "user.name", "tmf"], repo)
            (repo / "sample.py").write_text("def f():\n    return 1\n", encoding="utf-8"); run(["git", "add", "sample.py"], repo); run(["git", "commit", "-m", "init"], repo)
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
            "accepted_claims": 0,
            "rejected_claims": 0,
        })

    def test_unavailable_semantic_backend_degrades_without_enqueue(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            run(["git", "init"], repo); run(["git", "config", "user.email", "tmf@example.com"], repo); run(["git", "config", "user.name", "tmf"], repo)
            (repo / "sample.py").write_text("def f():\n    return 1\n", encoding="utf-8"); run(["git", "add", "sample.py"], repo); run(["git", "commit", "-m", "init"], repo)
            claims = derive_claims_for_path(GitRepo(repo), "sample.py", semantic_backend=UnavailableSemanticBackend())
        self.assertEqual(claims[0].body["semantic_extraction"], {
            "available": False,
            "degraded": True,
            "queued_background_refresh": False,
            "extraction_tier": "semantic-resolved",
            "accepted_claims": 0,
            "rejected_claims": 0,
        })

    def test_semantic_claims_are_accepted_only_as_attributed_capped_overlay(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            run(["git", "init"], repo); run(["git", "config", "user.email", "tmf@example.com"], repo); run(["git", "config", "user.name", "tmf"], repo)
            (repo / "sample.py").write_text("def f():\n    return 1\n", encoding="utf-8"); run(["git", "add", "sample.py"], repo); run(["git", "commit", "-m", "init"], repo)
            syntactic_id = stable_function_claim_id("sample.py", "f")
            semantic = Claim(
                id="claim_semantic_dep_demo",
            claim="semantic overlay demo",
            kind="structure",
            scope="cross-repo",
            bindings=[],
            provenance="scip",
            evidence="attributed",
            confidence=0.9,
            endorsed_by=None,
            last_verified="2026-01-01T00:00:00Z",
            model="scip-stub",
            body={"edge_kind": "semantic_depends_on", "source_id": syntactic_id, "target_symbol": "external.Symbol", "extraction_tier": "semantic-resolved"},
            )
            bad = Claim(
                id=syntactic_id,
            claim="attempt to override syntactic node",
            kind="structure",
            scope="function",
            bindings=[],
            provenance="scip",
            evidence="observed",
            confidence=1.0,
            endorsed_by=None,
            last_verified="2026-01-01T00:00:00Z",
            model="scip-stub",
            body={"qualname": "f", "extraction_tier": "semantic-resolved"},
            )
            claims = derive_claims_for_path(GitRepo(repo), "sample.py", semantic_backend=StubSemanticBackend([semantic, bad]))
        got = [c for c in claims if c.id == "claim_semantic_dep_demo"]
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0].evidence, "attributed")
        self.assertLessEqual(got[0].confidence, 0.6)
        self.assertEqual(got[0].body["extraction_tier"], "semantic-resolved")
        self.assertEqual(got[0].body["tier"], "semantic-resolved")
        self.assertEqual(len([c for c in claims if c.id == syntactic_id]), 1)
        self.assertEqual(claims[0].body["semantic_extraction"]["accepted_claims"], 1)
        self.assertEqual(claims[0].body["semantic_extraction"]["rejected_claims"], 1)


if __name__ == "__main__":
    unittest.main()
