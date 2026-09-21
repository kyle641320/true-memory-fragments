from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from bench.agent_ab.same_version_chain_v1 import m10_successor_protocol as protocol
from bench.agent_ab.same_version_chain_v1.m10_successor_protocol import (
    LiveExecutionDisabled, ProtocolAdmissionError, ScriptedAdapter, _run_one_with_factory,
)
from bench.agent_ab.same_version_chain_v1.m10_successor_run_ledger import (
    EVIDENCE_KIND, RunAdmissionLedger, RunLedgerError,
)


SEAL = "b" * 64


class OfflineSpy:
    def __init__(self, events, responses=None):
        self.events = events
        self.requests = []
        self.closed = False
        self.responses = responses or [{"action": "compile"},
                                       {"action": "final", "files": [], "answer": "No change."}]

    def respond(self, request):
        self.events.append("respond")
        self.requests.append(request)
        return json.dumps(self.responses[len(self.requests) - 1])

    def close(self):
        self.events.append("close")
        self.closed = True

    def snapshot(self):
        self.events.append("snapshot")
        if not self.closed:
            raise AssertionError("snapshot before cleanup")
        return {"private_run_attribution": "evaluator only", "closed": True}


class M10SuccessorProtocolBridgeSeamTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "fixture"
        self.root.mkdir()
        (self.root / "Dispatcher.java").write_text("class Dispatcher {}\n")
        self.ledger = RunAdmissionLedger(self.root.parent / "runs.jsonl", SEAL, ("opaque", "pending"))
        self.addCleanup(self.ledger.close)
        self.events = []
        self.adapter = None

    def verify(self):
        self.events.append("verify")
        return {"ok": True, "seal_sha256": SEAL}

    def admit(self):
        self.events.append("admit")
        self.ledger.start("opaque")

    def factory(self):
        self.events.append("factory")
        snapshot = self.ledger.snapshot()
        self.assertEqual("opaque", snapshot["pending_run_id"])
        self.assertTrue(snapshot["journal_integrity_verified"])
        self.adapter = OfflineSpy(self.events)
        return self.adapter

    def compile(self, root):
        self.events.append("compile")
        self.assertNotEqual(self.root, root)
        return {"ok": True}

    def score(self, root):
        self.events.append("score")
        return {"semantic_pass": True}

    def run_private(self, **changes):
        options = dict(
            adapter_factory=self.factory, compile_fn=self.compile, score_fn=self.score,
            verify=self.verify, source_files=("Dispatcher.java",), run_id="opaque",
            evidence_kind=EVIDENCE_KIND, on_admit=self.admit,
            adapter_evidence=lambda adapter: adapter.snapshot(),
        )
        options.update(changes)
        return _run_one_with_factory(self.root, [{"role": "user", "content": "Use <workspace>."}], **options)

    def test_durable_admission_before_factory_and_post_execution_private_evidence(self):
        row = self.run_private()
        self.assertEqual(["verify", "admit", "factory"], self.events[:3])
        self.assertEqual(["score", "compile", "close", "snapshot"], self.events[-4:])
        self.assertTrue(row.protocol_ok)
        self.assertTrue(row.durable_ledger)
        self.assertEqual(EVIDENCE_KIND, row.evidence_kind)
        self.assertEqual(EVIDENCE_KIND, row.admission_events[0]["evidence_kind"])
        self.assertEqual(SEAL, row.admission_events[0]["seal_sha256"])
        self.assertEqual({"private_run_attribution": "evaluator only", "closed": True}, row.adapter_evidence)
        for request in self.adapter.requests:
            rendered = json.dumps(asdict(request))
            for private in ("private_run_attribution", "evaluator only", "opaque", SEAL, EVIDENCE_KIND):
                self.assertNotIn(private, rendered)
        self.assertEqual(3, len(self.adapter.requests[1].messages))
        self.ledger.complete(asdict(row))
        self.assertEqual(2, self.ledger.snapshot()["denominator"])

    def test_failed_verifier_or_start_never_constructs_adapter(self):
        with self.assertRaises(ProtocolAdmissionError):
            self.run_private(verify=lambda: {"ok": False})
        self.assertEqual([], self.events)
        with patch.object(protocol, "tempfile") as temporary:
            with patch.object(self.ledger, "start", side_effect=RunLedgerError("write failed")):
                with self.assertRaises(RunLedgerError):
                    self.run_private()
            temporary.TemporaryDirectory.assert_not_called()
        self.assertEqual(["verify", "admit"], self.events)
        self.assertIsNone(self.adapter)
        self.assertEqual(2, self.ledger.snapshot()["admitted_runs"])
        self.assertEqual(0, self.ledger.snapshot()["started_runs"])

    def test_failed_start_fsync_has_zero_factory_work_and_all_ids_remain(self):
        with patch.object(protocol.os, "fsync", side_effect=OSError("disk failure")):
            with self.assertRaises(RunLedgerError):
                self.run_private()
        self.assertEqual(["verify", "admit"], self.events)
        self.assertIsNone(self.adapter)
        self.assertEqual(["opaque", "pending"], [row["run_id"] for row in self.ledger.records()])

    def test_factory_error_remains_itt_failure_with_independent_evaluation(self):
        def failed_factory():
            self.events.append("factory")
            raise RuntimeError("fixed adapter unavailable")

        row = self.run_private(adapter_factory=failed_factory)
        self.assertEqual("adapter_factory_error:RuntimeError", row.failure_reason)
        self.assertFalse(row.protocol_ok)
        self.assertTrue(row.semantic["semantic_pass"])
        self.assertTrue(row.compilation["ok"])
        self.assertEqual(["verify", "admit", "factory", "score", "compile"], self.events)
        self.ledger.complete(asdict(row))
        self.assertEqual(2, self.ledger.snapshot()["denominator"])

    def test_response_failure_still_closes_and_collects_evidence(self):
        original = self.factory

        def factory():
            adapter = original()
            adapter.responses = [{"action": "forbidden"}]
            return adapter

        row = self.run_private(adapter_factory=factory)
        self.assertEqual("invalid_action", row.failure_reason)
        self.assertEqual(["score", "compile", "close", "snapshot"], self.events[-4:])
        self.assertTrue(row.adapter_evidence["closed"])
        self.assertFalse(row.protocol_ok)

    def test_cleanup_and_evidence_errors_cannot_leave_a_successful_protocol(self):
        original = self.factory

        def factory():
            adapter = original()

            def failed_close():
                self.events.append("close")
                raise RuntimeError("cleanup failed")

            adapter.close = failed_close
            return adapter

        row = self.run_private(adapter_factory=factory)
        self.assertFalse(row.protocol_ok)
        self.assertEqual("failed", row.protocol_status)
        self.assertEqual("adapter_evidence_or_cleanup_failed", row.failure_reason)
        self.assertEqual({"close_error": "RuntimeError", "snapshot_error": "AssertionError"},
                         row.adapter_evidence["executor_lifecycle_errors"])
        self.assertTrue(row.semantic["semantic_pass"])
        self.assertTrue(row.compilation["ok"])
        self.ledger.complete(asdict(row))

    def test_snapshot_error_does_not_overwrite_original_execution_failure(self):
        original = self.factory

        def factory():
            adapter = original()
            adapter.responses = [{"action": "forbidden"}]
            return adapter

        row = self.run_private(adapter_factory=factory, adapter_evidence=lambda adapter: float("nan"))
        self.assertEqual("invalid_action", row.failure_reason)
        self.assertEqual({"snapshot_error": "TypeError"}, row.adapter_evidence["executor_lifecycle_errors"])
        self.assertTrue(self.adapter.closed)

    def test_interruption_closes_adapter_and_reopen_keeps_started_and_unstarted(self):
        with patch.object(OfflineSpy, "respond", side_effect=KeyboardInterrupt("stop")):
            with self.assertRaises(KeyboardInterrupt):
                self.run_private()
        self.assertTrue(self.adapter.closed)
        self.ledger.close()
        with RunAdmissionLedger(self.root.parent / "runs.jsonl", SEAL, ("opaque", "pending")) as recovered:
            rows = recovered.records()
            self.assertEqual(["started", "not_started"], [row["run_ledger_state"] for row in rows])
            self.assertTrue(all(row["itt_included"] and not row["protocol_ok"] for row in rows))

    def test_legacy_exact_type_live_and_freshness_guards_precede_private_executor(self):
        class Subclass(ScriptedAdapter):
            pass

        reused = ScriptedAdapter([])
        reused.calls = 1
        cases = ((OfflineSpy([]), False, LiveExecutionDisabled),
                 (Subclass([]), False, LiveExecutionDisabled),
                 (ScriptedAdapter([]), True, LiveExecutionDisabled),
                 (reused, False, ProtocolAdmissionError))
        with patch.object(protocol, "_run_one_with_factory", side_effect=AssertionError("gate bypass")):
            for adapter, live, error in cases:
                with self.subTest(adapter=type(adapter).__name__, live=live), self.assertRaises(error):
                    protocol.run_one(self.root, [], adapter, compile_fn=self.compile,
                                     score_fn=self.score, verify=self.verify, live=live)
        self.assertEqual([], self.events)


if __name__ == "__main__":
    unittest.main()
