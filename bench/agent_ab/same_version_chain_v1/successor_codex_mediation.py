"""Successor's existing seven repo actions behind a private runtime boundary.

No model, shell, credential, network, or provider code lives in this module.
Scientific byte/action limits are not native-provider token measurements.
"""
from __future__ import annotations

import os
import signal
import stat
import time
from copy import deepcopy
from pathlib import Path
from typing import Callable

from .m10_successor_fixture import FILE, PKG_FILES
from .m10_successor_protocol import (
    ACTION_SCHEMAS, BudgetCaps, _Workspace, _bytes, _compile_result,
    _hashes, _json, _parse_action, _ProtocolFailure,
    _semantic_result,
)


class RuntimeViolation(RuntimeError):
    def __init__(self, category: str):
        self.category = category
        super().__init__(category)


def bounded_call(function: Callable, seconds: float):
    """POSIX main-thread deadline; nested actions never extend the outer clock."""
    if seconds <= 0:
        raise TimeoutError("deadline elapsed")
    started = time.monotonic()
    old_timer = signal.getitimer(signal.ITIMER_REAL)
    limit = min(seconds, old_timer[0]) if old_timer[0] > 0 else seconds
    def timed_out(signum, frame):
        raise TimeoutError("execution deadline elapsed")
    old_handler = signal.signal(signal.SIGALRM, timed_out)
    signal.setitimer(signal.ITIMER_REAL, limit)
    try:
        return function()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
        if old_timer[0] > 0 or old_timer[1] > 0:
            remaining = max(0.000001, old_timer[0] - (time.monotonic() - started))
            signal.setitimer(signal.ITIMER_REAL, remaining, old_timer[1])


