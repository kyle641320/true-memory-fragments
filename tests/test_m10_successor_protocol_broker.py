from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bench.agent_ab.same_version_chain_v1 import m10_successor_protocol_broker as broker
from bench.agent_ab.same_version_chain_v1.m10_successor_adapter_contract import canonical
from bench.agent_ab.same_version_chain_v1.m10_successor_process_io import ProcessTransportError
from bench.agent_ab.same_version_chain_v1.m10_successor_protocol import (
    ACTION_SCHEMAS, AdapterRequest, LiveExecutionDisabled, _ProtocolFailure, _parse_action,
)
from bench.agent_ab.same_version_chain_v1.m10_successor_token_budget import TokenBudgetLedger, TokenLimits


class ProtocolBrokerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.limits = TokenLimits(10000, 4096, 14096, 300000, 50000, 144)
        self.contract = broker.fixed_protocol_contract("a" * 64, self.limits)
        self.ledger = TokenBudgetLedger(self.root / "client.jsonl", self.limits)
        self.addCleanup(self.ledger.close)
        self.request = AdapterRequest(
            ({"role": "system", "content": "Use the supplied JSON action schemas."},
             {"role": "user", "content": "Insert the hook at the current local handoff in <workspace>."}),
            copy.deepcopy(ACTION_SCHEMAS), 4096, 16000, 90.0,
        )
        self.counter = 0

    def adapter(self, scenario="ok", **kwargs):
        self.counter += 1
        return broker.OfflineProtocolBroker(
            self.contract, client_ledger=self.ledger, broker_ledger_path=self.root / "broker.jsonl",
            evidence_dir=self.root / f"run-{self.counter}", scenario=scenario, **kwargs,
        )

    def next_request(self, request, action):
        return replace(request, messages=(*request.messages,
                       {"role": "assistant", "content": action},
                       {"role": "tool", "content": canonical({"ok": True, "result": "complete tool feedback"})}))

    def drive(self, adapter, turns=5):
        request, actions = self.request, []
        for _ in range(turns):
            action = adapter.respond(request)
            actions.append(json.loads(action))
            request = self.next_request(request, action)
        return request, actions

    def test_constructor_is_transport_free_and_close_preserves_external_ledger(self):
        with patch.object(broker, "_exchange") as exchange:
            adapter = self.adapter()
            adapter.close()
            snapshot = adapter.snapshot()
        exchange.assert_not_called()
        self.assertFalse((self.root / "broker.jsonl").exists())
        self.assertTrue(snapshot["closed"])
        self.assertEqual([], snapshot["turns"])
        self.assertEqual(0, self.ledger.snapshot()["admitted_calls"])
        self.assertFalse(snapshot["joint_dispatch_guard_supplied"])

    def test_five_turn_real_workers_full_history_original_bytes_and_one_deadline_per_action(self):
        adapter = self.adapter(verify_before_dispatch=lambda: None)
        exchange, admitted_observations = broker._exchange, []

        def inspect(source, raw, **options):
            message = json.loads(raw)
            if message["op"] == "complete":
                event = json.loads((self.root / "client.jsonl").read_bytes().splitlines()[-1])
                self.assertEqual("admitted", event["event"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), event["request_sha256"])
                admitted_observations.append(message["call_id"])
            return exchange(source, raw, **options)

        with patch.object(broker, "_exchange", side_effect=inspect):
            _, actions = self.drive(adapter)
        snapshot = adapter.snapshot()
        self.assertEqual(["list", "read_range", "edit", "compile", "final"], [a["action"] for a in actions])
        self.assertEqual(5, len(admitted_observations))
        self.assertEqual(0, snapshot["model_calls"])
        self.assertEqual("fictional_fixture_not_provider", snapshot["usage_origin"])
        self.assertEqual("matching_known_usage", snapshot["accounting_reconciliation"])
        self.assertTrue(snapshot["joint_dispatch_guard_supplied"])
        self.assertEqual(30000, snapshot["client_ledger"]["charged_input_tokens"])
        self.assertEqual(160, snapshot["broker_ledger"]["charged_output_tokens"])
        self.assertEqual(snapshot["client_ledger"], snapshot["broker_ledger"])
        for number, turn in enumerate(snapshot["turns"], 1):
            directory = self.root / "run-1" / f"turn-{number:04d}"
            payload_raw = (directory / "model-payload.json").read_text()
            payload = json.loads(payload_raw)
            self.assertEqual(2 * number, len(payload["messages"]))
            self.assertIn(canonical(ACTION_SCHEMAS), payload["messages"][0]["content"])
            self.assertEqual(4096, payload["max_completion_tokens"])
            self.assertEqual(90.0, turn["declared_timeout_seconds"])
            self.assertEqual(10.0, turn["effective_timeout_seconds"])
            self.assertEqual(["capabilities", "count", "completion"], [f["phase"] for f in turn["wire_frames"]])
            self.assertEqual(3, len(turn["process_attempts"]))  # No ordinary-turn replay probe.
            self.assertEqual(1, len({a["deadline_monotonic"] for a in turn["process_attempts"]}))
            self.assertEqual(["capabilities", "count", "capabilities", "count", "complete"],
                             [e["operation"] for e in turn["backend_trace"]])
            self.assertEqual(1, len({e["deadline_monotonic"] for e in turn["backend_trace"]}))
            for event in turn["backend_trace"]:
                if event["operation"] != "capabilities":
                    self.assertEqual(payload_raw, event["payload_json"])
                    self.assertEqual(4096, event["output_cap"])
            for hidden in (turn["call_id"], str(self.root), "experiment_seal", "run-1", "scenario"):
                self.assertNotIn(hidden, payload_raw)
            original = (directory / "original-response.bin").read_bytes()
            receipt = json.loads((directory / "03-completion.receipt.bin").read_bytes())
            self.assertNotEqual(canonical(json.loads(original)).encode(), original)
            self.assertEqual(json.loads(original), receipt["response"])
            self.assertEqual(hashlib.sha256(original).hexdigest(), turn["original_response"]["sha256"])
            self.assertEqual("original_backend_field_not_added_by_broker", receipt["response"]["fixture_provenance"])
            self.assertEqual({"prompt_tokens": 6000, "completion_tokens": 32, "total_tokens": 6032},
                             receipt["response"]["usage"])

    def test_separate_adapter_runs_share_both_aggregate_budgets(self):
        first = self.adapter()
        self.drive(first, 2)
        first.close()
        second = self.adapter()
        self.assertEqual({"action": "list"}, json.loads(second.respond(self.request)))
        snapshot = second.snapshot()
        self.assertEqual(3, snapshot["client_ledger"]["admitted_calls"])
        self.assertEqual(3, snapshot["broker_ledger"]["admitted_calls"])
        self.assertEqual(18000, snapshot["broker_ledger"]["charged_input_tokens"])
        self.assertEqual(96, snapshot["client_ledger"]["charged_output_tokens"])

    def test_wrong_model_on_edit_retains_known_broker_and_unknown_client_without_retry(self):
        adapter = self.adapter("wrong_model")
        request, _ = self.drive(adapter, 2)
        with self.assertRaisesRegex(_ProtocolFailure, "broker_response_error"):
            adapter.respond(request)
        snapshot = adapter.snapshot()
        self.assertEqual("broker_known_client_unknown", snapshot["accounting_reconciliation"])
        self.assertEqual(96, snapshot["broker_ledger"]["charged_output_tokens"])
        self.assertEqual(64 + 4096, snapshot["client_ledger"]["charged_output_tokens"])
        self.assertEqual(1, snapshot["client_ledger"]["unknown_usage_calls"])
        self.assertEqual(0, snapshot["broker_ledger"]["unknown_usage_calls"])
        self.assertEqual(3, len(snapshot["turns"][-1]["process_attempts"]))
        self.assertEqual("wrong-fictional-model", json.loads(
            (self.root / "run-1" / "turn-0003" / "original-response.bin").read_bytes())["model"])
        with patch.object(broker, "_exchange") as exchange:
            with self.assertRaises(_ProtocolFailure):
                adapter.respond(request)
            following = self.adapter()
            with self.assertRaises(_ProtocolFailure):
                following.respond(self.request)
        exchange.assert_not_called()
        self.assertEqual(3, following.snapshot()["client_ledger"]["admitted_calls"])

    def test_missing_usage_on_edit_keeps_both_unknown_and_conservative(self):
        adapter = self.adapter("missing_usage")
        request, _ = self.drive(adapter, 2)
        with self.assertRaises(_ProtocolFailure):
            adapter.respond(request)
        snapshot = adapter.snapshot()
        self.assertEqual("both_unknown_conservative", snapshot["accounting_reconciliation"])
        for owner in ("client", "broker"):
            ledger = snapshot[f"{owner}_ledger"]
            self.assertTrue(ledger["halted"])
            self.assertIsNone(ledger["provider_usage"])
            self.assertEqual(1, ledger["unknown_usage_calls"])
            self.assertEqual(64 + 4096, ledger["charged_output_tokens"])

    def test_real_timeout_on_edit_retains_pending_broker_after_worker_kill(self):
        adapter = self.adapter("backend_timeout")
        request, _ = self.drive(adapter, 2)
        with self.assertRaises(TimeoutError):
            adapter.respond(request)
        snapshot = adapter.snapshot()
        last = snapshot["turns"][-1]
        self.assertEqual("timeout", last["category"])
        self.assertEqual("completion", last["phase"])
        self.assertEqual(3, len(last["process_attempts"]))
        self.assertEqual(last["call_id"], snapshot["broker_ledger"]["pending_call_id"])
        self.assertEqual("unsettled_reservation_after_reopen", snapshot["broker_ledger"]["halt_reason"])
        self.assertEqual(64 + 4096, snapshot["broker_ledger"]["charged_output_tokens"])
        self.assertEqual(1, snapshot["broker_ledger"]["unknown_usage_calls"])
        self.assertIsNone(last["original_response"])
        self.assertFalse(snapshot["provider_cancellation_confirmed"])
        self.assertEqual("complete", last["backend_trace"][-1]["operation"])

    def test_invalid_action_is_known_usage_but_rejected_by_existing_action_parser(self):
        adapter = self.adapter("invalid_action")
        request, _ = self.drive(adapter, 2)
        raw = adapter.respond(request)
        with self.assertRaises(_ProtocolFailure):
            _parse_action(raw, ACTION_SCHEMAS)
        snapshot = adapter.snapshot()
        self.assertEqual("ok", snapshot["turns"][-1]["status"])
        self.assertEqual("matching_known_usage", snapshot["accounting_reconciliation"])
        self.assertEqual(96, snapshot["client_ledger"]["provider_usage"]["output_tokens"])

    def test_guard_rejects_each_phase_before_that_worker_and_preserves_reservations(self):
        for target in range(1, 4):
            with self.subTest(phase=target), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                guarded = []

                def guard():
                    guarded.append(True)
                    if len(guarded) == target:
                        raise ValueError("joint source drift detail must not escape")

                with TokenBudgetLedger(root / "client.jsonl", self.limits) as ledger:
                    adapter = broker.OfflineProtocolBroker(
                        self.contract, client_ledger=ledger, broker_ledger_path=root / "broker.jsonl",
                        evidence_dir=root / "run", verify_before_dispatch=guard,
                    )
                    with self.assertRaisesRegex(_ProtocolFailure, "broker_contract_error") as raised:
                        adapter.respond(self.request)
                    self.assertIsNone(raised.exception.__context__)
                    snapshot = adapter.snapshot()
                turn = snapshot["turns"][0]
                self.assertEqual(target - 1, len(turn["process_attempts"]))
                self.assertEqual("not_dispatched", turn["wire_frames"][-1]["status"])
                self.assertEqual(target == 3, turn["candidate_call_admitted"])
                self.assertFalse(turn["broker_call_admitted"])
                self.assertEqual(4096 if target == 3 else 0, snapshot["client_ledger"]["charged_output_tokens"])

    def test_contract_bound_material_drift_blocks_next_dispatch(self):
        adapter = self.adapter()
        original, invocations = broker.inventory, []

        def changed():
            result = original()
            invocations.append(True)
            result[broker.MATERIALS[0]] = "0" * 64
            return result

        with patch.object(broker, "inventory", side_effect=changed), patch.object(broker, "_exchange") as exchange:
            with self.assertRaisesRegex(_ProtocolFailure, "broker_contract_error"):
                adapter.respond(self.request)
        exchange.assert_not_called()
        self.assertTrue(invocations)
        self.assertEqual(0, adapter.snapshot()["client_ledger"]["admitted_calls"])

    def test_late_actual_completion_keeps_broker_known_client_unknown_and_raw_receipt(self):
        adapter = self.adapter()
        exchange, clock = broker._exchange, {"expired": None}

        def late(source, raw, **kwargs):
            response = exchange(source, raw, **kwargs)
            if json.loads(raw)["op"] == "complete":
                # Healthy real startup uses the full fixed budget. Only AFTER
                # a settled reply returns do we inject deadline expiry.
                clock["expired"] = kwargs["deadline_monotonic"] + 1.0
            return response

        fake_time = SimpleNamespace(monotonic=lambda: clock["expired"] or time.monotonic())
        with patch.object(broker, "_exchange", side_effect=late), patch.object(broker, "time", fake_time):
            with self.assertRaises(TimeoutError):
                adapter.respond(self.request)
        snapshot = adapter.snapshot()
        self.assertEqual("broker_known_client_unknown", snapshot["accounting_reconciliation"])
        self.assertEqual(32, snapshot["broker_ledger"]["charged_output_tokens"])
        self.assertEqual(4096, snapshot["client_ledger"]["charged_output_tokens"])
        self.assertIsNone(snapshot["turns"][0]["completion"])
        self.assertIsNotNone(snapshot["turns"][0]["wire_frames"][-1]["receipt_sha256"])

    def test_wire_frame_cap_is_separate_from_the_model_payload_cap(self):
        request = replace(self.request, messages=(self.request.messages[0], {"role": "user", "content": "x" * 65000}))
        adapter = self.adapter()
        adapter.respond(request)
        turn = adapter.snapshot()["turns"][0]
        self.assertLess(turn["payload_bytes"], self.contract.max_request_bytes)
        self.assertGreater(turn["wire_frames"][-1]["request_bytes"], self.contract.max_request_bytes)
        self.assertLess(turn["wire_frames"][-1]["request_bytes"], broker.PROCESS_CAPS.max_request_bytes)
        oversized = replace(self.request, messages=(self.request.messages[0], {"role": "user", "content": "x" * 120000}))
        other = self.adapter()
        with patch.object(broker, "_exchange") as exchange, self.assertRaises(_ProtocolFailure):
            other.respond(oversized)
        exchange.assert_not_called()
        self.assertEqual(1, other.snapshot()["client_ledger"]["admitted_calls"])

    def test_fixed_worker_checks_source_bytes_before_import_or_ledger_creation(self):
        materials = broker.inventory()
        materials[broker.MATERIALS[0]] = "0" * 64
        deadline = time.monotonic() + self.contract.timeout_seconds
        source = broker._worker_source(
            self.contract, materials=materials, broker_ledger_path=self.root / "broker.jsonl",
            trace_path=self.root / "trace.jsonl", scenario="ok", deadline_monotonic=deadline,
        )
        with self.assertRaises(ProcessTransportError) as raised:
            broker._exchange(source, b"{}", caps=broker.PROCESS_CAPS,
                             timeout_seconds=self.contract.timeout_seconds, deadline_monotonic=deadline)
        self.assertEqual("process_exit", raised.exception.category)
        self.assertFalse((self.root / "broker.jsonl").exists())
        self.assertFalse((self.root / "trace.jsonl").exists())

    def test_nonfixed_identities_and_scenario_overrides_are_rejected_without_transport(self):
        changes = ({"provider_id": "other"}, {"request_model": "other"}, {"response_model": "other"},
                   {"endpoint": "https://example.invalid/v1/chat/completions"},
                   {"broker_runtime_sha256": "0" * 64}, {"timeout_seconds": 1})
        with patch.object(broker, "_exchange") as exchange:
            for change in changes:
                with self.subTest(change=change), self.assertRaises(LiveExecutionDisabled):
                    broker.OfflineProtocolBroker(
                        replace(self.contract, **change), client_ledger=self.ledger,
                        broker_ledger_path=self.root / "broker.jsonl", evidence_dir=self.root / "rejected",
                    )
            with self.assertRaises(ValueError):
                self.adapter("unregistered-backend")
        exchange.assert_not_called()

    def test_aggregate_call_limit_cannot_be_reset_by_another_adapter(self):
        limits = replace(self.limits, max_calls=1)
        contract = broker.fixed_protocol_contract("b" * 64, limits)
        with TokenBudgetLedger(self.root / "limited-client.jsonl", limits) as ledger:
            arguments = {"client_ledger": ledger, "broker_ledger_path": self.root / "limited-broker.jsonl"}
            first = broker.OfflineProtocolBroker(contract, evidence_dir=self.root / "limited-first", **arguments)
            first.respond(self.request)
            first.close()
            second = broker.OfflineProtocolBroker(contract, evidence_dir=self.root / "limited-second", **arguments)
            with self.assertRaisesRegex(_ProtocolFailure, "broker_budget_exceeded"):
                second.respond(self.request)
            snapshot = second.snapshot()
        self.assertEqual(1, snapshot["client_ledger"]["admitted_calls"])
        self.assertEqual(1, snapshot["broker_ledger"]["admitted_calls"])
        self.assertEqual("admission", snapshot["turns"][0]["phase"])
        self.assertEqual("budget_exceeded", snapshot["turns"][0]["category"])
        self.assertFalse(any(e["operation"] == "complete" for e in snapshot["turns"][0]["backend_trace"]))

    def test_corrupted_shared_journal_blocks_next_adapter_without_worker(self):
        first = self.adapter()
        first.respond(self.request)
        with (self.root / "broker.jsonl").open("ab") as stream:
            stream.write(b"{truncated")
        following = self.adapter()
        with patch.object(broker, "_exchange") as exchange, self.assertRaises(_ProtocolFailure):
            following.respond(self.request)
        exchange.assert_not_called()
        snapshot = following.snapshot()
        self.assertEqual("unverified", snapshot["broker_ledger_state"])
        self.assertEqual("unverified_ledger_state", snapshot["accounting_reconciliation"])
        self.assertEqual("ledger_error", snapshot["turns"][0]["category"])

    def test_changed_shared_limits_are_rejected_before_any_dispatch(self):
        adapter = self.adapter()
        original = self.ledger.limits.total_input
        object.__setattr__(self.ledger.limits, "total_input", original + 1)
        try:
            with patch.object(broker, "_exchange") as exchange, self.assertRaisesRegex(
                    _ProtocolFailure, "broker_ledger_error"):
                adapter.respond(self.request)
            exchange.assert_not_called()
            self.assertEqual(0, adapter.snapshot()["client_ledger"]["admitted_calls"])
        finally:
            object.__setattr__(self.ledger.limits, "total_input", original)


if __name__ == "__main__":
    unittest.main()
