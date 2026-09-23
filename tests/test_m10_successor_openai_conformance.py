"""Fixed-sequence tests: fictional receipts, zero real count/generation calls."""
from __future__ import annotations

import copy
import dataclasses
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from bench.agent_ab.same_version_chain_v1 import successor_openai_conformance as flow
from bench.agent_ab.same_version_chain_v1 import successor_openai_responses as codec
from bench.agent_ab.same_version_chain_v1 import successor_openai_transport as transport
from bench.agent_ab.same_version_chain_v1.m10_successor_protocol import ACTION_SCHEMAS
from tests.test_m10_successor_openai_responses import encoded, response
from tests.test_guava_m10_successor import compiler_available


class NativeFake:
    """Fictional constant count for branch testing, not tokenizer evidence."""
    def __init__(self, *, defect=None):
        self.calls, self.generations = [], 0
        self.defect = defect

    def post(self, url, body, *, deadline_monotonic):
        value = json.loads(body)
        self.calls.append((url, value))
        if url == transport.COUNT_URL:
            count = 800
            if self.defect == "count_disagreement" and len(self.calls) == 8:
                count = 801
            if self.defect == "first_count_failure":
                return transport.PostResult(500, {}, b'{}')
            return transport.PostResult(200, {}, encoded({"object": "response.input_tokens", "input_tokens": count}))
        self.generations += 1
        purpose = "output_cap" if value["max_output_tokens"] == 64 else "scientific"
        prepared = codec.prepare_request(value["input"], ACTION_SCHEMAS, purpose=purpose)
        assert body == prepared.generation_json.encode("utf-8")
        result = response(prepared)
        result["id"] = "resp_fake_" + str(self.generations)
        for item in result["output"]:
            item["id"] += "_" + str(self.generations)
            if "call_id" in item:
                item["call_id"] += "_" + str(self.generations)
        if purpose == "output_cap":
            result["status"] = "incomplete"
            result["incomplete_details"] = {"reason": "max_output_tokens"}
            result["output"] = []
            result["usage"]["output_tokens"] = 64
            result["usage"]["total_tokens"] = 864
            result["usage"]["output_tokens_details"]["reasoning_tokens"] = 64
            if self.defect == "cap_not_observed":
                result["status"], result["incomplete_details"] = "completed", None
        elif self.generations == 1:
            if self.defect == "missing_state":
                result["output"] = result["output"][1:]
            elif self.defect == "final_at_C1":
                result["output"][-1].update(name="final", arguments=codec.canonical({"answer": "done", "files": []}))
            elif self.defect == "wrong_model":
                result["model"] = "unapproved"
        return transport.PostResult(200, {"x-request-id": "fixture-only"}, encoded(result))


def small_seal():
    """Sequence plumbing only; actual scientific seal has separate production tests."""
    request = codec.prepare_request([{"role": "system", "content": "Use native functions."},
                                     {"role": "user", "content": "offline sequence only"}], ACTION_SCHEMAS)
    cap = codec.prepare_request(flow.C3_INPUT, ACTION_SCHEMAS, purpose="output_cap")
    return {"seal_sha256": "a" * 64,
            "initial_native_requests": {arm: dataclasses.asdict(request) for arm in flow.ARMS},
            "cap_probe_request": dataclasses.asdict(cap)}


class SequenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        no_network = patch("socket.socket.connect", side_effect=AssertionError("network forbidden"))
        no_network.start()
        self.addCleanup(no_network.stop)

    def run_sequence(self, defect=None):
        fake = NativeFake(defect=defect)
        with transport.OperationJournal(self.root / "operations.jsonl", authorization_id=flow.AUTHORIZATION_ID,
                                        seal_sha256="a" * 64) as journal:
            broker = transport.CountedBroker(fake, journal, self.root / "evidence")
            report = flow.execute_sequence(small_seal(), broker)
        return fake, report

    def test_success_exact_12_counts_3_generations_preserves_state_and_frozen_feedback(self):
        fake, report = self.run_sequence()
        self.assertTrue(report["ok"], report)
        self.assertEqual(12, report["accounting"]["count_requests"])
        self.assertEqual(3, report["accounting"]["generation_requests"])
        self.assertEqual([], report["skipped"])
        steps = report["steps"]
        c1 = json.loads(steps["C1"]["request"]["generation_json"])
        c2 = json.loads(steps["C2"]["request"]["generation_json"])
        output = steps["C1"]["observation"]["output_items"]
        self.assertEqual(c1["input"] + output, c2["input"][:-1])
        self.assertEqual(flow.FROZEN_LOCAL_RESULT, c2["input"][-1]["output"])
        self.assertEqual(output[-1]["call_id"], c2["input"][-1]["call_id"])
        self.assertEqual(64, fake.calls[-1][1]["max_output_tokens"])
        self.assertFalse(report["live_pilot_executed"])
        for index, (url, generated) in enumerate(fake.calls):
            if url == transport.GENERATION_URL:
                self.assertEqual(fake.calls[index-1][1], {k: generated[k] for k in codec.SCIENTIFIC_FIELDS})

    def test_first_count_failure_stops_all_generation(self):
        fake, report = self.run_sequence("first_count_failure")
        self.assertFalse(report["ok"])
        self.assertEqual(1, len(fake.calls))
        self.assertEqual(0, fake.generations)
        self.assertEqual(["C1", "C2", "C3"], report["skipped"])

    def test_broker_count_disagreement_prevents_first_generation(self):
        fake, report = self.run_sequence("count_disagreement")
        self.assertFalse(report["ok"])
        self.assertEqual(8, len(fake.calls))
        self.assertEqual(0, fake.generations)

    def test_missing_encrypted_state_is_insufficient_not_synthetic_C2(self):
        fake, report = self.run_sequence("missing_state")
        self.assertFalse(report["ok"])
        self.assertEqual(1, fake.generations)
        self.assertEqual(["C2", "C3"], report["skipped"])
        self.assertEqual(920, report["accounting"]["known_usage"]["total_tokens"])

    def test_final_C1_not_replaced_with_convenient_function(self):
        fake, report = self.run_sequence("final_at_C1")
        self.assertFalse(report["ok"])
        self.assertEqual(1, fake.generations)
        self.assertEqual("C1_final_cannot_test_continuation", report["failure"]["category"])

    def test_rejected_identity_still_settles_known_usage(self):
        fake, report = self.run_sequence("wrong_model")
        self.assertEqual(1, fake.generations)
        self.assertFalse(report["ok"])
        self.assertEqual(920, report["accounting"]["known_usage"]["total_tokens"])
        self.assertEqual(920, report["accounting"]["charged_usage"]["total_tokens"])

    def test_cap_not_observed_ends_without_fourth_generation(self):
        fake, report = self.run_sequence("cap_not_observed")
        self.assertFalse(report["ok"])
        self.assertEqual(3, fake.generations)
        self.assertEqual(12, report["accounting"]["count_requests"])
        self.assertEqual("C3", report["failure"]["stage"])

    def test_audit_receipt_must_match_exact_seal_and_authorization(self):
        seal = small_seal()
        receipt = {"verdict": "READY", "seal_sha256": seal["seal_sha256"],
                   "authorization_id": flow.AUTHORIZATION_ID, "independent_reviewer": "audit-agent",
                   "offline_tests_passed": True, "no_blocking_findings": True}
        flow.validate_audit_receipt(receipt, seal)
        for field, value in (("verdict", "PENDING"), ("seal_sha256", "b" * 64),
                             ("offline_tests_passed", False), ("independent_reviewer", "parent"),
                             ("authorization_id", "different-authorization")):
            with self.assertRaises(ValueError):
                flow.validate_audit_receipt({**receipt, field: value}, seal)

    def audit(self):
        return {"verdict": "READY", "seal_sha256": "a" * 64, "authorization_id": flow.AUTHORIZATION_ID,
                "independent_reviewer": "fictional-offline-reviewer-not-live-authorization",
                "offline_tests_passed": True, "no_blocking_findings": True}

    def test_live_gate_fixed_lifetime_path_cannot_be_reset_by_new_invocation(self):
        fake, credential = NativeFake(), Mock(side_effect=AssertionError("no real credential"))
        with patch.object(flow, "LIVE_STATE_ROOT", self.root / "fixed-state"), \
             patch.object(flow, "verify_seal", return_value={"ok": True}), \
             patch.object(transport, "SinglePostTransport", return_value=fake) as constructor:
            report = flow.run_authorized_conformance(small_seal(), self.audit(), credential_provider=credential)
            self.assertTrue(report["ok"])
            with self.assertRaises(FileExistsError):
                flow.run_authorized_conformance(small_seal(), self.audit(), credential_provider=credential)
            self.assertEqual(1, constructor.call_count)
        credential.assert_not_called()
        self.assertEqual(3, fake.generations)

    def test_bad_seal_or_audit_never_constructs_transport_or_reads_credentials(self):
        credential = Mock(side_effect=AssertionError("no credential"))
        with patch.object(flow, "LIVE_STATE_ROOT", self.root / "fixed-state"), \
             patch.object(transport, "SinglePostTransport") as constructor:
            with patch.object(flow, "verify_seal", side_effect=ValueError("bad seal")):
                with self.assertRaises(ValueError):
                    flow.run_authorized_conformance(small_seal(), self.audit(), credential_provider=credential)
            with patch.object(flow, "verify_seal", return_value={"ok": True}):
                with self.assertRaises(ValueError):
                    flow.run_authorized_conformance(small_seal(), {**self.audit(), "verdict": "NOT READY"},
                                                   credential_provider=credential)
            constructor.assert_not_called()
        credential.assert_not_called()
        self.assertFalse((self.root / "fixed-state").exists())

    def test_crash_leaves_lifetime_latch_and_no_auto_resume(self):
        with patch.object(flow, "LIVE_STATE_ROOT", self.root / "fixed-state"), \
             patch.object(flow, "verify_seal", return_value={"ok": True}), \
             patch.object(transport, "SinglePostTransport", return_value=NativeFake()), \
             patch.object(flow, "execute_sequence", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                flow.run_authorized_conformance(small_seal(), self.audit(), credential_provider=Mock())
            with self.assertRaises(FileExistsError):
                flow.run_authorized_conformance(small_seal(), self.audit(), credential_provider=Mock())

    def test_cost_never_double_counts_reasoning_or_calls_unknown_count_free(self):
        _, report = self.run_sequence()
        self.assertTrue(report["cost"]["generation_cost_complete"])
        self.assertEqual("unknown", report["cost"]["all_in_cost"])
        # Input800: cached200, written100, ordinary500. Output120+120+64.
        from decimal import Decimal
        expected = Decimal(3 * 500 * 10 + 3 * 200) / 1_000_000
        expected += Decimal(300) * Decimal("12.5") / 1_000_000
        expected += Decimal(304 * 50) / 1_000_000
        self.assertEqual(expected, Decimal(report["cost"]["known_generation_at_frozen_rates"]))


@unittest.skipUnless(compiler_available(), "frozen offline JARs/javac unavailable; dedicated CI requires full seal")
class ProductionSealTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seal = flow.build_seal()

    def test_real_production_chain_native_equality_and_count_projection(self):
        s = self.seal
        flow.verify_seal(s)
        self.assertFalse(s["live_pilot_enabled"])
        requests = s["initial_native_requests"]
        self.assertEqual(requests[flow.SOURCE_ONLY], requests[flow.STALE_WITHHELD_SILENT])
        for arm, data in requests.items():
            p = flow._prepared(data)
            self.assertNotIn("exactly one JSON action", p.generation_json)
            self.assertNotIn(arm, p.generation_json)
            self.assertIn(flow.COMMON_NATIVE_PROMPT, json.loads(p.generation_json)["input"][-1]["content"])

    def test_rehashed_treatment_or_config_drift_rejected_by_reconstruction(self):
        changed = copy.deepcopy(self.seal)
        changed["plan"]["count_limit"] = 13
        changed["seal_sha256"] = codec.digest(codec.canonical({k: v for k, v in changed.items() if k != "seal_sha256"}))
        with self.assertRaisesRegex(ValueError, "reconstruction"):
            flow.verify_seal(changed)


if __name__ == "__main__":
    unittest.main()