class MediatedWorkspace:
    """One private workspace, no arbitrary path/command/reader escape hatch.

    ``emit`` must return only after durable evidence. ``verify_active`` checks
    the batch, runtime identity and lifetime before each accepted action.
    Their implementations are host responsibilities, never model arguments.
    """

    def __init__(self, root: Path, *, budgets: BudgetCaps, compile_fn: Callable,
                 score_fn: Callable, emit: Callable, verify_active: Callable,
                 initial_messages: list[dict]):
        budgets.validate()
        self.root = Path(root).absolute()
        self.caps = budgets
        self.compile_fn, self.score_fn = compile_fn, score_fn
        self.emit, self.verify_active = emit, verify_active
        self.messages = deepcopy(initial_messages)
        if not self.messages or any(
                type(m) is not dict or set(m) != {"role", "content"}
                or m["role"] not in ("system", "user") or type(m["content"]) is not str
                for m in self.messages):
            raise RuntimeViolation("invalid_scientific_messages")
        self.failure_reason = None
        self.final_answer = None
        self.protocol_ok = False
        self.transcript: list[dict] = []
        self.source_acquisition: list[dict] = []
        self.usage = {"budget_unit": "scientific_utf8_bytes_and_mediated_actions_not_native_tokens",
                      "turns": 0, "input_bytes": 0, "output_bytes": 0,
                      "turns_scope": "mediated_action_steps_not_native_inferences",
                      "externally_admitted_agent_turns": 0,
                      "tool_calls": 0, "successful_edits": 0, "provider_tokens": None,
                      "source_read_actions": 0, "source_content_bytes_received": 0,
                      "source_files_received": [], "scientific_input_charges": 0}
        self._precharged_action_material = None
        self._expected_history = self._scientific_material()
        self._root_identity = None
        self._last_compile = None
        self._deadline = time.monotonic() + budgets.run_timeout_seconds
        self._check_workspace()
        self.initial_hashes = _hashes(self.root, PKG_FILES)
        self.workspace = _Workspace(self.root, tuple(PKG_FILES), (FILE,), budgets)

    def _fail(self, category: str):
        self.failure_reason = self.failure_reason or category
        self.protocol_ok = False
        raise RuntimeViolation(self.failure_reason)

    def _check_workspace(self):
        try:
            identity = self.root.stat()
            if (self.root.resolve() != self.root or self.root.is_symlink()
                    or not stat.S_ISDIR(identity.st_mode)):
                self._fail("workspace_escape")
            key = (identity.st_dev, identity.st_ino)
            if self._root_identity is not None and key != self._root_identity:
                self._fail("workspace_replaced")
            self._root_identity = key
            if {p.name for p in self.root.iterdir()} != set(PKG_FILES):
                self._fail("workspace_inventory_drift")
            for name in PKG_FILES:
                target = self.root / name
                info = target.lstat()
                if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                        or target.resolve() != target):
                    self._fail("workspace_escape")
                if info.st_size > self.caps.max_file_bytes:
                    self._fail("file_budget_exceeded")
        except (OSError, ValueError):
            self._fail("workspace_unavailable")

    def _emit(self, event: dict):
        try:
            self.emit(deepcopy(event))
        except Exception:
            self._fail("evidence_write_failed")

    def _active(self):
        if self.failure_reason is not None:
            self._fail(self.failure_reason)
        if self.final_answer is not None:
            self._fail("action_after_final")
        if time.monotonic() >= self._deadline:
            self._fail("run_timeout")
        try:
            self.verify_active()
        except RuntimeViolation as exc:
            self._fail(exc.category)
        except Exception:
            self._fail("runtime_identity_unverified")
        self._check_workspace()

    def _scientific_material(self):
        return _json({"messages": self.messages, "action_schemas": ACTION_SCHEMAS})

    def _check_scientific_history(self):
        material = self._scientific_material()
        if material != self._expected_history:
            self._fail("scientific_input_drift_after_admission")
        return material

    def _charge_scientific_input(self, material: str, boundary: str):
        """Enforce the same byte ledger at observable, controllable boundaries."""
        incoming = len(material.encode("utf-8"))
        if (incoming > self.caps.max_input_bytes_per_turn
                or self.usage["input_bytes"] + incoming > self.caps.max_total_input_bytes):
            self._fail("input_budget_exceeded")
        self._emit({"event": "scientific_input_admitted", "input_bytes": incoming,
                    "charge_index": self.usage["scientific_input_charges"], "boundary": boundary,
                    "native_inference_reservation": False})
        self.usage["input_bytes"] += incoming
        self.usage["scientific_input_charges"] += 1

    def call(self, action: dict) -> dict:
        self._active()
        if not self.usage["externally_admitted_agent_turns"]:
            self._fail("input_not_admitted_before_agent_turn")
        material = self._check_scientific_history()
        if self.usage["turns"] >= self.caps.max_turns:
            self._fail("action_budget_exceeded")
        try:
            raw = _json(action)
            parsed = _parse_action(raw, ACTION_SCHEMAS)
        except _ProtocolFailure as exc:
            self._fail(exc.category)
        except (ValueError, TypeError, RecursionError):
            self._fail("invalid_action")
        size = len(raw.encode("utf-8"))
        if (size > self.caps.max_output_bytes_per_turn
                or self.usage["output_bytes"] + size > self.caps.max_total_output_bytes):
            self._fail("output_budget_exceeded")
        # A submitted external turn has already paid for its first unchanged
        # history. Later actions in that turn pay for the current full history.
        # This ledger is never presented as hidden native prompt consumption.
        if self._precharged_action_material != material:
            self._charge_scientific_input(material, "mediated_action")
        self.usage["turns"] += 1
        self.usage["output_bytes"] += size
        self._precharged_action_material = None
        entry = {"turn": self.usage["turns"], "action": parsed, "response": raw}
        self.transcript.append(entry)
        self._emit({"event": "action_admitted", **entry})
        # Evidence delivery cannot leave a stale authority valid across awaits.
        self._active()
        self._check_scientific_history()
        self.messages.append({"role": "assistant", "content": raw})
        self._expected_history = self._scientific_material()
        try:
            kind = parsed["action"]
            if kind == "final":
                current = _hashes(self.root, PKG_FILES)
                changed = sorted(name for name in PKG_FILES if current[name] != self.initial_hashes[name])
                if sorted(parsed["files"]) != changed:
                    self._fail("final_file_report_mismatch")
                if self._last_compile != current:
                    self._fail("final_without_current_compile")
                result = {"ok": True, "finished": True}
            else:
                seconds = min(self.caps.action_timeout_seconds, self._deadline - time.monotonic())
                if seconds <= 0:
                    self._fail("run_timeout")
                self.usage["tool_calls"] += 1
                if kind == "compile":
                    value = bounded_call(lambda: self.compile_fn(self.root), seconds)
                    result = _compile_result(value, self.root)
                    self._last_compile = _hashes(self.root, PKG_FILES)
                else:
                    result = bounded_call(lambda: self.workspace.dispatch(parsed), seconds)
                if kind == "edit":
                    self.usage["successful_edits"] += 1
            self._check_workspace()
            if time.monotonic() >= self._deadline:
                self._fail("run_timeout")
            self.verify_active()
            if _bytes(result) > self.caps.max_tool_output_bytes:
                self._fail("tool_output_budget_exceeded")
            # The result is not released to the runtime until this is durable.
            self._emit({"event": "tool_result", "turn": entry["turn"], "result": result})
            self.verify_active()
            entry["result"] = deepcopy(result)
            if kind in ("search", "read_range", "read_symbol"):
                if kind == "search":
                    paths = sorted({m["path"] for m in result["matches"]})
                    delivered = sum(len(m["text"].encode("utf-8")) for m in result["matches"])
                elif result.get("ok") is True:
                    paths = [result["path"]]
                    delivered = len(result["text"].encode("utf-8"))
                else:
                    paths, delivered = [], 0
                self.usage["source_read_actions"] += 1
                self.usage["source_content_bytes_received"] += delivered
                self.usage["source_files_received"] = sorted(set(self.usage["source_files_received"]) | set(paths))
                self.source_acquisition.append({"turn": entry["turn"], "action": kind,
                                                "paths": paths, "content_bytes": delivered})
            self.messages.append({"role": "tool", "content": _json(result)})
            self._expected_history = self._scientific_material()
            if kind == "final":
                self.final_answer, self.protocol_ok = deepcopy(parsed), True
            return deepcopy(result)
        except _ProtocolFailure as exc:
            self._fail(exc.category)
        except RuntimeViolation as exc:
            self._fail(exc.category)
        except TimeoutError:
            self._fail("action_timeout")
        except Exception:
            self._fail("runtime_tool_failure")

    def prepare_agent_turn(self):
        """Charge submitted scientific input once per external Agent turn.

        Internal native reasoning/retry/iterations require no reservation. A
        further external dispatch is a fresh charge, even for unchanged input.
        """
        if self.failure_reason is not None:
            self._fail(self.failure_reason)
        if self.final_answer is not None:
            self._fail("action_after_final")
        if time.monotonic() >= self._deadline:
            self._fail("run_timeout")
        self._check_workspace()
        material = self._check_scientific_history()
        if self.usage["externally_admitted_agent_turns"] >= self.caps.max_turns:
            self._fail("agent_turn_budget_exceeded")
        self._charge_scientific_input(material, "external_agent_turn")
        self._check_scientific_history()
        self.usage["externally_admitted_agent_turns"] += 1
        self._precharged_action_material = material

    def prepare_inference(self):
        """Legacy alias for external-turn input accounting, not native inference."""
        self.prepare_agent_turn()

    def evaluate(self) -> dict:
        """Evaluator-only; failure is not permission to omit either outcome."""
        result = {}
        for key, fn, projector, unknown in (
            ("semantic", self.score_fn, _semantic_result, {"semantic_pass": None}),
            ("compilation", self.compile_fn, lambda v: _compile_result(v, self.root), {"ok": None}),
        ):
            try:
                self._check_workspace()
                value = bounded_call(lambda: fn(self.root), self.caps.evaluation_timeout_seconds)
                result[key] = projector(value)
            except Exception as exc:
                result[key] = {**unknown, "evaluation_error": type(exc).__name__}
        return result

    def artifact_bytes(self) -> bytes:
        """Evaluator-only bounded read through pinned, no-follow descriptors."""
        self._check_workspace()
        directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        source = None
        try:
            metadata = os.fstat(directory)
            if (metadata.st_dev, metadata.st_ino) != self._root_identity:
                self._fail("workspace_replaced")
            source = os.open(FILE, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            before = os.fstat(source)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                self._fail("workspace_escape")
            if before.st_size > self.caps.max_file_bytes:
                self._fail("file_budget_exceeded")
            data = bytearray()
            while chunk := os.read(source, min(65536, self.caps.max_file_bytes + 1 - len(data))):
                data.extend(chunk)
                if len(data) > self.caps.max_file_bytes:
                    self._fail("file_budget_exceeded")
            after = os.fstat(source)
            current = os.stat(FILE, dir_fd=directory, follow_symlinks=False)
            fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
            if fields(before) != fields(after) or fields(after) != fields(current):
                self._fail("workspace_artifact_changed")
            self._check_workspace()
            return bytes(data)
        finally:
            if source is not None:
                os.close(source)
            os.close(directory)

    def snapshot(self) -> dict:
        final_hashes = {}
        try:
            self._check_workspace()
            final_hashes = _hashes(self.root, PKG_FILES)
        except RuntimeViolation:
            pass
        return deepcopy({"transcript": self.transcript, "source_acquisition": self.source_acquisition,
                         "usage": self.usage, "initial_source_sha256": self.initial_hashes,
                         "final_source_sha256": final_hashes, "final_answer": self.final_answer,
                         "final_received": self.final_answer is not None,
                         "protocol_ok": self.protocol_ok, "failure_reason": self.failure_reason})
