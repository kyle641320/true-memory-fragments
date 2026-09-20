from __future__ import annotations

import hashlib
import json
import os
import socket
import tempfile
import unittest
from dataclasses import FrozenInstanceError, asdict, replace
from pathlib import Path
from unittest.mock import patch

from bench.agent_ab.same_version_chain_v1.m10_successor_token_budget import (
    TokenBudgetExceeded,
    TokenBudgetLedger,
    TokenLedgerError,
    TokenLedgerHalted,
    TokenLedgerLocked,
    TokenLimits,
    TokenSettlementError,
    TokenUsage,
)


LIMITS = TokenLimits(input_per_turn=10, output_per_turn=6, context_window=16,
                     total_input=20, total_output=12, max_calls=2)
REQUEST_HASH = hashlib.sha256(b"immutable contract and provider request").hexdigest()


class M10SuccessorTokenBudgetTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / "budget.jsonl"

    def open(self, limits=LIMITS, path=None):
        ledger = TokenBudgetLedger(self.path if path is None else path, limits)
        self.addCleanup(ledger.close)
        return ledger

    @staticmethod
    def reserve(ledger, call_id="call-1", input_tokens=10, output_tokens=6):
        return ledger.reserve(call_id, request_sha256=REQUEST_HASH,
                              input_tokens=input_tokens, max_output_tokens=output_tokens)

    def events(self):
        return [json.loads(line) for line in self.path.read_bytes().splitlines()]

    def write_rehashed(self, events):
        """Build structurally intact adversarial histories for replay checks."""
        previous = "0" * 64
        lines = []
        for index, event in enumerate(events):
            body = {k: v for k, v in event.items() if k != "sha256"}
            body.update(seq=index, prev_sha256=previous)
            encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
            previous = hashlib.sha256(encoded).hexdigest()
            lines.append(json.dumps({**body, "sha256": previous}, sort_keys=True,
                                    separators=(",", ":")).encode() + b"\n")
        self.path.write_bytes(b"".join(lines))

    def test_limits_are_explicit_strict_positive_integers(self):
        with self.assertRaises(TypeError):
            TokenLimits()
        for field in asdict(LIMITS):
            for invalid in (0, -1, True, False, 1.0, "1", None):
                with self.subTest(field=field, invalid=invalid):
                    with self.assertRaises(ValueError):
                        replace(LIMITS, **{field: invalid})
        LIMITS.validate()
        ledger = self.open()
        self.assertEqual(LIMITS, ledger.limits)
        with self.assertRaises(AttributeError):
            ledger.limits = replace(LIMITS, max_calls=3)
        with self.assertRaises(FrozenInstanceError):
            ledger.limits.max_calls = 3

    def test_usage_requires_nonnegative_counts_and_exact_sum(self):
        self.assertEqual(TokenUsage(0, 0, 0), TokenUsage.from_mapping({
            "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
        }))
        for field in ("input_tokens", "output_tokens", "total_tokens"):
            for invalid in (-1, True, False, 1.0, "1", None):
                with self.subTest(field=field, invalid=invalid):
                    values = {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}
                    values[field] = invalid
                    with self.assertRaises(ValueError):
                        TokenUsage(**values)
        with self.assertRaises(ValueError):
            TokenUsage(2, 3, 4)

    def test_all_exact_limits_are_allowed_and_accounted_without_network(self):
        with patch.object(socket, "socket", side_effect=AssertionError("network forbidden")):
            ledger = self.open()
            for call_id in ("first", "second"):
                self.reserve(ledger, call_id)
                result = ledger.settle(call_id, usage=TokenUsage(10, 6, 16))
                self.assertEqual("completed", result["status"])
            summary = ledger.snapshot()
        self.assertEqual(2, summary["admitted_calls"])
        self.assertEqual(20, summary["charged_input_tokens"])
        self.assertEqual(12, summary["charged_output_tokens"])
        self.assertEqual(32, summary["charged_total_tokens"])
        self.assertEqual({"input_tokens": 20, "output_tokens": 12, "total_tokens": 32},
                         summary["provider_usage"])
        self.assertFalse(summary["halted"])
        self.assertTrue(all(record["itt_included"] for record in summary["records"]))

    def test_per_turn_and_combined_context_rejections_do_not_admit(self):
        cases = [
            (LIMITS, 11, 1, "input_per_turn"),
            (LIMITS, 1, 7, "output_per_turn"),
            (replace(LIMITS, context_window=15), 10, 6, "context_window"),
        ]
        for index, (limits, input_tokens, output_tokens, reason) in enumerate(cases):
            with self.subTest(reason=reason):
                path = self.root / f"gate-{index}.jsonl"
                ledger = self.open(limits, path)
                before = path.read_bytes()
                with self.assertRaisesRegex(TokenBudgetExceeded, reason):
                    self.reserve(ledger, input_tokens=input_tokens, output_tokens=output_tokens)
                self.assertEqual(before, path.read_bytes())
                self.assertEqual(0, ledger.snapshot()["admitted_calls"])

    def test_each_cumulative_cap_and_max_calls_reject_before_journaling(self):
        cases = [
            (replace(LIMITS, total_input=19), "total_input"),
            (replace(LIMITS, total_output=11), "total_output"),
            (replace(LIMITS, total_input=30, total_output=18, max_calls=1), "max_calls"),
        ]
        for index, (limits, reason) in enumerate(cases):
            with self.subTest(reason=reason):
                path = self.root / f"cumulative-{index}.jsonl"
                ledger = self.open(limits, path)
                self.reserve(ledger)
                ledger.settle("call-1", usage=TokenUsage(10, 6, 16))
                before, summary = path.read_bytes(), ledger.snapshot()
                with self.assertRaisesRegex(TokenBudgetExceeded, reason):
                    self.reserve(ledger, "call-2")
                self.assertEqual(before, path.read_bytes())
                self.assertEqual(summary, ledger.snapshot())

    def test_untaken_output_capacity_can_only_be_released_by_valid_settlement(self):
        ledger = self.open(replace(LIMITS, total_output=6))
        self.reserve(ledger)
        self.assertIsNone(ledger.snapshot()["provider_usage"])
        with self.assertRaises(TokenLedgerHalted):
            self.reserve(ledger, "call-2", input_tokens=1, output_tokens=1)
        ledger.settle("call-1", usage=TokenUsage(10, 0, 10))
        self.reserve(ledger, "call-2")
        ledger.settle("call-2", usage=TokenUsage(10, 6, 16))
        self.assertEqual(6, ledger.snapshot()["charged_output_tokens"])
        self.assertEqual(2, ledger.snapshot()["admitted_calls"])

    def test_zero_exact_input_is_valid_but_output_reservation_must_be_positive(self):
        ledger = self.open()
        before = self.path.read_bytes()
        for invalid in (0, -1, True, 1.0, "1", None):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.reserve(ledger, input_tokens=0, output_tokens=invalid)
        self.assertEqual(before, self.path.read_bytes())
        self.reserve(ledger, input_tokens=0, output_tokens=1)
        ledger.settle("call-1", usage=TokenUsage(0, 0, 0))
        self.assertEqual(0, ledger.snapshot()["charged_total_tokens"])

    def test_invalid_input_ids_and_digests_do_not_change_accounting(self):
        ledger = self.open()
        before, snapshot = self.path.read_bytes(), ledger.snapshot()
        for invalid in (-1, True, 1.0, "1", None):
            with self.subTest(input=invalid), self.assertRaises(ValueError):
                self.reserve(ledger, input_tokens=invalid)
        for invalid in ("", "a" * 129, "contains space", None, True):
            with self.subTest(call_id=invalid), self.assertRaises(ValueError):
                self.reserve(ledger, call_id=invalid)
        for invalid in ("", "a" * 63, "a" * 65, "A" * 64, "z" * 64, None):
            with self.subTest(digest=invalid), self.assertRaises(ValueError):
                ledger.reserve("call-1", input_tokens=10, max_output_tokens=6,
                               request_sha256=invalid)
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(snapshot, ledger.snapshot())

    def test_admission_fsync_precedes_return_and_file_is_append_only(self):
        ledger = self.open()
        initialized = self.path.read_bytes()
        original_fsync = os.fsync
        witnessed = []

        def witness(fd):
            witnessed.append(self.events()[-1]["event"])
            original_fsync(fd)

        with patch.object(os, "fsync", side_effect=witness):
            reservation = self.reserve(ledger)
            self.assertEqual(["admitted"], witnessed)
            admitted = self.path.read_bytes()
            ledger.settle("call-1", usage=TokenUsage(10, 2, 12))
            self.assertEqual(["admitted", "completed"], witnessed)
        self.assertEqual(REQUEST_HASH, reservation.request_sha256)
        self.assertTrue(admitted.startswith(initialized))
        self.assertTrue(self.path.read_bytes().startswith(admitted))
        self.assertEqual(["limits", "admitted", "completed"],
                         [event["event"] for event in self.events()])
        self.assertEqual(REQUEST_HASH, self.events()[1]["request_sha256"])
        self.assertTrue(self.events()[1]["itt_included"])

    def test_duplicate_retry_and_out_of_order_settlements_never_change_journal(self):
        ledger = self.open()
        self.reserve(ledger)
        before, snapshot = self.path.read_bytes(), ledger.snapshot()
        with self.assertRaises(TokenSettlementError):
            ledger.settle("different-call", usage=TokenUsage(10, 6, 16))
        with self.assertRaises(TokenSettlementError):
            self.reserve(ledger)
        with self.assertRaises(ValueError):
            ledger.settle("call-1", usage=TokenUsage(10, 6, 16), outcome="retry")
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(snapshot, ledger.snapshot())
        ledger.settle("call-1", usage=TokenUsage(10, 1, 11))
        before, snapshot = self.path.read_bytes(), ledger.snapshot()
        with self.assertRaises(TokenSettlementError):
            ledger.settle("call-1", usage=TokenUsage(10, 0, 10))
        with self.assertRaises(TokenSettlementError):
            self.reserve(ledger)
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(snapshot, ledger.snapshot())

    def test_malformed_missing_usage_remains_unknown_and_fully_charged(self):
        invalid_usages = [
            None, {}, [], "tokens", {"input_tokens": 10, "output_tokens": 0},
            {"input_tokens": True, "output_tokens": 0, "total_tokens": 1},
            {"input_tokens": 10, "output_tokens": -1, "total_tokens": 9},
            {"input_tokens": 10, "output_tokens": 0.0, "total_tokens": 10},
            {"input_tokens": 10, "output_tokens": 2, "total_tokens": 11},
            {"input_tokens": 10, "output_tokens": 0, "total_tokens": 10, "cached": 5},
        ]
        for index, usage in enumerate(invalid_usages):
            with self.subTest(usage=usage):
                ledger = self.open(path=self.root / f"unknown-{index}.jsonl")
                self.reserve(ledger)
                record = ledger.settle("call-1", usage=usage)
                self.assertEqual("unknown", record["status"])
                self.assertIsNone(record["provider_usage"])
                summary = ledger.snapshot()
                self.assertIsNone(summary["provider_usage"])
                self.assertEqual(1, summary["unknown_usage_calls"])
                self.assertEqual(10, summary["charged_input_tokens"])
                self.assertEqual(6, summary["charged_output_tokens"])
                self.assertTrue(summary["halted"])
                self.assertTrue(record["itt_included"])
                with self.assertRaises(TokenLedgerHalted):
                    self.reserve(ledger, "retry")

    def test_unknown_or_timeout_does_not_turn_even_supplied_counts_into_known_usage(self):
        for outcome in ("unknown", "timeout"):
            with self.subTest(outcome=outcome):
                path = self.root / f"{outcome}.jsonl"
                ledger = self.open(path=path)
                self.reserve(ledger)
                record = ledger.settle("call-1", usage=TokenUsage(10, 0, 10), outcome=outcome)
                self.assertEqual("unknown", record["status"])
                self.assertIsNone(record["provider_usage"])
                self.assertEqual(16, ledger.snapshot()["charged_total_tokens"])
                before = ledger.snapshot()
                ledger.close()
                recovered = self.open(path=path)
                self.assertEqual(before, recovered.snapshot())
                with self.assertRaises(TokenLedgerHalted):
                    self.reserve(recovered, "retry")

    def test_known_failed_response_is_counted_and_terminal(self):
        ledger = self.open()
        self.reserve(ledger)
        result = ledger.settle("call-1", usage=TokenUsage(10, 2, 12), outcome="error")
        self.assertEqual("failed", result["status"])
        self.assertEqual(asdict(TokenUsage(10, 2, 12)), result["provider_usage"])
        self.assertEqual(12, ledger.snapshot()["charged_total_tokens"])
        self.assertTrue(ledger.snapshot()["halted"])
        self.assertEqual(0, ledger.snapshot()["unknown_usage_calls"])
        with self.assertRaises(TokenLedgerHalted):
            self.reserve(ledger, "retry")

    def test_error_without_usage_does_not_invent_zero(self):
        ledger = self.open()
        self.reserve(ledger)
        result = ledger.settle("call-1", usage=None, outcome="error")
        self.assertEqual("unknown", result["status"])
        self.assertIsNone(result["provider_usage"])
        self.assertEqual(16, ledger.snapshot()["charged_total_tokens"])

    def test_valid_count_mismatch_keeps_max_reservation_observation_and_halts(self):
        cases = [(9, 2, 10, 6), (11, 2, 11, 6), (10, 7, 10, 7), (30, 30, 30, 30)]
        for index, (input_tokens, output_tokens, charged_input, charged_output) in enumerate(cases):
            with self.subTest(input=input_tokens, output=output_tokens):
                path = self.root / f"mismatch-{index}.jsonl"
                ledger = self.open(path=path)
                self.reserve(ledger)
                usage = TokenUsage(input_tokens, output_tokens, input_tokens + output_tokens)
                result = ledger.settle("call-1", usage=usage)
                self.assertEqual("usage_mismatch", result["status"])
                self.assertEqual(asdict(usage), result["provider_usage"])
                self.assertEqual(charged_input, result["charged_input_tokens"])
                self.assertEqual(charged_output, result["charged_output_tokens"])
                self.assertTrue(ledger.snapshot()["halted"])
                before = ledger.snapshot()
                ledger.close()
                recovered = self.open(path=path)
                self.assertEqual(before, recovered.snapshot())
                with self.assertRaises(TokenLedgerHalted):
                    self.reserve(recovered, "retry")

    def test_verified_success_reopens_with_same_limits_and_recovered_totals(self):
        ledger = self.open()
        self.reserve(ledger)
        ledger.settle("call-1", usage=TokenUsage(10, 3, 13))
        before = ledger.snapshot()
        ledger.close()
        recovered = self.open()
        self.assertEqual(before, recovered.snapshot())
        self.reserve(recovered, "call-2")
        recovered.settle("call-2", usage=TokenUsage(10, 6, 16))
        self.assertEqual(29, recovered.snapshot()["charged_total_tokens"])

    def test_crash_pending_reservation_is_unknown_and_cannot_be_refunded_or_retried(self):
        ledger = self.open()
        self.reserve(ledger)
        before = self.path.read_bytes()
        ledger.close()  # The durable disk state is identical after a process crash.
        recovered = self.open()
        summary = recovered.snapshot()
        self.assertEqual(1, summary["admitted_calls"])
        self.assertEqual(16, summary["charged_total_tokens"])
        self.assertIsNone(summary["provider_usage"])
        self.assertEqual("unknown", summary["records"][0]["status"])
        self.assertTrue(summary["records"][0]["itt_included"])
        self.assertTrue(summary["halted"])
        with self.assertRaises(TokenLedgerHalted):
            self.reserve(recovered, "retry")
        with self.assertRaises(TokenLedgerHalted):
            recovered.settle("call-1", usage=TokenUsage(10, 0, 10))
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(summary, recovered.snapshot())

    def test_nonblocking_single_owner_lock_and_release(self):
        ledger = self.open()
        before = self.path.read_bytes()
        with self.assertRaises(TokenLedgerLocked):
            TokenBudgetLedger(self.path, LIMITS)
        self.assertEqual(before, self.path.read_bytes())
        ledger.close()
        recovered = self.open()
        self.assertEqual(0, recovered.snapshot()["admitted_calls"])

    def test_different_limits_reopening_are_rejected_without_rewriting(self):
        ledger = self.open()
        ledger.close()
        before = self.path.read_bytes()
        with self.assertRaises(TokenLedgerError):
            TokenBudgetLedger(self.path, replace(LIMITS, max_calls=3))
        self.assertEqual(before, self.path.read_bytes())

    def test_truncated_empty_and_malformed_journals_fail_closed_without_repair(self):
        ledger = self.open()
        self.reserve(ledger)
        ledger.close()
        original = self.path.read_bytes()
        cases = [b"", original[:-1], original + b'{"event":', original + b"\n",
                 original + b"not json\n", original + b"{\"event\":NaN}\n",
                 original + b'{"event":"one","event":"two"}\n']
        for data in cases:
            with self.subTest(tail=data[-40:]):
                self.path.write_bytes(data)
                with self.assertRaises(TokenLedgerError):
                    TokenBudgetLedger(self.path, LIMITS)
                self.assertEqual(data, self.path.read_bytes())

    def test_changed_count_without_valid_hash_is_rejected_on_reopen(self):
        ledger = self.open()
        self.reserve(ledger)
        ledger.close()
        changed = self.path.read_bytes().replace(b'"input_tokens":10', b'"input_tokens":11')
        self.path.write_bytes(changed)
        with self.assertRaises(TokenLedgerError):
            TokenBudgetLedger(self.path, LIMITS)
        self.assertEqual(changed, self.path.read_bytes())

    def test_structurally_rehashed_but_invalid_histories_are_rejected(self):
        ledger = self.open()
        self.reserve(ledger)
        ledger.settle("call-1", usage=TokenUsage(10, 6, 16))
        ledger.close()
        header, admission, completion = self.events()
        cases = [
            [header, completion],
            [header, admission, admission],
            [header, admission, completion, completion],
            [header, admission, completion, admission],
            [header, {**admission, "itt_included": False}],
            [header, {**admission, "input_tokens": True}],
            [header, {**admission, "max_output_tokens": 7}],
            [header, admission, {**completion, "call_id": "wrong"}],
            [header, admission, {**completion, "usage": {"input_tokens": 10, "output_tokens": 1, "total_tokens": 99}}],
            [header, admission, {**completion, "outcome": "unknown"}],
            [header, admission, {**completion, "usage": None, "usage_error": "missing_usage"},
             {**admission, "call_id": "retry"}],
        ]
        for index, events in enumerate(cases):
            with self.subTest(case=index):
                self.write_rehashed(events)
                before = self.path.read_bytes()
                with self.assertRaises(TokenLedgerError):
                    TokenBudgetLedger(self.path, LIMITS)
                self.assertEqual(before, self.path.read_bytes())

    def test_tampering_while_owned_halts_before_a_new_admission(self):
        ledger = self.open()
        self.reserve(ledger)
        ledger.settle("call-1", usage=TokenUsage(10, 0, 10))
        data = self.path.read_bytes().replace(b'"input_tokens":10', b'"input_tokens":11')
        self.path.write_bytes(data)
        with self.assertRaises(TokenLedgerError):
            self.reserve(ledger, "call-2")
        self.assertEqual(data, self.path.read_bytes())
        self.assertTrue(ledger.snapshot()["halted"])
        self.assertEqual(1, ledger.snapshot()["admitted_calls"])

    def test_snapshot_immediately_detects_corruption_without_certifying_accounting(self):
        ledger = self.open()
        self.reserve(ledger)
        ledger.settle("call-1", usage=TokenUsage(10, 2, 12))
        self.assertTrue(ledger.snapshot()["journal_integrity_verified"])
        self.path.write_bytes(self.path.read_bytes()[:-1])
        snapshot = ledger.snapshot()
        self.assertTrue(snapshot["halted"])
        self.assertFalse(snapshot["journal_integrity_verified"])
        self.assertEqual("journal_changed", snapshot["halt_reason"])
        self.assertEqual(12, snapshot["charged_total_tokens"])
        with self.assertRaises(TokenLedgerError):
            self.reserve(ledger, "call-2")

    def test_replaced_path_cannot_bypass_existing_owner_lock(self):
        ledger = self.open()
        self.path.rename(self.root / "moved.jsonl")
        self.path.write_bytes(b"")
        with self.assertRaises(TokenLedgerError):
            self.reserve(ledger)
        self.assertEqual(b"", self.path.read_bytes())
        self.assertEqual(0, ledger.snapshot()["admitted_calls"])

    def test_symlink_and_nonregular_file_are_rejected(self):
        target = self.root / "target.jsonl"
        target.write_text("keep", encoding="utf-8")
        self.path.symlink_to(target)
        with self.assertRaises(TokenLedgerError):
            TokenBudgetLedger(self.path, LIMITS)
        self.assertEqual("keep", target.read_text(encoding="utf-8"))
        with self.assertRaises(TokenLedgerError):
            TokenBudgetLedger(self.root, LIMITS)

    def test_closed_or_fork_inherited_handle_cannot_admit(self):
        ledger = self.open()
        with patch.object(os, "getpid", return_value=os.getpid() + 1):
            with self.assertRaises(TokenLedgerError):
                self.reserve(ledger)
        ledger.close()
        with self.assertRaises(TokenLedgerError):
            self.reserve(ledger)

    def test_admission_fsync_failure_never_returns_dispatch_permit(self):
        ledger = self.open()
        with patch.object(os, "fsync", side_effect=OSError("simulated disk failure")):
            with self.assertRaises(TokenLedgerError):
                self.reserve(ledger)
        summary = ledger.snapshot()
        self.assertTrue(summary["halted"])
        self.assertFalse(summary["journal_integrity_verified"])
        self.assertEqual("journal_write_failed", summary["halt_reason"])
        self.assertEqual(16, summary["charged_total_tokens"])
        self.assertIsNone(summary["provider_usage"])
        ledger.close()
        recovered = self.open()
        self.assertTrue(recovered.snapshot()["halted"])
        self.assertIsNone(recovered.snapshot()["provider_usage"])

    def test_partial_admission_write_is_preserved_and_reopen_fails_closed(self):
        ledger = self.open()
        before = self.path.read_bytes()
        original_write = os.write
        writes = 0

        def partial(fd, data):
            nonlocal writes
            writes += 1
            if writes == 1:
                return original_write(fd, data[:10])
            raise OSError("simulated partial write")

        with patch.object(os, "write", side_effect=partial):
            with self.assertRaises(TokenLedgerError):
                self.reserve(ledger)
        damaged = self.path.read_bytes()
        self.assertTrue(damaged.startswith(before))
        self.assertEqual(len(before) + 10, len(damaged))
        self.assertEqual(16, ledger.snapshot()["charged_total_tokens"])
        ledger.close()
        with self.assertRaises(TokenLedgerError):
            TokenBudgetLedger(self.path, LIMITS)
        self.assertEqual(damaged, self.path.read_bytes())

    def test_failed_completion_durability_cannot_release_capacity(self):
        for index, usage in enumerate((TokenUsage(10, 0, 10), TokenUsage(11, 7, 18))):
            with self.subTest(usage=usage):
                ledger = self.open(path=self.root / f"completion-io-{index}.jsonl")
                self.reserve(ledger)
                with patch.object(os, "fsync", side_effect=OSError("simulated fsync failure")):
                    with self.assertRaises(TokenLedgerError):
                        ledger.settle("call-1", usage=usage)
                summary = ledger.snapshot()
                self.assertTrue(summary["halted"])
                self.assertIsNone(summary["provider_usage"])
                self.assertEqual(max(10, usage.input_tokens), summary["charged_input_tokens"])
                self.assertEqual(max(6, usage.output_tokens), summary["charged_output_tokens"])

    def test_readback_failure_after_completion_fsync_retains_observed_overcount(self):
        ledger = self.open()
        self.reserve(ledger)
        original_fsync = os.fsync
        original_read = os.read
        synced = False

        def synced_fsync(fd):
            nonlocal synced
            original_fsync(fd)
            synced = True

        def failed_readback(fd, size):
            if synced:
                raise OSError("read failed after fsync")
            return original_read(fd, size)

        with patch.object(os, "fsync", side_effect=synced_fsync), \
                patch.object(os, "read", side_effect=failed_readback):
            with self.assertRaises(TokenLedgerError):
                ledger.settle("call-1", usage=TokenUsage(11, 7, 18))
        snapshot = ledger.snapshot()
        self.assertTrue(snapshot["halted"])
        self.assertFalse(snapshot["journal_integrity_verified"])
        self.assertEqual(18, snapshot["charged_total_tokens"])
        self.assertIsNone(snapshot["provider_usage"])

    def test_returned_records_and_snapshots_cannot_change_internal_state(self):
        ledger = self.open()
        self.reserve(ledger)
        record = ledger.settle("call-1", usage={"input_tokens": 10, "output_tokens": 1, "total_tokens": 11})
        before = ledger.snapshot()
        record["provider_usage"]["input_tokens"] = 0
        record["reservation"]["input_tokens"] = 0
        changed = ledger.snapshot()
        changed["records"][0]["charged_input_tokens"] = 0
        self.assertEqual(before, ledger.snapshot())


if __name__ == "__main__":
    unittest.main()
