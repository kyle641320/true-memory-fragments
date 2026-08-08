from __future__ import annotations

import importlib.util
import json
from unittest import mock
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tmf.java_extract import JAVA_DEGRADE_HINT, java_status
from tmf.warm import warm_repo


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ten_repo_mutation_gate.py"


def load_gate():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("ten_repo_mutation_gate", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def run(args: list[str], cwd: Path) -> bytes:
    return subprocess.run(args, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def init_repo(root: Path, dirty: bool = False) -> Path:
    repo = root / "repo"
    repo.mkdir()
    run(["git", "init"], repo)
    run(["git", "config", "user.email", "tmf@example.com"], repo)
    run(["git", "config", "user.name", "tmf"], repo)
    (repo / "A.java").write_text("package demo;\npublic class A { int x = 1; }\n", encoding="utf-8")
    (repo / "B.java").write_text("package demo;\npublic class B { int y = 2; }\n", encoding="utf-8")
    run(["git", "add", "A.java", "B.java"], repo)
    run(["git", "commit", "-m", "fixture"], repo)
    warm_repo(repo)
    if dirty:
        (repo / "A.java").write_text("package demo;\npublic class A { int x = 3; }\n", encoding="utf-8")
        warm_repo(repo)
    return repo


@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class TenRepoMutationGateTests(unittest.TestCase):
    def test_probe_preserves_existing_dirty_file_and_restores_exact_bytes(self):
        gate = load_gate()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = init_repo(root, dirty=True)
            output = root / "out"
            before_a = (repo / "A.java").read_bytes()
            before_b = (repo / "B.java").read_bytes()
            before_diff = gate.tracked_diff_fingerprint(repo)

            result = gate.run_probe("fixture", repo, output)

            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["path"], "B.java")
            self.assertEqual((repo / "A.java").read_bytes(), before_a)
            self.assertEqual((repo / "B.java").read_bytes(), before_b)
            self.assertEqual(gate.tracked_diff_fingerprint(repo), before_diff)
            self.assertTrue(all(result["checks"].values()))

            replayed = gate.run_probe("fixture", repo, output)
            self.assertEqual(replayed, result)

    def test_startup_recovery_restores_only_expected_probe_bytes(self):
        gate = load_gate()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = init_repo(root)
            target = repo / "A.java"
            original = target.read_bytes()
            mutation = gate.mutated_bytes(original, "recovery")
            journal_path = root / "journal.json"
            journal = {
                "schema": "tmf-mutation-journal-v1", "state": "mutated", "repo": str(repo), "path": "A.java",
                "mode": target.stat().st_mode & 0o7777,
                "original_b64": gate.base64.b64encode(original).decode("ascii"),
                "original_sha256": gate.sha256_bytes(original), "mutated_sha256": gate.sha256_bytes(mutation),
            }
            gate.atomic_write_json(journal_path, journal)
            gate.atomic_write_bytes(target, mutation, journal["mode"])

            recovered = gate.recover_journal(journal_path)

            self.assertEqual(recovered["state"], "recovered")
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual(json.loads(journal_path.read_text(encoding="utf-8"))["recovery"], "restored_from_journal")

    def test_recovery_refuses_to_overwrite_concurrent_change(self):
        gate = load_gate()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = init_repo(root)
            target = repo / "A.java"
            original = target.read_bytes()
            mutation = gate.mutated_bytes(original, "recovery")
            journal_path = root / "journal.json"
            gate.atomic_write_json(journal_path, {
                "state": "mutated", "repo": str(repo), "path": "A.java", "mode": target.stat().st_mode & 0o7777,
                "original_b64": gate.base64.b64encode(original).decode("ascii"),
                "original_sha256": gate.sha256_bytes(original), "mutated_sha256": gate.sha256_bytes(mutation),
            })
            target.write_bytes(b"concurrent\n")

            with self.assertRaisesRegex(RuntimeError, "refusing to overwrite concurrent change"):
                gate.recover_journal(journal_path)
            self.assertEqual(target.read_bytes(), b"concurrent\n")

    def test_workers_return_warm_and_streamed_audit_results(self):
        gate = load_gate()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = init_repo(root)
            output = root / "out"

            warm = gate.run_worker("warm", repo, output)
            audit = gate.run_worker("audit", repo, output, "A.java")

            self.assertEqual(warm["result"]["derived"], 0)
            self.assertEqual(audit["stale"], 0)
            self.assertGreater(audit["claims"], 0)
            self.assertTrue(audit["changed_path_claim_ids"])
            self.assertFalse(list(output.glob(".*.json")))

    def test_worker_failure_still_restores_probe_bytes(self):
        gate = load_gate()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = init_repo(root)
            output = root / "out"
            before = {path.name: path.read_bytes() for path in repo.glob("*.java")}
            calls = 0

            def fail_mutation_warm(kind, worker_repo, worker_output, changed_path=None):
                nonlocal calls
                calls += 1
                if calls == 3:
                    raise RuntimeError("simulated worker kill")
                if kind == "warm":
                    return gate.timed_warm(worker_repo)
                return gate.audit_claims(worker_repo, changed_path)

            with mock.patch.object(gate, "run_worker", side_effect=fail_mutation_warm):
                result = gate.run_probe("fixture", repo, output)

            self.assertEqual(result["status"], "BLOCKED")
            self.assertIn("simulated worker kill", result["error"])
            self.assertEqual({path.name: path.read_bytes() for path in repo.glob("*.java")}, before)
            self.assertTrue(result["checks"]["bytes_restored"])
            self.assertTrue(result["checks"]["tracked_diff_restored"])


if __name__ == "__main__":
    unittest.main()
