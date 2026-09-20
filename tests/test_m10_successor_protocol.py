from __future__ import annotations

import json
import socket
import tempfile
import time
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

from bench.agent_ab.same_version_chain_v1.m10_successor_protocol import (
    ACTION_SCHEMAS,
    BudgetCaps,
    EVIDENCE_KIND,
    LiveExecutionDisabled,
    ProtocolAdmissionError,
    ScriptedAdapter,
    ScriptedFailure,
    aggregate_itt,
    build_action_schemas,
    records_from_ledger,
    run_one,
)


SOURCE = """class Dispatcher {
  private void hook() {}
  void dispatch() {
    target();
  }
  void target() {}
}
"""
EDIT = {"action": "edit", "path": "Dispatcher.java", "old": "    target();",
        "new": "    hook();\n    target();"}
FINAL = {"action": "final", "answer": "Inserted the hook before target handoff.",
         "files": ["Dispatcher.java"]}


class M10SuccessorProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "secret_arm_template"
        self.root.mkdir()
        (self.root / "Dispatcher.java").write_text(SOURCE, encoding="utf-8")
        (self.root / "EventBus.java").write_text("class EventBus {}\n", encoding="utf-8")
        # Evaluation-only files must not be copied or discoverable by tools.
        (self.root / ".tmf").mkdir()
        (self.root / ".tmf" / "arm.json").write_text('{"arm":"SECRET_ARM"}', encoding="utf-8")
        (self.root / "seal.json").write_text("secret_seal", encoding="utf-8")
        self.ledger = Path(self.temporary.name) / "accounting" / "ledger.jsonl"
        self.messages = [{"role": "system", "content": "Use the action protocol."},
                         {"role": "user", "content": "Fixture root: <workspace>"}]
        self.events: list[str] = []

    def verify(self):
        self.events.append("verify")
        self.assertFalse(self.ledger.exists())
        return {"ok": True, "seal_sha256": "a" * 64}

    def compile(self, root):
        self.events.append("compile")
        self.assertNotEqual(root, self.root)
        self.assertEqual({"Dispatcher.java", "EventBus.java"}, {path.name for path in root.iterdir()})
        return {"ok": True, "exit": 0, "stdout": "", "stderr": ""}

    @staticmethod
    def score(root):
        source = (root / "Dispatcher.java").read_text(encoding="utf-8")
        return {"semantic_pass": "    hook();\n    target();" in source}

    def run_script(self, responses, **kwargs):
        adapter = ScriptedAdapter(responses)
        options = dict(
            compile_fn=self.compile, score_fn=self.score, verify=self.verify,
            source_files=("Dispatcher.java", "EventBus.java"), ledger_path=self.ledger,
        )
        options.update(kwargs)
        record = run_one(self.root, self.messages, adapter, **options)
        return record, adapter

    def test_all_actions_end_to_end_isolated_and_transport_contract(self):
        responses = [
            {"action": "list"}, {"action": "search", "query": "target"},
            {"action": "read_range", "path": "Dispatcher.java", "start": 1, "end": 20},
            {"action": "read_symbol", "path": "Dispatcher.java", "symbol": "Dispatcher.dispatch"},
            EDIT, {"action": "compile"}, FINAL,
        ]
        with patch.object(socket, "socket", side_effect=AssertionError("network forbidden")):
            record, adapter = self.run_script(responses)
        self.assertTrue(record.protocol_ok)
        self.assertTrue(record.semantic["semantic_pass"])
        self.assertTrue(record.compilation["ok"])
        self.assertTrue(record.joint_success)
        self.assertEqual(EVIDENCE_KIND, record.evidence_kind)
        self.assertFalse(record.model_pilot_admitted)
        self.assertFalse(record.provider_token_limits_verified)
        self.assertEqual("verify", self.events[0])
        self.assertEqual(SOURCE, (self.root / "Dispatcher.java").read_text(encoding="utf-8"))
        self.assertEqual(7, adapter.calls)
        self.assertEqual(6, record.usage["tool_calls"])
        self.assertEqual(1, record.usage["successful_edits"])
        self.assertEqual(3, record.usage["source_read_actions"])
        self.assertEqual(["Dispatcher.java"], record.usage["source_files_received"])
        self.assertGreater(record.usage["source_content_bytes_received"], len(SOURCE))
        self.assertEqual([2, 3, 4], [row["turn"] for row in record.source_acquisition])
        for request in adapter.requests:
            rendered = json.dumps(asdict(request))
            self.assertNotIn(str(self.root), rendered)
            self.assertNotIn("secret_arm", rendered)
            self.assertNotIn("seal.json", rendered)
            self.assertNotIn(".tmf", rendered)
            self.assertNotIn(record.run_id, rendered)
            self.assertEqual(4096, request.max_output_tokens)
            self.assertGreater(request.max_output_bytes, 0)
            self.assertGreater(request.timeout_seconds, 0)
            self.assertEqual("utf8_bytes_not_provider_tokens", request.budget_unit)
        rows = records_from_ledger(self.ledger)
        self.assertEqual(1, len(rows))
        self.assertEqual(1, aggregate_itt(rows)["joint_success"])

    def test_admission_durable_before_first_adapter_call(self):
        original = ScriptedAdapter.respond

        def observed(adapter, request):
            events = [json.loads(line) for line in self.ledger.read_text().splitlines()]
            self.assertEqual(["admitted"], [event["event"] for event in events])
            self.assertTrue(events[0]["itt_included"])
            return original(adapter, request)

        with patch.object(ScriptedAdapter, "respond", observed):
            record, _ = self.run_script([ScriptedFailure("error")])
        self.assertTrue(record.admitted)
        self.assertEqual("adapter_error", record.failure_reason)

    def test_failed_verification_prevents_copy_admission_and_adapter(self):
        for receipt in ({"ok": False, "seal_sha256": "a" * 64},
                        {"ok": True}, {"ok": True, "seal_sha256": "bad"}):
            with self.subTest(receipt=receipt):
                adapter = ScriptedAdapter([{"action": "list"}])
                with patch("tempfile.TemporaryDirectory", side_effect=AssertionError("copy before verifier")):
                    with self.assertRaises(ProtocolAdmissionError):
                        run_one(self.root, self.messages, adapter, compile_fn=self.compile,
                                score_fn=self.score, verify=lambda: receipt, ledger_path=self.ledger)
                self.assertEqual(0, adapter.calls)
                self.assertFalse(self.ledger.exists())

    def test_verifier_exception_never_calls_adapter(self):
        adapter = ScriptedAdapter([{"action": "list"}])

        def failed():
            raise RuntimeError("sealed fixture changed")

        with self.assertRaisesRegex(RuntimeError, "sealed fixture changed"):
            run_one(self.root, self.messages, adapter, compile_fn=self.compile,
                    score_fn=self.score, verify=failed)
        self.assertEqual(0, adapter.calls)

    def test_live_custom_and_subclass_adapters_cannot_be_admitted(self):
        class ModelSpy:
            calls = 0

            def respond(self, request):
                self.calls += 1
                raise AssertionError("broker call forbidden")

        class ScriptedSubclass(ScriptedAdapter):
            pass

        for adapter, live in ((ModelSpy(), False), (ScriptedSubclass([]), False),
                              (ScriptedAdapter([]), True)):
            with self.subTest(adapter=type(adapter).__name__, live=live):
                with self.assertRaises(LiveExecutionDisabled):
                    run_one(self.root, self.messages, adapter, compile_fn=self.compile,
                            score_fn=self.score, verify=self.verify, live=live)
                self.assertEqual(0, adapter.calls)
        self.assertEqual([], self.events)
        self.assertFalse(self.ledger.exists())

    def test_complete_schemas_match_dispatch_actions(self):
        self.assertEqual({"list", "search", "read_range", "read_symbol", "edit", "compile", "final"}, set(ACTION_SCHEMAS))
        self.assertEqual(["Dispatcher.java"], ACTION_SCHEMAS["edit"]["properties"]["path"]["enum"])
        for name, schema in ACTION_SCHEMAS.items():
            self.assertFalse(schema["additionalProperties"])
            self.assertEqual(name, schema["properties"]["action"]["const"])
            self.assertIn("action", schema["required"])
        self.assertEqual(11, len(ACTION_SCHEMAS["read_range"]["properties"]["path"]["enum"]))

    def test_all_path_escape_and_noneditable_actions_are_itt_failures(self):
        for path in ("../Dispatcher.java", "/etc/passwd", ".tmf/arm.json", "seal.json", "EventBus.java"):
            with self.subTest(path=path):
                record, _ = self.run_script([{**EDIT, "path": path}], ledger_path=None)
                self.assertFalse(record.protocol_ok)
                self.assertEqual("invalid_action_schema", record.failure_reason)
                self.assertTrue(record.itt_included)
                self.assertFalse(record.semantic["semantic_pass"])
                self.assertTrue(record.compilation["ok"])

    def test_source_symlink_is_rejected_after_admission_without_adapter(self):
        (self.root / "EventBus.java").unlink()
        (self.root / "EventBus.java").symlink_to(self.root / "Dispatcher.java")
        record, adapter = self.run_script([{"action": "list"}])
        self.assertEqual("source_path_denied", record.failure_reason)
        self.assertEqual(0, adapter.calls)
        self.assertEqual(1, aggregate_itt([record])["denominator"])

    def test_invalid_json_schema_actions_not_silently_retried(self):
        cases = [
            "no JSON", '[{"action":"list"}]', '{"action":"list","action":"compile"}',
            {"action": []},
            {"action": "shell", "command": "anything"}, {"action": "list", "metadata": "extra"},
            {"action": "read_range", "path": "Dispatcher.java", "start": True, "end": 2},
            {"action": "read_range", "path": "Dispatcher.java", "start": 0, "end": 2},
            {"action": "final", "answer": "", "files": []},
        ]
        for response in cases:
            with self.subTest(response=response):
                record, adapter = self.run_script([response, EDIT, {"action": "compile"}, FINAL], ledger_path=None)
                self.assertEqual(1, adapter.calls)
                self.assertFalse(record.protocol_ok)
                self.assertTrue(record.itt_included)

    def test_ledger_cannot_modify_fixture_template(self):
        adapter = ScriptedAdapter([])
        with self.assertRaisesRegex(ProtocolAdmissionError, "outside"):
            run_one(self.root, self.messages, adapter, compile_fn=self.compile,
                    score_fn=self.score, verify=self.verify, ledger_path=self.root / "Dispatcher.java")
        self.assertEqual(SOURCE, (self.root / "Dispatcher.java").read_text(encoding="utf-8"))
        self.assertEqual(0, adapter.calls)

    def test_host_fixture_path_cannot_leak_in_input(self):
        adapter = ScriptedAdapter([])
        with self.assertRaisesRegex(ProtocolAdmissionError, "host path"):
            run_one(self.root, [{"role": "user", "content": f"Work in {self.root}"}], adapter,
                    compile_fn=self.compile, score_fn=self.score, verify=self.verify)
        self.assertEqual(0, adapter.calls)

    def test_semantics_compile_and_protocol_are_independent_on_failure(self):
        record, _ = self.run_script([EDIT, ScriptedFailure("error")])
        self.assertEqual("adapter_error", record.failure_reason)
        self.assertFalse(record.protocol_ok)
        self.assertTrue(record.semantic["semantic_pass"])
        self.assertTrue(record.compilation["ok"])
        self.assertFalse(record.joint_success)
        summary = aggregate_itt([record])
        self.assertEqual(1, summary["denominator"])
        self.assertEqual(1, summary["semantic_pass"])
        self.assertEqual(1, summary["compile_pass"])
        self.assertEqual(0, summary["joint_success"])

    def test_compile_failure_does_not_filter_semantic_record(self):
        record, _ = self.run_script([EDIT, {"action": "compile"}, FINAL],
                                    compile_fn=lambda root: {"ok": False, "exit": 1})
        self.assertTrue(record.protocol_ok)
        self.assertTrue(record.semantic["semantic_pass"])
        self.assertFalse(record.compilation["ok"])
        self.assertEqual(1, aggregate_itt([record])["denominator"])
        self.assertEqual(0, aggregate_itt([record])["joint_success"])

    def test_no_final_turn_cap_is_enforced(self):
        record, adapter = self.run_script([EDIT, {"action": "list"}, {"action": "compile"}, FINAL],
                                          budgets=replace(BudgetCaps(), max_turns=2))
        self.assertEqual(2, adapter.calls)
        self.assertEqual(2, record.usage["turns"])
        self.assertEqual("no_final", record.failure_reason)
        self.assertTrue(record.semantic["semantic_pass"])
        self.assertEqual(1, aggregate_itt([record])["no_final"])

    def test_empty_script_is_counted_no_final(self):
        record, adapter = self.run_script([])
        self.assertEqual(1, adapter.calls)
        self.assertEqual("no_final", record.failure_reason)
        self.assertEqual(1, aggregate_itt([record])["denominator"])

    def test_input_budget_includes_schemas_before_call(self):
        record, adapter = self.run_script([EDIT], budgets=replace(BudgetCaps(), max_input_bytes_per_turn=1))
        self.assertEqual("input_budget_exceeded", record.failure_reason)
        self.assertEqual(0, adapter.calls)
        self.assertEqual(1, aggregate_itt([record])["denominator"])

    def test_total_input_budget_recounts_growing_history(self):
        schemas = build_action_schemas(("Dispatcher.java", "EventBus.java"))
        first = len(json.dumps({"messages": tuple(self.messages), "action_schemas": schemas},
                               sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        record, adapter = self.run_script([{"action": "list"}, EDIT],
                                          budgets=replace(BudgetCaps(), max_total_input_bytes=first))
        self.assertEqual(1, adapter.calls)
        self.assertEqual(first, record.usage["input_bytes"])
        self.assertEqual("input_budget_exceeded", record.failure_reason)

    def test_output_budget_counts_utf8_bytes_before_parsing(self):
        record, adapter = self.run_script(["汉字"], budgets=replace(BudgetCaps(), max_output_bytes_per_turn=4))
        self.assertEqual("output_budget_exceeded", record.failure_reason)
        self.assertEqual(6, record.usage["output_bytes"])
        self.assertEqual(1, adapter.calls)
        self.assertIsNone(record.usage["provider_tokens"])

    def test_total_output_cap_reaches_adapter_request(self):
        first = '{"action":"list"}'
        record, adapter = self.run_script([first, first],
                                          budgets=replace(BudgetCaps(), max_total_output_bytes=len(first) + 2))
        self.assertEqual(2, adapter.calls)
        self.assertEqual(2, adapter.requests[1].max_output_bytes)
        self.assertEqual("output_budget_exceeded", record.failure_reason)

    def test_tool_output_cap_and_file_cap_are_enforced(self):
        record, _ = self.run_script([{"action": "list"}],
                                    budgets=replace(BudgetCaps(), max_tool_output_bytes=1))
        self.assertEqual("tool_output_budget_exceeded", record.failure_reason)
        self.ledger.unlink()
        record, adapter = self.run_script([EDIT], budgets=replace(BudgetCaps(), max_file_bytes=10))
        self.assertEqual("file_budget_exceeded", record.failure_reason)
        self.assertEqual(0, adapter.calls)

    def test_adapter_timeout_is_itt_included(self):
        record, _ = self.run_script([EDIT, ScriptedFailure("timeout")])
        self.assertEqual("adapter_timeout", record.failure_reason)
        self.assertTrue(record.semantic["semantic_pass"])
        self.assertEqual(1, aggregate_itt([record])["denominator"])

    def test_action_wall_timeout_is_enforced_and_evaluator_still_runs(self):
        calls = 0

        def slow_first_compile(root):
            nonlocal calls
            calls += 1
            if calls == 1:
                time.sleep(1)
            return {"ok": True}

        started = time.monotonic()
        record, _ = self.run_script([EDIT, {"action": "compile"}, FINAL], compile_fn=slow_first_compile,
                                    budgets=replace(BudgetCaps(), action_timeout_seconds=0.02))
        self.assertLess(time.monotonic() - started, 0.8)
        self.assertEqual("action_timeout", record.failure_reason)
        self.assertTrue(record.semantic["semantic_pass"])
        self.assertTrue(record.compilation["ok"])
        self.assertEqual(2, calls)

    def test_evaluator_failures_are_unknown_not_removed(self):
        def broken_score(root):
            raise ValueError("evaluation failed")

        record, _ = self.run_script([ScriptedFailure("error")], score_fn=broken_score,
                                    compile_fn=lambda root: {"not-ok": True})
        self.assertIsNone(record.semantic["semantic_pass"])
        self.assertIsNone(record.compilation["ok"])
        summary = aggregate_itt([record])
        self.assertEqual(1, summary["denominator"])
        self.assertEqual(1, summary["semantic_unknown"])
        self.assertEqual(1, summary["compile_unknown"])

    def test_final_requires_current_compile_and_correct_file_report(self):
        for responses, expected in (
            ([EDIT, FINAL], "final_without_current_compile"),
            ([{"action": "compile"}, EDIT, FINAL], "final_without_current_compile"),
            ([EDIT, {"action": "compile"}, {**FINAL, "files": []}], "final_file_report_mismatch"),
        ):
            with self.subTest(expected=expected):
                record, _ = self.run_script(responses, ledger_path=None)
                self.assertEqual(expected, record.failure_reason)
                self.assertTrue(record.final_received)
                self.assertTrue(record.semantic["semantic_pass"])

    def test_compile_feedback_redacts_host_paths_and_evaluator_fields(self):
        def compile_paths(root):
            return {"ok": True, "exit": 0, "stderr": f"{root}/Dispatcher.java:3 /root/.m2/private.jar",
                    "arm": "HIDDEN", "semantic_pass": True, "classpath": "/secret"}

        record, adapter = self.run_script([EDIT, {"action": "compile"}, FINAL], compile_fn=compile_paths)
        rendered = json.dumps(asdict(adapter.requests[-1]))
        self.assertNotIn("/root", rendered)
        self.assertNotIn("private.jar", rendered)
        self.assertNotIn("HIDDEN", rendered)
        self.assertNotIn("semantic_pass", rendered)
        self.assertNotIn("classpath", rendered)
        self.assertIn("<workspace>/Dispatcher.java", rendered)
        self.assertTrue(record.protocol_ok)

    def test_interrupted_admission_is_in_ledger_denominator(self):
        self.ledger.parent.mkdir()
        self.ledger.write_text(json.dumps({"event": "admitted", "run_id": "opaque1",
                                          "seal_sha256": "b" * 64}) + "\n", encoding="utf-8")
        rows = records_from_ledger(self.ledger)
        self.assertEqual("incomplete", rows[0]["protocol_status"])
        self.assertEqual("missing_completion_record", rows[0]["failure_reason"])
        self.assertEqual(1, aggregate_itt(rows)["denominator"])
        self.assertEqual(0, aggregate_itt(rows)["joint_success"])

    def test_aggregate_refuses_exclusions_and_duplicate_ids(self):
        record, _ = self.run_script([])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            aggregate_itt([record, record])
        hidden = asdict(record)
        hidden["itt_included"] = False
        with self.assertRaisesRegex(ValueError, "cannot be excluded"):
            aggregate_itt([hidden])


if __name__ == "__main__":
    unittest.main()
