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


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init"], repo)
    run(["git", "config", "user.email", "tmf@example.com"], repo)
    run(["git", "config", "user.name", "tmf"], repo)
    (repo / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    run(["git", "add", "app.py"], repo)
    run(["git", "commit", "-m", "init"], repo)
    return repo


class ExplainTests(unittest.TestCase):
    def test_explain_json_has_agent_branch_fields_and_recomputes_stale(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td))
            retrieve = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "app.py", "--repo", str(repo), "--model-derive"], ROOT).stdout)
            fn = [c for c in retrieve["claims"] if c["scope"] == "function"][0]
            (repo / "app.py").write_text("def add(a, b):\n    return a + b + 1\n", encoding="utf-8")
            explained = json.loads(run([sys.executable, "-m", "tmf.cli", "explain", fn["id"], "--repo", str(repo), "--json"], ROOT).stdout)
            self.assertFalse(explained["fresh"])
            self.assertTrue(explained["stale_reasons"])
            self.assertEqual(explained["action_hint"], "degrade_to_source_or_rederive")
            self.assertIn("trust", explained)
            self.assertIn("freshness_bindings", explained)
            self.assertIn("anchors", explained)

    def test_explain_reviewer_text_separates_provenance_from_freshness(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td))
            retrieve = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "app.py", "--repo", str(repo), "--model-derive"], ROOT).stdout)
            fn = [c for c in retrieve["claims"] if c["scope"] == "function"][0]
            text = run([sys.executable, "-m", "tmf.cli", "explain", fn["id"], "--repo", str(repo)], ROOT).stdout
            self.assertIn("[FRESH]", text)
            self.assertIn("trust_basis:", text)
            self.assertIn("belief_provenance:", text)
            self.assertIn("freshness_bindings:", text)
            self.assertIn("source_anchors:", text)

    def test_explain_shows_raw_confidence_cap_for_attributed_claim(self):
        from tmf.extract import extract_functions
        from tmf.git import GitRepo
        from tmf.llm import ModelCandidate
        from tmf.model_derive import _claim_from_candidate
        from tmf.provenance import collect_function_provenance
        from tmf.store import Store

        with tempfile.TemporaryDirectory() as td:
            repo_path = Path(td) / "repo"
            repo_path.mkdir()
            run(["git", "init"], repo_path)
            run(["git", "config", "user.email", "tmf@example.com"], repo_path)
            run(["git", "config", "user.name", "tmf"], repo_path)
            (repo_path / "app.py").write_text('def charge(x):\n    """Reject negative balances because ledger settlement cannot carry debt."""\n    return x >= 0\n', encoding="utf-8")
            run(["git", "add", "app.py"], repo_path)
            run(["git", "commit", "-m", "init"], repo_path)
            repo = GitRepo(repo_path)
            fn = extract_functions("app.py", repo.read_file("app.py"))[0]
            evidence = collect_function_provenance(repo, path="app.py", qualname=fn.qualname, docstring=fn.docstring, line_start=fn.line_start, line_end=fn.line_end)
            candidate = ModelCandidate(
                claim="charge rejects negative balances because ledger settlement cannot carry debt.",
                kind="intent",
                evidence_class="intent_needs_provenance",
                support=["ledger settlement cannot carry debt"],
                confidence=0.99,
            )
            claim = _claim_from_candidate(repo, fn, candidate, "fake-model", provenance_evidence=evidence)
            Store(repo.root).put_claim(claim)
            explained = json.loads(run([sys.executable, "-m", "tmf.cli", "explain", claim.id, "--repo", str(repo_path), "--json"], ROOT).stdout)
            self.assertEqual(explained["trust"]["level"], "attributed")
            self.assertEqual(explained["raw_confidence"], 0.99)
            self.assertLessEqual(explained["confidence"], 0.6)
            self.assertTrue(explained["confidence_cap_applied"])
            self.assertEqual(explained["belief_provenance"][0]["type"], "docstring")
            self.assertIn("quoted_text_untrusted_data", explained["belief_provenance"][0])


if __name__ == "__main__":
    unittest.main()
