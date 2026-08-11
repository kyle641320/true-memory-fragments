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

    def test_first_screen_round_robins_relevant_paths_without_language_rules(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "model/Visit.java": "package model; public class Visit { int visitCode; void visitCopy() {} }\n",
                "flow/VisitScheduler.java": "package flow; public class VisitScheduler { void visitBooking() {} }\n",
                "downstream/VisitListener.java": "package downstream; public class VisitListener { void visitBooked() {} }\n",
            })
            warm_repo(repo)
            result = retrieve_text(repo, "visit booking flow impact", limit=3)
            paths = [item.claim.bindings[0].path for item in result.claims]
            self.assertEqual(len(set(paths)), 3)


if __name__ == "__main__":
    unittest.main()
