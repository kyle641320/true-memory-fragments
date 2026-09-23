"""Native function calls reach only the existing bounded local repo tools."""
from __future__ import annotations

import dataclasses
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from bench.agent_ab.same_version_chain_v1.successor_openai_protocol import LocalMediation, MediationFailure
from bench.agent_ab.same_version_chain_v1.m10_successor_fixture import prepare_fixture, compile_check
from bench.agent_ab.same_version_chain_v1.guava_m10_successor_runner import score_placement_ast
from bench.agent_ab.same_version_chain_v1.m10_successor_protocol import BudgetCaps
from tests.test_m10_successor_openai_responses import prepared, response, encoded
from tests.test_guava_m10_successor import compiler_available


class MediationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.template = self.root / "template"
        prepare_fixture(self.template)
        self.compile = Mock(return_value={"ok": True, "exit": 0})
        self.score = lambda root: score_placement_ast((root / "Dispatcher.java").read_text())
        guard = patch("socket.socket.connect", side_effect=AssertionError("network forbidden"))
        guard.start()
        self.addCleanup(guard.stop)

    def session(self, **kwargs):
        session = LocalMediation(self.template, prepared(), compile_fn=kwargs.pop("compile_fn", self.compile),
                                 score_fn=self.score, ledger_path=self.root / "ledger.jsonl", **kwargs)
        self.addCleanup(session.__exit__)
        return session

    def raw(self, session, name="list", arguments=None):
        value = response(session.prepared, name=name, arguments=arguments)
        suffix = str(session.turns)
        value["id"] += suffix
        for item in value["output"]:
            item["id"] += suffix
            if "call_id" in item:
                item["call_id"] += suffix
        return encoded(value)

    def step(self, session, name="list", arguments=None):
        return session.step(self.raw(session, name, arguments), expected_input_tokens=800)

    def test_read_tool_feedback_and_all_state_enter_next_frozen_input(self):
        session = self.session()
        before = json.loads(session.prepared.count_json)["input"]
        raw = self.raw(session, "read_range", {"path": "Dispatcher.java", "start": 1, "end": 2})
        observed = json.loads(raw)["output"]
        after = session.step(raw, expected_input_tokens=800)
        items = json.loads(after.count_json)["input"]
        self.assertEqual(before + observed, items[:-1])
        self.assertEqual(observed[-1]["call_id"], items[-1]["call_id"])
        self.assertTrue(json.loads(items[-1]["output"])["ok"])
        self.compile.assert_not_called()

    def test_edit_compile_final_and_independent_semantic_result(self):
        session = self.session()
        before = (self.template / "Dispatcher.java").read_bytes()
        self.step(session, "edit", {"path": "Dispatcher.java", "old": "      prepared.subscriber.dispatchEvent(prepared.event);",
                                    "new": "      hook();\n      prepared.subscriber.dispatchEvent(prepared.event);"})
        self.step(session, "compile")
        self.assertIsNone(self.step(session, "final", {"answer": "handoff", "files": ["Dispatcher.java"]}))
        result = session.evaluate()
        self.assertTrue(result["protocol_ok"])
        self.assertTrue(result["semantic"]["semantic_pass"])
        self.assertTrue(result["compile"]["ok"])
        self.assertEqual(before, (self.template / "Dispatcher.java").read_bytes())
        self.assertEqual(2, self.compile.call_count)

    @unittest.skipUnless(compiler_available(), "frozen offline JARs/javac unavailable; dedicated CI requires compilation")
    def test_real_javac_native_compile_is_not_mock_evidence(self):
        session = self.session(compile_fn=compile_check)
        result = self.step(session, "compile")
        feedback = json.loads(json.loads(result.count_json)["input"][-1]["output"])
        self.assertTrue(feedback["ok"], feedback)

    def test_stale_compile_cannot_finish_after_edit(self):
        session = self.session()
        self.step(session, "compile")
        self.step(session, "edit", {"path": "Dispatcher.java", "old": "class Dispatcher", "new": "class /*中文*/ Dispatcher"})
        with self.assertRaisesRegex(MediationFailure, "current_compile"):
            self.step(session, "final", {"answer": "done", "files": ["Dispatcher.java"]})
        result = session.evaluate()
        self.assertFalse(result["protocol_ok"])
        self.assertTrue(result["itt_included"])

    def test_final_file_mismatch_is_terminal(self):
        session = self.session()
        self.step(session, "compile")
        with self.assertRaisesRegex(MediationFailure, "file_report"):
            self.step(session, "final", {"answer": "done", "files": ["Dispatcher.java"]})
        with self.assertRaisesRegex(MediationFailure, "closed"):
            self.step(session, "compile")

    def test_forbidden_path_never_enters_local_tool(self):
        session = self.session()
        before = (session.root / "Dispatcher.java").read_bytes()
        with self.assertRaises(MediationFailure):
            self.step(session, "edit", {"path": "../outside.java", "old": "a", "new": "b"})
        self.assertEqual(before, (session.root / "Dispatcher.java").read_bytes())
        self.compile.assert_not_called()
        self.assertFalse(session.evaluate()["protocol_ok"])

    def test_multiple_calls_reject_before_any_tool_dispatch(self):
        session = self.session()
        value = json.loads(self.raw(session))
        value["output"].append({**value["output"][-1], "id": "different", "call_id": "different"})
        with patch.object(session.workspace, "dispatch") as dispatch:
            with self.assertRaises(MediationFailure):
                session.step(encoded(value), expected_input_tokens=800)
            dispatch.assert_not_called()

    def test_unknown_tool_and_bad_json_fail_before_mediation(self):
        for name, arguments in (("web_search", "{}"), ("list", '{"x":1,"x":2}')):
            with self.subTest(name=name):
                session = self.session()
                value = json.loads(self.raw(session))
                value["output"][-1].update(name=name, arguments=arguments)
                with self.assertRaises(MediationFailure):
                    session.step(encoded(value), expected_input_tokens=800)
        self.compile.assert_not_called()

    def test_replayed_function_id_cannot_execute_local_action_twice(self):
        session = self.session()
        self.step(session, "list")
        value = json.loads(self.raw(session, "compile"))
        value["output"][-1]["call_id"] = "call_offline0"
        with self.assertRaises(MediationFailure):
            session.step(encoded(value), expected_input_tokens=800)
        self.compile.assert_not_called()

    def test_tool_failure_kept_in_itt_ledger_not_retried(self):
        session = self.session()
        with self.assertRaises(MediationFailure):
            self.step(session, "edit", {"path": "Dispatcher.java", "old": "absent-anchor", "new": "x"})
        rows = [json.loads(line) for line in (self.root / "ledger.jsonl").read_text().splitlines()]
        self.assertEqual("local_failed", rows[-1]["event"])
        self.assertTrue(rows[-1]["itt_included"])
        self.assertEqual(1, session.turns)

    def test_tool_output_limit_is_terminal_without_truncation(self):
        caps = dataclasses.replace(BudgetCaps(), max_tool_output_bytes=100)
        session = self.session(caps=caps)
        with self.assertRaisesRegex(MediationFailure, "tool_output_budget"):
            self.step(session, "read_range", {"path": "Dispatcher.java", "start": 1, "end": 100})

    def test_template_symlink_rejected(self):
        target = self.template / "Dispatcher.java"
        original = self.root / "outside.java"
        target.rename(original)
        target.symlink_to(original)
        with self.assertRaisesRegex(MediationFailure, "source_path_denied"):
            self.session()


if __name__ == "__main__":
    unittest.main()
