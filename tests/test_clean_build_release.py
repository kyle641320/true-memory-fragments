from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "evaluate_clean_build_release.py"


def load_gate():
    spec = importlib.util.spec_from_file_location("evaluate_clean_build_release", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def policy() -> dict:
    return {
        "policy_id": "test-v1",
        "scope": {"runtime_boundaries_allowed": ["eventuate"]},
        "hard_limits": {
            "clean_elapsed_seconds_max": 100,
            "clean_maxrss_kb_max": 1000,
            "noop_elapsed_seconds_max": 10,
        },
        "target_limits": {
            "clean_elapsed_seconds_max": 50,
            "clean_maxrss_kb_max": 500,
            "noop_elapsed_seconds_max": 5,
        },
        "required_invariants": {
            "coverage": "complete",
            "failed_files_empty": True,
            "noop_derived": 0,
            "noop_failed_files_empty": True,
        },
    }


def repo(clean_seconds=40, rss=400, noop_seconds=4, derived=0) -> dict:
    return {
        "status": "PASS",
        "warm_1": {
            "elapsed_seconds": clean_seconds,
            "maxrss_kb": rss,
            "result": {"coverage": "complete", "failed_files": {}, "files": 10},
        },
        "warm_2": {
            "elapsed_seconds": noop_seconds,
            "maxrss_kb": rss,
            "result": {"coverage": "complete", "failed_files": {}, "derived": derived, "files": 10},
        },
    }


class CleanBuildReleaseTests(unittest.TestCase):
    def test_all_targets_pass_is_go(self):
        gate = load_gate()
        result = gate.evaluate({"repositories": {"repo": repo()}}, policy())
        self.assertEqual(result["decision"], "GO")
        self.assertTrue(result["formal_release_allowed"])

    def test_hard_pass_target_failure_is_go_with_warnings(self):
        gate = load_gate()
        result = gate.evaluate({"repositories": {"repo": repo(clean_seconds=75)}}, policy())
        self.assertEqual(result["decision"], "GO_WITH_WARNINGS")
        self.assertEqual(result["warnings"], ["repo"])

    def test_hard_failure_is_no_go(self):
        gate = load_gate()
        result = gate.evaluate({"repositories": {"repo": repo(rss=1001)}}, policy())
        self.assertEqual(result["decision"], "NO-GO")
        self.assertFalse(result["formal_release_allowed"])

    def test_invariant_failure_is_no_go(self):
        gate = load_gate()
        result = gate.evaluate({"repositories": {"repo": repo(derived=1)}}, policy())
        self.assertEqual(result["decision"], "NO-GO")

    def test_override_replaces_old_repository_evidence(self):
        gate = load_gate()
        old = repo(clean_seconds=101)
        replacement = repo(clean_seconds=40)
        replacement["evidence_kind"] = "override"
        result = gate.evaluate({"repositories": {"guava": old}}, policy(), {"guava": replacement})
        self.assertEqual(result["decision"], "GO")
        self.assertEqual(result["repositories"]["guava"]["evidence_kind"], "override")

    def test_declared_runtime_boundary_does_not_force_failure(self):
        gate = load_gate()
        item = repo()
        item["status"] = "PARTIAL"
        result = gate.evaluate({"repositories": {"eventuate": item}}, policy())
        self.assertEqual(result["decision"], "GO")
        self.assertTrue(result["repositories"]["eventuate"]["runtime_boundary"])


if __name__ == "__main__":
    unittest.main()
