"""Execution-only profile, sticky identity guard and bounded durable evidence.

These checks are necessary, not sufficient, for live admission. A dictionary
claiming an attestation is not host authority. The stock-host qualifier refuses
live execution until a supported host seam can provide and enforce this data.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import time
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from .m10_successor_protocol import ACTION_SCHEMAS, BudgetCaps, _json
from .successor_codex_mediation import RuntimeViolation


SCHEMA = "tmf-successor-codex-control.v1"
MODEL = "openai/gpt-5.6-sol"
NATIVE_MODEL = "gpt-5.6-sol"
EFFORT = "medium"
RUNTIME = "openclaw-codex-app-server"
TOOL_NAME = "successor_action"
MAX_EVENT_BYTES = 256_000
MAX_EVIDENCE_BYTES = 8_000_000
MAX_EVENTS = 512


def digest(value) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def native_tool() -> dict:
    # Identity, schema descriptions, paths and action payloads are unchanged.
    return {"name": TOOL_NAME, "description": "Submit one successor repo action using the supplied schemas.",
            "input_schema": {"oneOf": deepcopy(list(ACTION_SCHEMAS.values()))}}


def runtime_profile() -> dict:
    caps = asdict(BudgetCaps())
    return {
        "schema": SCHEMA, "experiment": "controlled_successor_on_openclaw_codex_agent_runtime",
        "provider": "openai", "request_model": MODEL, "native_model": NATIVE_MODEL,
        "reasoning_effort": EFFORT, "runtime": RUNTIME,
        "auth": "existing_host_owned_chatgpt_codex_subscription_no_credential_export",
        "platform_api_allowed": False, "model_fallback_allowed": False,
        "scientific_changes": False, "native_tool": native_tool(),
        "common_protocol_carrier": "Use successor_action to submit each JSON action; its schema and results are the supplied repo protocol. No other repo tools are available.",
        "permissions": {"source_access": "only_successor_action_local_mediation",
                        "native_shell": False, "native_filesystem": False,
                        "native_web": False, "native_mcp": False, "native_apps": False,
                        "delegation": False, "extra_tools": False,
                        "project_docs": False, "memory_tools": False,
                        "runtime_cwd": "empty_common_carrier_not_source_or_evaluator_directory",
                        "evaluator_and_other_runs_accessible": False},
        "budget": {"scientific_caps": caps,
                   "max_observed_runtime_inferences_per_run": caps["max_turns"],
                   "max_runtime_observable_output_bytes": caps["max_total_output_bytes"],
                   "provider_output_token_cap_verified": False,
                   "provider_output_token_cap": None,
                   "native_context_token_count_verified": False,
                   "byte_scope": "scientific_history_and_schemas_not_hidden_native_prompt",
                   "native_timeout_scope": "controller_absolute_run_deadline_including_common_retries"},
        "native_state": "fresh_per_run_common_runtime_owned_history",
        "common_runtime_policy": "prompt_state_retry_usage_projection_allowed_and_recorded",
        "identity_policy": "actual_resolved_model_effort_and_policy_before_each_inference_drift_aborts_block",
        "failure_policy": "stop_block_preserve_all_six_admitted_ids_no_retry_resume_replacement",
        "required_host_capabilities": ["pre_inference_resolved_native_model_effort_gate",
                                       "verified_no_native_or_external_tool_bypass",
                                       "ordered_runtime_events_and_synchronous_abort",
                                       "all_inference_admission_and_absolute_deadline",
                                       "no_hidden_cross_run_instructions_or_state"],
        "pilot": {"blocks": 1, "arms": 6, "runs_per_arm": 1, "replacement_runs": 0},
        "provider_observability": {"immutable_deployment_revision": "unavailable",
                                   "tokenizer_revision": "unavailable",
                                   "usage": "runtime_projection_not_platform_raw_usage"},
    }


def expected_identity(profile: dict) -> dict:
    return {"provider": profile["provider"], "request_model": profile["request_model"],
            "resolved_model": profile["native_model"], "effort": profile["reasoning_effort"],
            "runtime": profile["runtime"], "tools_sha256": digest(profile["native_tool"]),
            "permissions_sha256": digest(profile["permissions"]),
            "profile_sha256": digest(profile)}


def durable_directory(path: Path) -> None:
    """Persist every new directory entry; reject symlink path components."""
    path = Path(path).absolute()
    if path == path.parent:
        return
    durable_directory(path.parent)
    if path.is_symlink():
        raise RuntimeViolation("evidence_path_symlink")
    try:
        path.mkdir(mode=0o700)
    except FileExistsError:
        if not path.is_dir():
            raise RuntimeViolation("evidence_path_not_directory")
    else:
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


class EventJournal:
    """Exclusive, bounded hash chain; uncertainty is sticky and stops dispatch."""

    def __init__(self, path: Path):
        self.path = Path(path).absolute()
        durable_directory(self.path.parent)
        self.failed = False
        self.fd = -1
        self.seq = 0
        self.size = 0
        self.previous = "0" * 64
        self._bytes_hash = hashlib.sha256()
        try:
            self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            parent = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
        except Exception:
            self.close()
            raise

    def emit(self, event: dict):
        if self.failed or self.fd < 0:
            raise RuntimeViolation("runtime_journal_unavailable")
        try:
            self.verify_live()
            body = {"seq": self.seq, "prev_sha256": self.previous, "event": deepcopy(event)}
            fingerprint = digest(body)
            data = (_json({**body, "sha256": fingerprint}) + "\n").encode("utf-8")
            if (len(data) > MAX_EVENT_BYTES or self.size + len(data) > MAX_EVIDENCE_BYTES
                    or self.seq >= MAX_EVENTS):
                raise RuntimeViolation("runtime_evidence_budget_exceeded")
            view = memoryview(data)
            while view:
                written = os.write(self.fd, view)
                if written <= 0:
                    raise OSError("short evidence write")
                view = view[written:]
            os.fsync(self.fd)
            self.previous, self.seq, self.size = fingerprint, self.seq + 1, self.size + len(data)
            self._bytes_hash.update(data)
        except Exception as exc:
            self.failed = True
            if isinstance(exc, RuntimeViolation):
                raise
            raise RuntimeViolation("runtime_evidence_write_failed") from None

    def verify_live(self) -> dict:
        """Bind integrity to admitted bytes and the open inode, not any valid prefix."""
        if self.failed or self.fd < 0:
            raise RuntimeViolation("runtime_journal_unavailable")
        try:
            opened, named = os.fstat(self.fd), self.path.lstat()
            if (not stat.S_ISREG(named.st_mode) or named.st_nlink != 1
                    or (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino)
                    or opened.st_size != self.size):
                raise ValueError("identity_or_size")
            hasher, offset = hashlib.sha256(), 0
            while offset < self.size:
                data = os.pread(self.fd, min(65536, self.size - offset), offset)
                if not data:
                    raise ValueError("short_read")
                hasher.update(data)
                offset += len(data)
            if hasher.hexdigest() != self._bytes_hash.hexdigest():
                raise ValueError("changed_bytes")
            return {"event_count": self.seq, "byte_count": self.size,
                    "tail_sha256": self.previous, "bytes_sha256": hasher.hexdigest()}
        except (OSError, ValueError):
            self.failed = True
            raise RuntimeViolation("runtime_evidence_changed") from None

    def close(self):
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1


def verify_event_journal(path: Path, *, expected: dict | None = None) -> list[dict]:
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_EVIDENCE_BYTES:
        raise RuntimeViolation("runtime_evidence_invalid")
    data = path.read_bytes()
    if not data or not data.endswith(b"\n"):
        raise RuntimeViolation("runtime_evidence_invalid")
    previous = "0" * 64
    events = []
    try:
        for seq, raw in enumerate(data.splitlines(keepends=True)):
            if len(raw) > MAX_EVENT_BYTES or seq >= MAX_EVENTS:
                raise ValueError("bounds")
            row = json.loads(raw)
            if set(row) != {"seq", "prev_sha256", "sha256", "event"} or _json(row).encode() + b"\n" != raw:
                raise ValueError("shape")
            claimed = row.pop("sha256")
            if type(row["seq"]) is not int or row["seq"] != seq or row["prev_sha256"] != previous or digest(row) != claimed:
                raise ValueError("chain")
            events.append(row["event"])
            previous = claimed
    except (ValueError, TypeError, KeyError, RecursionError):
        raise RuntimeViolation("runtime_evidence_invalid") from None
    if expected is not None and expected != {
            "event_count": len(events), "byte_count": len(data), "tail_sha256": previous,
            "bytes_sha256": hashlib.sha256(data).hexdigest()}:
        raise RuntimeViolation("runtime_evidence_anchor_mismatch")
    return events


class RuntimeGuard:
    """Sticky control machine. It is NOT a certificate issuer for live hosts."""

    def __init__(self, profile: dict, *, emit: Callable, abort: Callable):
        if profile != runtime_profile():
            raise RuntimeViolation("runtime_profile_drift")
        self.profile, self.expected = deepcopy(profile), expected_identity(profile)
        self.emit, self.abort = emit, abort
        self.failure_reason = None
        self.abort_acknowledged = None
        self.inferences = 0
        self.output_bytes = 0
        self.attested = False
        self.phase = "idle"
        self.deadline = time.monotonic() + profile["budget"]["scientific_caps"]["run_timeout_seconds"]
        self.events = []

    def halt(self, category: str):
        if self.failure_reason is None:
            self.failure_reason, self.attested = category, False
            self.phase = "failed"
            try:
                self.abort_acknowledged = self.abort(category) is True
            except Exception:
                self.abort_acknowledged = False
            try:
                self.emit({"event": "block_halted", "category": category,
                           "abort_acknowledged": self.abort_acknowledged})
            except Exception:
                pass  # Original failure never disappears when evidence fails too.
        raise RuntimeViolation(self.failure_reason)

    def _record(self, event: dict):
        try:
            self.emit(event)
        except Exception:
            self.halt("runtime_evidence_write_failed")
        self.events.append(deepcopy(event))

    def check(self):
        if self.failure_reason:
            raise RuntimeViolation(self.failure_reason)
        if time.monotonic() >= self.deadline:
            self.halt("run_timeout")
        if self.phase == "completed":
            self.halt("event_after_runtime_completed")
        if not self.attested or self.phase != "inference":
            self.halt("actual_native_identity_missing")

    def before_inference(self, actual: dict):
        if self.failure_reason:
            raise RuntimeViolation(self.failure_reason)
        if time.monotonic() >= self.deadline:
            self.halt("run_timeout")
        if self.phase != "idle":
            self.halt("invalid_inference_transition")
        if type(actual) is not dict or actual != self.expected:
            self._record({"event": "identity_rejected", "actual": actual})
            self.halt("actual_native_configuration_mismatch")
        if self.inferences >= self.profile["budget"]["max_observed_runtime_inferences_per_run"]:
            self.halt("inference_budget_exceeded")
        self._record({"event": "inference_admitted", "actual": actual, "index": self.inferences})
        self.inferences += 1
        self.attested = True
        self.phase = "inference"

    def tool(self, name: str):
        self.check()
        if name != TOOL_NAME:
            self.halt("tool_bypass")

    def observe(self, event: dict):
        if (type(event) is dict and event.get("event") == "runtime_completed"
                and self.phase == "idle" and self.inferences > 0 and self.failure_reason is None):
            if time.monotonic() >= self.deadline:
                self.halt("run_timeout")
            self._record(event)
            self.phase = "completed"
            return
        self.check()
        if type(event) is not dict or type(event.get("event")) is not str:
            self.halt("invalid_runtime_event")
        self._record(event)
        kind = event["event"]
        if kind in ("model/rerouted", "effort_drift", "configuration_drift", "native_tool", "runtime_failure"):
            self.halt(kind.replace("/", "_"))
        elif kind == "configuration_observed":
            if event.get("actual") != self.expected:
                self.halt("actual_native_configuration_mismatch")
        elif kind == "assistant_output":
            if type(event.get("text")) is not str:
                self.halt("invalid_runtime_output")
            self.output_bytes += len(event["text"].encode("utf-8"))
            if self.output_bytes > self.profile["budget"]["max_runtime_observable_output_bytes"]:
                self.halt("runtime_output_budget_exceeded")
        elif kind == "inference_completed":
            self.phase, self.attested = "idle", False
        elif kind not in ("retry_observed", "usage_observed"):
            self.halt("unknown_runtime_event")

    def snapshot(self) -> dict:
        return {"failure_reason": self.failure_reason, "abort_acknowledged": self.abort_acknowledged,
                "inferences": self.inferences, "observable_output_bytes": self.output_bytes,
                "phase": self.phase,
                "actual_identity_verified_at_control_boundary": self.attested and self.failure_reason is None,
                "events": deepcopy(self.events)}
