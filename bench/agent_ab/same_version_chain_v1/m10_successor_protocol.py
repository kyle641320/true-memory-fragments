"""Offline-only action protocol for the M10 successor.

This is protocol rehearsal infrastructure, not a model experiment runner. The
public run_one entry admits only the in-process scripted adapter below. A private
shared executor also serves the separately sealed, fixed offline broker bridge.
Accepting a provider-shaped request does not establish that any real provider
honours its token limits: live execution is unconditionally disabled here.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import signal
import tempfile
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path, PurePosixPath
from typing import Any


WORKSPACE_LABEL = "<workspace>"
EVIDENCE_KIND = "offline_scripted_protocol_rehearsal"
MODEL_EXECUTION_ENABLED = False
DEFAULT_SOURCE_FILES = (
    "AllowConcurrentEvents.java", "AsyncEventBus.java", "DeadEvent.java",
    "Dispatcher.java", "EventBus.java", "ParametricNullness.java",
    "Subscribe.java", "Subscriber.java", "SubscriberExceptionContext.java",
    "SubscriberExceptionHandler.java", "SubscriberRegistry.java",
)


class ProtocolAdmissionError(RuntimeError):
    """No run was admitted and no adapter may have been called."""


class LiveExecutionDisabled(ProtocolAdmissionError):
    """This module cannot admit paid, broker, or custom model adapters."""


class _ProtocolFailure(RuntimeError):
    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(category)


@dataclass(frozen=True)
class BudgetCaps:
    """Enforced offline byte budgets, never reported as provider tokens.

    Every request counts the entire growing message history plus all schemas.
    Output is counted before parsing; malformed and oversized output still
    consumes a turn.  Evaluation after termination has a separate timeout and
    never feeds scoring back to the adapter.
    """

    max_turns: int = 24
    max_input_bytes_per_turn: int = 120_000
    max_total_input_bytes: int = 1_200_000
    max_output_bytes_per_turn: int = 16_000
    max_total_output_bytes: int = 120_000
    max_tool_output_bytes: int = 24_000
    max_file_bytes: int = 240_000
    run_timeout_seconds: float = 300.0
    action_timeout_seconds: float = 90.0
    evaluation_timeout_seconds: float = 90.0
    # Required future transport contract; deliberately NOT a verified token cap.
    required_provider_max_output_tokens: int = 4_096

    def validate(self) -> None:
        for name, value in asdict(self).items():
            if name.endswith("seconds"):
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ProtocolAdmissionError(f"invalid budget: {name}")
                if not math.isfinite(value) or value <= 0:
                    raise ProtocolAdmissionError(f"invalid budget: {name}")
            elif type(value) is not int or value <= 0:
                raise ProtocolAdmissionError(f"invalid budget: {name}")


def build_action_schemas(
    source_files: Sequence[str] = DEFAULT_SOURCE_FILES,
    allowed_edit_paths: Sequence[str] = ("Dispatcher.java",),
) -> dict[str, dict[str, Any]]:
    """The complete model-facing JSON action schemas, identical for all arms."""
    string = {"type": "string"}
    path = {"type": "string", "enum": sorted(source_files)}
    descriptions = {
        "list": "List all available relative source paths.",
        "search": "Case-sensitive literal text search over all sources or the optional relative path.",
        "read_range": "Read inclusive, one-based source lines; end is clipped to the file length.",
        "read_symbol": "Read an exact qualified Java class/method name, or a unique simple name; ambiguity returns candidates.",
        "edit": "Replace exactly one occurrence of old with new in an editable source file; ambiguous or no-effect edits fail.",
        "compile": "Compile the current source state; compilation is not a semantic placement evaluation.",
        "final": "Finish with an explanation and exactly the changed relative paths, after compiling the final source state.",
    }

    def schema(name: str, props: dict[str, Any], required: Sequence[str]) -> dict[str, Any]:
        return {
            "type": "object",
            "description": descriptions[name],
            "properties": {"action": {"const": name}, **props},
            "required": ["action", *required],
            "additionalProperties": False,
        }

    return {
        "list": schema("list", {}, ()),
        "search": schema("search", {
            "query": {"type": "string", "minLength": 1, "maxLength": 1000},
            "path": path,
        }, ("query",)),
        "read_range": schema("read_range", {
            "path": path, "start": {"type": "integer", "minimum": 1},
            "end": {"type": "integer", "minimum": 1},
        }, ("path", "start", "end")),
        "read_symbol": schema("read_symbol", {
            "path": path, "symbol": {"type": "string", "minLength": 1},
        }, ("path", "symbol")),
        "edit": schema("edit", {
            "path": {"type": "string", "enum": sorted(allowed_edit_paths)},
            "old": {"type": "string", "minLength": 1}, "new": string,
        }, ("path", "old", "new")),
        "compile": schema("compile", {}, ()),
        "final": schema("final", {
            "answer": {"type": "string", "minLength": 1},
            "files": {"type": "array", "items": path, "uniqueItems": True},
        }, ("answer", "files")),
    }


ACTION_SCHEMAS = build_action_schemas()


@dataclass(frozen=True)
class AdapterRequest:
    """Future provider seam; no arm, run ID, absolute root, or evaluator data.

    A future real transport must independently prove tokenizer-aware input
    admission, usage accounting, and forwarding/enforcement of
    ``max_output_tokens``. This offline implementation proves none of those.
    """

    messages: tuple[dict[str, str], ...]
    action_schemas: dict[str, dict[str, Any]]
    max_output_tokens: int
    max_output_bytes: int
    timeout_seconds: float
    budget_unit: str = "utf8_bytes_not_provider_tokens"


@dataclass(frozen=True)
class ScriptedFailure:
    category: str


@dataclass
class ScriptedAdapter:
    """Finite action script with no subprocess, network, broker, or model path."""

    responses: Sequence[str | Mapping[str, Any] | ScriptedFailure]
    calls: int = field(default=0, init=False)
    requests: list[AdapterRequest] = field(default_factory=list, init=False)

    def respond(self, request: AdapterRequest) -> str:
        self.requests.append(request)
        index = self.calls
        self.calls += 1
        if index >= len(self.responses):
            raise _ProtocolFailure("no_final")
        response = self.responses[index]
        if isinstance(response, ScriptedFailure):
            if response.category == "timeout":
                raise TimeoutError("scripted timeout")
            raise _ProtocolFailure("adapter_error")
        if isinstance(response, str):
            return response
        if isinstance(response, Mapping):
            return _json(dict(response))
        raise _ProtocolFailure("invalid_adapter_response")


@dataclass
class RunRecord:
    run_id: str
    admitted: bool = True
    itt_included: bool = True
    evidence_kind: str = EVIDENCE_KIND
    model_execution_enabled: bool = False
    model_pilot_admitted: bool = False
    provider_token_limits_verified: bool = False
    seal_sha256: str = ""
    protocol_status: str = "admitted"
    protocol_ok: bool = False
    failure_reason: str | None = None
    final_received: bool = False
    semantic: dict[str, Any] = field(default_factory=dict)
    compilation: dict[str, Any] = field(default_factory=dict)
    final_answer: dict[str, Any] | None = None
    usage: dict[str, Any] = field(default_factory=lambda: {
        "budget_unit": "utf8_bytes_not_provider_tokens", "turns": 0,
        "input_bytes": 0, "output_bytes": 0, "tool_calls": 0,
        "successful_edits": 0, "provider_tokens": None,
        "source_read_actions": 0, "source_content_bytes_received": 0,
        "source_files_received": [],
    })
    budgets: dict[str, Any] = field(default_factory=dict)
    transcript: list[dict[str, Any]] = field(default_factory=list)
    source_acquisition: list[dict[str, Any]] = field(default_factory=list)
    admission_events: list[dict[str, Any]] = field(default_factory=list)
    durable_ledger: bool = False
    initial_source_sha256: dict[str, str] = field(default_factory=dict)
    final_source_sha256: dict[str, str] = field(default_factory=dict)
    # Captured only after execution/cleanup. Never part of AdapterRequest or a
    # tool result, even when it contains evaluator-only journal attribution.
    adapter_evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def joint_success(self) -> bool:
        return (
            self.protocol_ok and self.semantic.get("semantic_pass") is True
            and self.compilation.get("ok") is True
        )


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _bytes(value: Any) -> int:
    return len(_json(value).encode("utf-8"))


def _relative_paths(values: Sequence[str]) -> tuple[str, ...]:
    result = tuple(values)
    if not result or len(set(result)) != len(result):
        raise ProtocolAdmissionError("source paths must be nonempty and unique")
    for value in result:
        if not isinstance(value, str):
            raise ProtocolAdmissionError("invalid source path")
        path = PurePosixPath(value)
        if (
            path.is_absolute() or path.as_posix() != value
            or any(part in (".", "..") or part.startswith(".") for part in path.parts)
            or "\\" in value or path.suffix != ".java"
        ):
            raise ProtocolAdmissionError("only canonical relative Java source paths are allowed")
    return result


def _append_ledger(path: Path | None, event: Mapping[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(_json(dict(event)) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _deadline_call(function: Callable[[], Any], seconds: float) -> Any:
    """A real wall-clock timeout, including blocking compiler subprocess calls.

    Runs are admitted only on the main thread on POSIX.  We refuse unsupported
    execution contexts rather than silently degrading timeout enforcement.
    """
    if seconds <= 0:
        raise TimeoutError("deadline elapsed")

    def alarm_handler(signum: int, frame: Any) -> None:
        raise TimeoutError("action deadline elapsed")

    old_handler = signal.signal(signal.SIGALRM, alarm_handler)
    old_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        return function()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
        if old_timer[0] or old_timer[1]:
            signal.setitimer(signal.ITIMER_REAL, *old_timer)


def _hashes(root: Path, paths: Sequence[str]) -> dict[str, str]:
    return {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in paths}


def _compile_result(value: Any, root: Path) -> dict[str, Any]:
    if not isinstance(value, Mapping) or type(value.get("ok")) is not bool:
        raise _ProtocolFailure("invalid_compile_result")
    result: dict[str, Any] = {"ok": value["ok"]}
    if "exit" in value and (value["exit"] is None or type(value["exit"]) is int):
        result["exit"] = value["exit"]
    for name in ("stdout", "stderr"):
        if name in value:
            text = str(value[name]).replace(str(root), WORKSPACE_LABEL)
            # Compiler diagnostics may mention classpath/temp paths outside root.
            text = re.sub(r"(?<![\w<>])/(?:[^\s:\"'<>]+/)*[^\s:\"'<>]+", "<host-path>", text)
            result[name] = text
    return result


def _semantic_result(value: Any) -> dict[str, Any]:
    result = asdict(value) if is_dataclass(value) else dict(value)
    if "semantic_pass" not in result and hasattr(value, "semantic_pass"):
        result["semantic_pass"] = value.semantic_pass
    if type(result.get("semantic_pass")) is not bool:
        raise _ProtocolFailure("invalid_semantic_result")
    # The scoring record is evaluator-only, never returned as a tool response.
    _json(result)
    return result


def _validate_value(value: Any, schema: Mapping[str, Any]) -> bool:
    if "const" in schema and value != schema["const"]:
        return False
    kind = schema.get("type")
    if kind == "string":
        if not isinstance(value, str):
            return False
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", math.inf):
            return False
    elif kind == "integer":
        if type(value) is not int or value < schema.get("minimum", -math.inf):
            return False
    elif kind == "array":
        if not isinstance(value, list) or not all(_validate_value(item, schema["items"]) for item in value):
            return False
        if schema.get("uniqueItems") and len(set(value)) != len(value):
            return False
    if "enum" in schema and value not in schema["enum"]:
        return False
    return True


def _parse_action(raw: str, schemas: Mapping[str, Any]) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    try:
        value = json.loads(raw, object_pairs_hook=reject_duplicates)
    except (ValueError, TypeError, RecursionError):
        raise _ProtocolFailure("invalid_json") from None
    if (
        not isinstance(value, dict) or not isinstance(value.get("action"), str)
        or value["action"] not in schemas
    ):
        raise _ProtocolFailure("invalid_action")
    schema = schemas[value["action"]]
    if not set(schema["required"]).issubset(value) or set(value) - set(schema["properties"]):
        raise _ProtocolFailure("invalid_action_schema")
    if not all(_validate_value(item, schema["properties"][name]) for name, item in value.items()):
        raise _ProtocolFailure("invalid_action_schema")
    return value


class _Workspace:
    def __init__(self, root: Path, sources: tuple[str, ...], edits: tuple[str, ...], caps: BudgetCaps) -> None:
        self.root, self.sources, self.edits, self.caps = root, sources, edits, caps

    def read(self, path: str) -> str:
        target = self.root / path
        if path not in self.sources or target.is_symlink() or not target.is_file():
            raise _ProtocolFailure("source_path_denied")
        if target.stat().st_size > self.caps.max_file_bytes:
            raise _ProtocolFailure("file_budget_exceeded")
        return target.read_text(encoding="utf-8")

    def dispatch(self, action: Mapping[str, Any]) -> dict[str, Any]:
        kind = action["action"]
        if kind == "list":
            return {"ok": True, "files": sorted(self.sources)}
        if kind == "search":
            paths = (action["path"],) if "path" in action else sorted(self.sources)
            return {"ok": True, "matches": [
                {"path": path, "line": index, "text": line}
                for path in paths for index, line in enumerate(self.read(path).splitlines(), 1)
                if action["query"] in line
            ]}
        if kind == "read_range":
            lines = self.read(action["path"]).splitlines()
            if action["start"] > action["end"] or action["start"] > len(lines):
                raise _ProtocolFailure("invalid_read_range")
            end = min(action["end"], len(lines))
            return {"ok": True, "path": action["path"], "start": action["start"],
                    "end": end, "text": "\n".join(lines[action["start"] - 1:end])}
        if kind == "read_symbol":
            from tmf.java_extract import extract_java_classes, extract_java_methods

            text = self.read(action["path"])
            symbols = extract_java_classes(action["path"], text) + extract_java_methods(action["path"], text)
            exact = [node for node in symbols if node.qualname == action["symbol"]]
            matches = exact or [node for node in symbols if node.qualname.rsplit(".", 1)[-1] == action["symbol"]]
            if len(matches) != 1:
                return {"ok": False, "error": "symbol_not_unique", "candidates": sorted(node.qualname for node in matches)}
            node = matches[0]
            return {"ok": True, "path": action["path"], "symbol": node.qualname,
                    "start": node.line_start, "end": node.line_end,
                    "text": "\n".join(text.splitlines()[node.line_start - 1:node.line_end])}
        if kind == "edit":
            if action["path"] not in self.edits:
                raise _ProtocolFailure("edit_path_denied")
            text = self.read(action["path"])
            if text.count(action["old"]) != 1:
                raise _ProtocolFailure("edit_anchor_not_unique")
            changed = text.replace(action["old"], action["new"], 1)
            if changed == text:
                raise _ProtocolFailure("no_effect_edit")
            if len(changed.encode("utf-8")) > self.caps.max_file_bytes:
                raise _ProtocolFailure("file_budget_exceeded")
            (self.root / action["path"]).write_text(changed, encoding="utf-8")
            return {"ok": True, "path": action["path"]}
        raise _ProtocolFailure("invalid_action")


def run_one(
    root: Path,
    model_messages: Sequence[Mapping[str, str]],
    adapter: ScriptedAdapter,
    *,
    compile_fn: Callable[[Path], Mapping[str, Any]],
    score_fn: Callable[[Path], Any],
    verify: Callable[[], Mapping[str, Any]],
    budgets: BudgetCaps = BudgetCaps(),
    source_files: Sequence[str] = DEFAULT_SOURCE_FILES,
    allowed_edit_paths: Sequence[str] = ("Dispatcher.java",),
    ledger_path: Path | None = None,
    run_id: str | None = None,
    live: bool = False,
) -> RunRecord:
    """Verify, admit/account, isolate, execute, and independently evaluate a run.

    ``verify`` must do the full seal/content/preflight validation and return an
    ``ok`` receipt plus the verified seal SHA256. A failed verifier prevents any
    fixture copy, admission, or adapter call. It must bind this call's messages,
    fixture, schemas, and budgets, not merely check a self-reported status.

    After admission, every terminal error returns an ITT-included record. A
    durable optional JSONL ledger writes and fsyncs admission before workspace
    creation, so an interrupted process can also be counted. Invalid actions
    are fail-fast protocol failures, not permission to retry until favourable.
    """
    if live or type(adapter) is not ScriptedAdapter:
        raise LiveExecutionDisabled("only offline ScriptedAdapter is enabled")
    if adapter.calls:
        raise ProtocolAdmissionError("adapter must be fresh for each run")
    return _run_one_with_factory(
        root, model_messages, adapter_factory=lambda: adapter,
        compile_fn=compile_fn, score_fn=score_fn, verify=verify,
        budgets=budgets, source_files=source_files, allowed_edit_paths=allowed_edit_paths,
        ledger_path=ledger_path, run_id=run_id,
    )


def _run_one_with_factory(
    root: Path,
    model_messages: Sequence[Mapping[str, str]],
    *,
    adapter_factory: Callable[[], Any],
    compile_fn: Callable[[Path], Mapping[str, Any]],
    score_fn: Callable[[Path], Any],
    verify: Callable[[], Mapping[str, Any]],
    budgets: BudgetCaps = BudgetCaps(),
    source_files: Sequence[str] = DEFAULT_SOURCE_FILES,
    allowed_edit_paths: Sequence[str] = ("Dispatcher.java",),
    ledger_path: Path | None = None,
    run_id: str | None = None,
    evidence_kind: str = EVIDENCE_KIND,
    on_admit: Callable[[], None] | None = None,
    adapter_evidence: Callable[[Any], Mapping[str, Any]] | None = None,
) -> RunRecord:
    """Private shared action loop, not a public adapter/live admission API.

    The fixed offline bridge owns its factory, joint verifier and durable batch
    ledger. Its on_admit callback must fsync the scheduled start before return;
    only then may the factory run. The public scripted path keeps its exact-type
    and freshness gate above this seam. Neither path enables model execution.
    """
    if evidence_kind not in (EVIDENCE_KIND, "offline_broker_protocol_rehearsal"):
        raise ProtocolAdmissionError("only known offline rehearsal evidence is allowed")
    if (not callable(adapter_factory) or (on_admit is not None and not callable(on_admit))
            or (adapter_evidence is not None and not callable(adapter_evidence))):
        raise ProtocolAdmissionError("invalid private executor callback")
    budgets.validate()
    sources = _relative_paths(source_files)
    edits = _relative_paths(allowed_edit_paths)
    if not set(edits).issubset(sources):
        raise ProtocolAdmissionError("editable paths must be readable source files")
    if threading.current_thread() is not threading.main_thread() or not hasattr(signal, "setitimer"):
        raise ProtocolAdmissionError("hard action deadlines require a POSIX main thread")
    messages = [dict(message) for message in model_messages]
    if not messages or any(
        set(message) != {"role", "content"}
        or message["role"] not in ("system", "user", "assistant", "tool")
        or not isinstance(message["content"], str)
        for message in messages
    ):
        raise ProtocolAdmissionError("messages must contain only role and text content")
    if any(str(Path(root).resolve()) in message["content"] for message in messages):
        raise ProtocolAdmissionError("fixture host path must not enter model messages; use <workspace>")
    if ledger_path is not None:
        try:
            ledger_path.resolve().relative_to(Path(root).resolve())
        except ValueError:
            pass
        else:
            raise ProtocolAdmissionError("ledger must be outside the immutable fixture template")
    receipt = verify()
    if (
        not isinstance(receipt, Mapping) or receipt.get("ok") is not True
        or re.fullmatch(r"[0-9a-f]{64}", str(receipt.get("seal_sha256", ""))) is None
    ):
        raise ProtocolAdmissionError("manifest/preflight verification did not pass")
    opaque_id = run_id or uuid.uuid4().hex
    if not isinstance(opaque_id, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", opaque_id) is None:
        raise ProtocolAdmissionError("invalid evaluator run ID")
    schemas = build_action_schemas(sources, edits)
    record = RunRecord(run_id=opaque_id, seal_sha256=receipt["seal_sha256"], evidence_kind=evidence_kind,
                       budgets=asdict(budgets), durable_ledger=ledger_path is not None)
    admission = {"event": "admitted", "run_id": opaque_id, "evidence_kind": evidence_kind,
                 "seal_sha256": receipt["seal_sha256"], "itt_included": True}
    # A failed durable write is a pre-admission failure, never an untracked run.
    _append_ledger(ledger_path, admission)
    if on_admit is not None:
        on_admit()
        record.durable_ledger = True
    record.admission_events.append(admission)
    deadline = time.monotonic() + budgets.run_timeout_seconds
    private_root: Path | None = None
    adapter: Any = None
    try:
        with tempfile.TemporaryDirectory(prefix="m10-") as directory:
            private_root = Path(directory)
            try:
                for path in sources:
                    source = Path(root) / path
                    # Resolve every component: a symlinked parent is also denied.
                    if source.is_symlink() or source.resolve() != Path(root).resolve() / path:
                        raise _ProtocolFailure("source_path_denied")
                    data = source.read_bytes()
                    if len(data) > budgets.max_file_bytes:
                        raise _ProtocolFailure("file_budget_exceeded")
                    data.decode("utf-8")
                    target = private_root / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                workspace = _Workspace(private_root, sources, edits, budgets)
                record.initial_source_sha256 = _hashes(private_root, sources)
                try:
                    adapter = adapter_factory()
                except Exception as error:
                    raise _ProtocolFailure("adapter_factory_error:" + type(error).__name__) from None
                last_compile_hashes: dict[str, str] | None = None
                for turn in range(1, budgets.max_turns + 1):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise _ProtocolFailure("run_timeout")
                    request = AdapterRequest(
                        messages=tuple(dict(message) for message in messages),
                        action_schemas=json.loads(_json(schemas)),
                        max_output_tokens=budgets.required_provider_max_output_tokens,
                        max_output_bytes=min(budgets.max_output_bytes_per_turn,
                                             budgets.max_total_output_bytes - record.usage["output_bytes"]),
                        timeout_seconds=min(remaining, budgets.action_timeout_seconds),
                    )
                    input_bytes = _bytes({"messages": request.messages, "action_schemas": schemas})
                    if input_bytes > budgets.max_input_bytes_per_turn or (
                        record.usage["input_bytes"] + input_bytes > budgets.max_total_input_bytes
                    ):
                        raise _ProtocolFailure("input_budget_exceeded")
                    if request.max_output_bytes <= 0:
                        raise _ProtocolFailure("output_budget_exceeded")
                    record.usage["turns"] += 1
                    record.usage["input_bytes"] += input_bytes
                    try:
                        raw = _deadline_call(lambda: adapter.respond(request), request.timeout_seconds)
                    except TimeoutError:
                        raise _ProtocolFailure("adapter_timeout") from None
                    if not isinstance(raw, str):
                        raise _ProtocolFailure("invalid_adapter_response")
                    size = len(raw.encode("utf-8"))
                    record.usage["output_bytes"] += size
                    entry: dict[str, Any] = {"turn": turn, "response": raw}
                    record.transcript.append(entry)
                    if size > request.max_output_bytes:
                        raise _ProtocolFailure("output_budget_exceeded")
                    action = _parse_action(raw, schemas)
                    entry["action"] = action
                    messages.append({"role": "assistant", "content": raw})
                    if action["action"] == "final":
                        record.final_received = True
                        record.final_answer = action
                        current = _hashes(private_root, sources)
                        changed = sorted(path for path in sources if current[path] != record.initial_source_sha256[path])
                        if sorted(action["files"]) != changed:
                            raise _ProtocolFailure("final_file_report_mismatch")
                        if last_compile_hashes != current:
                            raise _ProtocolFailure("final_without_current_compile")
                        record.protocol_status = "completed"
                        record.protocol_ok = True
                        break
                    record.usage["tool_calls"] += 1
                    seconds = min(budgets.action_timeout_seconds, deadline - time.monotonic())
                    try:
                        if action["action"] == "compile":
                            value = _deadline_call(lambda: compile_fn(private_root), seconds)
                            result = _compile_result(value, private_root)
                            last_compile_hashes = _hashes(private_root, sources)
                        else:
                            result = _deadline_call(lambda: workspace.dispatch(action), seconds)
                    except TimeoutError:
                        raise _ProtocolFailure("action_timeout") from None
                    if action["action"] == "edit":
                        record.usage["successful_edits"] += 1
                    if _bytes(result) > budgets.max_tool_output_bytes:
                        raise _ProtocolFailure("tool_output_budget_exceeded")
                    if action["action"] in ("search", "read_range", "read_symbol"):
                        record.usage["source_read_actions"] += 1
                        if action["action"] == "search":
                            paths = sorted({match["path"] for match in result["matches"]})
                            content_bytes = sum(len(match["text"].encode("utf-8")) for match in result["matches"])
                        elif result.get("ok") is True:
                            paths = [result["path"]]
                            content_bytes = len(result["text"].encode("utf-8"))
                        else:
                            paths, content_bytes = [], 0
                        record.usage["source_content_bytes_received"] += content_bytes
                        record.usage["source_files_received"] = sorted(
                            set(record.usage["source_files_received"]) | set(paths)
                        )
                        record.source_acquisition.append({
                            "turn": turn, "action": action["action"],
                            "paths": paths, "content_bytes": content_bytes,
                        })
                    entry["result"] = result
                    messages.append({"role": "tool", "content": _json(result)})
                else:
                    raise _ProtocolFailure("no_final")
            except _ProtocolFailure as error:
                record.protocol_status = "failed"
                record.failure_reason = error.category
            except Exception as error:
                record.protocol_status = "failed"
                record.failure_reason = "execution_error:" + type(error).__name__
            finally:
                # Independent evaluation even after invalid actions, no final,
                # budget exhaustion, timeouts, adapter errors or compile failure.
                try:
                    record.final_source_sha256 = _hashes(private_root, sources)
                    value = _deadline_call(lambda: score_fn(private_root), budgets.evaluation_timeout_seconds)
                    record.semantic = _semantic_result(value)
                except Exception as error:
                    record.semantic = {"semantic_pass": None, "evaluation_error": type(error).__name__}
                try:
                    value = _deadline_call(lambda: compile_fn(private_root), budgets.evaluation_timeout_seconds)
                    record.compilation = _compile_result(value, private_root)
                except Exception as error:
                    record.compilation = {"ok": None, "evaluation_error": type(error).__name__}
    except Exception as error:
        # Includes workspace creation/cleanup errors; admission remains counted.
        record.protocol_status = "failed"
        record.protocol_ok = False
        record.failure_reason = "workspace_error:" + type(error).__name__
    finally:
        if adapter is not None:
            lifecycle_errors: dict[str, str] = {}
            try:
                close = getattr(adapter, "close", None)
                if close is not None:
                    close()
            except Exception as error:
                lifecycle_errors["close_error"] = type(error).__name__
            if adapter_evidence is not None:
                try:
                    snapshot = adapter_evidence(adapter)
                    if not isinstance(snapshot, Mapping):
                        raise TypeError("adapter evidence must be a mapping")
                    # Detach mutable transport state and reject non-JSON/NaN.
                    record.adapter_evidence = json.loads(_json(dict(snapshot)))
                except Exception as error:
                    lifecycle_errors["snapshot_error"] = type(error).__name__
            if lifecycle_errors:
                record.adapter_evidence["executor_lifecycle_errors"] = lifecycle_errors
                record.protocol_status = "failed"
                record.protocol_ok = False
                if record.failure_reason is None:
                    record.failure_reason = "adapter_evidence_or_cleanup_failed"
    completion = {"event": "completed", "run_id": opaque_id, "record": asdict(record)}
    _append_ledger(ledger_path, completion)
    return record


def aggregate_itt(records: Sequence[RunRecord | Mapping[str, Any]]) -> dict[str, Any]:
    """No semantic-evaluable/compile-clean/protocol-clean denominator filter."""
    rows = [asdict(row) if is_dataclass(row) else dict(row) for row in records]
    admitted = [row for row in rows if row.get("admitted") is True]
    identifiers = [row["run_id"] for row in admitted]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("duplicate admitted run IDs")
    if any(row.get("itt_included") is not True for row in admitted):
        raise ValueError("an admitted run cannot be excluded from ITT")
    return {
        "evidence_kind": EVIDENCE_KIND, "denominator": len(admitted),
        "protocol_complete": sum(row.get("protocol_ok") is True for row in admitted),
        "semantic_pass": sum(row.get("semantic", {}).get("semantic_pass") is True for row in admitted),
        "compile_pass": sum(row.get("compilation", {}).get("ok") is True for row in admitted),
        "joint_success": sum(
            row.get("protocol_ok") is True and row.get("semantic", {}).get("semantic_pass") is True
            and row.get("compilation", {}).get("ok") is True for row in admitted
        ),
        "semantic_unknown": sum(row.get("semantic", {}).get("semantic_pass") is None for row in admitted),
        "compile_unknown": sum(row.get("compilation", {}).get("ok") is None for row in admitted),
        "no_final": sum(row.get("final_received") is not True for row in admitted),
        "model_pilot_admitted": False,
    }


def records_from_ledger(path: Path) -> list[dict[str, Any]]:
    """Reconstruct ITT, retaining admissions interrupted before completion."""
    rows: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        run_id = event["run_id"]
        if event["event"] == "admitted":
            if run_id in rows:
                raise ValueError("duplicate admission in ledger")
            rows[run_id] = asdict(RunRecord(
                run_id=run_id, seal_sha256=event["seal_sha256"],
                protocol_status="incomplete", failure_reason="missing_completion_record",
            ))
        elif event["event"] == "completed":
            if run_id not in rows or rows[run_id]["protocol_status"] != "incomplete":
                raise ValueError("completion without unique prior admission")
            if event["record"]["run_id"] != run_id or event["record"].get("admitted") is not True:
                raise ValueError("invalid completion record")
            rows[run_id] = event["record"]
        else:
            raise ValueError("unknown ledger event")
    return list(rows.values())
