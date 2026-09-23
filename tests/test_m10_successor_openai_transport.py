"""Credential-free/offline transport and journal fault injection.

The fictional counts and responses here are test inputs, never provider evidence.
Network socket use is forbidden in every test, including HTTP-wrapper tests.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import stat
import tempfile
import threading
import time
import types
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from bench.agent_ab.same_version_chain_v1 import successor_openai_transport as transport
from bench.agent_ab.same_version_chain_v1.m10_successor_protocol import ACTION_SCHEMAS


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def fictional_prepared(cap=4096):
    """Broker plumbing fake; the separately tested real codec owns rendering."""
    counted = encoded({"model": "fictional-only", "input": [{"role": "user", "content": "中文"}]}).decode()
    generated = encoded({**json.loads(counted), "max_output_tokens": cap}).decode()
    return types.SimpleNamespace(count_json=counted, generation_json=generated,
                                 scientific_sha256=hashlib.sha256(counted.encode()).hexdigest(),
                                 generation_sha256=hashlib.sha256(generated.encode()).hexdigest(),
                                 max_output_tokens=cap, purpose="output_cap" if cap == 64 else "scientific")


def fictional_observation(raw, prepared, **kwargs):
    value = json.loads(raw)
    usage = value.get("usage")
    return {"ok": value.get("ok", True), "errors": [] if value.get("ok", True) else ["wrong_model"],
            "usage": usage, "response": value, "action": {"action": "list"},
            "cap_observed": kwargs.get("expect_cap", False)}


def response(*, ok=True, usage=True, output=17):
    value = {"ok": ok, "response_id": "fictional-id"}
    if usage:
        value["usage"] = {"input_tokens": 123, "output_tokens": output, "total_tokens": 123 + output}
    return transport.PostResult(200, {"x-request-id": "fictional-request-id"}, encoded(value))


class FakeSender:
    def __init__(self):
        self.calls = []
        self.count_value = 123
        self.generation_response = response()
        self.before = lambda *args: None

    def post(self, url, body, *, deadline_monotonic):
        self.calls.append((url, body, deadline_monotonic))
        self.before(url, body)
        if url == transport.COUNT_URL:
            return transport.PostResult(200, {}, encoded({"input_tokens": self.count_value}))
        return self.generation_response


class OfflineCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.network = patch("socket.socket.connect", side_effect=AssertionError("network forbidden"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def journal(self, name="operations.jsonl", **kwargs):
        result = transport.OperationJournal(self.root / name,
                                             authorization_id=kwargs.get("authorization_id", "test-authorization"),
                                             seal_sha256=kwargs.get("seal_sha256", "a" * 64))
        self.addCleanup(result.close)
        return result

    def admit(self, journal, opid, operation="count", cap=4096, inp=123):
        journal.admit(opid, operation, request_sha256="b" * 64, scientific_sha256="c" * 64,
                      input_tokens=inp if operation == "generation" else 0,
                      max_output_tokens=cap if operation == "generation" else 0)

    def settle_count(self, journal, opid):
        journal.settle(opid, ok=True, category="ok", input_count=123)


class OperationJournalTests(OfflineCase):
    def test_policy_unknown_count_price_and_fixed_limits(self):
        self.assertEqual(transport.operation_policy()["count_pricing"], "unknown")
        self.assertEqual(transport.operation_policy()["generation_output_caps"], [4096, 4096, 64])
        self.assertEqual(transport.operation_policy()["max_count_requests"], 12)

    def test_admission_is_durable_hash_chained_before_settlement(self):
        journal = self.journal()
        with patch.object(transport.os, "fsync", wraps=os.fsync) as sync:
            self.admit(journal, "count-1")
        self.assertGreater(sync.call_count, 0)
        rows = [json.loads(line) for line in journal.path.read_bytes().splitlines()]
        self.assertEqual(rows[-1]["event"]["kind"], "admitted")
        self.assertEqual(rows[1]["previous"], rows[0]["sha256"])
        self.assertEqual(journal.snapshot()["count_requests"], 1)
        self.settle_count(journal, "count-1")
        self.assertIsNone(journal.snapshot()["pending"])

    def test_count_limit_cannot_refund_or_retry(self):
        journal = self.journal()
        for index in range(12):
            self.admit(journal, f"count-{index}")
            self.settle_count(journal, f"count-{index}")
        with self.assertRaises(transport.JournalError):
            self.admit(journal, "count-13")
        self.assertEqual(journal.snapshot()["count_requests"], 12)

    def test_generation_cap_schedule_and_hard_totals(self):
        journal = self.journal()
        for index, cap in enumerate((4096, 4096, 64)):
            self.admit(journal, f"gen-{index}", "generation", cap=cap, inp=10_000)
            journal.settle(f"gen-{index}", ok=True, category="ok",
                           usage={"input_tokens": 10_000, "output_tokens": cap, "total_tokens": 10_000 + cap})
        snap = journal.snapshot()
        self.assertEqual(snap["input_reserved"], 30_000)
        self.assertEqual(snap["output_reserved"], 8256)
        self.assertEqual(snap["charged_usage"]["total_tokens"], 38_256)
        self.assertTrue(snap["complete"])
        for operation in ("count", "generation"):
            with self.assertRaises(transport.JournalError):
                self.admit(journal, "after-finished", operation)

    def test_wrong_output_cap_or_input_bound_rejected(self):
        for inp, cap in ((10_001, 4096), (True, 4096), (123, 64), (123, 4095)):
            journal = self.journal(f"bad-{inp}-{cap}.jsonl")
            with self.assertRaises(transport.JournalError):
                self.admit(journal, "gen", "generation", inp=inp, cap=cap)
            self.assertEqual(journal.snapshot()["generation_requests"], 0)

    def test_failed_known_usage_retained_and_halts(self):
        journal = self.journal()
        self.admit(journal, "gen", "generation")
        journal.settle("gen", ok=False, category="wrong_model", usage={
            "input_tokens": 123, "output_tokens": 10, "total_tokens": 133})
        snap = journal.snapshot()
        self.assertEqual(snap["known_usage"]["total_tokens"], 133)
        self.assertEqual(snap["charged_usage"]["total_tokens"], 133)
        self.assertEqual(snap["halt_reason"], "wrong_model")
        with self.assertRaises(transport.JournalError):
            self.admit(journal, "later")

    def test_unknown_usage_reserves_full_tokens(self):
        journal = self.journal()
        self.admit(journal, "gen", "generation")
        journal.settle("gen", ok=False, category="transport_timeout")
        snap = journal.snapshot()
        self.assertEqual(snap["known_usage"]["total_tokens"], 0)
        self.assertEqual(snap["charged_usage"]["total_tokens"], 4219)

    def test_pending_reopen_conservative_inspection_only(self):
        journal = self.journal()
        self.admit(journal, "gen", "generation")
        journal.close()
        reopened = self.journal()
        snap = reopened.snapshot()
        self.assertTrue(snap["inspection_only"])
        self.assertEqual(snap["pending"], "gen")
        self.assertEqual(snap["charged_usage"]["total_tokens"], 4219)
        with self.assertRaises(transport.JournalError):
            reopened.settle("gen", ok=False, category="timeout")
        with self.assertRaises(transport.JournalError):
            self.admit(reopened, "new")

    def test_clean_reopen_does_not_reset_budget(self):
        journal = self.journal()
        self.admit(journal, "count-1")
        self.settle_count(journal, "count-1")
        journal.close()
        reopened = self.journal()
        self.assertEqual(reopened.snapshot()["count_requests"], 1)
        with self.assertRaises(transport.JournalError):
            self.admit(reopened, "count-2")

    def test_reopened_authorization_and_seal_must_match(self):
        journal = self.journal()
        journal.close()
        for kwargs in ({"authorization_id": "another"}, {"seal_sha256": "f" * 64}):
            with self.assertRaises(transport.JournalError):
                self.journal(**kwargs)

    def test_duplicate_admission_and_pending_admission_rejected(self):
        journal = self.journal()
        self.admit(journal, "count-1")
        with self.assertRaises(transport.JournalError):
            self.admit(journal, "count-2")
        self.settle_count(journal, "count-1")
        with self.assertRaises(transport.JournalError):
            self.admit(journal, "count-1")

    def test_second_owner_and_symlink_refused(self):
        journal = self.journal()
        with self.assertRaises(transport.JournalError):
            self.journal()
        (self.root / "link.jsonl").symlink_to(journal.path)
        with self.assertRaises(transport.JournalError):
            self.journal("link.jsonl")

    def test_corruption_replacement_truncation_detected(self):
        for mode in ("append", "replace", "truncate"):
            journal = self.journal(f"{mode}.jsonl")
            if mode == "append":
                with journal.path.open("ab") as stream:
                    stream.write(b"unexpected\n")
            elif mode == "replace":
                other = self.root / "replacement"
                other.write_bytes(journal.path.read_bytes())
                other.replace(journal.path)
            else:
                journal.path.write_bytes(journal.path.read_bytes()[:-1])
            with self.assertRaises(transport.JournalError):
                journal.snapshot()
            with self.assertRaises(transport.JournalError):
                self.admit(journal, "must-not-dispatch")

    def test_replay_rejects_semantically_invalid_rehashed_event(self):
        journal = self.journal()
        self.admit(journal, "count")
        journal.close()
        rows = [json.loads(row) for row in journal.path.read_bytes().splitlines()]
        rows[1]["event"]["input_tokens"] = True
        core = {key: rows[1][key] for key in ("sequence", "previous", "event")}
        rows[1]["sha256"] = hashlib.sha256(encoded(core)).hexdigest()
        journal.path.write_bytes(b"\n".join(encoded(row) for row in rows) + b"\n")
        with self.assertRaises(transport.JournalError):
            self.journal()

    def test_fsync_failure_never_allows_dispatch(self):
        journal = self.journal()
        with patch.object(transport.os, "fsync", side_effect=OSError("fictional fsync failure")):
            with self.assertRaises(transport.JournalError):
                self.admit(journal, "count")
        with self.assertRaises(transport.JournalError):
            self.admit(journal, "later")

    def test_usage_rejects_bool_negative_and_double_counted_total(self):
        for index, usage in enumerate((
                {"input_tokens": True, "output_tokens": 1, "total_tokens": 2},
                {"input_tokens": 123, "output_tokens": -1, "total_tokens": 122},
                {"input_tokens": 123, "output_tokens": 10, "total_tokens": 140})):
            journal = self.journal(f"usage-{index}.jsonl")
            self.admit(journal, "gen", "generation")
            with self.assertRaises(transport.JournalError):
                journal.settle("gen", ok=True, category="ok", usage=usage)

    def test_over_contract_usage_cannot_settle_success_but_is_retained_on_failure(self):
        journal = self.journal()
        self.admit(journal, "gen", "generation")
        usage = {"input_tokens": 124, "output_tokens": 4097, "total_tokens": 4221}
        with self.assertRaises(transport.JournalError):
            journal.settle("gen", ok=True, category="ok", usage=usage)
        journal.settle("gen", ok=False, category="usage_contract_violation", usage=usage)
        self.assertEqual(journal.snapshot()["known_usage"], usage)
        self.assertEqual(journal.snapshot()["charged_usage"], usage)


class CountedBrokerTests(OfflineCase):
    def setUp(self):
        super().setUp()
        for name, value in (("verify_prepared", lambda prepared: None),
                            ("parse_count", lambda raw: json.loads(raw)["input_tokens"]),
                            ("inspect_response", fictional_observation)):
            mock = patch.object(transport.codec, name, value)
            mock.start()
            self.addCleanup(mock.stop)
        self.ledger = self.journal()
        self.sender = FakeSender()
        self.broker = transport.CountedBroker(self.sender, self.ledger, self.root / "evidence")
        self.prepared = fictional_prepared()

    def complete(self, **kwargs):
        return self.broker.complete(self.prepared, operation_id=kwargs.get("operation_id", "C1"),
                                    expected_input_tokens=kwargs.get("expected_input_tokens", 123),
                                    deadline_monotonic=time.monotonic() + 5)

    def test_new_evidence_directory_and_ancestors_are_durable_before_first_post(self):
        raw = self.root / "new-raw"
        real_sync, synced = os.fsync, []

        def sync(fd):
            info = os.fstat(fd)
            synced.append((info.st_dev, info.st_ino))
            real_sync(fd)

        def before(url, body):
            expected = [(p.stat().st_dev, p.stat().st_ino) for p in (raw, *raw.parents)]
            self.assertEqual(expected, synced[:len(expected)])
            self.assertTrue((raw / "count.request.json").is_file())
            self.assertTrue((raw / "count.admission.json").is_file())

        self.sender.before = before
        with patch.object(transport.os, "fsync", side_effect=sync):
            broker = transport.CountedBroker(self.sender, self.ledger, raw)
            broker.count(self.prepared, operation_id="count", deadline_monotonic=time.monotonic() + 5)
        self.assertEqual(1, len(self.sender.calls))

    def test_evidence_ancestor_fsync_failure_cannot_dispatch(self):
        real_sync = os.fsync
        failed_inode = self.root.stat().st_ino

        def sync(fd):
            info = os.fstat(fd)
            if stat.S_ISDIR(info.st_mode) and info.st_ino == failed_inode:
                raise OSError("simulated evidence parent fsync failure")
            real_sync(fd)

        with patch.object(transport.os, "fsync", side_effect=sync):
            with self.assertRaises(OSError):
                transport.CountedBroker(self.sender, self.ledger, self.root / "new-raw")
        self.assertEqual([], self.sender.calls)
        self.assertEqual(0, self.ledger.snapshot()["count_requests"])

    def test_count_exact_frozen_bytes_admitted_before_post(self):
        def assert_admitted(url, body):
            state = self.ledger.snapshot()
            self.assertEqual(state["pending"], "initial-1")
            self.assertEqual(state["count_requests"], 1)
            self.assertEqual(body, self.prepared.count_json.encode())
            self.assertEqual((self.broker.evidence_dir / "initial-1.request.json").read_bytes(), body)
        self.sender.before = assert_admitted
        self.assertEqual(self.broker.count(self.prepared, operation_id="initial-1",
                                          deadline_monotonic=time.monotonic() + 5), 123)

    def test_generation_recounts_and_retains_original_evidence(self):
        result = self.complete()
        self.assertTrue(result["ok"])
        self.assertEqual([entry[0] for entry in self.sender.calls], [transport.COUNT_URL, transport.GENERATION_URL])
        self.assertEqual(self.sender.calls[0][1], self.prepared.count_json.encode())
        self.assertEqual(self.sender.calls[1][1], self.prepared.generation_json.encode())
        self.assertEqual((self.broker.evidence_dir / "C1.response.bin").read_bytes(), self.sender.generation_response.body)
        self.assertEqual(self.ledger.snapshot()["known_usage"]["total_tokens"], 140)

    def test_recount_mismatch_no_generation_and_halts(self):
        with self.assertRaises(transport.BrokerFailure) as caught:
            self.complete(expected_input_tokens=124)
        self.assertEqual(caught.exception.category, "count_mismatch")
        self.assertEqual(len(self.sender.calls), 1)
        self.assertEqual(self.ledger.snapshot()["generation_requests"], 0)
        self.assertEqual(self.ledger.snapshot()["halt_reason"], "count_mismatch")

    def test_wrong_identity_preserves_usage_and_raw_response(self):
        self.sender.generation_response = response(ok=False)
        with self.assertRaises(transport.BrokerFailure) as caught:
            self.complete()
        self.assertEqual(caught.exception.category, "response_contract_failure")
        self.assertEqual(caught.exception.receipt["journal"]["known_usage"]["total_tokens"], 140)
        self.assertEqual((self.broker.evidence_dir / "C1.response.bin").read_bytes(), self.sender.generation_response.body)
        with self.assertRaises(transport.BrokerFailure):
            self.complete(operation_id="replacement-C1")
        self.assertEqual(len(self.sender.calls), 2)

    def test_unknown_usage_charged_conservatively_without_retry(self):
        self.sender.generation_response = response(usage=False)
        with self.assertRaises(transport.BrokerFailure) as caught:
            self.complete()
        self.assertEqual(caught.exception.receipt["journal"]["charged_usage"]["total_tokens"], 4219)
        self.assertEqual(len(self.sender.calls), 2)

    def test_generation_transport_uncertainty_no_retry(self):
        def fail_generation(url, body):
            if url == transport.GENERATION_URL:
                raise OSError("fictional secret must not escape")
        self.sender.before = fail_generation
        with self.assertRaises(transport.BrokerFailure) as caught:
            self.complete()
        self.assertNotIn("secret", str(caught.exception) + json.dumps(caught.exception.receipt))
        self.assertEqual(self.ledger.snapshot()["charged_usage"]["total_tokens"], 4219)
        self.assertEqual(len(self.sender.calls), 2)

    def test_count_transport_failure_consumes_one_count_and_zero_generation(self):
        self.sender.before = lambda *args: (_ for _ in ()).throw(TimeoutError("fake"))
        with self.assertRaises(transport.BrokerFailure):
            self.complete()
        state = self.ledger.snapshot()
        self.assertEqual(state["count_requests"], 1)
        self.assertEqual(state["generation_requests"], 0)
        self.assertEqual(len(self.sender.calls), 1)

    def test_expired_deadline_and_invalid_prepared_never_dispatch(self):
        with self.assertRaises(transport.BrokerFailure):
            self.broker.count(self.prepared, operation_id="expired", deadline_monotonic=time.monotonic() - 1)
        self.assertEqual(self.sender.calls, [])
        self.assertEqual(self.ledger.snapshot()["count_requests"], 0)

    def test_count_response_above_cap_halts_before_generation(self):
        self.sender.count_value = 10_001
        with self.assertRaises(transport.BrokerFailure) as caught:
            self.complete()
        self.assertEqual(caught.exception.category, "input_count_limit")
        self.assertEqual(len(self.sender.calls), 1)

    def test_purpose_mismatch_rejected_before_count(self):
        with self.assertRaises(transport.BrokerFailure) as caught:
            self.broker.complete(self.prepared, operation_id="C1", expected_input_tokens=123,
                                 deadline_monotonic=time.monotonic() + 5, expect_cap=True)
        self.assertEqual(caught.exception.category, "response_purpose_mismatch")
        self.assertEqual(self.sender.calls, [])
        self.assertEqual(self.ledger.snapshot()["count_requests"], 0)

    def test_http_error_retains_known_usage(self):
        original = response()
        self.sender.generation_response = transport.PostResult(429, original.headers, original.body)
        with self.assertRaises(transport.BrokerFailure) as caught:
            self.complete()
        self.assertEqual(caught.exception.category, "http_status")
        self.assertEqual(self.ledger.snapshot()["known_usage"]["total_tokens"], 140)

    def test_evidence_failure_preserves_received_known_usage(self):
        real_write = transport._write_new
        def fail_metadata(path, raw):
            if path.name == "C1.metadata.json":
                raise OSError("fictional disk failure")
            return real_write(path, raw)
        with patch.object(transport, "_write_new", fail_metadata):
            with self.assertRaises(transport.BrokerFailure):
                self.complete()
        self.assertEqual(self.ledger.snapshot()["known_usage"]["total_tokens"], 140)
        self.assertEqual(len(self.sender.calls), 2)

    def test_journal_modified_during_post_cannot_report_success(self):
        def corrupt(url, body):
            if url == transport.GENERATION_URL:
                with self.ledger.path.open("ab") as stream:
                    stream.write(b"tampered")
        self.sender.before = corrupt
        with self.assertRaises(transport.BrokerFailure) as caught:
            self.complete()
        self.assertEqual(caught.exception.category, "journal_error")
        self.assertEqual(caught.exception.receipt["journal_integrity"], "failed")
        self.assertTrue((self.broker.evidence_dir / "C1.response.bin").exists())

    def test_six_initial_counts_plus_three_double_counts_equals_twelve(self):
        for index in range(6):
            self.broker.count(self.prepared, operation_id=f"initial-{index}", deadline_monotonic=time.monotonic() + 5)
        for index, cap in enumerate((4096, 4096, 64)):
            prepared = fictional_prepared(cap)
            count = self.broker.count(prepared, operation_id=f"C{index + 1}-client-count",
                                      deadline_monotonic=time.monotonic() + 5)
            self.broker.complete(prepared, operation_id=f"C{index + 1}", expected_input_tokens=count,
                                 deadline_monotonic=time.monotonic() + 5, expect_cap=cap == 64)
        snap = self.ledger.snapshot()
        self.assertEqual(snap["count_requests"], 12)
        self.assertEqual(snap["generation_requests"], 3)
        self.assertTrue(snap["complete"])
        self.assertEqual(len(self.sender.calls), 15)


class FakeHTTPResponse(io.BytesIO):
    def __init__(self, body=b"{}", status=200, headers=None):
        super().__init__(body)
        self.status = status
        self.headers = headers or {}


class CodecBrokerIntegrationTests(OfflineCase):
    """Unpatched real renderer/parser/journal; only upstream bytes are fake."""

    def setUp(self):
        super().setUp()
        self.prepared = transport.codec.prepare_request([
            {"role": "system", "content": "Use the identical frozen local tools."},
            {"role": "user", "content": "Inspect source; Unicode 中文 and escaping \\\"."},
        ], ACTION_SCHEMAS)
        self.ledger = self.journal()
        self.calls = []
        self.mutate = lambda value: None
        owner = self
        class Sender:
            def post(self, url, body, *, deadline_monotonic):
                owner.calls.append((url, body))
                if url == transport.COUNT_URL:
                    value = {"object": "response.input_tokens", "input_tokens": 123}
                else:
                    generation = json.loads(body)
                    value = {key: generation[key] for key in (
                        "model", "reasoning", "text", "parallel_tool_calls", "tool_choice", "tools",
                        "truncation", "background", "service_tier", "max_output_tokens")}
                    value["prompt_cache_options"] = {
                        "mode": "implicit", "ttl": "30m", "comparison_response_id": None,
                    }
                    cap = generation["max_output_tokens"] == 64
                    value.update(id="fictional-response", object="response", created_at=1_790_000_000,
                                 status="incomplete" if cap else "completed",
                                 incomplete_details={"reason": "max_output_tokens"} if cap else None,
                                 error=None, usage={"input_tokens": 123, "output_tokens": 17, "total_tokens": 140,
                                                   "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                                                   "output_tokens_details": {"reasoning_tokens": 7}},
                                 output=[{"type": "reasoning", "id": "fictional-rs", "summary": [],
                                          "encrypted_content": "FAKE-OPAQUE-STATE-NOT-PROVIDER-EVIDENCE"}])
                    if not cap:
                        value["output"].append({"type": "function_call", "id": "fictional-fc", "call_id": "fictional-call",
                                                "name": "list", "arguments": "{}", "status": "completed"})
                    serial = str(sum(url == transport.GENERATION_URL for url, _ in owner.calls))
                    value["id"] += serial
                    for item in value["output"]:
                        item["id"] += serial
                        if "call_id" in item:
                            item["call_id"] += serial
                    owner.mutate(value)
                return transport.PostResult(200, {}, encoded(value))
        self.broker = transport.CountedBroker(Sender(), self.ledger, self.root / "real-codec-fake-provider")

    def complete(self, prepared=None, opid="C1", expect_cap=False):
        return self.broker.complete(prepared or self.prepared, operation_id=opid,
                                    expected_input_tokens=123, deadline_monotonic=time.monotonic() + 5,
                                    expect_cap=expect_cap)

    def test_native_action_usage_and_exact_scientific_projection(self):
        observed = self.complete()
        self.assertEqual(observed["action"], {"action": "list"})
        self.assertEqual(observed["usage_details"]["reasoning_tokens"], 7)
        self.assertEqual(self.ledger.snapshot()["known_usage"]["output_tokens"], 17)
        counted, generated = (json.loads(call[1]) for call in self.calls)
        self.assertEqual(counted, {key: generated[key] for key in counted})
        self.assertEqual(self.calls[0][1], self.prepared.count_json.encode())
        self.assertEqual(self.calls[1][1], self.prepared.generation_json.encode())
        admitted = json.loads((self.root / "real-codec-fake-provider/C1.admission.json").read_bytes())
        self.assertGreater(admitted["admitted_unix_ns"], 0)
        self.assertEqual(admitted["endpoint"], transport.GENERATION_URL)
        self.assertEqual(admitted["request_sha256"], self.prepared.generation_sha256)

    def test_real_codec_wrong_model_retains_usage_and_suppresses_action(self):
        self.mutate = lambda value: value.update(model="wrong-fictional-model")
        with self.assertRaises(transport.BrokerFailure) as caught:
            self.complete()
        observation = caught.exception.receipt["observation"]
        self.assertIn("response_model_mismatch", observation["errors"])
        self.assertIsNone(observation["action"])
        self.assertEqual(self.ledger.snapshot()["known_usage"]["total_tokens"], 140)

    def test_real_c1_c2_stateless_continuation_and_last_cap(self):
        first = self.complete()
        continued = transport.codec.continuation_input(self.prepared, first, "frozen local result 中文")
        second = transport.codec.prepare_request(continued, ACTION_SCHEMAS)
        self.complete(second, "C2")
        cap = transport.codec.prepare_request([
            {"role": "system", "content": "Frozen cap probe; no tools."},
            {"role": "user", "content": "Produce the fixed long output."},
        ], ACTION_SCHEMAS, purpose="output_cap")
        result = self.complete(cap, "C3", expect_cap=True)
        self.assertTrue(result["cap_observed"])
        self.assertTrue(self.ledger.snapshot()["complete"])
        self.assertEqual(self.ledger.snapshot()["output_reserved"], 8256)
        self.assertEqual(json.loads(self.calls[2][1])["input"], continued)


class HTTPTransportTests(OfflineCase):
    def sender(self, responder):
        calls, keys = [], []
        def credential():
            keys.append("requested")
            return "fictional-test-credential"
        class Opener:
            def open(self, request, timeout):
                calls.append((request, timeout))
                return responder(request, timeout)
        return transport.SinglePostTransport(credential, opener=Opener()), calls, keys

    def test_lazy_credentials_exact_post_and_safe_headers(self):
        sender, calls, keys = self.sender(lambda *args: FakeHTTPResponse(b"original bytes", headers={
            "x-request-id": "test", "Authorization": "must-not-be-retained", "Set-Cookie": "private"}))
        self.assertEqual(keys, [])
        result = sender.post(transport.GENERATION_URL, b'{"input":"x"}', deadline_monotonic=time.monotonic() + 2)
        self.assertEqual(keys, ["requested"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0].method, "POST")
        self.assertEqual(calls[0][0].data, b'{"input":"x"}')
        self.assertEqual(result.body, b"original bytes")
        self.assertEqual(result.headers, {"x-request-id": "test"})

    def test_endpoint_whitelist_blocks_credentials_and_egress(self):
        sender, calls, keys = self.sender(lambda *args: FakeHTTPResponse())
        for url in ("https://api.openai.com.evil/v1/responses", "http://api.openai.com/v1/responses",
                    transport.GENERATION_URL + "?key=x", "https://api.openai.com/v1/chat/completions"):
            with self.assertRaises(transport.BrokerFailure):
                sender.post(url, b"{}", deadline_monotonic=time.monotonic() + 2)
        self.assertEqual((calls, keys), ([], []))

    def test_no_redirect_handler_and_original_http_error(self):
        self.assertIsNone(transport._NoRedirect().redirect_request(None, None, 302, "m", {}, "https://other"))
        def redirect(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 302, "Found", {"Location": "https://other"}, io.BytesIO(b"redirect"))
        sender, calls, _ = self.sender(redirect)
        result = sender.post(transport.COUNT_URL, b"{}", deadline_monotonic=time.monotonic() + 2)
        self.assertEqual(result.status, 302)
        self.assertEqual(result.body, b"redirect")
        self.assertEqual(len(calls), 1)

    def test_uncertain_error_sanitized_and_not_retried(self):
        def fail(*args):
            raise urllib.error.URLError("fictional-secret-in-reason")
        sender, calls, _ = self.sender(fail)
        with self.assertRaises(transport.BrokerFailure) as caught:
            sender.post(transport.COUNT_URL, b"{}", deadline_monotonic=time.monotonic() + 2)
        self.assertEqual(caught.exception.category, "transport_uncertain")
        self.assertNotIn("fictional-secret", str(caught.exception))
        self.assertEqual(len(calls), 1)

    def test_absolute_deadline_bounds_blocking_headers_without_retry(self):
        release = threading.Event()
        exited = threading.Event()
        def blocked(*args):
            try:
                release.wait(2)
                return FakeHTTPResponse()
            finally:
                exited.set()
        sender, calls, _ = self.sender(blocked)
        started = time.monotonic()
        try:
            with self.assertRaises(transport.BrokerFailure) as caught:
                sender.post(transport.COUNT_URL, b"{}", deadline_monotonic=started + 0.03)
            self.assertEqual(caught.exception.category, "transport_timeout")
            self.assertLess(time.monotonic() - started, 0.5)
            self.assertEqual(len(calls), 1)
        finally:
            release.set()
            exited.wait(1)

    def test_read_size_limit_and_request_size_limit(self):
        sender, calls, keys = self.sender(lambda *args: FakeHTTPResponse(b"x" * (transport.MAX_RESPONSE_BYTES + 1)))
        with self.assertRaises(transport.BrokerFailure) as caught:
            sender.post(transport.COUNT_URL, b"{}", deadline_monotonic=time.monotonic() + 2)
        self.assertEqual(caught.exception.category, "response_size")
        self.assertEqual(len(calls), 1)
        with self.assertRaises(transport.BrokerFailure):
            sender.post(transport.COUNT_URL, b"x" * (transport.MAX_REQUEST_BYTES + 1), deadline_monotonic=time.monotonic() + 2)
        self.assertEqual(len(keys), 1)


if __name__ == "__main__":
    unittest.main()
