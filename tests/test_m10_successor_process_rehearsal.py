from __future__ import annotations

import copy
import json
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from bench.agent_ab.same_version_chain_v1 import m10_successor_process_rehearsal as rehearsal
from bench.agent_ab.same_version_chain_v1.m10_successor_process_io import ProcessCaps
from bench.agent_ab.same_version_chain_v1.m10_successor_protocol import ACTION_SCHEMAS, AdapterRequest, LiveExecutionDisabled
from bench.agent_ab.same_version_chain_v1.m10_successor_token_budget import TokenBudgetLedger, TokenLimits


class ProcessRehearsalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.contract = rehearsal.offline_contract(
            experiment_seal_sha256="0" * 64, limits=TokenLimits(10000, 4096, 14096, 30000, 12288, 24),
            max_request_bytes=120000, max_response_bytes=64000, timeout_seconds=2,
        )
        self.request = AdapterRequest(
            ({"role": "system", "content": "Use the JSON action protocol."},
             {"role": "user", "content": "List source paths under <workspace>."}),
            copy.deepcopy(ACTION_SCHEMAS), 4096, 16000, 2,
        )
        self.caps = ProcessCaps(1000000, 64000, 4096)
        self.number = 0

    def ledger(self):
        self.number += 1
        ledger = TokenBudgetLedger(self.root / f"ledger-{self.number}.jsonl", self.contract.limits)
        self.addCleanup(ledger.close)
        return ledger

    def invoke(self, scenario="ok", ledger=None, **options):
        return rehearsal.rehearse_turn(self.contract, options.pop("request", self.request),
                                       ledger=ledger or self.ledger(), scenario=scenario,
                                       caps=options.pop("caps", self.caps), **options)

    def test_real_three_process_roundtrip_has_only_fictional_evidence(self):
        record = self.invoke()
        self.assertEqual("ok", record["status"])
        self.assertEqual('{"action":"list"}', record["completion"]["text"])
        self.assertEqual(["capabilities", "count", "completion"], [r["phase"] for r in record["process_attempts"]])
        self.assertTrue(all(r["status"] == "completed" for r in record["process_attempts"]))
        self.assertTrue(record["candidate_call_admitted"])
        self.assertEqual(6032, record["ledger"]["provider_usage"]["total_tokens"])
        self.assertEqual("fictional_fixture_not_provider", record["usage_origin"])
        self.assertEqual(0, record["model_calls"])
        for key in ("model_execution_enabled", "model_pilot_admitted", "provider_token_limits_verified"):
            self.assertIs(record[key], False)

    def test_nonfictional_contract_is_rejected_before_any_process(self):
        for changed in (replace(self.contract, provider_id="real-provider"),
                        replace(self.contract, request_model="real-model"),
                        replace(self.contract, endpoint="https://example.invalid/v1/chat/completions")):
            with patch.object(rehearsal, "_exchange") as exchange, self.assertRaises(LiveExecutionDisabled):
                rehearsal.rehearse_turn(changed, self.request, ledger=self.ledger(), caps=self.caps)
            exchange.assert_not_called()

    def test_pre_admission_faults_are_reported_without_reservation(self):
        for scenario in ("legacy_capabilities", "estimated_count", "count_timeout"):
            with self.subTest(scenario=scenario):
                record = self.invoke(scenario, request=replace(self.request, timeout_seconds=0.5))
                self.assertEqual("failed", record["status"])
                self.assertFalse(record["candidate_call_admitted"])
                self.assertEqual(0, record["ledger"]["admitted_calls"])
                self.assertNotIn("completion", [r["phase"] for r in record["process_attempts"]])
                self.assertTrue(rehearsal.expected_outcome(record))

    def test_all_uncertain_completion_faults_charge_once_and_do_not_retry(self):
        cases = ("timeout", "exit_before_reply", "reply_then_exit", "stdout_flood", "stderr_flood",
                 "malformed_json", "extra_frame", "wrong_identity", "wrong_hash", "missing_usage")
        for scenario in cases:
            with self.subTest(scenario=scenario):
                record = self.invoke(scenario, request=replace(self.request, timeout_seconds=0.7))
                self.assertEqual("failed", record["status"])
                self.assertIsNone(record["completion"])
                self.assertTrue(record["candidate_call_admitted"])
                self.assertEqual(3, len(record["process_attempts"]))
                ledger = record["ledger"]
                self.assertTrue(ledger["halted"])
                self.assertTrue(ledger["journal_integrity_verified"])
                self.assertEqual(1, ledger["admitted_calls"])
                self.assertIsNone(ledger["provider_usage"])
                self.assertEqual((6000, 4096), (ledger["charged_input_tokens"], ledger["charged_output_tokens"]))
                self.assertTrue(ledger["records"][0]["itt_included"])
                self.assertTrue(rehearsal.expected_outcome(record))

    def test_known_refusal_and_truncation_keep_usage_but_not_action_text(self):
        for scenario in ("refusal", "length"):
            record = self.invoke(scenario)
            self.assertEqual("protocol_failed", record["status"])
            self.assertEqual("", record["completion"]["text"])
            self.assertFalse(record["completion"]["usable_action_text"])
            self.assertTrue(record["ledger"]["halted"])
            self.assertEqual(32, record["ledger"]["provider_usage"]["output_tokens"])
            self.assertTrue(rehearsal.expected_outcome(record))

    def test_unexpected_failure_is_not_a_passing_negative_scenario(self):
        record = self.invoke("legacy_capabilities")
        self.assertTrue(rehearsal.expected_outcome(record))
        wrong = copy.deepcopy(record)
        wrong["category"] = "spawn_error"
        self.assertFalse(rehearsal.expected_outcome(wrong))
        wrong = copy.deepcopy(record)
        wrong["phase"] = "count"
        self.assertFalse(rehearsal.expected_outcome(wrong))
        wrong = copy.deepcopy(record)
        wrong["process_attempts"].append({"phase": "retry"})
        self.assertFalse(rehearsal.expected_outcome(wrong))
        wrong = copy.deepcopy(record)
        wrong["model_pilot_admitted"] = True
        self.assertFalse(rehearsal.expected_outcome(wrong))

    def test_admission_is_durable_before_completion_process_starts(self):
        ledger = self.ledger()
        exchange = rehearsal._exchange
        observed = []

        def inspect(source, raw, **kwargs):
            op = json.loads(raw)["request"]["op"]
            snapshot = ledger.snapshot()
            observed.append((op, snapshot["admitted_calls"]))
            if op == "complete":
                self.assertTrue(snapshot["journal_integrity_verified"])
                self.assertIsNotNone(snapshot["pending_call_id"])
                lines = (self.root / f"ledger-{self.number}.jsonl").read_text().splitlines()
                self.assertEqual("admitted", json.loads(lines[-1])["event"])
            return exchange(source, raw, **kwargs)

        with patch.object(rehearsal, "_exchange", side_effect=inspect):
            record = self.invoke(ledger=ledger)
        self.assertEqual("ok", record["status"])
        self.assertEqual([("capabilities", 0), ("count", 0), ("complete", 1)], observed)

    def test_failed_admission_fsync_never_launches_completion(self):
        ledger = self.ledger()
        with patch("bench.agent_ab.same_version_chain_v1.m10_successor_token_budget.os.fsync",
                   side_effect=OSError("deliberate offline fixture")):
            record = self.invoke(ledger=ledger)
        self.assertEqual("failed", record["status"])
        self.assertEqual("ledger_error", record["category"])
        self.assertTrue(record["candidate_call_admitted"])
        self.assertEqual(2, len(record["process_attempts"]))
        self.assertTrue(record["ledger"]["halted"])
        self.assertFalse(record["ledger"]["journal_integrity_verified"])
        self.assertEqual(4096, record["ledger"]["charged_output_tokens"])

    def test_corruption_after_settlement_cannot_return_usable_completion(self):
        ledger = self.ledger()
        ledger_path = self.root / f"ledger-{self.number}.jsonl"
        accept = rehearsal.accept_completion

        def corrupt(*args, **kwargs):
            completion = accept(*args, **kwargs)
            with ledger_path.open("ab") as stream:
                stream.write(b"corrupt")
            return completion

        with patch.object(rehearsal, "accept_completion", side_effect=corrupt):
            record = self.invoke(ledger=ledger)
        self.assertEqual(("failed", "ledger_error"), (record["status"], record["category"]))
        self.assertIsNone(record["completion"])
        self.assertTrue(record["candidate_call_admitted"])
        self.assertTrue(record["ledger"]["halted"])
        self.assertFalse(record["ledger"]["journal_integrity_verified"])
        self.assertEqual(1, record["ledger"]["admitted_calls"])
        self.assertEqual(6032, record["ledger"]["provider_usage"]["total_tokens"])
        self.assertFalse(rehearsal.expected_outcome(record))

    def test_cli_duplicate_results_cannot_hide_missing_scenarios(self):
        valid = self.invoke()
        with patch.object(rehearsal, "rehearse_turn", side_effect=lambda *a, **kw: copy.deepcopy(valid)):
            summary = rehearsal.conformance_rehearsal(self.root / "duplicate-results")
        self.assertEqual(16, summary["scenarios"])
        self.assertEqual(set(rehearsal.SCENARIOS), set(summary["checks"]))
        self.assertTrue(summary["checks"]["ok"])
        self.assertFalse(summary["checks"]["timeout"])
        self.assertFalse(summary["coverage_verified"])
        self.assertFalse(summary["unique_call_ids"])
        self.assertFalse(summary["all_expected_outcomes"])

    def test_cli_reused_call_id_cannot_certify_complete_coverage(self):
        valid = self.invoke()

        def duplicate_id(*args, **kwargs):
            record = copy.deepcopy(valid)
            record["scenario"] = kwargs["scenario"]
            return record

        # Isolate correlation identity from the already separately tested
        # fault-outcome validator; correct labels alone are not sufficient.
        with patch.object(rehearsal, "rehearse_turn", side_effect=duplicate_id), \
                patch.object(rehearsal, "expected_outcome", return_value=True):
            summary = rehearsal.conformance_rehearsal(self.root / "duplicate-call-ids")
        self.assertTrue(summary["coverage_verified"])
        self.assertFalse(summary["unique_call_ids"])
        self.assertFalse(summary["all_expected_outcomes"])

    def test_halted_and_pending_ledgers_do_not_launch_even_capabilities(self):
        ledger = self.ledger()
        self.invoke("missing_usage", ledger=ledger)
        pending = self.ledger()
        pending.reserve("unsettled", request_sha256="1" * 64, input_tokens=6000, max_output_tokens=4096)
        for value in (ledger, pending):
            with patch.object(rehearsal, "_exchange") as exchange:
                record = self.invoke(ledger=value)
            exchange.assert_not_called()
            self.assertEqual("ledger_error", record["category"])
            self.assertEqual(1, record["ledger"]["admitted_calls"])
            self.assertFalse(record["candidate_call_admitted"])

    def test_complete_ipc_envelope_cap_is_checked_before_spawn(self):
        with patch.object(rehearsal, "_exchange") as exchange:
            record = self.invoke(caps=ProcessCaps(64, 64000, 4096))
        exchange.assert_not_called()
        self.assertEqual("request_too_large", record["category"])
        self.assertFalse(record["candidate_call_admitted"])

    def test_transport_drift_after_reservation_cannot_dispatch_or_refund(self):
        original = rehearsal.transport_seal
        calls = []

        def drift(*args):
            calls.append(1)
            seal = original(*args)
            if len(calls) == 4:  # Initial seal + two read-only exchanges, then complete.
                seal["seal_sha256"] = "0" * 64
            return seal

        with patch.object(rehearsal, "transport_seal", side_effect=drift):
            record = self.invoke()
        self.assertTrue(record["candidate_call_admitted"])
        self.assertEqual(2, len(record["process_attempts"]))
        self.assertEqual("contract_error", record["category"])
        self.assertEqual(4096, record["ledger"]["charged_output_tokens"])
        self.assertIsNone(record["ledger"]["provider_usage"])

    def test_three_exchanges_share_one_declining_deadline(self):
        exchange = rehearsal._exchange
        deadlines = []

        def capture(*args, **kwargs):
            deadlines.append(kwargs["timeout_seconds"])
            return exchange(*args, **kwargs)

        with patch.object(rehearsal, "_exchange", side_effect=capture):
            record = self.invoke()
        self.assertEqual("ok", record["status"])
        self.assertEqual(3, len(deadlines))
        self.assertTrue(2 >= deadlines[0] > deadlines[1] > deadlines[2] > 0)

    def test_slow_serialization_cannot_restart_deadline_or_launch_completion(self):
        canonical = rehearsal.canonical

        def delayed(value):
            if isinstance(value, dict) and value.get("request", {}).get("op") == "complete":
                time.sleep(0.7)
            return canonical(value)

        with patch.object(rehearsal, "canonical", side_effect=delayed):
            record = self.invoke(request=replace(self.request, timeout_seconds=0.6))
        self.assertEqual("failed", record["status"])
        self.assertEqual("timeout", record["category"])
        self.assertEqual("completion", record["phase"])
        self.assertEqual(2, len(record["process_attempts"]))
        self.assertTrue(record["candidate_call_admitted"])
        self.assertTrue(record["ledger"]["halted"])
        self.assertIsNone(record["ledger"]["provider_usage"])

    def test_reply_returned_after_deadline_is_not_accepted_as_success(self):
        exchange = rehearsal._exchange

        def delayed(source, raw, **kwargs):
            reply = exchange(source, raw, **kwargs)
            if json.loads(raw)["request"]["op"] == "complete":
                time.sleep(0.7)
            return reply

        with patch.object(rehearsal, "_exchange", side_effect=delayed):
            record = self.invoke(request=replace(self.request, timeout_seconds=0.6))
        self.assertEqual("timeout", record["category"])
        self.assertIsNone(record["completion"])
        self.assertTrue(record["ledger"]["halted"])
        self.assertEqual(4096, record["ledger"]["charged_output_tokens"])

    def test_seal_is_stable_and_opaque_ids_do_not_change_model_payload(self):
        self.assertEqual(rehearsal.transport_seal(self.contract, self.caps),
                         rehearsal.transport_seal(self.contract, self.caps))
        a, b = self.invoke(), self.invoke()
        self.assertNotEqual(a["call_id"], b["call_id"])
        self.assertEqual(a["payload_sha256"], b["payload_sha256"])
        self.assertEqual(a["transport_seal_sha256"], b["transport_seal_sha256"])

    def test_internal_error_after_reservation_still_preserves_admission(self):
        exchange = rehearsal._exchange

        def fail_after_admission(source, raw, **kwargs):
            if json.loads(raw)["request"]["op"] == "complete":
                raise RuntimeError("must not appear in a public result")
            return exchange(source, raw, **kwargs)

        with patch.object(rehearsal, "_exchange", side_effect=fail_after_admission):
            record = self.invoke()
        self.assertEqual("internal_error", record["category"])
        self.assertTrue(record["ledger"]["halted"])
        self.assertEqual(1, record["ledger"]["admitted_calls"])
        self.assertNotIn("must not appear", json.dumps(record))


if __name__ == "__main__":
    unittest.main()
