from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

from bench.agent_ab.same_version_chain_v1 import m10_successor_adapter_contract as codec
from bench.agent_ab.same_version_chain_v1 import m10_successor_broker_core as broker
from bench.agent_ab.same_version_chain_v1.m10_successor_protocol import (
    ACTION_SCHEMAS, AdapterRequest, LiveExecutionDisabled,
)
from bench.agent_ab.same_version_chain_v1.m10_successor_token_budget import (
    TokenBudgetLedger, TokenLedgerError, TokenLimits,
)


def encoded(value) -> bytes:
    return codec.canonical(value).encode("utf-8")


def fixture_contract() -> codec.BrokerContract:
    """Every pin/count below is fictional; this is not provider evidence."""
    return codec.BrokerContract(
        experiment_seal_sha256="1" * 64, provider_id="fictional-broker-test",
        endpoint="https://fictional.invalid/v1/chat/completions",
        request_model="fictional-request", response_model="fictional-response-v1",
        deployment_revision="fictional-revision", broker_build_sha256="2" * 64,
        broker_runtime_sha256="3" * 64, tokenizer_id="fictional-count-v1",
        tokenizer_sha256="4" * 64,
        inference_json=codec.canonical({"temperature": 0, "top_p": 1,
                                        "seed": 7, "reasoning_effort": "low"}),
        limits=TokenLimits(10000, 4096, 14096, 30000, 12288, 3),
        max_request_bytes=120000, max_response_bytes=64000, timeout_seconds=90,
    )


def fixture_request() -> AdapterRequest:
    return AdapterRequest(
        messages=({"role": "system", "content": "Use the action protocol."},
                  {"role": "user", "content": "Read the fixture source."},
                  {"role": "assistant", "content": '{"action":"list"}'},
                  {"role": "tool", "content": 'Fixture.java\n"quoted" 中文'}),
        action_schemas=copy.deepcopy(ACTION_SCHEMAS), max_output_tokens=4096,
        max_output_bytes=16000, timeout_seconds=80,
    )


def fictional_count(payload_json: str) -> int:
    # Intentionally NOT a tokenizer or a provider token estimate. A varying
    # fixture number ensures the core really binds/recounts the full payload.
    return 100 + len(payload_json.encode("utf-8")) // 17


class FictionalBackend:
    """An in-memory fake of upstream bytes, never network/model execution."""

    def __init__(self, contract):
        self.contract = contract
        self.calls = []
        self.hooks = {}
        self.mutate_capabilities = lambda value: None
        self.mutate_count = lambda value: None
        self.mutate_response = lambda value: None
        self.raw_response = None
        self.return_nonbytes = False
        self.last_response = None

    def record(self, phase, arguments):
        self.calls.append((phase, arguments))
        if phase in self.hooks:
            self.hooks[phase]()

    def capabilities(self, *, contract_sha256, deadline_monotonic):
        self.record("capabilities", dict(contract_sha256=contract_sha256,
                                        deadline_monotonic=deadline_monotonic))
        value = {
            "protocol": codec.PROTOCOL, "op": "capabilities", "contract_sha256": contract_sha256,
            "identity": self.contract.identity(),
            "tokenizer": {"id": self.contract.tokenizer_id, "sha256": self.contract.tokenizer_sha256},
            "semantics": {"stateless": True, "native_tools": False, "network_owner": "broker",
                          "credential_owner": "broker", "max_attempts": 1, "fallback": False,
                          "truncation": False, "input_count": "exact_full_payload",
                          "output_parameter": "max_completion_tokens",
                          "usage": "all_provider_tokens_including_reasoning"},
        }
        self.mutate_capabilities(value)
        return encoded(value)

    def count(self, *, payload_json, payload_sha256, contract_sha256, deadline_monotonic):
        self.record("count", dict(payload_json=payload_json, payload_sha256=payload_sha256,
                                  contract_sha256=contract_sha256, deadline_monotonic=deadline_monotonic))
        value = {"protocol": codec.PROTOCOL, "op": "count", "contract_sha256": contract_sha256,
                 "payload_sha256": payload_sha256, "tokenizer_id": self.contract.tokenizer_id,
                 "tokenizer_sha256": self.contract.tokenizer_sha256,
                 "input_tokens": fictional_count(payload_json), "exact": True, "generation_calls": 0}
        self.mutate_count(value)
        return encoded(value)

    def complete(self, *, payload_json, deadline_monotonic, max_response_bytes):
        self.record("complete", dict(payload_json=payload_json, deadline_monotonic=deadline_monotonic,
                                     max_response_bytes=max_response_bytes))
        if self.return_nonbytes:
            return "not bytes"
        if self.raw_response is not None:
            return self.raw_response
        tokens = fictional_count(payload_json)
        value = {"id": "fictional-original-id", "object": "chat.completion",
                 "model": self.contract.response_model, "system_fingerprint": "original-fixture-field",
                 "choices": [{"index": 0, "finish_reason": "stop", "message": {
                     "role": "assistant", "content": '{"action":"list","label":"中文"}'}}],
                 "usage": {"prompt_tokens": tokens, "completion_tokens": 13, "total_tokens": tokens + 13,
                           "prompt_tokens_details": {"cached_tokens": 5, "fixture_extra": 2},
                           "completion_tokens_details": {"reasoning_tokens": 7, "fixture_extra": 3}}}
        self.mutate_response(value)
        self.last_response = copy.deepcopy(value)
        return encoded(value)


class BrokerCoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.number = 0
        self.contract = fixture_contract()
        self.request = fixture_request()
        self.prepared = codec.prepare_turn(self.contract, self.request)

    def ledger(self, *, limits=None, path=None):
        self.number += 1
        path = path or Path(self.temp.name) / f"ledger-{self.number}.jsonl"
        value = TokenBudgetLedger(path, limits or self.contract.limits)
        self.addCleanup(value.close)
        return value, path

    def server(self, *, contract=None, ledger=None, frame_cap=1000000):
        contract = contract or self.contract
        if ledger is None:
            ledger, _ = self.ledger(limits=contract.limits)
        backend = FictionalBackend(contract)
        core = broker.BrokerCore(contract, ledger, backend, max_request_frame_bytes=frame_cap)
        return core, backend, ledger

    def message(self, *, prepared=None, call_id="a" * 32, contract=None):
        prepared = prepared or self.prepared
        contract = contract or self.contract
        return {"protocol": codec.PROTOCOL, "op": "complete", "call_id": call_id,
                "identity": contract.identity(), "prepared": prepared.binding(),
                "input_tokens": fictional_count(prepared.payload_json),
                "tokenizer_sha256": contract.tokenizer_sha256, "max_attempts": 1, "fallback": False}

    def count_request(self, *, prepared=None):
        prepared = prepared or self.prepared
        return {"protocol": codec.PROTOCOL, "op": "count", "contract_sha256": prepared.contract_sha256,
                "payload_json": prepared.payload_json, "payload_sha256": prepared.payload_sha256}

    def capabilities_request(self):
        return {"protocol": codec.PROTOCOL, "op": "capabilities",
                "contract_sha256": self.prepared.contract_sha256}

    def handle(self, core, value, *, deadline=None):
        return core.handle(value if type(value) is bytes else encoded(value),
                           deadline_monotonic=deadline if deadline is not None else broker.time.monotonic() + 60)

    def assert_error(self, core, value, category, *, deadline=None):
        with self.assertRaises(broker.BrokerError) as caught:
            self.handle(core, value, deadline=deadline)
        error = caught.exception
        self.assertEqual(category, error.category)
        self.assertEqual(category, str(error))
        self.assertIsNone(error.__context__)
        self.assertIsNone(error.__cause__)

    def assert_unknown(self, ledger):
        snapshot = ledger.snapshot()
        self.assertTrue(snapshot["halted"])
        self.assertTrue(snapshot["journal_integrity_verified"])
        self.assertEqual(1, snapshot["admitted_calls"])
        self.assertEqual(1, snapshot["unknown_usage_calls"])
        self.assertIsNone(snapshot["provider_usage"])
        self.assertEqual(4096, snapshot["charged_output_tokens"])
        self.assertTrue(snapshot["records"][0]["itt_included"])

    def test_full_raw_client_broker_roundtrip_recounts_and_preserves_original(self):
        core, backend, server_ledger = self.server()
        client_ledger, _ = self.ledger()
        with patch("socket.socket", side_effect=AssertionError("no network")), \
             patch("subprocess.Popen", side_effect=AssertionError("no process")):
            capabilities = self.handle(core, self.capabilities_request())
            count = self.handle(core, self.count_request())
            admitted = codec.admit_turn(self.contract, self.prepared, capabilities=capabilities,
                                       count_receipt=count, ledger=client_ledger, call_id="a" * 32)
            reply = core.handle(admitted.completion_request_json.encode("utf-8"),
                                deadline_monotonic=broker.time.monotonic() + 60)
            result = codec.accept_completion(self.contract, admitted, reply, ledger=client_ledger)
        self.assertTrue(result.usable_action_text)
        self.assertEqual(backend.last_response, json.loads(reply)["response"])
        self.assertEqual(['capabilities', 'count', 'capabilities', 'count', 'complete'],
                         [name for name, _ in backend.calls])
        for phase, arguments in backend.calls:
            if phase in {"count", "complete"}:
                self.assertEqual(self.prepared.payload_json, arguments["payload_json"])
                self.assertNotIn("call_id", json.loads(arguments["payload_json"]))
        self.assertEqual(server_ledger.snapshot(), client_ledger.snapshot())
        self.assertEqual(13, server_ledger.snapshot()["charged_output_tokens"])

    def test_independent_frame_budget_does_not_shrink_model_payload_allowance(self):
        payload_size = len(self.prepared.payload_json.encode("utf-8"))
        contract = replace(self.contract, max_request_bytes=payload_size + 1)
        prepared = codec.prepare_turn(contract, self.request)
        message = self.message(contract=contract, prepared=prepared)
        frame = encoded(message)
        self.assertGreater(len(frame), contract.max_request_bytes)
        core, backend, ledger = self.server(contract=contract, frame_cap=len(frame))
        self.handle(core, frame)
        self.assertEqual("completed", ledger.snapshot()["records"][0]["status"])
        core, backend, ledger = self.server(contract=contract, frame_cap=len(frame) - 1)
        self.assert_error(core, frame, "request_error")
        self.assertEqual([], backend.calls)

    def test_exact_request_shapes_strict_json_and_frame_caps_reject_before_backend(self):
        values = [b'{', b'[]', b'{} {}', b'{"op":"count","op":"count"}',
                  b'{"x":NaN}', b'\xff', b'{"x":"\\ud800"}',
                  b'{"x":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}',
                  b'x' * 1000001]
        for mutation in (lambda m: m.update(protocol="v1"), lambda m: m.update(op="execute"),
                         lambda m: m.update(contract={}), lambda m: m.update(identity={}),
                         lambda m: m.update(contract_sha256="0" * 64)):
            value = self.capabilities_request()
            mutation(value)
            values.append(encoded(value))
        values.append(json.dumps(self.capabilities_request(), indent=2).encode())
        for raw in values:
            with self.subTest(raw=raw[:80]):
                core, backend, ledger = self.server()
                self.assert_error(core, raw, "request_error")
                self.assertEqual([], backend.calls)
                self.assertEqual(0, ledger.snapshot()["admitted_calls"])
        core, backend, _ = self.server()
        with self.assertRaises(broker.BrokerError):
            core.handle("not bytes", deadline_monotonic=broker.time.monotonic() + 60)

    def test_complete_identity_control_fields_and_call_ids_cannot_override_server(self):
        mutations = [lambda m: m["identity"].update(endpoint="https://other.invalid/v1/chat/completions"),
                     lambda m: m["identity"].update(response_model="other"),
                     lambda m: m.update(identity=True), lambda m: m.update(max_attempts=2),
                     lambda m: m.update(max_attempts=True), lambda m: m.update(fallback=0),
                     lambda m: m.update(fallback=True), lambda m: m.update(tokenizer_sha256="f" * 64),
                     lambda m: m.update(input_tokens=True), lambda m: m.update(input_tokens=0),
                     lambda m: m.update(call_id="A" * 32), lambda m: m.update(call_id="a" * 31),
                     lambda m: m.update(call_id="named-id"), lambda m: m.update(extra="SECRET")]
        for mutation in mutations:
            core, backend, ledger = self.server()
            message = self.message()
            mutation(message)
            with self.subTest(mutation=mutation):
                self.assert_error(core, message, "request_error")
                self.assertEqual([], backend.calls)
                self.assertEqual(0, ledger.snapshot()["admitted_calls"])

    def test_resigned_deep_payload_tampering_fails_source_rerender(self):
        mutations = [lambda b: b.update(model="other"), lambda b: b.update(n=True),
                     lambda b: b.update(max_completion_tokens=512), lambda b: b.update(stream=True),
                     lambda b: b.update(store=True), lambda b: b.update(temperature=1),
                     lambda b: b.update(tools=[]), lambda b: b.update(metadata={"private": "SECRET"}),
                     lambda b: b["messages"][0].update(content="replace schemas"),
                     lambda b: b["messages"][3].update(content="unquoted tool result")]
        for mutation in mutations:
            body = json.loads(self.prepared.payload_json)
            mutation(body)
            payload = codec.canonical(body)
            prepared = replace(self.prepared, payload_json=payload, payload_sha256=codec.digest(payload))
            core, backend, ledger = self.server()
            with self.subTest(mutation=mutation):
                self.assert_error(core, self.message(prepared=prepared), "request_error")
                self.assertEqual([], backend.calls)
        for field, value in (("max_output_tokens", 4097), ("max_output_bytes", 64001),
                             ("timeout_seconds", 91), ("contract_sha256", "0" * 64),
                             ("source_request_json", '{"messages":[],"messages":[]}')):
            core, backend, _ = self.server()
            message = self.message()
            message["prepared"][field] = value
            self.assert_error(core, message, "request_error")
            self.assertEqual([], backend.calls)

    def test_count_payload_pins_parameters_roles_caps_and_no_native_tools(self):
        mutations = [lambda b: b.update(model="wrong"), lambda b: b.update(n=True),
                     lambda b: b.update(store=0), lambda b: b.update(stream=True),
                     lambda b: b.update(temperature=None), lambda b: b.update(seed=9),
                     lambda b: b.update(max_completion_tokens=4097),
                     lambda b: b.update(max_completion_tokens=True), lambda b: b.update(max_completion_tokens=0),
                     lambda b: b.update(max_tokens=10), lambda b: b.update(tools=[]),
                     lambda b: b.update(tool_choice="auto"), lambda b: b.update(messages=[]),
                     lambda b: b["messages"][1].update(role="tool"),
                     lambda b: b["messages"][1].update(content={}),
                     lambda b: b["messages"][1].update(tool_call_id="x")]
        for mutation in mutations:
            request = self.count_request()
            body = json.loads(request["payload_json"])
            mutation(body)
            request["payload_json"] = codec.canonical(body)
            request["payload_sha256"] = codec.digest(request["payload_json"])
            core, backend, _ = self.server()
            with self.subTest(mutation=mutation):
                self.assert_error(core, request, "request_error")
                self.assertEqual([], backend.calls)
        for payload, digest in ((self.prepared.payload_json, "0" * 64),
                                (" " + self.prepared.payload_json, None),
                                ("x" * 120001, None)):
            request = self.count_request()
            request.update(payload_json=payload, payload_sha256=digest or codec.digest(payload))
            core, backend, _ = self.server()
            self.assert_error(core, request, "request_error")
            self.assertEqual([], backend.calls)

    def test_original_capability_receipt_not_synthesized_and_drift_rejected(self):
        for mutation in (lambda c: c.update(protocol="v1"),
                         lambda c: c["identity"].update(provider_id="changed"),
                         lambda c: c["semantics"].update(max_attempts=True),
                         lambda c: c["semantics"].update(native_tools=True),
                         lambda c: c.update(extra="SECRET")):
            core, backend, ledger = self.server()
            backend.mutate_capabilities = mutation
            self.assert_error(core, self.message(), "capability_error")
            self.assertEqual(["capabilities"], [name for name, _ in backend.calls])
            self.assertEqual(0, ledger.snapshot()["admitted_calls"])
        core, backend, _ = self.server()
        original = backend.capabilities(contract_sha256=self.prepared.contract_sha256,
                                        deadline_monotonic=0)
        backend.capabilities = lambda **kwargs: b" \n" + original + b" \n"
        self.assertEqual(b" \n" + original + b" \n", self.handle(core, self.capabilities_request()))

    def test_fresh_exact_count_receipt_required_and_client_count_never_trusted(self):
        mutations = [("protocol", "v1"), ("op", "complete"), ("contract_sha256", "0" * 64),
                     ("payload_sha256", "0" * 64), ("tokenizer_id", "changed"),
                     ("tokenizer_sha256", "f" * 64), ("exact", False), ("exact", 1),
                     ("generation_calls", 1), ("generation_calls", False),
                     ("input_tokens", True), ("input_tokens", 0), ("extra", "SECRET")]
        for field, value in mutations:
            core, backend, ledger = self.server()
            backend.mutate_count = lambda c, f=field, v=value: c.update({f: v})
            self.assert_error(core, self.message(), "count_error")
            self.assertEqual(["capabilities", "count"], [name for name, _ in backend.calls])
            self.assertEqual(0, ledger.snapshot()["admitted_calls"])
        core, backend, ledger = self.server()
        message = self.message()
        message["input_tokens"] += 1
        self.assert_error(core, message, "count_error")
        self.assertEqual(0, ledger.snapshot()["admitted_calls"])

    def test_input_context_and_aggregate_limits_stop_before_generation(self):
        tokens = fictional_count(self.prepared.payload_json)
        contracts = [replace(self.contract, limits=replace(self.contract.limits, input_per_turn=tokens - 1)),
                     replace(self.contract, limits=replace(self.contract.limits, context_window=tokens + 4095)),
                     replace(self.contract, limits=replace(self.contract.limits, total_input=tokens - 1)),
                     replace(self.contract, limits=replace(self.contract.limits, total_output=4095))]
        for contract in contracts:
            prepared = codec.prepare_turn(contract, self.request)
            core, backend, ledger = self.server(contract=contract)
            self.assert_error(core, self.message(contract=contract, prepared=prepared), "budget_exceeded")
            self.assertNotIn("complete", [name for name, _ in backend.calls])
            self.assertEqual(0, ledger.snapshot()["admitted_calls"])
        contract = replace(self.contract, limits=replace(self.contract.limits, max_calls=1))
        prepared = codec.prepare_turn(contract, self.request)
        core, backend, ledger = self.server(contract=contract)
        self.handle(core, self.message(contract=contract, prepared=prepared))
        self.assert_error(core, self.message(contract=contract, prepared=prepared, call_id="b" * 32),
                          "budget_exceeded")
        self.assertEqual(1, [name for name, _ in backend.calls].count("complete"))

    def test_admission_is_fsynced_before_exactly_one_complete_dispatch(self):
        ledger, path = self.ledger()
        core, backend, _ = self.server(ledger=ledger)
        with patch("os.fsync", wraps=os.fsync) as fsync:
            def at_dispatch():
                events = [json.loads(line) for line in path.read_bytes().splitlines()]
                self.assertEqual(["limits", "admitted"], [e["event"] for e in events])
                self.assertEqual("a" * 32, ledger.snapshot()["pending_call_id"])
                self.assertGreaterEqual(fsync.call_count, 1)
            backend.hooks["complete"] = at_dispatch
            self.handle(core, self.message())
        self.assertEqual(["capabilities", "count", "complete"], [name for name, _ in backend.calls])

    def test_admission_fsync_failure_preserves_pending_charge_and_never_dispatches(self):
        core, backend, ledger = self.server()
        with patch("os.fsync", side_effect=OSError("SECRET raw filesystem error")):
            self.assert_error(core, self.message(), "ledger_error")
        self.assertEqual(["capabilities", "count"], [name for name, _ in backend.calls])
        snapshot = ledger.snapshot()
        self.assertTrue(snapshot["halted"])
        self.assertFalse(snapshot["journal_integrity_verified"])
        self.assertEqual(4096, snapshot["charged_output_tokens"])
        self.assertEqual(1, snapshot["admitted_calls"])

    def test_backend_exceptions_sanitized_without_retry_or_free_admission(self):
        for phase in ("capabilities", "count", "complete"):
            for error, category in ((RuntimeError("SECRET upstream error"), "backend_error"),
                                    (TimeoutError("SECRET upstream timeout"), "timeout")):
                core, backend, ledger = self.server()
                def fail(error=error):
                    raise error
                backend.hooks[phase] = fail
                self.assert_error(core, self.message(), category)
                self.assertEqual(1, [name for name, _ in backend.calls].count(phase))
                if phase == "complete":
                    self.assert_unknown(ledger)
                    prior_calls = list(backend.calls)
                    self.assert_error(core, self.message(call_id="b" * 32), "ledger_error")
                    self.assertEqual(prior_calls, backend.calls)
                else:
                    self.assertEqual(0, ledger.snapshot()["admitted_calls"])

    def test_one_inherited_absolute_deadline_and_late_count_never_reserves(self):
        now = [100.0]
        core, backend, ledger = self.server()
        backend.hooks = {"capabilities": lambda: now.__setitem__(0, 110.0),
                         "count": lambda: now.__setitem__(0, 120.0),
                         "complete": lambda: now.__setitem__(0, 130.0)}
        with patch.object(broker.time, "monotonic", side_effect=lambda: now[0]):
            self.handle(core, self.message(), deadline=150.0)
        self.assertEqual([150.0] * 3, [arguments["deadline_monotonic"] for _, arguments in backend.calls])
        core, backend, ledger = self.server()
        now[0] = 100.0
        backend.hooks["count"] = lambda: now.__setitem__(0, 151.0)
        with patch.object(broker.time, "monotonic", side_effect=lambda: now[0]):
            self.assert_error(core, self.message(), "timeout", deadline=150.0)
        self.assertEqual(0, ledger.snapshot()["admitted_calls"])
        self.assertEqual(["capabilities", "count"], [name for name, _ in backend.calls])

    def test_late_returned_response_keeps_known_usage_but_suppresses_output(self):
        now = [100.0]
        core, backend, ledger = self.server()
        backend.hooks["complete"] = lambda: now.__setitem__(0, 151.0)
        with patch.object(broker.time, "monotonic", side_effect=lambda: now[0]):
            self.assert_error(core, self.message(), "timeout", deadline=150.0)
        snapshot = ledger.snapshot()
        self.assertEqual("failed", snapshot["records"][0]["status"])
        self.assertEqual(13, snapshot["charged_output_tokens"])
        self.assertTrue(snapshot["halted"])

    def test_invalid_deadlines_and_expired_deadline_do_not_reach_backend(self):
        for deadline, category in ((True, "request_error"), (float("nan"), "request_error"),
                                   (float("inf"), "request_error"), (10 ** 1000, "request_error"),
                                   (0.0, "timeout")):
            core, backend, _ = self.server()
            self.assert_error(core, self.message(), category, deadline=deadline)
            self.assertEqual([], backend.calls)

    def test_replay_completed_id_rejected_before_any_backend_call_even_after_reopen(self):
        ledger, path = self.ledger()
        core, backend, _ = self.server(ledger=ledger)
        self.handle(core, self.message())
        previous = list(backend.calls)
        self.assert_error(core, self.message(), "duplicate_call")
        self.assertEqual(previous, backend.calls)
        ledger.close()
        reopened, _ = self.ledger(path=path)
        core, backend, _ = self.server(ledger=reopened)
        self.assert_error(core, self.message(), "duplicate_call")
        self.assertEqual([], backend.calls)
        self.handle(core, self.message(call_id="b" * 32))
        self.assertEqual(2, reopened.snapshot()["admitted_calls"])

    def test_pending_crash_and_reopened_uncertain_ledgers_reject_all_backend_work(self):
        ledger, path = self.ledger()
        ledger.reserve("a" * 32, request_sha256="f" * 64,
                       input_tokens=fictional_count(self.prepared.payload_json), max_output_tokens=4096)
        core, backend, _ = self.server(ledger=ledger)
        for message in (self.capabilities_request(), self.count_request(), self.message()):
            self.assert_error(core, message, "ledger_error")
        self.assertEqual([], backend.calls)
        ledger.close()
        reopened, _ = self.ledger(path=path)
        core, backend, _ = self.server(ledger=reopened)
        self.assert_error(core, self.message(), "ledger_error")
        self.assertEqual([], backend.calls)
        self.assert_unknown(reopened)
        self.assertEqual("unsettled_reservation_after_reopen", reopened.snapshot()["halt_reason"])

    def test_unknown_settlement_persists_and_reopen_cannot_retry(self):
        ledger, path = self.ledger()
        core, backend, _ = self.server(ledger=ledger)
        backend.raw_response = b'{'
        self.assert_error(core, self.message(), "response_error")
        ledger.close()
        reopened, _ = self.ledger(path=path)
        core, backend, _ = self.server(ledger=reopened)
        self.assert_error(core, self.message(call_id="b" * 32), "ledger_error")
        self.assertEqual([], backend.calls)
        self.assert_unknown(reopened)

    def test_limits_drift_and_reopen_limits_mismatch_fail_closed(self):
        ledger, path = self.ledger()
        different = replace(self.contract, limits=replace(self.contract.limits, max_calls=4))
        with self.assertRaises(broker.BrokerError) as caught:
            self.server(contract=different, ledger=ledger)
        self.assertEqual("ledger_error", caught.exception.category)
        ledger.close()
        with self.assertRaises(TokenLedgerError):
            TokenBudgetLedger(path, different.limits)

    def test_corruption_before_request_and_between_callbacks_prevents_dispatch(self):
        for when in ("before", "capabilities", "count"):
            ledger, path = self.ledger()
            core, backend, _ = self.server(ledger=ledger)
            def corrupt():
                with path.open("ab") as stream:
                    stream.write(b"SECRET corruption")
            if when == "before":
                corrupt()
            else:
                backend.hooks[when] = corrupt
            self.assert_error(core, self.message(), "ledger_error")
            self.assertNotIn("complete", [name for name, _ in backend.calls])
            self.assertFalse(ledger.snapshot()["journal_integrity_verified"])

    def test_final_integrity_failure_suppresses_already_settled_success(self):
        ledger, path = self.ledger()
        core, backend, _ = self.server(ledger=ledger)
        settle = ledger.settle
        def corrupt_after_settle(*args, **kwargs):
            record = settle(*args, **kwargs)
            with path.open("ab") as stream:
                stream.write(b"corruption after durable completion")
            return record
        with patch.object(ledger, "settle", side_effect=corrupt_after_settle):
            self.assert_error(core, self.message(), "ledger_error")
        snapshot = ledger.snapshot()
        self.assertFalse(snapshot["journal_integrity_verified"])
        self.assertEqual(13, snapshot["provider_usage"]["output_tokens"])
        self.assertEqual("completed", snapshot["records"][0]["status"])

    def test_invalid_raw_responses_preserve_full_unknown_reservation(self):
        values = [b'{', b'[]', b'{} {}', b'\xff', b'{"x":NaN}',
                  b'{"model":"a","model":"b"}', b'x' * 64001]
        for raw in values:
            core, backend, ledger = self.server()
            backend.raw_response = raw
            self.assert_error(core, self.message(), "response_error")
            self.assert_unknown(ledger)
        core, backend, ledger = self.server()
        backend.return_nonbytes = True
        self.assert_error(core, self.message(), "response_error")
        self.assert_unknown(ledger)

    def test_bad_model_object_id_and_error_envelope_retain_known_usage_without_repair(self):
        mutations = [lambda r: r.update(model="wrong-original-model"),
                     lambda r: r.pop("model"), lambda r: r.update(object="wrong-object"),
                     lambda r: r.update(id=""), lambda r: r.update(id=True),
                     lambda r: r.update(error={"message": "SECRET upstream error"})]
        for mutation in mutations:
            core, backend, ledger = self.server()
            backend.mutate_response = mutation
            self.assert_error(core, self.message(), "response_error")
            snapshot = ledger.snapshot()
            self.assertTrue(snapshot["halted"])
            self.assertEqual(13, snapshot["provider_usage"]["output_tokens"])
            self.assertEqual("failed", snapshot["records"][0]["status"])

    def test_missing_or_malformed_usage_is_unknown_never_inferred_from_cap(self):
        mutations = [lambda r: r.pop("usage"), lambda r: r.update(usage=None),
                     lambda r: r["usage"].update(prompt_tokens=True),
                     lambda r: r["usage"].update(completion_tokens=-1),
                     lambda r: r["usage"].update(total_tokens=1),
                     lambda r: r["usage"].update(completion_tokens_details=[]),
                     lambda r: r["usage"]["completion_tokens_details"].update(reasoning_tokens=14),
                     lambda r: r["usage"]["prompt_tokens_details"].update(cached_tokens=99999)]
        for mutation in mutations:
            core, backend, ledger = self.server()
            backend.mutate_response = mutation
            self.assert_error(core, self.message(), "response_error")
            self.assert_unknown(ledger)

    def test_observed_input_or_output_overcount_records_known_conservative_mismatch(self):
        tokens = fictional_count(self.prepared.payload_json)
        for prompt, output in ((tokens - 1, 13), (tokens + 1, 13), (tokens, 4097)):
            core, backend, ledger = self.server()
            backend.mutate_response = lambda r, p=prompt, o=output: r.update(
                usage={"prompt_tokens": p, "completion_tokens": o, "total_tokens": p + o})
            self.assert_error(core, self.message(), "response_error")
            snapshot = ledger.snapshot()
            self.assertTrue(snapshot["halted"])
            self.assertEqual("usage_mismatch", snapshot["records"][0]["status"])
            self.assertEqual(prompt, snapshot["provider_usage"]["input_tokens"])
            self.assertEqual(max(4096, output), snapshot["charged_output_tokens"])

    def test_refusal_length_and_invalid_content_return_known_terminal_receipts_not_actions(self):
        mutations = [lambda r: r["choices"][0].update(finish_reason="length"),
                     lambda r: r["choices"][0].update(finish_reason="content_filter"),
                     lambda r: r["choices"][0]["message"].update(refusal="fixture refusal"),
                     lambda r: r["choices"][0]["message"].update(content="x" * 16001),
                     lambda r: r["choices"][0]["message"].update(content=None),
                     lambda r: r["choices"][0]["message"].update(tool_calls=[]),
                     lambda r: r.update(choices=[])]
        for mutation in mutations:
            core, backend, server_ledger = self.server()
            backend.mutate_response = mutation
            client_ledger, _ = self.ledger()
            caps = self.handle(core, self.capabilities_request())
            count = self.handle(core, self.count_request())
            admitted = codec.admit_turn(self.contract, self.prepared, capabilities=caps,
                                       count_receipt=count, ledger=client_ledger, call_id="a" * 32)
            reply = self.handle(core, admitted.completion_request_json.encode())
            result = codec.accept_completion(self.contract, admitted, reply, ledger=client_ledger)
            self.assertFalse(result.usable_action_text)
            self.assertEqual("", result.text)
            self.assertEqual(backend.last_response, json.loads(reply)["response"])
            self.assertEqual(server_ledger.snapshot(), client_ledger.snapshot())
            self.assertTrue(server_ledger.snapshot()["halted"])
            self.assertEqual("failed", server_ledger.snapshot()["records"][0]["status"])
            previous = list(backend.calls)
            self.assert_error(core, self.message(call_id="b" * 32), "ledger_error")
            self.assertEqual(previous, backend.calls)

    def test_near_response_cap_wrapper_overflow_keeps_known_observed_usage(self):
        core, backend, ledger = self.server()
        def near_cap(response):
            response["extra"] = "x" * 63000
        backend.mutate_response = near_cap
        self.assert_error(core, self.message(), "response_error")
        self.assertLessEqual(len(encoded(backend.last_response)), self.contract.max_response_bytes)
        self.assertEqual(13, ledger.snapshot()["provider_usage"]["output_tokens"])
        self.assertTrue(ledger.snapshot()["halted"])

    def test_expiry_after_durable_settlement_suppresses_reply_without_erasing_known_evidence(self):
        core, backend, ledger = self.server()
        now = [100.0]
        settle = ledger.settle
        def slow_settle(*args, **kwargs):
            result = settle(*args, **kwargs)
            now[0] = 151.0
            return result
        with patch.object(broker.time, "monotonic", side_effect=lambda: now[0]), \
             patch.object(ledger, "settle", side_effect=slow_settle):
            self.assert_error(core, self.message(), "timeout", deadline=150.0)
        self.assertEqual(13, ledger.snapshot()["provider_usage"]["output_tokens"])
        self.assertEqual("completed", ledger.snapshot()["records"][0]["status"])
        previous = list(backend.calls)
        self.assert_error(core, self.message(), "duplicate_call")
        self.assertEqual(previous, backend.calls)

    def test_material_drift_and_closed_ledger_fail_before_backend(self):
        core, backend, ledger = self.server()
        with patch.object(codec, "implementation_inventory", return_value={"changed": "0" * 64}):
            self.assert_error(core, self.capabilities_request(), "request_error")
        self.assertEqual([], backend.calls)
        ledger.close()
        self.assert_error(core, self.capabilities_request(), "ledger_error")
        self.assertEqual([], backend.calls)

    def test_constructor_owns_contract_copy_and_rejects_invalid_frame_bounds(self):
        original = fixture_contract()
        core, backend, _ = self.server(contract=original)
        object.__setattr__(original, "request_model", "mutated-caller-object")
        # Backend capabilities still claim the original fixture identity here;
        # the server must not silently adopt the caller's later mutation.
        backend.contract = self.contract
        self.handle(core, self.message())
        self.assertEqual(self.contract.request_model, json.loads(backend.calls[-1][1]["payload_json"])["model"])
        for cap in (True, 0, -1, 1.5):
            with self.assertRaises(broker.BrokerError):
                self.server(frame_cap=cap)

    def test_reentrant_request_does_not_queue_or_dispatch_additional_callbacks(self):
        core, backend, ledger = self.server()
        backend.hooks["capabilities"] = lambda: self.assert_error(core, self.capabilities_request(), "ledger_error")
        self.handle(core, self.message())
        self.assertEqual(["capabilities", "count", "complete"], [name for name, _ in backend.calls])
        self.assertEqual(1, ledger.snapshot()["admitted_calls"])

    def test_existing_live_execution_gate_remains_disabled(self):
        self.assertFalse(broker.MODEL_EXECUTION_ENABLED)
        with self.assertRaises(LiveExecutionDisabled):
            codec.execute_model()


if __name__ == "__main__":
    unittest.main()
