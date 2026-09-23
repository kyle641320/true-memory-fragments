"""Execution boundaries, not treatment-effect or live-host evidence."""
from __future__ import annotations

import copy
import io
import json
import os
import tempfile
import time
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import Mock, patch

from bench.agent_ab.same_version_chain_v1 import successor_codex_control as control
from bench.agent_ab.same_version_chain_v1 import successor_codex_runner as runner
from bench.agent_ab.same_version_chain_v1 import successor_codex_mediation as mediation
from bench.agent_ab.same_version_chain_v1.m10_successor_fixture import FILE, PKG_FILES, prepare_fixture
from bench.agent_ab.same_version_chain_v1.m10_successor_protocol import BudgetCaps, RunRecord
from bench.agent_ab.same_version_chain_v1.m10_successor_run_ledger import (
    CODEX_OFFLINE_KIND, CODEX_PILOT_KIND, RunAdmissionLedger, RunLedgerError, RunLedgerTransitionError,
)
from bench.agent_ab.same_version_chain_v1.successor_codex_control import (
    EventJournal, RuntimeGuard, expected_identity, runtime_profile, verify_event_journal,
)
from bench.agent_ab.same_version_chain_v1.successor_codex_mediation import MediatedWorkspace, RuntimeViolation
from bench.agent_ab.same_version_chain_v1.successor_codex_host import HostNotReadyError


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.abort = Mock(return_value=True)
        self.profile = runtime_profile()
        self.guard = RuntimeGuard(self.profile, emit=self.events.append, abort=self.abort)

    def arm(self):
        self.guard.before_agent_turn(expected_identity(self.profile))

    def test_frozen_request_admission_required_before_tools(self):
        with self.assertRaisesRegex(RuntimeViolation, "requested_configuration_missing"):
            self.guard.tool(control.TOOL_NAME)
        self.abort.assert_called_once()

    def test_every_requested_model_effort_runtime_policy_mismatch_is_sticky(self):
        for key in expected_identity(self.profile):
            with self.subTest(key=key):
                guard = RuntimeGuard(self.profile, emit=lambda e: None, abort=self.abort)
                requested = expected_identity(self.profile)
                requested[key] = "different"
                with self.assertRaisesRegex(RuntimeViolation, "configuration_mismatch"):
                    guard.before_agent_turn(requested)
                self.assertEqual(0, guard.agent_turns)
                with self.assertRaises(RuntimeViolation):
                    guard.before_agent_turn(expected_identity(self.profile))

    def test_reroute_effort_config_failure_and_native_tool_abort(self):
        for kind in ("model/rerouted", "model_mismatch", "effort_drift", "configuration_drift",
                     "runtime_failure", "native_tool", "tool_bypass", "workspace_escape", "blocking_runtime_anomaly"):
            with self.subTest(kind=kind):
                guard = RuntimeGuard(self.profile, emit=self.events.append, abort=self.abort)
                guard.before_agent_turn(expected_identity(self.profile))
                with self.assertRaises(RuntimeViolation):
                    guard.observe({"event": kind})
                with self.assertRaises(RuntimeViolation):
                    guard.tool(control.TOOL_NAME)
                self.assertIs(guard.abort_acknowledged, True)

    def test_different_tool_is_rejected_before_dispatch(self):
        self.arm()
        with self.assertRaisesRegex(RuntimeViolation, "tool_bypass"):
            self.guard.tool("exec_command")

    def test_effort_observation_not_requested_string_drives_rejection(self):
        self.arm()
        with self.assertRaisesRegex(RuntimeViolation, "effort_drift"):
            self.guard.observe({"event": "configuration_observed",
                                "observed": {"effort": "high", "source": "test_runtime_event"}})

    def test_unavailable_provider_attestation_is_accepted_without_fabrication(self):
        self.arm()
        self.guard.tool(control.TOOL_NAME)
        admitted = self.events[-1]
        self.assertEqual("agent_turn_admitted", admitted["event"])
        self.assertEqual({}, admitted["observed"])
        self.assertNotIn("actual", admitted)
        self.assertEqual(expected_identity(self.profile), admitted["requested_and_controlled"])
        self.assertIs(admitted["provider_actual_model_attested"], False)
        self.assertIs(admitted["provider_effective_effort_attested"], False)
        snapshot = self.guard.snapshot()
        self.assertIs(snapshot["request_configuration_verified_at_control_boundary"], True)
        self.assertIsNone(snapshot["not_observable"]["pre_inference_provider_actual_model"])
        self.assertIsNone(snapshot["not_observable"]["pre_inference_provider_effective_effort"])
        self.assertNotIn("actual_identity_verified_at_control_boundary", snapshot)

    def test_matching_runtime_observation_never_becomes_provider_attestation(self):
        observation = {"model": control.NATIVE_MODEL, "effort": control.EFFORT,
                       "source": "test_thread_response_not_provider_attestation"}
        self.guard.before_agent_turn(expected_identity(self.profile), observation)
        self.assertEqual(observation, self.events[-1]["observed"])
        self.assertIs(self.guard.snapshot()["provider_actual_model_attested"], False)
        self.assertIs(self.guard.snapshot()["provider_effective_effort_attested"], False)
        self.guard.observe({"event": "model_observed",
                            "observed": {"model": control.MODEL, "source": "test_runtime_event"}})

    def test_present_pre_agent_turn_observation_mismatch_rejects_before_admission(self):
        for key, value, category in (("model", "other-model", "observed_model_mismatch"),
                                     ("effort", "high", "effort_drift"),
                                     ("runtime", "other-runtime", "observed_runtime_mismatch"),
                                     ("openclaw_version", "2026.9.5", "observed_configuration_mismatch"),
                                     ("model_fallback_allowed", True, "observed_configuration_mismatch")):
            with self.subTest(key=key):
                events = []
                guard = RuntimeGuard(self.profile, emit=events.append, abort=self.abort)
                observed = {key: value, "source": "test_runtime_event"}
                with self.assertRaisesRegex(RuntimeViolation, category):
                    guard.before_agent_turn(expected_identity(self.profile), observed)
                self.assertEqual(0, guard.agent_turns)
                self.assertEqual(observed, events[0]["observed"])
                self.assertFalse(any(e["event"] == "agent_turn_admitted" for e in events))

    def test_null_observation_is_not_mismatch_and_request_cannot_fill_actual(self):
        self.guard.before_agent_turn(expected_identity(self.profile), {"model": None, "effort": None})
        self.assertEqual({"model": None, "effort": None}, self.events[-1]["observed"])
        with self.assertRaisesRegex(RuntimeViolation, "unlabelled_actual_identity_evidence"):
            self.guard.observe({"event": "configuration_observed", "actual": expected_identity(self.profile)})

    def test_observed_value_requires_explicit_source_and_wrong_types_fail(self):
        for observed, category in (({"model": control.NATIVE_MODEL}, "observation_source_missing"),
                                   ({"model": control.NATIVE_MODEL, "source": " "}, "observation_source_missing"),
                                   ({"source": "test", "model_fallback_allowed": 0}, "configuration_mismatch"),
                                   ({"source": "test", "request_model": control.MODEL}, "invalid_runtime_observation")):
            with self.subTest(observed=observed):
                guard = RuntimeGuard(self.profile, emit=self.events.append, abort=self.abort)
                with self.assertRaisesRegex(RuntimeViolation, category):
                    guard.before_agent_turn(expected_identity(self.profile), observed)
                self.assertEqual(0, guard.agent_turns)

    def test_drift_event_between_agent_turns_is_retained_and_stops_block(self):
        self.arm()
        self.guard.end_agent_turn()
        event = {"event": "model_observed", "observed": {"model": "other-model", "source": "test_runtime_event"}}
        with self.assertRaisesRegex(RuntimeViolation, "observed_model_mismatch"):
            self.guard.observe(event)
        self.assertIn(event, self.events)
        self.assertIs(self.guard.abort_acknowledged, True)

    def test_openclaw_version_and_disabled_fallback_are_frozen_controls(self):
        requested = expected_identity(self.profile)
        self.assertEqual("2026.9.2", requested["openclaw_version"])
        self.assertIs(requested["model_fallback_allowed"], False)
        self.assertEqual(control.MODEL, requested["request_model"])
        self.assertEqual(control.NATIVE_MODEL, requested["request_native_model"])
        self.assertEqual("medium", requested["request_effort"])
        self.assertNotIn("resolved_model", requested)
        self.assertNotIn("effort", requested)
        requested["model_fallback_allowed"] = 0
        with self.assertRaisesRegex(RuntimeViolation, "requested_configuration_mismatch"):
            self.guard.before_agent_turn(requested)

    def test_external_agent_turn_cap_is_independent_of_internal_retry_observations(self):
        for _ in range(BudgetCaps().max_turns):
            self.arm()
            self.guard.observe({"event": "retry_observed", "reason": "common_runtime_retry"})
            self.guard.end_agent_turn()
        with self.assertRaisesRegex(RuntimeViolation, "agent_turn_budget_exceeded"):
            self.arm()
        self.assertEqual(BudgetCaps().max_turns, self.guard.agent_turns)

    def test_internal_iterations_and_retries_are_telemetry_not_external_admissions(self):
        self.arm()
        for index in range(BudgetCaps().max_turns + 1):
            self.guard.observe({"event": "retry_observed", "source": "test", "index": index})
            self.guard.observe({"event": "inference_completed", "source": "test"})
            self.guard.tool(control.TOOL_NAME)
        self.assertEqual(1, self.guard.agent_turns)
        self.guard.end_agent_turn()
        for kind in ("runtime_event", "usage_observed", "retry_observed", "iteration_observed"):
            self.guard.observe({"event": kind, "source": "test", "value": None})
        snapshot = self.guard.snapshot()
        self.assertIsNone(snapshot["internal_inference_count"])
        self.assertIsNone(snapshot["internal_retry_count"])
        self.assertEqual(25, snapshot["telemetry_event_counts_not_internal_totals"]["inference_completed"])
        self.assertEqual("idle", snapshot["phase"])
        self.assertNotIn("inferences", snapshot)

    def test_generic_runtime_observation_still_checks_present_drift_between_turns(self):
        self.arm()
        self.guard.end_agent_turn()
        with self.assertRaisesRegex(RuntimeViolation, "effort_drift"):
            self.guard.observe({"event": "runtime_event", "observed": {"effort": "high", "source": "test"}})
        self.abort.assert_called_once()

    def test_external_budget_profile_retains_caps_without_internal_inference_requirement(self):
        caps = asdict(BudgetCaps())
        self.assertEqual(caps, self.profile["budget"]["scientific_caps"])
        self.assertEqual(24, self.profile["budget"]["max_external_agent_turns_per_run"])
        self.assertEqual(24, self.profile["budget"]["max_mediated_actions_per_run"])
        self.assertIs(self.profile["budget"]["native_inference_pre_reservation_required"], False)
        self.assertIsNone(self.profile["budget"]["native_inference_retry_count_cap"])
        self.assertNotIn("max_observed_runtime_inferences_per_run", self.profile["budget"])
        self.assertNotIn("all_inference_admission_and_absolute_deadline", self.profile["required_host_capabilities"])

    def test_output_and_unknown_events_fail_closed(self):
        self.arm()
        with self.assertRaisesRegex(RuntimeViolation, "output_budget"):
            self.guard.observe({"event": "assistant_output", "text": "x" * 120001})
        guard = RuntimeGuard(self.profile, emit=lambda e: None, abort=self.abort)
        guard.before_agent_turn(expected_identity(self.profile))
        with self.assertRaisesRegex(RuntimeViolation, "unknown_runtime_event"):
            guard.observe({"event": "unexpected"})

    def test_deadline_is_absolute_and_abort_uncertainty_is_retained(self):
        self.arm()
        self.guard.abort = Mock(side_effect=OSError())
        self.guard.deadline = 0
        with self.assertRaisesRegex(RuntimeViolation, "run_timeout"):
            self.guard.check()
        self.assertIs(self.guard.abort_acknowledged, False)

    def test_durable_admission_failure_prevents_external_turn(self):
        self.guard.emit = Mock(side_effect=OSError())
        with self.assertRaisesRegex(RuntimeViolation, "evidence_write_failed"):
            self.arm()
        self.assertEqual(0, self.guard.agent_turns)
        self.abort.assert_called_once()

    def test_profile_cannot_silently_change_caps_or_model(self):
        self.profile["reasoning_effort"] = "high"
        with self.assertRaisesRegex(RuntimeViolation, "profile_drift"):
            RuntimeGuard(self.profile, emit=self.events.append, abort=self.abort)

    def test_external_agent_turn_completion_revokes_tool_authority(self):
        self.arm()
        self.guard.end_agent_turn()
        with self.assertRaisesRegex(RuntimeViolation, "requested_configuration_missing"):
            self.guard.tool(control.TOOL_NAME)

    def test_runtime_completion_is_terminal_and_nested_admission_is_rejected(self):
        self.arm()
        self.guard.end_agent_turn()
        self.guard.observe({"event": "runtime_completed"})
        self.assertEqual("completed", self.guard.phase)
        with self.assertRaisesRegex(RuntimeViolation, "after_runtime_completed"):
            self.guard.observe({"event": "assistant_output", "text": "late"})
        guard = RuntimeGuard(self.profile, emit=self.events.append, abort=self.abort)
        guard.before_agent_turn(expected_identity(self.profile))
        with self.assertRaisesRegex(RuntimeViolation, "agent_turn_transition"):
            guard.before_agent_turn(expected_identity(self.profile))

    def test_unresponsive_peer_is_bounded_without_waiting_for_callback(self):
        class Stalled:
            def run(self, guard, workspace):
                time.sleep(3)
        self.guard.deadline = time.monotonic() + 0.03
        before = time.monotonic()
        with self.assertRaisesRegex(RuntimeViolation, "run_timeout"):
            runner.run_bounded_peer(Stalled(), self.guard, None)
        self.assertLess(time.monotonic() - before, 1)
        self.abort.assert_called_once()

    def test_nested_action_does_not_reset_outer_absolute_deadline(self):
        with patch.object(mediation.time, "monotonic", side_effect=[100, 104]), \
             patch.object(mediation.signal, "getitimer", return_value=(10, 0)), \
             patch.object(mediation.signal, "signal"), \
             patch.object(mediation.signal, "setitimer") as timer:
            self.assertEqual("ok", mediation.bounded_call(lambda: "ok", 20))
        values = [call.args[1:] for call in timer.call_args_list]
        self.assertEqual([(10,), (0,), (6, 0)], values)


class MediationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "source"
        self.root.mkdir()
        prepare_fixture(self.root, "t1")
        self.events = []
        self.compile = Mock(return_value={"ok": True})
        self.score = Mock(return_value={"semantic_pass": False})

    def workspace(self, caps=BudgetCaps(), **kwargs):
        return MediatedWorkspace(self.root, budgets=caps, compile_fn=self.compile,
                                 score_fn=self.score, emit=kwargs.get("emit", self.events.append),
                                 verify_active=kwargs.get("verify_active", lambda: None),
                                 initial_messages=[{"role": "system", "content": "common"},
                                                   {"role": "user", "content": "common task"}])

    def call(self, workspace, action):
        workspace.prepare_agent_turn()
        return workspace.call(action)

    def test_scientific_input_must_be_charged_before_runtime_request(self):
        ws = self.workspace()
        with self.assertRaisesRegex(RuntimeViolation, "input_not_admitted"):
            ws.call({"action": "list"})
        ws = self.workspace(replace(BudgetCaps(), max_input_bytes_per_turn=1))
        with self.assertRaisesRegex(RuntimeViolation, "input_budget"):
            ws.prepare_agent_turn()
        self.assertEqual(0, ws.usage["scientific_input_charges"])
        ws = self.workspace()
        ws.prepare_agent_turn()
        self.assertGreater(ws.usage["input_bytes"], 0)
        ws.messages.append({"role": "user", "content": "changed after count"})
        with self.assertRaisesRegex(RuntimeViolation, "input_drift"):
            ws.call({"action": "list"})

    def test_external_dispatch_charges_input_once_then_multiple_actions_charge_history(self):
        ws = self.workspace()
        ws.prepare_agent_turn()
        initial = ws.usage["input_bytes"]
        ws.prepare_agent_turn()
        self.assertEqual(2 * initial, ws.usage["input_bytes"])
        ws.call({"action": "list"})
        self.assertEqual(2 * initial, ws.usage["input_bytes"])
        ws.call({"action": "list"})
        self.assertGreater(ws.usage["input_bytes"], 3 * initial)
        self.assertEqual(3, ws.usage["scientific_input_charges"])
        self.assertEqual(2, ws.usage["externally_admitted_agent_turns"])
        self.assertEqual(2, ws.usage["turns"])

    def test_one_external_turn_cannot_bypass_action_cap(self):
        ws = self.workspace(replace(BudgetCaps(), max_turns=1))
        ws.prepare_agent_turn()
        ws.call({"action": "list"})
        with self.assertRaisesRegex(RuntimeViolation, "action_budget_exceeded"):
            ws.call({"action": "compile"})
        self.compile.assert_not_called()

    def test_later_action_checks_growing_history_total_before_effects(self):
        probe = self.workspace()
        probe.prepare_agent_turn()
        initial = probe.usage["input_bytes"]
        ws = self.workspace(replace(BudgetCaps(), max_total_input_bytes=initial * 2))
        ws.prepare_agent_turn()
        ws.call({"action": "list"})
        with self.assertRaisesRegex(RuntimeViolation, "input_budget_exceeded"):
            ws.call({"action": "compile"})
        self.compile.assert_not_called()
        self.assertEqual(1, ws.usage["turns"])

    def test_internal_telemetry_neither_charges_scientific_input_nor_revokes_tools(self):
        ws = self.workspace()
        guard = RuntimeGuard(runtime_profile(), emit=self.events.append, abort=lambda _: True)
        ws.verify_active = guard.check
        ws.prepare_agent_turn()
        guard.before_agent_turn(expected_identity(runtime_profile()))
        initial = ws.usage["input_bytes"]
        for _ in range(25):
            guard.observe({"event": "retry_observed", "source": "test"})
            guard.observe({"event": "inference_completed", "source": "test"})
        guard.tool(control.TOOL_NAME)
        ws.call({"action": "list"})
        self.assertEqual(initial, ws.usage["input_bytes"])
        guard.tool(control.TOOL_NAME)
        ws.call({"action": "compile"})
        self.assertEqual(1, ws.usage["externally_admitted_agent_turns"])
        self.assertEqual(2, ws.usage["turns"])
        guard.end_agent_turn()
        with self.assertRaisesRegex(RuntimeViolation, "requested_configuration_missing"):
            ws.call({"action": "list"})

    def test_same_actions_preserve_tool_and_scoring_boundaries(self):
        ws = self.workspace()
        self.call(ws, {"action": "read_range", "path": FILE, "start": 1, "end": 5})
        self.call(ws, {"action": "compile"})
        self.call(ws, {"action": "final", "answer": "No change", "files": []})
        self.assertTrue(ws.protocol_ok)
        self.assertEqual(1, ws.usage["source_read_actions"])
        self.assertEqual([FILE], ws.usage["source_files_received"])
        self.assertNotIn(str(self.root), json.dumps(self.events))
        self.score.assert_not_called()
        result = ws.evaluate()
        self.assertFalse(result["semantic"]["semantic_pass"])
        self.assertTrue(result["compilation"]["ok"])

    def test_private_reader_rejects_escape_absolute_and_unknown_action(self):
        for action in ({"action": "read_range", "path": "../other/Dispatcher.java", "start": 1, "end": 2},
                       {"action": "read_range", "path": str(self.root / FILE), "start": 1, "end": 2},
                       {"action": "exec", "command": "cat ../control.json"}):
            with self.subTest(action=action), self.assertRaises(RuntimeViolation):
                self.call(self.workspace(), action)

    def test_symlink_hardlink_and_unexpected_file_refused(self):
        target = self.root / FILE
        content = target.read_bytes()
        external = self.root.parent / "outside"
        external.write_bytes(content)
        target.unlink()
        target.symlink_to(external)
        with self.assertRaisesRegex(RuntimeViolation, "workspace_escape"):
            self.workspace()
        target.unlink()
        os.link(external, target)
        with self.assertRaisesRegex(RuntimeViolation, "workspace_escape"):
            self.workspace()
        target.unlink()
        target.write_bytes(content)
        (self.root / "control.json").write_text("not model material")
        with self.assertRaisesRegex(RuntimeViolation, "inventory_drift"):
            self.workspace()

    def test_source_swap_during_admission_is_detected_before_edit(self):
        target = self.root / FILE
        original = target.read_text()
        external = self.root.parent / "outside"
        external.write_text(original)
        def emit(event):
            if event["event"] == "action_admitted":
                target.unlink()
                target.symlink_to(external)
        ws = self.workspace(emit=emit)
        with self.assertRaises(RuntimeViolation):
            self.call(ws, {"action": "edit", "path": FILE, "old": "prepared.event", "new": "changed"})
        self.assertEqual(original, external.read_text())

    def test_admission_evidence_failure_prevents_edit(self):
        before = (self.root / FILE).read_bytes()
        ws = self.workspace(emit=Mock(side_effect=OSError()))
        with self.assertRaisesRegex(RuntimeViolation, "evidence_write_failed"):
            self.call(ws, {"action": "edit", "path": FILE,
                     "old": "      prepared.subscriber.dispatchEvent(prepared.event);", "new": "      hook();"})
        self.assertEqual(before, (self.root / FILE).read_bytes())

    def test_result_evidence_failure_does_not_claim_read_was_delivered(self):
        def emit(event):
            if event["event"] == "tool_result":
                raise OSError()
        ws = self.workspace(emit=emit)
        with self.assertRaises(RuntimeViolation):
            self.call(ws, {"action": "read_range", "path": FILE, "start": 1, "end": 2})
        self.assertEqual(0, ws.usage["source_read_actions"])
        with self.assertRaises(RuntimeViolation):
            self.call(ws, {"action": "list"})

    def test_action_input_output_tool_and_file_caps(self):
        cases = [(replace(BudgetCaps(), max_turns=1), "agent_turn_budget_exceeded"),
                 (replace(BudgetCaps(), max_input_bytes_per_turn=1), "input_budget_exceeded"),
                 (replace(BudgetCaps(), max_output_bytes_per_turn=1), "output_budget_exceeded"),
                 (replace(BudgetCaps(), max_tool_output_bytes=1), "tool_output_budget_exceeded")]
        for caps, category in cases:
            ws = self.workspace(caps)
            if category == "agent_turn_budget_exceeded":
                self.call(ws, {"action": "list"})
            with self.subTest(category=category), self.assertRaisesRegex(RuntimeViolation, category):
                self.call(ws, {"action": "list"})
        with self.assertRaisesRegex(RuntimeViolation, "file_budget_exceeded"):
            self.workspace(replace(BudgetCaps(), max_file_bytes=1))

    def test_final_requires_compile_and_exact_files_and_cannot_continue(self):
        with self.assertRaisesRegex(RuntimeViolation, "without_current_compile"):
            self.call(self.workspace(), {"action": "final", "answer": "done", "files": []})
        ws = self.workspace()
        self.call(ws, {"action": "compile"})
        with self.assertRaisesRegex(RuntimeViolation, "file_report_mismatch"):
            self.call(ws, {"action": "final", "answer": "done", "files": [FILE]})
        ws = self.workspace()
        self.call(ws, {"action": "compile"})
        self.call(ws, {"action": "final", "answer": "done", "files": []})
        with self.assertRaisesRegex(RuntimeViolation, "after_final"):
            self.call(ws, {"action": "list"})

    def test_both_evaluations_run_after_protocol_or_scorer_failure(self):
        ws = self.workspace()
        with self.assertRaises(RuntimeViolation):
            self.call(ws, {"action": "bad"})
        self.score.side_effect = ValueError()
        result = ws.evaluate()
        self.assertIsNone(result["semantic"]["semantic_pass"])
        self.assertTrue(result["compilation"]["ok"])
        self.assertEqual(1, self.compile.call_count)

    def test_artifact_preservation_refuses_replaced_root_or_source(self):
        ws = self.workspace()
        expected = (self.root / FILE).read_bytes()
        self.assertEqual(expected, ws.artifact_bytes())
        outside = self.root.parent / "outside"
        outside.write_text("not experiment source")
        (self.root / FILE).unlink()
        (self.root / FILE).symlink_to(outside)
        with self.assertRaises(RuntimeViolation):
            ws.artifact_bytes()

    def test_artifact_preservation_survives_non_workspace_protocol_failure(self):
        ws = self.workspace()
        expected = (self.root / FILE).read_bytes()
        with self.assertRaises(RuntimeViolation):
            self.call(ws, {"action": "invalid"})
        self.assertEqual(expected, ws.artifact_bytes())


