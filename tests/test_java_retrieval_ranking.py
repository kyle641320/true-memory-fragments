from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tmf.retrieve import retrieve_text
from tmf.warm import warm_repo
from tests.test_java_inherit import init_repo


class JavaRetrievalRankingTests(unittest.TestCase):
    def test_declaration_and_repository_intents_prefer_governing_source(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "domain/Owner.java": "package domain; public class Owner {}\n",
                "repo/OwnerRepository.java": "package repo; public interface OwnerRepository {}\n",
                "web/OwnerController.java": "package web; class OwnerController { String ownerRoute = \"/owners\"; }\n",
            })
            warm_repo(repo)
            declares = retrieve_text(repo, "Which source declares Owner?", limit=3)
            persists = retrieve_text(repo, "Which repository persists owners?", limit=3)
            self.assertTrue(declares.claims[0].claim.bindings[0].path.endswith("domain/Owner.java"))
            self.assertTrue(persists.claims[0].claim.bindings[0].path.endswith("repo/OwnerRepository.java"))


if __name__ == "__main__":
    unittest.main()
