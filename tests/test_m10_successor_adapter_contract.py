from __future__ import annotations

import copy
import json
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

from bench.agent_ab.same_version_chain_v1 import m10_successor_adapter_contract as codec
from bench.agent_ab.same_version_chain_v1.m10_successor_protocol import (
    ACTION_SCHEMAS, AdapterRequest, LiveExecutionDisabled, run_one,
)
from bench.agent_ab.same_version_chain_v1.m10_successor_token_budget import (
    TokenBudgetExceeded, TokenBudgetLedger, TokenLimits,
)


def example_contract() -> codec.BrokerContract:
    """Invented offline pins, not a claim about any configured provider."""
    return codec.BrokerContract(
        experiment_seal_sha256="1" * 64, provider_id="offline-example",
        endpoint="https://example.invalid/v1/chat/completions",
        request_model="example-model", response_model="example-model-snapshot",
        deployment_revision="example-deployment-1", broker_build_sha256="2" * 64,
        broker_runtime_sha256="3" * 64, tokenizer_id="example-tokenizer",
        tokenizer_sha256="4" * 64,
        inference_json=codec.canonical({"temperature": 0, "top_p": 1,
                                        "seed": 7, "reasoning_effort": "low"}),
        limits=TokenLimits(10_000, 4096, 14_096, 30_000, 12_288, 3),
        max_request_bytes=120_000, max_response_bytes=64_000, timeout_seconds=90,
    )


def example_request() -> AdapterRequest:
    return AdapterRequest(
        messages=({"role": "system", "content": "Use the action protocol."},
                  {"role": "user", "content": "Workspace: <workspace>\nEdit the source."}),
        action_schemas=copy.deepcopy(ACTION_SCHEMAS), max_output_tokens=4096,
        max_output_bytes=16_000, timeout_seconds=80,
    )


def encoded(value: dict) -> bytes:
    return codec.canonical(value).encode("utf-8")


def capabilities(contract: codec.BrokerContract) -> dict:
    return {
        "protocol": "tmf-successor-broker-v2", "op": "capabilities",
        "contract_sha256": codec.seal_contract(contract)["seal_sha256"],
        "identity": contract.identity(),
        "tokenizer": {"id": contract.tokenizer_id, "sha256": contract.tokenizer_sha256},
        "semantics": {"stateless": True, "native_tools": False, "network_owner": "broker",
                      "credential_owner": "broker", "max_attempts": 1, "fallback": False,
                      "truncation": False, "input_count": "exact_full_payload",
                      "output_parameter": "max_completion_tokens",
                      "usage": "all_provider_tokens_including_reasoning"},
    }


def counted(contract: codec.BrokerContract, prepared: codec.PreparedTurn) -> dict:
    return {"protocol": "tmf-successor-broker-v2", "op": "count",
            "contract_sha256": prepared.contract_sha256, "payload_sha256": prepared.payload_sha256,
            "tokenizer_id": contract.tokenizer_id, "tokenizer_sha256": contract.tokenizer_sha256,
            "input_tokens": 6000, "exact": True, "generation_calls": 0}


def completion(contract: codec.BrokerContract, admitted: codec.AdmittedTurn) -> dict:
    return {
        "protocol": "tmf-successor-broker-v2", "op": "complete", "call_id": admitted.call_id,
        "request_sha256": admitted.request_sha256, "identity": contract.identity(),
        "submitted_payload_sha256": admitted.prepared.payload_sha256,
        "submitted_max_completion_tokens": 4096, "attempts": 1,
        "response": {"id": "example-completion", "object": "chat.completion",
                     "model": contract.response_model,
                     "choices": [{"index": 0, "finish_reason": "stop", "message": {
                         "role": "assistant", "content": '{"action":"list"}'}}],
                     "usage": {"prompt_tokens": 6000, "completion_tokens": 1000, "total_tokens": 7000,
                               "prompt_tokens_details": {"cached_tokens": 5500},
                               "completion_tokens_details": {"reasoning_tokens": 900}}},
    }


class AdapterContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.contract = example_contract()
        self.request = example_request()
        self.prepared = codec.prepare_turn(self.contract, self.request)
        self.number = 0

    def ledger(self) -> TokenBudgetLedger:
        self.number += 1
        ledger = TokenBudgetLedger(Path(self.temp.name) / f"ledger-{self.number}.jsonl", self.contract.limits)
        self.addCleanup(ledger.close)
        return ledger

    def admit(self, ledger: TokenBudgetLedger, *, prepared=None, cap=None, count=None):
        prepared = prepared or self.prepared
        return codec.admit_turn(self.contract, prepared,
                                capabilities=encoded(cap if cap is not None else capabilities(self.contract)),
                                count_receipt=encoded(count if count is not None else counted(self.contract, prepared)),
                                ledger=ledger, call_id="a" * 32)

    def test_complete_offline_lifecycle_retains_reasoning_and_cached_tokens(self):
        ledger = self.ledger()
        with patch("socket.socket", side_effect=AssertionError("no socket")), \
             patch("subprocess.Popen", side_effect=AssertionError("no subprocess")):
            admitted = self.admit(ledger)
            before = ledger.snapshot()
            self.assertEqual(1, before["admitted_calls"])
            self.assertEqual(6000, before["charged_input_tokens"])
            self.assertEqual(4096, before["charged_output_tokens"])
            result = codec.accept_completion(self.contract, admitted,
                                             encoded(completion(self.contract, admitted)), ledger=ledger)
        self.assertTrue(result.usable_action_text)
        self.assertEqual('{"action":"list"}', result.text)
        after = ledger.snapshot()
        self.assertEqual({"input_tokens": 6000, "output_tokens": 1000, "total_tokens": 7000}, after["provider_usage"])
        self.assertEqual(1000, after["charged_output_tokens"])
        self.assertFalse(after["halted"])
        self.assertTrue(after["records"][0]["itt_included"])
        self.assertEqual(codec.digest(admitted.completion_request_json), before["records"][0]["request_sha256"])

    def test_payload_is_complete_deterministic_snapshot_without_metadata(self):
        request = replace(self.request, messages=self.request.messages + (
            {"role": "assistant", "content": '{"action":"list"}'},
            {"role": "tool", "content": 'A.java\n"quoted" 中文'},))
        prepared = codec.prepare_turn(self.contract, request)
        body = json.loads(prepared.payload_json)
        self.assertEqual(4096, body["max_completion_tokens"])
        self.assertNotIn("max_tokens", body)
        self.assertEqual(1, body["n"])
        self.assertFalse(body["stream"])
        self.assertFalse(body["store"])
        self.assertEqual(["system", "user", "assistant", "user"], [m["role"] for m in body["messages"]])
        self.assertEqual(codec.TOOL_RESULT_PREFIX + codec.canonical(request.messages[-1]["content"]), body["messages"][-1]["content"])
        self.assertIn(codec.canonical(ACTION_SCHEMAS), body["messages"][0]["content"])
        for forbidden in ("call_id", "contract_sha256", "experiment_seal", "broker_build", "tools", "metadata"):
            self.assertNotIn(forbidden, body)
        self.assertEqual(prepared, codec.prepare_turn(self.contract, request))
        # Mutation after preparation cannot silently change the already-counted request.
        request.action_schemas["list"]["description"] += " MUTATION_SENTINEL"
        self.assertNotEqual(prepared.payload_sha256, codec.prepare_turn(self.contract, request).payload_sha256)
        self.assertNotIn("MUTATION_SENTINEL", prepared.payload_json)

    def test_v1_capabilities_and_inexact_counts_fail_before_reservation(self):
        cases = []
        cap = capabilities(self.contract)
        cap["protocol"] = "tmf-agent-broker-v1"
        cases.append((cap, counted(self.contract, self.prepared)))
        for field, value in (("exact", False), ("exact", 1), ("generation_calls", 1),
                             ("generation_calls", False), ("payload_sha256", "f" * 64),
                             ("input_tokens", True), ("input_tokens", -1),
                             ("tokenizer_sha256", "0" * 64)):
            count = counted(self.contract, self.prepared)
            count[field] = value
            cases.append((capabilities(self.contract), count))
        for cap, count in cases:
            ledger = self.ledger()
            with self.subTest(count=count), self.assertRaises(codec.ContractError):
                self.admit(ledger, cap=cap, count=count)
            self.assertEqual(0, ledger.snapshot()["admitted_calls"])

    def test_byte_token_timeout_and_full_history_limits_fail_closed(self):
        variants = [replace(self.request, max_output_tokens=4097),
                    replace(self.request, max_output_tokens=True),
                    replace(self.request, max_output_bytes=64_001),
                    replace(self.request, timeout_seconds=91),
                    replace(self.request, timeout_seconds=float("nan")),
                    replace(self.request, messages=({"role": "system", "content": "x" * 120_000}, self.request.messages[1])),
                    replace(self.request, messages=self.request.messages + ({"role": "assistant", "content": "x"},)),
                    replace(self.request, messages=({"role": "user", "content": "x"}, self.request.messages[1]))]
        for request in variants:
            with self.subTest(request=request.max_output_tokens), self.assertRaises(codec.ContractError):
                codec.prepare_turn(self.contract, request)
        count = counted(self.contract, self.prepared)
        count["input_tokens"] = 10_001
        ledger = self.ledger()
        with self.assertRaises(TokenBudgetExceeded):
            self.admit(ledger, count=count)
        self.assertEqual(0, ledger.snapshot()["admitted_calls"])

    def test_resigned_payload_rewrite_and_material_drift_cannot_be_admitted(self):
        body = json.loads(self.prepared.payload_json)
        body["messages"][1]["content"] += " leaked instruction"
        rewritten = codec.canonical(body)
        prepared = replace(self.prepared, payload_json=rewritten, payload_sha256=codec.digest(rewritten))
        ledger = self.ledger()
        with self.assertRaises(codec.ContractError):
            self.admit(ledger, prepared=prepared)
        with patch.object(codec, "implementation_inventory", return_value={"changed.py": "0" * 64}):
            with self.assertRaises(codec.ContractError):
                self.admit(ledger)
        self.assertEqual(0, ledger.snapshot()["admitted_calls"])

    def test_bad_receipts_never_release_reservation_or_invent_zero_usage(self):
        mutations = [
            lambda r: r.update(call_id="b" * 32),
            lambda r: r.update(request_sha256="0" * 64),
            lambda r: r.update(submitted_payload_sha256="0" * 64),
            lambda r: r.update(submitted_max_completion_tokens=512),
            lambda r: r.update(attempts=2),
            lambda r: r.update(attempts=True),
            lambda r: r["identity"].update(deployment_revision="changed"),
            lambda r: r["response"].update(model=self.contract.request_model),
            lambda r: r["response"].pop("usage"),
            lambda r: r["response"]["usage"].update(prompt_tokens=True),
            lambda r: r["response"]["usage"].update(total_tokens=1),
            lambda r: r["response"]["usage"]["completion_tokens_details"].update(reasoning_tokens=1001),
        ]
        for mutate in mutations:
            ledger = self.ledger()
            admitted = self.admit(ledger)
            receipt = completion(self.contract, admitted)
            mutate(receipt)
            with self.subTest(mutation=mutate), self.assertRaises(codec.ContractError):
                codec.accept_completion(self.contract, admitted, encoded(receipt), ledger=ledger)
            snapshot = ledger.snapshot()
            self.assertTrue(snapshot["halted"])
            self.assertEqual(1, snapshot["admitted_calls"])
            self.assertEqual(4096, snapshot["charged_output_tokens"])
            self.assertIsNone(snapshot["provider_usage"])

    def test_duplicate_malformed_and_oversized_json_are_unknown_not_free_retries(self):
        for raw in (b'{"attempts":1,"attempts":1}', b'{"x":NaN}', b'[]', b'{', b'\xff', b'x' * 64_001):
            ledger = self.ledger()
            admitted = self.admit(ledger)
            with self.subTest(raw=raw[:30]), self.assertRaises(codec.ContractError):
                codec.accept_completion(self.contract, admitted, raw, ledger=ledger)
            self.assertEqual(1, ledger.snapshot()["unknown_usage_calls"])

    def test_valid_usage_violation_is_recorded_before_error_not_erased(self):
        for prompt, output in ((5999, 1000), (6001, 1000), (6000, 4097)):
            ledger = self.ledger()
            admitted = self.admit(ledger)
            receipt = completion(self.contract, admitted)
            receipt["response"]["usage"] = {"prompt_tokens": prompt, "completion_tokens": output,
                                             "total_tokens": prompt + output}
            with self.assertRaises(codec.ContractError):
                codec.accept_completion(self.contract, admitted, encoded(receipt), ledger=ledger)
            snapshot = ledger.snapshot()
            self.assertEqual("usage_mismatch", snapshot["records"][0]["status"])
            self.assertEqual(prompt, snapshot["provider_usage"]["input_tokens"])
            self.assertEqual(max(4096, output), snapshot["charged_output_tokens"])
            self.assertTrue(snapshot["halted"])

    def test_refusal_truncation_and_bad_content_keep_known_usage(self):
        mutations = [lambda c: c.update(finish_reason="length"),
                     lambda c: c.update(finish_reason="content_filter"),
                     lambda c: c["message"].update(refusal="refused"),
                     lambda c: c["message"].update(content=None),
                     lambda c: c["message"].update(content="x" * 16_001),
                     lambda c: c["message"].update(tool_calls=[{"id": "not-supported"}])]
        for mutate in mutations:
            ledger = self.ledger()
            admitted = self.admit(ledger)
            receipt = completion(self.contract, admitted)
            mutate(receipt["response"]["choices"][0])
            result = codec.accept_completion(self.contract, admitted, encoded(receipt), ledger=ledger)
            self.assertFalse(result.usable_action_text)
            self.assertEqual("", result.text)
            self.assertEqual(1000, ledger.snapshot()["provider_usage"]["output_tokens"])
            self.assertTrue(ledger.snapshot()["halted"])

    def test_replayed_completion_cannot_spend_or_refund_twice(self):
        ledger = self.ledger()
        admitted = self.admit(ledger)
        raw = encoded(completion(self.contract, admitted))
        codec.accept_completion(self.contract, admitted, raw, ledger=ledger)
        before = ledger.snapshot()
        with self.assertRaises(codec.ContractError):
            codec.accept_completion(self.contract, admitted, raw, ledger=ledger)
        self.assertEqual(before, ledger.snapshot())

    def test_cross_ledger_and_tampered_admission_are_not_authority(self):
        ledger = self.ledger()
        admitted = self.admit(ledger)
        raw = encoded(completion(self.contract, admitted))
        other = self.ledger()
        with self.assertRaises(codec.ContractError):
            codec.accept_completion(self.contract, admitted, raw, ledger=other)
        altered = replace(admitted, completion_request_json=admitted.completion_request_json + " ")
        with self.assertRaises(codec.ContractError):
            codec.accept_completion(self.contract, altered, raw, ledger=ledger)
        self.assertTrue(ledger.snapshot()["halted"])
        self.assertEqual(0, other.snapshot()["admitted_calls"])

    def test_seal_is_reproducible_but_not_a_model_admission(self):
        first = codec.seal_contract(self.contract)
        self.assertEqual(first, codec.seal_contract(self.contract))
        self.assertEqual("offline_adapter_contract_conformance", first["evidence_kind"])
        for key in ("model_execution_enabled", "model_pilot_admitted", "provider_token_limits_verified"):
            self.assertIs(first[key], False)
        self.assertNotEqual(first["seal_sha256"], codec.seal_contract(replace(self.contract, deployment_revision="other"))["seal_sha256"])
        self.assertIn("bench/agent_ab/same_version_chain_v1/m10_successor_token_budget.py", first["implementation_sha256"])
        with self.assertRaises(LiveExecutionDisabled):
            codec.execute_model(transport=lambda: self.fail("must not invoke"))
        with self.assertRaises(LiveExecutionDisabled):
            run_one(Path(self.temp.name), list(self.request.messages), object(),
                    compile_fn=lambda _: self.fail("no compile"),
                    score_fn=lambda _: self.fail("no scoring"),
                    verify=lambda: self.fail("no admission"),
                    live=True)

    def test_pins_are_explicit_and_secrets_cannot_appear_in_endpoint(self):
        for endpoint in ("http://example.invalid/v1/chat/completions",
                         "https://name:secret@example.invalid/v1/chat/completions",
                         "https://example.invalid/v1/chat/completions?key=secret"):
            with self.assertRaises(codec.ContractError):
                replace(self.contract, endpoint=endpoint)
        for values in ({"broker_build_sha256": "not-a-hash"}, {"timeout_seconds": True},
                       {"inference_json": '{"max_tokens":512}'}, {"max_request_bytes": 0}):
            with self.assertRaises(codec.ContractError):
                replace(self.contract, **values)


if __name__ == "__main__":
    unittest.main()
