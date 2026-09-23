"""Local native-function mediation. No provider calls or pilot entry point.

This new experiment reuses the frozen task's local action semantics, not the old
text-JSON provider protocol. A raw Responses observation is validated again
before any local action; all provider output items enter the next input.
"""
from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from .m10_successor_protocol import (
    ACTION_SCHEMAS, DEFAULT_SOURCE_FILES, BudgetCaps, _Workspace,
    _append_ledger, _compile_result, _deadline_call, _hashes, _semantic_result,
)
from .successor_openai_responses import (
    canonical, continuation_input, inspect_response, prepare_request, verify_prepared,
)


class MediationFailure(RuntimeError):
    pass


class LocalMediation:
    """Single bounded local trajectory; callers own provider admission/accounting.

    This class cannot invoke a model. It is used by offline protocol tests only
    in this release. Live six-arm orchestration remains unimplemented/forbidden.
    Compilation and semantic evaluation stay separate from protocol completion.
    """

    def __init__(self, template: Path, prepared, *, compile_fn, score_fn,
                 ledger_path: Path, caps: BudgetCaps = BudgetCaps()):
        caps.validate()
        verify_prepared(prepared)
        if prepared.purpose != "scientific":
            raise MediationFailure("scientific_request_required")
        self.caps, self.compile_fn, self.score_fn = caps, compile_fn, score_fn
        self.ledger_path = Path(ledger_path)
        self.temp = tempfile.TemporaryDirectory(prefix="responses-local-")
        self.root = Path(self.temp.name)
        self.prepared = prepared
        self.turns = self.input_bytes = self.output_bytes = 0
        self.deadline = time.monotonic() + caps.run_timeout_seconds
        self.last_compile = None
        self.closed = self.finished = False
        self.events = []
        self.failure = None
        self.final = None
        try:
            template = Path(template)
            for name in DEFAULT_SOURCE_FILES:
                source = template / name
                if source.is_symlink() or not source.is_file() or source.resolve().parent != template.resolve():
                    raise MediationFailure("source_path_denied")
                data = source.read_bytes()
                if len(data) > caps.max_file_bytes:
                    raise MediationFailure("file_budget_exceeded")
                data.decode("utf-8")
                (self.root / name).write_bytes(data)
            self.initial = _hashes(self.root, DEFAULT_SOURCE_FILES)
            self.workspace = _Workspace(self.root, DEFAULT_SOURCE_FILES, ("Dispatcher.java",), caps)
            self._record({"event": "local_admitted", "itt_included": True,
                          "evidence_kind": "offline_native_mediation", "model_calls": 0,
                          "request_sha256": prepared.generation_sha256})
        except Exception:
            self.temp.cleanup()
            raise

    def _record(self, event):
        _append_ledger(self.ledger_path, event)
        self.events.append(event)

    def step(self, raw: bytes, *, expected_input_tokens: int):
        if self.closed or self.finished or self.failure:
            raise MediationFailure("trajectory_closed")
        try:
            self.turns += 1
            self.input_bytes += len(self.prepared.generation_json.encode("utf-8"))
            if (self.turns > self.caps.max_turns
                    or self.input_bytes > self.caps.max_total_input_bytes):
                raise MediationFailure("trajectory_budget_exceeded")
            seconds = min(self.caps.action_timeout_seconds, self.deadline - time.monotonic())
            if seconds <= 0:
                raise MediationFailure("run_timeout")
            observation = inspect_response(raw, self.prepared,
                                           expected_input_tokens=expected_input_tokens)
            self._record({"event": "provider_observation", "turn": self.turns,
                          "observation": observation})
            if not observation["ok"]:
                raise MediationFailure("invalid_provider_response")
            action = observation["action"]
            action_bytes = len(canonical(action).encode("utf-8"))
            self.output_bytes += action_bytes
            if (action_bytes > self.caps.max_output_bytes_per_turn
                    or self.output_bytes > self.caps.max_total_output_bytes):
                raise MediationFailure("action_output_budget_exceeded")
            kind = action["action"]
            if kind == "final":
                current = _hashes(self.root, DEFAULT_SOURCE_FILES)
                changed = sorted(n for n in current if current[n] != self.initial[n])
                if sorted(action["files"]) != changed:
                    raise MediationFailure("final_file_report_mismatch")
                if self.last_compile != current:
                    raise MediationFailure("final_without_current_compile")
                self.final, self.finished = action, True
                self._record({"event": "local_completed", "itt_included": True, "final": action})
                return None
            if kind == "compile":
                result = _compile_result(_deadline_call(lambda: self.compile_fn(self.root), seconds), self.root)
                self.last_compile = _hashes(self.root, DEFAULT_SOURCE_FILES)
            else:
                result = _deadline_call(lambda: self.workspace.dispatch(action), seconds)
            if len(canonical(result).encode("utf-8")) > self.caps.max_tool_output_bytes:
                raise MediationFailure("tool_output_budget_exceeded")
            next_input = continuation_input(self.prepared, observation, canonical(result))
            self.prepared = prepare_request(next_input, ACTION_SCHEMAS)
            self._record({"event": "local_tool_result", "turn": self.turns, "action": action,
                          "result": result, "next_request_sha256": self.prepared.generation_sha256})
            return self.prepared
        except Exception as exc:
            self.failure = (str(exc) if isinstance(exc, MediationFailure)
                            else "local_failure:" + type(exc).__name__)
            self._record({"event": "local_failed", "itt_included": True, "reason": self.failure})
            raise MediationFailure(self.failure) from None

    def evaluate(self):
        """Retain failed trajectories; never condition scoring on protocol success."""
        result = {"itt_included": True, "protocol_ok": self.finished and not self.failure,
                  "failure": self.failure, "final": self.final}
        for name, fn, normalize in (("compile", self.compile_fn, lambda v: _compile_result(v, self.root)),
                                    ("semantic", self.score_fn, _semantic_result)):
            try:
                result[name] = normalize(_deadline_call(lambda: fn(self.root), self.caps.evaluation_timeout_seconds))
            except Exception as exc:
                result[name] = {"evaluation_error": type(exc).__name__}
        self._record({"event": "local_evaluated", **result})
        return result

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True
        self.temp.cleanup()
