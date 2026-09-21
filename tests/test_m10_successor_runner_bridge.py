"""Failure-boundary regressions; mandatory CLI separately uses real preflight."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from bench.agent_ab.same_version_chain_v1 import m10_successor_runner_bridge as bridge
from bench.agent_ab.same_version_chain_v1.m10_successor_protocol import BudgetCaps, RunRecord
from bench.agent_ab.same_version_chain_v1.m10_successor_run_ledger import RunAdmissionLedger


class RunnerBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.experiment = {
            "randomization": {"blocks": 1, "schedule": bridge.scientific.build_randomized_schedule(1, 20260920)},
            "inputs": {arm: [{"role": "system", "content": "common"},
                            {"role": "user", "content": "common task"}] for arm in bridge.scientific.ARMS},
            "execution": {"budgets": asdict(BudgetCaps())},
            "action_schemas": copy.deepcopy(bridge.scientific.ACTION_SCHEMAS),
        }
        self.experiment["seal_sha256"] = bridge.digest(bridge.canonical(self.experiment))

    def joint(self):
        # Only these bookkeeping tests stub scientific validity.
        # The production CLI accepts no bypass and reconstructs preflight.
        with patch.object(bridge.scientific, "verify_sealed_manifest"):
            return bridge.build_joint_manifest(self.experiment)

    def test_invalid_joint_digest_prevents_output_admission_and_adapter(self):
        joint = self.joint()
        joint["scenario"] = "wrong_model"
        with patch.object(bridge, "OfflineProtocolBroker") as factory:
            with self.assertRaises(bridge.PreflightInvariantError):
                bridge.run_joint_batch(joint, self.root / "batch")
        factory.assert_not_called()
        self.assertFalse((self.root / "batch").exists())

    def test_rehashed_altered_contract_rejected_before_scientific_run(self):
        joint = self.joint()
        joint["broker_contract"]["limits"]["max_calls"] += 1
        content = {k: v for k, v in joint.items() if k != "seal_sha256"}
        joint["seal_sha256"] = bridge.digest(bridge.canonical(content))
        with patch.object(bridge.scientific, "verify_sealed_manifest"):
            with self.assertRaises(bridge.PreflightInvariantError):
                bridge.verify_joint_manifest(joint)

    def test_fast_guard_requires_previously_admitted_digest_even_after_rehash(self):
        joint = self.joint()
        pinned = joint["seal_sha256"]
        joint["scenario"] = "wrong_model"
        joint["seal_sha256"] = bridge.digest(bridge.canonical({k: v for k, v in joint.items() if k != "seal_sha256"}))
        with self.assertRaises(bridge.PreflightInvariantError):
            bridge.verify_joint_manifest(joint, full_preflight=False, admitted_joint_sha256=pinned)
        with self.assertRaises(bridge.PreflightInvariantError):
            bridge.verify_joint_manifest(joint, full_preflight=False)

    def test_atomic_batch_and_start_exist_before_first_adapter_factory(self):
        joint = self.joint()
        destination = self.root / "batch"
        observed = []

        def fail_factory(*args, **kwargs):
            events = [json.loads(line) for line in (destination / "runs.jsonl").read_bytes().splitlines()]
            observed.extend(events)
            self.assertEqual(2, len(events))
            self.assertTrue((destination / "client-tokens.jsonl").exists())
            raise RuntimeError("injected construction failure")

        with patch.object(bridge.scientific, "verify_sealed_manifest"), \
             patch.object(bridge.scientific, "compile_check", return_value={"ok": True}), \
             patch.object(bridge, "OfflineProtocolBroker", side_effect=fail_factory) as factory:
            summary = bridge.run_joint_batch(joint, destination)
        self.assertEqual(1, factory.call_count)
        self.assertEqual(2, len(observed))
        records = json.loads((destination / "run-records.json").read_text())
        accounting = json.loads((destination / "accounting.json").read_text())
        self.assertEqual(6, summary["denominator"])
        self.assertEqual("adapter_factory_error:RuntimeError", records[0]["failure_reason"])
        self.assertEqual(["not_started_after_batch_admission"] * 5, [r["failure_reason"] for r in records[1:]])
        self.assertEqual(1, accounting["runs"]["started_runs"])
        self.assertEqual(1, accounting["runs"]["completed_runs"])
        self.assertEqual(0, accounting["client"]["admitted_calls"])
        self.assertFalse((destination / "broker-tokens.jsonl").exists())

    def test_client_initialization_failure_keeps_whole_admitted_schedule(self):
        joint = self.joint()
        destination = self.root / "batch"
        with patch.object(bridge.scientific, "verify_sealed_manifest"), \
             patch.object(bridge, "TokenBudgetLedger", side_effect=OSError("injected disk failure")), \
             patch.object(bridge, "OfflineProtocolBroker") as factory:
            summary = bridge.run_joint_batch(joint, destination)
        factory.assert_not_called()
        self.assertEqual(6, summary["denominator"])
        self.assertEqual(0, summary["protocol_complete"])
        self.assertEqual(6, summary["compile_unknown"])
        self.assertFalse(summary["journal_integrity_verified"])
        records = json.loads((destination / "run-records.json").read_text())
        self.assertTrue(all(r["failure_reason"] == "not_started_after_batch_admission" for r in records))

    def test_dispatch_requires_correct_durable_active_run_and_sticky_integrity(self):
        joint = self.joint()
        row = joint["experiment"]["randomization"]["schedule"][0]
        ids = [r["run_id"] for r in joint["experiment"]["randomization"]["schedule"]]
        path = self.root / "runs.jsonl"
        with RunAdmissionLedger(path, joint["seal_sha256"], ids) as ledger:
            with patch.object(bridge, "_run_binding") as binding:
                args = (joint, joint["seal_sha256"], ledger, self.root, row, [], BudgetCaps())
                with self.assertRaises(bridge.PreflightInvariantError):
                    bridge._dispatch_guard(*args)
                binding.assert_not_called()
                ledger.start(row["run_id"])
                bridge._dispatch_guard(*args)
                self.assertEqual(1, binding.call_count)
                original = path.read_bytes()
                path.write_bytes(original + b"corruption")
                with self.assertRaises(bridge.PreflightInvariantError):
                    bridge._dispatch_guard(*args)
                path.write_bytes(original)
                with self.assertRaises(bridge.PreflightInvariantError):
                    bridge._dispatch_guard(*args)
                self.assertEqual(1, binding.call_count)

    def test_duplicate_or_missing_fault_coverage_rejected_before_batch(self):
        for scenarios in (("ok",) * 6, bridge.SCENARIOS[:-1], tuple(reversed(bridge.SCENARIOS))):
            with self.subTest(scenarios=scenarios), patch.object(bridge, "SCENARIOS", scenarios), \
                 patch.object(bridge, "run_joint_batch") as execute:
                with self.assertRaises(bridge.PreflightInvariantError):
                    bridge.conformance_rehearsal(self.experiment, self.root / "output")
                execute.assert_not_called()

    def test_last_live_integrity_failure_cannot_be_cleared_by_valid_reopen(self):
        joint = self.joint()
        valid = {"journal_integrity_verified": True, "halted": False}

        class LiveLedger:
            def __init__(self, *args):
                self.reads = 0
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def snapshot(self):
                self.reads += 1
                return {**valid, "journal_integrity_verified": self.reads != 7}

        def completed(*args, **kwargs):
            kwargs["on_admit"]()
            return RunRecord(
                run_id=kwargs["run_id"], seal_sha256=joint["seal_sha256"],
                evidence_kind=bridge.EVIDENCE_KIND, durable_ledger=True,
                protocol_ok=True, protocol_status="completed", final_received=True,
                semantic={"semantic_pass": True}, compilation={"ok": True},
                adapter_evidence={"closed": True, "failed": False,
                                  "client_ledger": valid, "broker_ledger": valid})

        destination = self.root / "batch"
        with patch.object(bridge.scientific, "verify_sealed_manifest"), \
             patch.object(bridge, "TokenBudgetLedger", LiveLedger), \
             patch.object(bridge, "_snapshot_token_journal", return_value=valid), \
             patch.object(bridge, "_run_one_with_factory", side_effect=completed):
            summary = bridge.run_joint_batch(joint, destination)
        self.assertEqual(6, summary["joint_success"])
        self.assertFalse(summary["offline_bridge_complete"])
        self.assertFalse(summary["journal_integrity_verified"])
        accounting = json.loads((destination / "accounting.json").read_text())
        self.assertFalse(accounting["client_before_close"]["journal_integrity_verified"])
        self.assertTrue(accounting["client"]["journal_integrity_verified"])
        self.assertIn({"boundary": "client_before_close", "journal_integrity_verified": False},
                      accounting["integrity_observations"])

    def test_interruption_is_fatal_and_reopen_recovers_all_six_without_resume(self):
        joint = self.joint()
        destination = self.root / "interrupted"
        with patch.object(bridge.scientific, "verify_sealed_manifest"), \
             patch.object(bridge.scientific, "compile_check", return_value={"ok": True}), \
             patch.object(bridge, "OfflineProtocolBroker", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                bridge.run_joint_batch(joint, destination)
        self.assertFalse((destination / "summary.json").exists())
        ids = [row["run_id"] for row in joint["experiment"]["randomization"]["schedule"]]
        with RunAdmissionLedger(destination / "runs.jsonl", joint["seal_sha256"], ids) as recovered:
            snapshot = recovered.snapshot()
            self.assertTrue(snapshot["inspection_only"])
            self.assertEqual(6, snapshot["denominator"])
            self.assertEqual(1, snapshot["started_runs"])
            self.assertEqual(0, snapshot["completed_runs"])
            self.assertEqual("missing_completion_record", recovered.records()[0]["failure_reason"])
            self.assertEqual(["not_started_after_batch_admission"] * 5,
                             [r["failure_reason"] for r in recovered.records()[1:]])

    def test_missing_real_evidence_cannot_pass_exact_evidence_oracle(self):
        directory = self.root / "evidence"
        directory.mkdir()
        for name, value in (("joint-manifest.json", self.joint()), ("summary.json", {}),
                            ("run-records.json", []), ("accounting.json", {})):
            (directory / name).write_text(bridge.canonical(value))
        with patch.object(bridge, "verify_joint_manifest"):
            with self.assertRaisesRegex(ValueError, "complete ordered ITT"):
                bridge.verify_batch_evidence(directory)


if __name__ == "__main__":
    unittest.main()
