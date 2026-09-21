from __future__ import annotations

import copy
import hashlib
import json
import os
import stat
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from bench.agent_ab.same_version_chain_v1 import m10_successor_run_ledger as journal
from bench.agent_ab.same_version_chain_v1.m10_successor_protocol import RunRecord, aggregate_itt
from bench.agent_ab.same_version_chain_v1.m10_successor_run_ledger import (
    EVIDENCE_KIND,
    RunAdmissionLedger,
    RunLedgerError,
    RunLedgerHalted,
    RunLedgerLocked,
    RunLedgerTransitionError,
    ledger_policy,
)


SEAL = "a" * 64
RUN_IDS = ("first", "second", "third")


def completed(run_id="first", **changes):
    row = asdict(RunRecord(
        run_id=run_id, seal_sha256=SEAL, evidence_kind=EVIDENCE_KIND,
        durable_ledger=True, protocol_status="completed", protocol_ok=True,
        final_received=True, semantic={"semantic_pass": True}, compilation={"ok": True},
    ))
    row.update(changes)
    return row


class M10SuccessorRunLedgerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / "runs.jsonl"

    def open(self, run_ids=RUN_IDS, seal=SEAL, path=None):
        ledger = RunAdmissionLedger(self.path if path is None else path, seal, run_ids)
        self.addCleanup(ledger.close)
        return ledger

    def events(self):
        return [json.loads(line) for line in self.path.read_bytes().splitlines()]

    def write_rehashed(self, events):
        previous, lines = "0" * 64, []
        for index, event in enumerate(events):
            body = {key: value for key, value in event.items() if key != "sha256"}
            body.update(seq=index, prev_sha256=previous)
            encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("ascii")
            previous = hashlib.sha256(encoded).hexdigest()
            lines.append(json.dumps({**body, "sha256": previous}, sort_keys=True,
                                    separators=(",", ":")).encode("ascii") + b"\n")
        self.path.write_bytes(b"".join(lines))

    def test_complete_schedule_is_atomic_fsynced_admission_before_constructor_returns(self):
        original_fsync, original_link = os.fsync, os.link
        calls = []

        def fsync(fd):
            kind = "directory" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file"
            calls.append(kind)
            if kind == "file":
                self.assertFalse(self.path.exists())
            else:
                self.assertEqual(list(RUN_IDS), self.events()[0]["run_ids"])
            original_fsync(fd)

        def link(source, target, **kwargs):
            self.assertEqual(["file"], calls)
            pending = [json.loads(line) for line in Path(source).read_bytes().splitlines()]
            self.assertEqual(1, len(pending))
            self.assertEqual(list(RUN_IDS), pending[0]["run_ids"])
            original_link(source, target, **kwargs)
            calls.append("publish")

        with patch.object(os, "fsync", side_effect=fsync), patch.object(os, "link", side_effect=link):
            ledger = self.open()
        self.assertEqual(["file", "publish", "directory"], calls)
        self.assertEqual(0o600, self.path.stat().st_mode & 0o777)
        self.assertEqual([self.path], list(self.root.iterdir()))
        snapshot = ledger.snapshot()
        self.assertTrue(snapshot["journal_integrity_verified"])
        self.assertEqual(3, snapshot["admitted_runs"])
        self.assertEqual(0, snapshot["started_runs"])
        self.assertEqual(3, aggregate_itt(ledger.records())["denominator"])

    def test_schedule_and_seal_are_validated_before_creating_any_file(self):
        invalid_schedules = ([], "one", ("duplicate", "duplicate"), ("bad id",),
                             ("a" * 129,), (1,), tuple(str(i) for i in range(6001)))
        for ids in invalid_schedules:
            with self.subTest(ids=str(ids)[:50]), self.assertRaises(ValueError):
                self.open(run_ids=ids)
            self.assertEqual([], list(self.root.iterdir()))
        for value in (None, "", "A" * 64, "a" * 63, True):
            with self.subTest(seal=value), self.assertRaises(ValueError):
                self.open(seal=value)
            self.assertEqual([], list(self.root.iterdir()))

    def test_initial_write_failure_publishes_no_partial_schedule(self):
        with patch.object(os, "fsync", side_effect=OSError("disk failure")):
            with self.assertRaises(RunLedgerError):
                self.open()
        self.assertFalse(self.path.exists())
        self.assertEqual([], list(self.root.iterdir()))

    def test_directory_fsync_failure_leaves_entire_inspectable_schedule_without_execution(self):
        original = os.fsync

        def failed(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError("directory durability uncertain")
            return original(fd)

        with patch.object(os, "fsync", side_effect=failed), self.assertRaises(RunLedgerError):
            self.open()
        with self.open() as recovered:
            self.assertTrue(recovered.snapshot()["inspection_only"])
            self.assertEqual(list(RUN_IDS), [row["run_id"] for row in recovered.records()])
            self.assertTrue(all(row["protocol_ok"] is False for row in recovered.records()))

    def test_constructor_interruption_releases_ownership_of_published_batch(self):
        original = os.fsync

        def interrupted(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise KeyboardInterrupt("stop after atomic publication")
            return original(fd)

        with patch.object(os, "fsync", side_effect=interrupted), self.assertRaises(KeyboardInterrupt):
            self.open()
        with self.open() as recovered:
            self.assertEqual(3, recovered.snapshot()["denominator"])
            self.assertTrue(recovered.snapshot()["inspection_only"])

    def test_fsynced_ordered_start_and_terminal_failure_keep_append_only_itt(self):
        ledger = self.open()
        original = os.fsync
        observed = []

        def fsync(fd):
            observed.append(self.events()[-1]["event"])
            original(fd)

        initial = self.path.read_bytes()
        with patch.object(os, "fsync", side_effect=fsync):
            ledger.start("first")
            self.assertEqual(["started"], observed)
            started = self.path.read_bytes()
            ledger.complete(completed(protocol_status="failed", protocol_ok=False,
                                      failure_reason="adapter_timeout", final_received=False))
        self.assertEqual(["started", "completed"], observed)
        self.assertTrue(started.startswith(initial))
        self.assertTrue(self.path.read_bytes().startswith(started))
        rows = ledger.records()
        self.assertEqual(list(RUN_IDS), [row["run_id"] for row in rows])
        self.assertEqual(["completed", "not_started", "not_started"],
                         [row["run_ledger_state"] for row in rows])
        self.assertEqual(3, aggregate_itt(rows)["denominator"])
        self.assertEqual(0, aggregate_itt(rows)["joint_success"])
        self.assertEqual(1, aggregate_itt(rows)["semantic_pass"])

    def test_reopen_is_inspection_only_with_completed_interrupted_and_not_started(self):
        ledger = self.open()
        ledger.start("first")
        ledger.complete(completed())
        ledger.start("second")
        ledger.close()
        reopened = self.open()
        rows = reopened.records()
        self.assertEqual(["completed", "started", "not_started"],
                         [row["run_ledger_state"] for row in rows])
        self.assertEqual([None, "missing_completion_record", "not_started_after_batch_admission"],
                         [row["failure_reason"] for row in rows])
        for row in rows:
            self.assertIs(row["admitted"], True)
            self.assertIs(row["itt_included"], True)
            self.assertIs(row["durable_ledger"], True)
            self.assertEqual(SEAL, row["seal_sha256"])
            self.assertEqual(EVIDENCE_KIND, row["evidence_kind"])
        before = self.path.read_bytes()
        for run_id in RUN_IDS:
            with self.subTest(run_id=run_id):
                with self.assertRaises(RunLedgerHalted):
                    reopened.start(run_id)
                with self.assertRaises(RunLedgerHalted):
                    reopened.complete(completed(run_id))
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(3, aggregate_itt(rows)["denominator"])
        self.assertEqual(1, aggregate_itt(rows)["joint_success"])

    def test_even_empty_progress_or_all_completed_reopen_cannot_execute(self):
        for finished in (False, True):
            with self.subTest(finished=finished):
                path = self.root / f"reopen-{finished}.jsonl"
                ledger = self.open(run_ids=("first",), path=path)
                if finished:
                    ledger.start("first")
                    ledger.complete(completed())
                ledger.close()
                reopened = self.open(run_ids=("first",), path=path)
                with self.assertRaises(RunLedgerHalted):
                    reopened.start("first")

    def test_no_duplicate_out_of_order_unknown_or_unstarted_completions(self):
        ledger = self.open()
        before = self.path.read_bytes()
        for run_id in ("second", "unknown", True):
            with self.subTest(run_id=run_id), self.assertRaises(RunLedgerTransitionError):
                ledger.start(run_id)
        with self.assertRaises(RunLedgerTransitionError):
            ledger.complete(completed())
        self.assertEqual(before, self.path.read_bytes())
        ledger.start("first")
        before = self.path.read_bytes()
        for run_id in ("first", "second"):
            with self.assertRaises(RunLedgerTransitionError):
                ledger.start(run_id)
        with self.assertRaises(RunLedgerTransitionError):
            ledger.complete(completed("second"))
        self.assertEqual(before, self.path.read_bytes())
        ledger.complete(completed())
        before = self.path.read_bytes()
        with self.assertRaises(RunLedgerTransitionError):
            ledger.complete(completed())
        with self.assertRaises(RunLedgerTransitionError):
            ledger.start("first")
        self.assertEqual(before, self.path.read_bytes())

    def test_completion_must_match_offline_identity_and_itt(self):
        ledger = self.open()
        ledger.start("first")
        before = self.path.read_bytes()
        changes = [
            {"run_id": "foreign"}, {"seal_sha256": "b" * 64},
            {"evidence_kind": "offline_scripted_protocol_rehearsal"},
            {"admitted": False}, {"admitted": 1}, {"itt_included": False},
            {"durable_ledger": False}, {"model_execution_enabled": True},
            {"model_pilot_admitted": True}, {"provider_token_limits_verified": True},
            {"protocol_ok": 1}, {"protocol_status": "failed"},
            {"final_received": False}, {"failure_reason": "still reports success"},
            {"semantic": {"semantic_pass": 1}}, {"compilation": {"ok": "true"}},
            {"protocol_status": "failed", "protocol_ok": False, "failure_reason": None},
        ]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(RunLedgerTransitionError):
                ledger.complete(completed(**change))
            self.assertEqual(before, self.path.read_bytes())
        ledger.complete(completed())

    def test_result_and_snapshot_are_detached_from_caller_mutation(self):
        ledger = self.open()
        ledger.start("first")
        row = completed()
        ledger.complete(row)
        row["semantic"]["semantic_pass"] = False
        rows = ledger.records()
        rows[0]["semantic"]["semantic_pass"] = False
        ledger.snapshot()["run_ids"].clear()
        self.assertTrue(ledger.records()[0]["semantic"]["semantic_pass"])
        self.assertEqual(3, ledger.snapshot()["denominator"])

    def test_failed_start_write_forbids_progress_and_keeps_all_planned_runs(self):
        ledger = self.open()
        with patch.object(os, "write", return_value=0), self.assertRaises(RunLedgerError):
            ledger.start("first")
        snapshot = ledger.snapshot()
        self.assertFalse(snapshot["journal_integrity_verified"])
        self.assertEqual(3, snapshot["denominator"])
        self.assertEqual(0, snapshot["started_runs"])
        self.assertTrue(all(row["protocol_ok"] is False for row in snapshot["records"]))
        with self.assertRaises(RunLedgerHalted):
            ledger.start("first")

    def test_failed_completion_fsync_preserves_pending_failure_not_success(self):
        ledger = self.open()
        ledger.start("first")
        with patch.object(os, "fsync", side_effect=OSError("disk full")):
            with self.assertRaises(RunLedgerError):
                ledger.complete(completed())
        snapshot = ledger.snapshot()
        self.assertFalse(snapshot["journal_integrity_verified"])
        self.assertEqual("first", snapshot["pending_run_id"])
        self.assertEqual(0, snapshot["completed_runs"])
        self.assertEqual(3, aggregate_itt(snapshot["records"])["denominator"])
        self.assertEqual(0, aggregate_itt(snapshot["records"])["joint_success"])
        with self.assertRaises(RunLedgerError):
            ledger.start("second")

    def test_partial_write_and_same_size_corruption_are_not_silently_replayed(self):
        ledger = self.open()
        ledger.start("first")
        ledger.close()
        original = self.path.read_bytes()
        corruptions = (b"", original[:-1], original + b'{"partial":',
                       original.replace(b'"started"', b'"starteD"', 1),
                       original.replace(b'"event":', b'"event":"started","event":', 1))
        for data in corruptions:
            with self.subTest(size=len(data)):
                self.path.write_bytes(data)
                with self.assertRaises(RunLedgerError):
                    self.open()

    def test_semantic_replay_rejects_forged_transitions_even_with_new_valid_hashes(self):
        ledger = self.open()
        ledger.start("first")
        ledger.complete(completed())
        ledger.close()
        original = self.events()
        variants = []
        variants.append([original[0], original[2]])
        variants.append([original[0], original[1], original[1]])
        variants.append([*original, original[2]])
        variants.append([*original, original[0]])
        for key, value in (("run_id", "second"), ("seal_sha256", "b" * 64),
                           ("itt_included", False), ("admitted", False),
                           ("evidence_kind", "model_pilot")):
            events = copy.deepcopy(original)
            events[2]["record"][key] = value
            variants.append(events)
        events = copy.deepcopy(original)
        events[2]["run_id"] = "second"
        variants.append(events)
        events = copy.deepcopy(original)
        events[0]["itt_included"] = False
        variants.append(events)
        for index, events in enumerate(variants):
            with self.subTest(index=index):
                self.write_rehashed(events)
                with self.assertRaises(RunLedgerError):
                    self.open()

    def test_reopening_requires_exact_jointseal_and_entire_ordered_schedule(self):
        self.open().close()
        for ids, seal in ((RUN_IDS, "b" * 64), (tuple(reversed(RUN_IDS)), SEAL),
                          (RUN_IDS[:2], SEAL), ((*RUN_IDS, "new"), SEAL)):
            with self.subTest(ids=ids, seal=seal), self.assertRaises(RunLedgerError):
                self.open(run_ids=ids, seal=seal)

    def test_exclusive_lock_path_replacement_and_owned_corruption_fail_closed(self):
        ledger = self.open()
        with self.assertRaises(RunLedgerLocked):
            self.open()
        ledger.start("first")
        ledger.complete(completed())
        data = self.path.read_bytes()
        self.path.write_bytes(data.replace(b'"first"', b'"First"', 1))
        snapshot = ledger.snapshot()
        self.assertFalse(snapshot["journal_integrity_verified"])
        self.assertEqual(3, snapshot["denominator"])
        self.assertEqual(0, aggregate_itt(snapshot["records"])["joint_success"])
        self.assertTrue(snapshot["records"][0]["run_ledger_prior_protocol"]["protocol_ok"])
        with self.assertRaises(RunLedgerError):
            ledger.start("second")
        self.path.write_bytes(data)
        # Integrity uncertainty is sticky even if somebody restores the bytes.
        self.assertFalse(ledger.snapshot()["journal_integrity_verified"])
        replacement = self.root / "replacement"
        replacement.write_bytes(data)
        replacement.replace(self.path)
        self.assertFalse(ledger.snapshot()["journal_integrity_verified"])

    def test_final_symlink_and_nonregular_file_are_rejected(self):
        target = self.root / "target"
        target.write_bytes(b"")
        self.path.symlink_to(target)
        with self.assertRaises(RunLedgerError):
            self.open()
        self.path.unlink()
        os.mkfifo(self.path)
        with self.assertRaises(RunLedgerError):
            self.open()

    def test_bounds_reject_oversized_results_and_excessive_replay_frames(self):
        ledger = self.open()
        ledger.start("first")
        before = self.path.read_bytes()
        for value in ("x" * journal._MAX_LINE_BYTES, float("nan"), 1 << 65):
            with self.subTest(kind=type(value).__name__), self.assertRaises(RunLedgerTransitionError):
                ledger.complete(completed(adapter_evidence={"bad": value}))
        self.assertEqual(before, self.path.read_bytes())
        with patch.object(journal, "_MAX_JOURNAL_BYTES", len(before) + 1):
            with self.assertRaises(RunLedgerError):
                ledger.complete(completed())
        self.assertEqual(3, ledger.snapshot()["denominator"])
        ledger.close()
        self.path.write_bytes(b" " * (journal._MAX_LINE_BYTES + 1) + b"\n")
        with self.assertRaises(RunLedgerError):
            self.open()

    def test_policy_is_explicit_detached_and_closed_owner_cannot_be_used(self):
        policy = ledger_policy()
        self.assertEqual("inspection_only_no_resume_or_retry", policy["reopen_policy"])
        self.assertEqual(6000, policy["max_runs"])
        policy["max_runs"] = 1
        self.assertEqual(6000, ledger_policy()["max_runs"])
        ledger = self.open()
        with patch.object(os, "getpid", return_value=os.getpid() + 1):
            with self.assertRaises(RunLedgerError):
                ledger.snapshot()
        ledger.close()
        ledger.close()
        with self.assertRaises(RunLedgerError):
            ledger.start("first")
        with self.assertRaises(RunLedgerError):
            ledger.snapshot()


if __name__ == "__main__":
    unittest.main()
