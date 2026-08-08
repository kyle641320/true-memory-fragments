from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.java_extract import JAVA_DEGRADE_HINT, java_status
from tmf.retrieve import retrieve_path
from tmf.store import Store

ROOT = Path(__file__).resolve().parents[1]


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def init_repo(tmp_path: Path, content: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init"], repo)
    run(["git", "config", "user.email", "tmf@example.com"], repo)
    run(["git", "config", "user.name", "tmf"], repo)
    (repo / "Sample.java").write_text(content, encoding="utf-8")
    run(["git", "add", "Sample.java"], repo)
    run(["git", "commit", "-m", "init"], repo)
    return repo


JAVA_FIXTURE = """package demo;

@interface Marker {}

@Marker
public class Sample {
    public static final String NAME = "tmf";
    private int count = 1;

    public Sample() {}

    public String greet(String who) {
        return NAME + who + count;
    }

    interface Inner {
        void run();
    }

    enum Mode { FAST, SLOW }
}
"""


@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaNodeTests(unittest.TestCase):
    def test_java_nodes_are_derived_without_edges(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), JAVA_FIXTURE)
            data = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "Sample.java", "--repo", str(repo)], ROOT).stdout)
            java_claims = [c for c in data["claims"] if c.get("language") == "java" and c.get("extraction_tier") == "java-treesitter-syntactic"]
            qualnames = {c["qualname"] for c in java_claims}
            self.assertIn("Sample", qualnames)
            self.assertIn("Sample.greet", qualnames)
            self.assertIn("Sample.NAME", qualnames)
            self.assertIn("Sample.count", qualnames)
            self.assertIn("Sample.Inner", qualnames)
            self.assertIn("Sample.Mode", qualnames)
            self.assertTrue(all(c.get("extraction_tier") == "java-treesitter-syntactic" for c in java_claims))
            for claim_id in [c["id"] for c in java_claims]:
                claim = Store(repo).get_claim(claim_id)
                self.assertIsNotNone(claim)
                self.assertTrue(check_freshness(GitRepo(repo), claim).fresh)

    def test_java_freshness_is_two_way_comments_whitespace_ignored_literals_included(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), JAVA_FIXTURE)
            result = retrieve_path(repo, "Sample.java")
            greet = next(item.claim for item in result.claims if item.claim.body.get("qualname") == "Sample.greet")
            class_claim = next(item.claim for item in result.claims if item.claim.body.get("qualname") == "Sample")
            edited = JAVA_FIXTURE.replace("return NAME + who + count;", "// trivia\n        return NAME + who + count;")
            (repo / "Sample.java").write_text(edited, encoding="utf-8")
            self.assertTrue(check_freshness(GitRepo(repo), greet).fresh)
            edited = JAVA_FIXTURE.replace("return NAME + who + count;", "return NAME + who + count + \"!\";")
            (repo / "Sample.java").write_text(edited, encoding="utf-8")
            self.assertFalse(check_freshness(GitRepo(repo), greet).fresh)
            self.assertFalse(check_freshness(GitRepo(repo), class_claim).fresh)

    def test_java_annotation_change_stales_method(self):
        source = JAVA_FIXTURE.replace("    public String greet", "    @Deprecated\n    public String greet")
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), source)
            result = retrieve_path(repo, "Sample.java")
            greet = next(item.claim for item in result.claims if item.claim.body.get("qualname") == "Sample.greet")
            edited = source.replace("@Deprecated", "@SuppressWarnings(\"unchecked\")")
            (repo / "Sample.java").write_text(edited, encoding="utf-8")
            self.assertFalse(check_freshness(GitRepo(repo), greet).fresh)

    def test_java_reformatting_remains_fresh(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), JAVA_FIXTURE)
            result = retrieve_path(repo, "Sample.java")
            greet = next(item.claim for item in result.claims if item.claim.body.get("qualname") == "Sample.greet")
            edited = JAVA_FIXTURE.replace("public String greet(String who) {", "public   String   greet( String who )   {")
            (repo / "Sample.java").write_text(edited, encoding="utf-8")
            self.assertTrue(check_freshness(GitRepo(repo), greet).fresh)

    def test_java_delete_reconciles_tombstone(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), JAVA_FIXTURE)
            result = retrieve_path(repo, "Sample.java")
            greet_id = next(item.claim.id for item in result.claims if item.claim.body.get("qualname") == "Sample.greet")
            self.assertIsNotNone(Store(repo).get_claim(greet_id))
            (repo / "Sample.java").write_text("public class Sample { int x; }\n", encoding="utf-8")
            retrieve_path(repo, "Sample.java")
            self.assertIsNone(Store(repo).get_claim(greet_id))


class JavaDegradeTests(unittest.TestCase):
    def test_missing_tree_sitter_degrades_to_file_claim_with_hint(self):
        import tmf.java_extract as java_extract

        original = java_extract._language_and_parser
        try:
            java_extract._java_available.cache_clear()
            java_extract._language_and_parser = lambda: (_ for _ in ()).throw(ImportError("simulated missing tree-sitter"))
            with tempfile.TemporaryDirectory() as td:
                repo = init_repo(Path(td), JAVA_FIXTURE)
                result = retrieve_path(repo, "Sample.java")
                claims = [item.claim for item in result.claims]
                self.assertEqual([c for c in claims if c.body.get("language") == "java"], [])
                self.assertIn("java_extraction", claims[0].body)
                self.assertTrue(claims[0].body["java_extraction"]["degraded"])
                self.assertIn("tree_sitter", claims[0].body["java_extraction"]["degrade_hint"])
                self.assertEqual(claims[0].scope, "file")
        finally:
            java_extract._language_and_parser = original
            java_extract._java_available.cache_clear()

    def test_java_status_uses_cached_availability_once(self):
        import tmf.java_extract as java_extract

        original = java_extract._language_and_parser
        calls = {"count": 0}

        def fake_parser():
            calls["count"] += 1
            raise ImportError("simulated missing tree-sitter")

        try:
            java_extract._java_available.cache_clear()
            java_extract._language_and_parser = fake_parser
            first = java_extract.java_status()
            second = java_extract.java_status()
            self.assertFalse(first.available)
            self.assertFalse(second.available)
            self.assertEqual(calls["count"], 1)
        finally:
            java_extract._language_and_parser = original
            java_extract._java_available.cache_clear()


if __name__ == "__main__":
    unittest.main()