class JournalTests(unittest.TestCase):
    def test_valid_prefix_truncation_and_inode_replacement_are_not_integrity(self):
        for kind in ("truncate", "replace", "rewrite"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "events"
                journal = EventJournal(path)
                self.addCleanup(journal.close)
                journal.emit({"event": "first"})
                prefix = path.read_bytes()
                journal.emit({"event": "second"})
                expected = journal.verify_live()
                full = path.read_bytes()
                if kind == "truncate":
                    path.write_bytes(prefix)
                    with self.assertRaises(RuntimeViolation):
                        verify_event_journal(path, expected=expected)
                elif kind == "replace":
                    replacement = Path(folder) / "replacement"
                    replacement.write_bytes(full)
                    replacement.replace(path)
                else:
                    path.write_bytes(full.replace(b'first', b'third'))
                with self.assertRaises(RuntimeViolation):
                    journal.verify_live()
                with self.assertRaises(RuntimeViolation):
                    journal.emit({"event": "must_not_continue"})

    def test_json_artifact_parent_entry_is_durable(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "summary.json"
            seen, real = [], os.fsync
            def sync(fd):
                seen.append(os.readlink('/proc/self/fd/' + str(fd)))
                real(fd)
            with patch.object(os, "fsync", side_effect=sync):
                runner._write(path, {"ok": True})
            self.assertEqual([str(path), folder], seen)
            with self.assertRaises(FileExistsError):
                runner._write(path, {"ok": False})

    def test_event_integrity_reopening_and_corruption(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "deep" / "raw" / "events.jsonl"
            journal = EventJournal(path)
            journal.emit({"event": "first"})
            journal.emit({"event": "second"})
            journal.close()
            self.assertEqual(2, len(verify_event_journal(path)))
            with self.assertRaises(FileExistsError):
                EventJournal(path)
            path.write_bytes(path.read_bytes()[:-1])
            with self.assertRaises(RuntimeViolation):
                verify_event_journal(path)

    def test_new_directory_entries_are_synced_before_event_dispatch(self):
        with tempfile.TemporaryDirectory() as folder:
            seen = []
            real = os.fsync
            def fsync(fd):
                seen.append(os.readlink('/proc/self/fd/' + str(fd)))
                real(fd)
            with patch.object(os, "fsync", side_effect=fsync):
                journal = EventJournal(Path(folder) / "a" / "b" / "events")
                journal.emit({"event": "admitted"})
                journal.close()
            self.assertEqual([folder, folder + '/a', folder + '/a/b', folder + '/a/b/events'], seen)

    def test_evidence_failure_stays_sticky(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = EventJournal(Path(folder) / "events")
            self.addCleanup(journal.close)
            with patch.object(os, "fsync", side_effect=OSError()):
                with self.assertRaises(RuntimeViolation):
                    journal.emit({"event": "first"})
            with self.assertRaises(RuntimeViolation):
                journal.emit({"event": "second"})

    def test_codex_ledger_keeps_six_ids_and_stops_after_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "runs"
            ids = [f"opaque_{i}" for i in range(6)]
            with RunAdmissionLedger(path, "a" * 64, ids, evidence_kind=CODEX_OFFLINE_KIND) as ledger:
                ledger.start(ids[0])
                row = asdict(RunRecord(run_id=ids[0], seal_sha256="a" * 64,
                                       evidence_kind=CODEX_OFFLINE_KIND, durable_ledger=True,
                                       protocol_status="failed", failure_reason="model_rerouted"))
                ledger.complete(row)
                with self.assertRaises(RunLedgerTransitionError):
                    ledger.start(ids[1])
                state = ledger.snapshot()
                self.assertEqual(6, state["denominator"])
                self.assertEqual(ids[1:], state["not_started_run_ids"])
            with RunAdmissionLedger(path, "a" * 64, ids, evidence_kind=CODEX_OFFLINE_KIND) as ledger:
                self.assertTrue(ledger.snapshot()["inspection_only"])
            with self.assertRaises(RunLedgerError):
                RunAdmissionLedger(path, "a" * 64, ids, evidence_kind=CODEX_PILOT_KIND)


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.science = {
            "randomization": {"blocks": 1, "schedule": runner.science.build_randomized_schedule(1, 20260923)},
            "inputs": {arm: [{"role": "system", "content": "common"},
                              {"role": "user", "content": "task"}] for arm in runner.science.ARMS},
            "execution": {"budgets": asdict(BudgetCaps())},
            "action_schemas": copy.deepcopy(runner.science.ACTION_SCHEMAS),
            "seal_sha256": "b" * 64,
        }

    def manifest(self):
        # Unit bookkeeping only. CLI always performs full production preflight.
        with patch.object(runner.science, "verify_sealed_manifest"), patch.object(runner, "inventory", return_value={}):
            return runner.build_manifest(self.science)

    def test_every_fault_stops_block_without_shrinking_denominator(self):
        for scenario in runner.SCENARIOS[1:]:
            out = self.root / scenario
            with self.subTest(scenario=scenario), patch.object(runner, "verify_manifest"), \
                 patch.object(runner.science, "compile_check", return_value={"ok": True}):
                result = runner.rehearse(self.manifest(), out, scenario=scenario)
            accounting = json.loads((out / "accounting.json").read_text())
            self.assertEqual(6, result["denominator"])
            self.assertEqual(0, result["protocol_complete"])
            self.assertEqual(1, accounting["started_runs"])
            self.assertEqual(5, len(accounting["not_started_run_ids"]))
            self.assertEqual(0, result["model_calls"])
            self.assertTrue(result["journal_integrity_verified"])
            self.assertEqual(runner.EXPECTED_FAILURES[scenario], result["stopped_reason"])
            self.assertTrue(runner.scenario_passes(result))
            unrelated = dict(result, stopped_reason="unrelated_infrastructure_failure")
            self.assertFalse(runner.scenario_passes(unrelated))

    def test_positive_fake_block_is_not_live_evidence(self):
        out = self.root / "ok"
        with patch.object(runner, "verify_manifest"), \
             patch.object(runner.science, "compile_check", return_value={"ok": True}):
            result = runner.rehearse(self.manifest(), out)
        self.assertEqual(6, result["protocol_complete"])
        self.assertEqual(6, result["joint_success"])
        self.assertEqual(0, result["live_model_runs"])
        self.assertEqual("NOT_READY_FOR_LIVE_HOST", result["readiness"])
        self.assertTrue(runner.scenario_passes(result))
        with patch.object(runner, "verify_manifest"), self.assertRaisesRegex(RuntimeViolation, "no_resume"):
            runner.rehearse(self.manifest(), out)

    def test_bad_seal_prevents_any_admission_or_peer(self):
        manifest = self.manifest()
        manifest["profile"]["reasoning_effort"] = "high"
        with patch.object(runner, "OfflinePeer") as peer, self.assertRaises(RuntimeViolation):
            runner.rehearse(manifest, self.root / "not-created")
        peer.assert_not_called()
        self.assertFalse((self.root / "not-created").exists())

    def test_live_entry_rejects_even_a_self_declared_ready_host_before_admission(self):
        manifest = self.manifest()
        manifest["host_qualification"] = {"verdict": "READY", "capabilities": ["everything"]}
        with patch.object(runner, "verify_manifest"), patch.object(runner, "OfflinePeer") as peer:
            with self.assertRaises(HostNotReadyError):
                runner.run_live_pilot(manifest, self.root / "never-admitted")
        peer.assert_not_called()
        self.assertFalse((self.root / "never-admitted").exists())

    def test_readiness_cli_is_structured_no_before_admission(self):
        path = self.root / "manifest.json"
        path.write_text(json.dumps(self.manifest()))
        with patch.object(runner, "verify_manifest"), patch.object(runner, "OfflinePeer") as peer, \
             patch("sys.stdout", new_callable=io.StringIO) as stdout:
            code = runner.main(["check-live-readiness", "--manifest", str(path)])
        self.assertEqual(2, code)
        self.assertFalse(json.loads(stdout.getvalue())["ready"])
        self.assertEqual(0, json.loads(stdout.getvalue())["admitted_runs"])
        peer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
