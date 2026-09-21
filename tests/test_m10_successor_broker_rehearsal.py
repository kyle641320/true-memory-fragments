from __future__ import annotations

import copy
import hashlib
import io
import json
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from bench.agent_ab.same_version_chain_v1 import m10_successor_broker_rehearsal as rehearsal
from bench.agent_ab.same_version_chain_v1.m10_successor_process_io import ProcessCaps, ProcessTransportError
from bench.agent_ab.same_version_chain_v1.m10_successor_protocol import ACTION_SCHEMAS, AdapterRequest, LiveExecutionDisabled
from bench.agent_ab.same_version_chain_v1.m10_successor_token_budget import TokenBudgetLedger


class BrokerRehearsalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.contract = rehearsal.fixed_contract()
        self.caps = ProcessCaps(1000000, 64000, 4096)
        self.request = AdapterRequest(
            ({"role": "system", "content": "Use the supplied JSON action schemas."},
             {"role": "user", "content": "List the relative source paths in <workspace>."}),
            copy.deepcopy(ACTION_SCHEMAS), 4096, 16000, 3,
        )
        self.number = 0

    def invoke(self, scenario="ok", *, request=None, caps=None):
        self.number += 1
        directory = self.root / str(self.number)
        directory.mkdir()
        with TokenBudgetLedger(directory / "client-ledger.jsonl", self.contract.limits) as ledger:
            record = rehearsal.rehearse_turn(
                self.contract, request or self.request, ledger=ledger,
                broker_ledger_path=directory / "broker-ledger.jsonl", trace_path=directory / "backend-events.jsonl",
                scenario=scenario, caps=caps or self.caps, evidence_dir=directory,
            )
        return record, directory

    def test_real_broker_roundtrip_preserves_original_fields_and_rejects_fresh_worker_replay(self):
        exchange, deadlines, remaining, observed_admission = rehearsal._exchange, [], [], []

        def inspect(source, raw, **options):
            deadlines.append(options["deadline_monotonic"])
            remaining.append(options["timeout_seconds"])
            if json.loads(raw)["op"] == "complete" and not observed_admission:
                latest = json.loads((self.root / "1" / "client-ledger.jsonl").read_bytes().splitlines()[-1])
                self.assertEqual("admitted", latest["event"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), latest["request_sha256"])
                observed_admission.append(True)
            return exchange(source, raw, **options)

        with patch.object(rehearsal, "_exchange", side_effect=inspect):
            record, directory = self.invoke()
        self.assertTrue(rehearsal.expected_outcome(record), record)
        self.assertEqual(1, len(set(deadlines)))
        self.assertTrue(all(left > right > 0 for left, right in zip(remaining, remaining[1:])))
        self.assertEqual([True], observed_admission)
        self.assertEqual(4, len(record["process_attempts"]))
        self.assertEqual(["capabilities", "count", "capabilities", "count", "complete"],
                         [event["operation"] for event in record["backend_trace"]])
        raw = json.loads((directory / "03-completion.receipt.bin").read_bytes())
        self.assertEqual("original_backend_field_not_added_by_broker", raw["response"]["fixture_provenance"])
        self.assertEqual("fictional-original-response", raw["response"]["id"])
        self.assertEqual(self.contract.response_model, raw["response"]["model"])
        self.assertEqual({"prompt_tokens": 6000, "completion_tokens": 32, "total_tokens": 6032}, raw["response"]["usage"])
        self.assertEqual(b'{"error":"duplicate_call","protocol":"tmf-successor-broker-v2"}',
                         (directory / "04-replay.receipt.bin").read_bytes())
        self.assertEqual((directory / "03-completion.request.bin").read_bytes(),
                         (directory / "04-replay.request.bin").read_bytes())
        for owner in ("client", "broker"):
            with TokenBudgetLedger(directory / f"{owner}-ledger.jsonl", self.contract.limits) as reopened:
                self.assertEqual(record[f"{owner}_ledger"], reopened.snapshot())
        self.assertEqual("matching_known_usage", record["accounting_reconciliation"])
        self.assertTrue(record["replay"]["backend_trace_unchanged"])
        self.assertEqual(0, record["model_calls"])

    def test_wrong_original_model_has_known_terminal_broker_usage_and_unknown_client_usage(self):
        record, _ = self.invoke("wrong_model")
        self.assertTrue(rehearsal.expected_outcome(record), record)
        self.assertEqual("response_error", record["category"])
        self.assertEqual("broker_known_client_unknown", record["accounting_reconciliation"])
        broker, client = record["broker_ledger"], record["client_ledger"]
        self.assertTrue(broker["halted"])
        self.assertEqual("failed", broker["records"][0]["status"])
        self.assertEqual(6032, broker["provider_usage"]["total_tokens"])
        self.assertEqual(32, broker["charged_output_tokens"])
        self.assertIsNone(client["provider_usage"])
        self.assertEqual(4096, client["charged_output_tokens"])

    def test_all_preadmission_faults_retain_records_without_either_reservation(self):
        for scenario in ("legacy_capabilities", "estimated_count", "count_timeout"):
            with self.subTest(scenario=scenario):
                record, _ = self.invoke(scenario)
                self.assertTrue(rehearsal.expected_outcome(record), record)
                self.assertFalse(record["candidate_call_admitted"])
                self.assertFalse(record["broker_call_admitted"])
                self.assertEqual(0, record["client_ledger"]["admitted_calls"])
                self.assertEqual(0, record["broker_ledger"]["admitted_calls"])

    def test_backend_failures_unknown_usage_and_known_unusable_outputs_are_not_refunded(self):
        for scenario in ("backend_exception", "malformed_response", "missing_usage", "oversize_response", "length", "refusal"):
            with self.subTest(scenario=scenario):
                record, _ = self.invoke(scenario)
                self.assertTrue(rehearsal.expected_outcome(record), record)
                self.assertTrue(record["client_ledger"]["halted"])
                self.assertTrue(record["broker_ledger"]["halted"])
                self.assertEqual(1, sum(e["operation"] == "complete" for e in record["backend_trace"]))
                self.assertNotIn("fictional backend detail", json.dumps(record))

    def test_killed_backend_preserves_pending_broker_charge_and_reopened_worker_cannot_dispatch(self):
        record, directory = self.invoke("backend_timeout")
        self.assertTrue(rehearsal.expected_outcome(record), record)
        self.assertEqual(record["call_id"], record["broker_ledger"]["pending_call_id"])
        self.assertEqual("unsettled_reservation_after_reopen", record["broker_ledger"]["halt_reason"])
        before = (directory / "backend-events.jsonl").read_bytes()
        deadline = time.monotonic() + 2
        source = rehearsal._worker_source(
            self.contract, materials=rehearsal.inventory(), broker_ledger_path=directory / "broker-ledger.jsonl",
            trace_path=directory / "backend-events.jsonl", scenario="backend_timeout",
            deadline_monotonic=deadline, max_request_frame_bytes=self.caps.max_request_bytes,
        )
        reply = rehearsal._exchange(source, (directory / "03-completion.request.bin").read_bytes(),
                                    caps=self.caps, timeout_seconds=2, deadline_monotonic=deadline)
        self.assertEqual({"protocol": rehearsal.PROTOCOL, "error": "ledger_error"}, json.loads(reply.stdout))
        self.assertEqual(before, (directory / "backend-events.jsonl").read_bytes())
        self.assertFalse(record["provider_cancellation_confirmed"])

    def test_client_deadline_can_expire_after_broker_settlement_without_rewriting_either_ledger(self):
        exchange = rehearsal._exchange

        def delayed(source, raw, **options):
            result = exchange(source, raw, **options)
            if json.loads(raw)["op"] == "complete":
                # Expire only after the real worker has returned a settled
                # response. Startup latency must not choose the fault phase.
                time.sleep(max(0, options["deadline_monotonic"] - time.monotonic()) + 0.05)
            return result

        with patch.object(rehearsal, "_exchange", side_effect=delayed):
            record, _ = self.invoke()
        self.assertEqual(("failed", "timeout"), (record["status"], record["category"]))
        self.assertEqual("broker_known_client_unknown", record["accounting_reconciliation"])
        self.assertEqual(32, record["broker_ledger"]["charged_output_tokens"])
        self.assertFalse(record["broker_ledger"]["halted"])
        self.assertTrue(record["client_ledger"]["halted"])
        self.assertEqual(4096, record["client_ledger"]["charged_output_tokens"])
        self.assertIsNone(record["completion"])
        self.assertIsNotNone(record["wire_frames"][2]["receipt_sha256"])
        self.assertFalse(rehearsal.expected_outcome(record))

    def test_runtime_ids_and_scenario_metadata_never_change_the_backend_payload(self):
        first, first_dir = self.invoke()
        second, second_dir = self.invoke("wrong_model")
        self.assertNotEqual(first["call_id"], second["call_id"])
        self.assertEqual(first["payload_sha256"], second["payload_sha256"])
        self.assertEqual((first_dir / "model-payload.json").read_bytes(), (second_dir / "model-payload.json").read_bytes())
        body = json.loads((first_dir / "model-payload.json").read_bytes())
        self.assertEqual({"messages", "model", "max_completion_tokens", "stream", "store", "n"}, set(body))
        payload = (first_dir / "model-payload.json").read_text()
        for value in (first["call_id"], second["call_id"], str(first_dir), "wrong_model", "broker_core_seal"):
            self.assertNotIn(value, payload)
        for record in (first, second):
            self.assertTrue(rehearsal.expected_outcome(record), record)
            self.assertEqual(record["payload_sha256"], record["backend_trace"][-1]["payload_sha256"])
            self.assertEqual(4096, record["backend_trace"][-1]["output_cap"])

    def test_wire_frame_has_independent_budget_and_oversized_completion_frame_never_spawns(self):
        large = replace(self.request, messages=(self.request.messages[0], {"role": "user", "content": "x" * 65000}))
        record, _ = self.invoke(request=large)
        self.assertTrue(rehearsal.expected_outcome(record), record)
        self.assertLess(record["payload_bytes"], self.contract.max_request_bytes)
        self.assertGreater(record["wire_frames"][2]["request_bytes"], self.contract.max_request_bytes)
        limited = ProcessCaps(record["wire_frames"][2]["request_bytes"] - 1, 64000, 4096)
        rejected, _ = self.invoke(request=large, caps=limited)
        self.assertEqual("request_too_large", rejected["category"])
        self.assertEqual(2, len(rejected["process_attempts"]))
        self.assertEqual("not_dispatched", rejected["wire_frames"][2]["status"])
        self.assertTrue(rejected["candidate_call_admitted"])
        self.assertFalse(rejected["broker_call_admitted"])
        self.assertEqual(4096, rejected["client_ledger"]["charged_output_tokens"])
        self.assertEqual(["capabilities", "count"], [e["operation"] for e in rejected["backend_trace"]])
        too_small, _ = self.invoke(caps=ProcessCaps(1000000, 64, 4096))
        self.assertEqual("stdout_limit", too_small["category"])
        self.assertFalse(too_small["candidate_call_admitted"])
        no_spawn, directory = self.invoke(caps=ProcessCaps(1, 64000, 4096))
        self.assertEqual("request_too_large", no_spawn["category"])
        self.assertEqual("not_created", no_spawn["broker_ledger_state"])
        self.assertIsNone(no_spawn["broker_ledger"])
        self.assertFalse((directory / "broker-ledger.jsonl").exists())

    def test_material_drift_after_client_admission_stops_broker_dispatch_without_refund(self):
        original, calls = rehearsal.broker_core_seal, []

        def drift(*args):
            calls.append(1)
            seal = original(*args)
            if len(calls) == 4:  # Initial, capabilities, count, then completion.
                seal["seal_sha256"] = "0" * 64
            return seal

        with patch.object(rehearsal, "broker_core_seal", side_effect=drift):
            record, _ = self.invoke()
        self.assertEqual("contract_error", record["category"])
        self.assertEqual(2, len(record["process_attempts"]))
        self.assertTrue(record["candidate_call_admitted"])
        self.assertFalse(record["broker_call_admitted"])
        self.assertEqual(4096, record["client_ledger"]["charged_output_tokens"])

    def test_worker_checks_material_hashes_before_import_or_ledger_creation(self):
        materials = rehearsal.inventory()
        materials["bench/agent_ab/same_version_chain_v1/m10_successor_broker_core.py"] = "0" * 64
        deadline = time.monotonic() + 2
        source = rehearsal._worker_source(
            self.contract, materials=materials, broker_ledger_path=self.root / "broker.jsonl",
            trace_path=self.root / "trace.jsonl", scenario="ok", deadline_monotonic=deadline,
            max_request_frame_bytes=self.caps.max_request_bytes,
        )
        with self.assertRaises(ProcessTransportError) as raised:
            rehearsal._exchange(source, b"{}", caps=self.caps, timeout_seconds=2, deadline_monotonic=deadline)
        self.assertEqual("process_exit", raised.exception.category)
        self.assertFalse((self.root / "broker.jsonl").exists())
        self.assertFalse((self.root / "trace.jsonl").exists())

    def test_nonfixture_contract_and_public_live_controls_are_rejected(self):
        for changed in (replace(self.contract, provider_id="other"), replace(self.contract, request_model="other"),
                        replace(self.contract, endpoint="https://example.invalid/v1/chat/completions")):
            with self.subTest(changed=changed.provider_id), patch.object(rehearsal, "_exchange") as exchange:
                with TokenBudgetLedger(self.root / (changed.provider_id + str(len(changed.endpoint)) + changed.request_model + ".jsonl"),
                                       self.contract.limits) as ledger, self.assertRaises(LiveExecutionDisabled):
                    rehearsal.rehearse_turn(changed, self.request, ledger=ledger, broker_ledger_path=self.root / "broker.jsonl",
                                            trace_path=self.root / "trace.jsonl", caps=self.caps)
                exchange.assert_not_called()
        with patch.object(sys, "argv", ["rehearsal", "--output", str(self.root / "out"), "--provider", "live"]), \
                redirect_stderr(io.StringIO()), \
                self.assertRaises(SystemExit) as raised:
            rehearsal.main()
        self.assertEqual(2, raised.exception.code)
        self.assertFalse((self.root / "out").exists())

    def test_exact_outcome_rejects_unrelated_fault_trace_and_ledger_failures(self):
        valid, _ = self.invoke("legacy_capabilities")
        self.assertTrue(rehearsal.expected_outcome(valid))
        for field, value in (("category", "spawn_error"), ("phase", "count"), ("scientific_run_admitted", True)):
            changed = copy.deepcopy(valid)
            changed[field] = value
            self.assertFalse(rehearsal.expected_outcome(changed))
        changed = copy.deepcopy(valid)
        changed["backend_trace"].append({"operation": "complete", "fictional": True})
        self.assertFalse(rehearsal.expected_outcome(changed))
        changed = copy.deepcopy(valid)
        changed["broker_ledger"]["journal_integrity_verified"] = False
        self.assertFalse(rehearsal.expected_outcome(changed))

    def test_cli_retains_all_twelve_cases_raw_bytes_and_distinct_call_ids(self):
        output = self.root / "conformance"
        summary = rehearsal.conformance_rehearsal(output)
        self.assertTrue(summary["all_expected_outcomes"], summary)
        self.assertEqual(12, summary["scenarios"])
        self.assertEqual(set(rehearsal.SCENARIOS), set(summary["checks"]))
        self.assertEqual("broker-core-seal", json.loads((output / "broker-core-seal.json").read_bytes())["name"])
        identifiers = []
        for scenario in rehearsal.SCENARIOS:
            directory = output / scenario
            record = json.loads((directory / "record.json").read_bytes())
            identifiers.append(record["call_id"])
            self.assertTrue(rehearsal.expected_outcome(record), record)
            self.assertEqual(record["payload_sha256"], hashlib.sha256((directory / "model-payload.json").read_bytes()).hexdigest())
            for frame in record["wire_frames"]:
                for kind in ("request", "receipt"):
                    if frame[kind + "_sha256"] is not None:
                        raw = (directory / frame[kind + "_file"]).read_bytes()
                        self.assertEqual(frame[kind + "_sha256"], hashlib.sha256(raw).hexdigest())
                        self.assertEqual(frame[kind + "_bytes"], len(raw))
        self.assertEqual(12, len(set(identifiers)))
        with self.assertRaises(FileExistsError):
            rehearsal.conformance_rehearsal(output)

    def test_cli_duplicate_scenarios_or_reused_ids_cannot_hide_missing_cases(self):
        valid, _ = self.invoke()
        with patch.object(rehearsal, "rehearse_turn", side_effect=lambda *a, **kw: copy.deepcopy(valid)):
            summary = rehearsal.conformance_rehearsal(self.root / "duplicates")
        self.assertFalse(summary["coverage_verified"])
        self.assertFalse(summary["unique_call_ids"])
        self.assertFalse(summary["all_expected_outcomes"])

        def reused_id(*args, **kwargs):
            record = copy.deepcopy(valid)
            record["scenario"] = kwargs["scenario"]
            return record

        with patch.object(rehearsal, "rehearse_turn", side_effect=reused_id), \
                patch.object(rehearsal, "expected_outcome", return_value=True):
            summary = rehearsal.conformance_rehearsal(self.root / "reused-ids")
        self.assertTrue(summary["coverage_verified"])
        self.assertFalse(summary["unique_call_ids"])
        self.assertFalse(summary["all_expected_outcomes"])


if __name__ == "__main__":
    unittest.main()
