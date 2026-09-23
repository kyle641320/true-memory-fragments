"""Source-only qualification of the observed OpenClaw/Codex host.

This is not an executable adapter, account probe, or live admission token.
Only the listed package/source/documentation files are read. No module from
the inspected installation is imported, and no auth store, config, process,
network, or model is accessed. Exact hashes identify an observed stock build;
they do NOT attest provider behavior or make that build ready for a pilot.

A future host needs a separately implemented and independently reviewed live
control seam. Changing a report boolean, package version, or source pin must
never unlock execution through this module.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, NoReturn


SCHEMA = "tmf.successor.codex-host-inspection.v1"
_MAX_SOURCE_BYTES = 4 * 1024 * 1024

# Deliberately no recursive discovery or wildcard reads. These are observations
# of the 2026.9.2 installation, not a supported-host authorization allowlist.
_SOURCE_PINS = (
    ("openclaw", "package.json", "aaba2fdde13e3d1a676102fc53195bac94d6236e9d9bef192c84dca04cf9ea5b"),
    ("openclaw", "docs/cli/agent.md", "64dd3b85c8f6e08933b0d5c47f889dcc9d867ce15c03925608bf3f0048d012db"),
    ("openclaw", "docs/plugins/hooks.md", "ae1d51dc1bd17ca726e59bf012ba6b62169de30bfb49b7aa74120e07eb12de5c"),
    ("openclaw", "docs/plugins/codex-harness-runtime.md", "e9fe9642149ebe672de284ef8c2088f7fb45a4baf6f5857807f06380640cb965"),
    ("openclaw", "docs/plugins/sdk-runtime.md", "09a399fbb9caf26c1ef4438ca51c72300ebd33b22e0c8f11f923bd3e9d06ceec"),
    ("openclaw", "dist/runtime-api-D4nuJwsj.d.ts", "021542920f0404a0278e7f2273e4f3e3e2a6d2b5f66abf46844e1ed907d69407"),
    ("openclaw", "dist/listeners-BogSNJ-R.js", "b03734b32c0f74c6637644269556ea46cff6d49d0fd604d66c43bc4e4793b4b3"),
    ("openclaw", "dist/runs-Cb42qain.js", "53eb9ed4d24f30626af7d0b85a961966177e983bc74262bbf5c46a3811915de1"),
    ("openclaw", "dist/lifecycle-hook-helpers-Cpmpoz3T.js", "305948cb1a79e08de397e325829194ecbcd00b2ad1e7ef6133b10351ef4cd8d8"),
    ("openclaw", "dist/plugin-sdk/agent-harness-runtime.d.ts", "9c44c5e74cfd191e17282edc68b507d29802e6026adf1409b0960b26b6abe9f1"),
    ("codex", "package.json", "8448f177f7501e2309fe40d0abf07fd5fb1866499555a0fcec61e0da67f65e81"),
    ("codex", "dist/run-attempt-BzthFQSM.js", "732b15bdd80b0bf5b4135baca42a6b1490e3c08c418026034e22680b6f446a64"),
    ("codex", "dist/thread-lifecycle-DPK30jad.js", "344d4a6332d59b5eb1d7551d6d308563f339d5d2251809c8f25e8cec04ede342"),
    ("codex", "dist/native-subagent-monitor-B3bvQGcg.js", "abd27a1adc170a93d6ba28f41f74579e308aed26bb16b9ac7dce0c6288f001b4"),
    ("codex", "dist/shared-client-CKhX2kFt.js", "7b18d1bc94074f8a20dc3a782a0292db0b4990e75c33faf572cf3b0bac544114"),
)

_ANCHORS = {
    "isolated_cli": ("openclaw", "docs/cli/agent.md", "For reproducible runs, pin the config instead of inheriting it."),
    "public_programmatic_run": ("openclaw", "docs/plugins/sdk-runtime.md", "`runEmbeddedAgent(...)` is the neutral helper"),
    "codex_input_gate_absent": ("openclaw", "docs/plugins/hooks.md", "CLI runners; do not rely on it as a Codex or Copilot input gate."),
    "prepare_hook_not_wired": ("openclaw", "docs/plugins/hooks.md", "enrichment. `agent_turn_prepare` and queued-injection draining are not currently\nwired into the Codex"),
    "dynamic_tool_hooks": ("openclaw", "docs/plugins/codex-harness-runtime.md", "`before_tool_call`, `after_tool_call`, and tool-result middleware run around OpenClaw-owned dynamic tools."),
    "native_tool_observation": ("openclaw", "docs/plugins/codex-harness-runtime.md", "block, delay, or mutate the native tool call."),
    "runtime_events_api": ("openclaw", "dist/runtime-api-D4nuJwsj.d.ts", "  events: {\n    onAgentEvent: typeof onAgentEvent;\n    onSessionTranscriptUpdate: typeof onSessionTranscriptUpdate;\n  };"),
    "llm_input_type": ("openclaw", "dist/runtime-api-D4nuJwsj.d.ts", "type PluginHookLlmInputEvent = {"),
    "llm_input_best_effort": ("openclaw", "dist/lifecycle-hook-helpers-Cpmpoz3T.js", "function runAgentHarnessLlmInputHook(params) {"),
    "observer_exceptions_isolated": ("openclaw", "dist/listeners-BogSNJ-R.js", "function notifyListeners(listeners, event, onError) {"),
    "sdk_abort_export": ("openclaw", "dist/plugin-sdk/agent-harness-runtime.d.ts", "abortEmbeddedAgentRun as abortAgentHarnessRun"),
    "abort_requires_active_handle": ("openclaw", "dist/runs-Cb42qain.js", "function abortEmbeddedAgentRun(sessionId, opts) {"),
    "thread_response_model": ("codex", "dist/thread-lifecycle-DPK30jad.js", "model: response.model ?? startParams.model ?? params.params.modelId,"),
    "effort_substitution": ("codex", "dist/thread-lifecycle-DPK30jad.js", "return supported.find((effort) => CODEX_REASONING_EFFORTS.indexOf(effort) >= requestedRank) ?? supported.at(-1);"),
    "actual_turn_model": ("codex", "dist/run-attempt-BzthFQSM.js", "model: resourceState.thread.model,\n\t\t\t\tmodelProvider: resourceState.thread.modelProvider"),
    "thread_ready_omits_model": ("codex", "dist/run-attempt-BzthFQSM.js", 'phase: "thread_ready",'),
    "turn_starting_requested_model": ("codex", "dist/run-attempt-BzthFQSM.js", 'phase: "turn_starting",\n\t\t\t\tthreadId: resourceState.thread.threadId,\n\t\t\t\tmodel: params.modelId,'),
    "llm_input_requested_model": ("codex", "dist/run-attempt-BzthFQSM.js", "const buildLlmInputEvent = () => ({\n\t\trunId: params.runId,\n\t\tsessionId: params.sessionId,\n\t\tprovider: usesSupervisionConnection ? resourceState.thread.modelProvider ?? effectiveRuntimeProviderId : params.provider,\n\t\tmodel: usesSupervisionConnection ? resourceState.thread.model ?? effectiveRuntimeModelId : params.modelId,"),
    "upstream_abort_signal": ("codex", "dist/run-attempt-BzthFQSM.js", "const abortFromUpstream = () => {"),
    "active_handle_registration": ("codex", "dist/run-attempt-BzthFQSM.js", "setActiveEmbeddedRun(params.sessionId, handle, params.sessionKey, params.sessionFile);"),
    "activation_after_start": ("codex", "dist/run-attempt-BzthFQSM.js", "const turnStart = await startCodexAttemptTurn(resources, turnRuntime, notifications, turnRequest);"),
    "reroute_projection": ("codex", "dist/native-subagent-monitor-B3bvQGcg.js", "handleModelRerouted(params) {"),
    "pre_aborted_request_rejected": ("codex", "dist/shared-client-CKhX2kFt.js", 'if (options.signal?.aborted) return Promise.reject(new CodexAppServerLocalRequestCancellationError(method, "aborted", false));'),
}


class HostNotReadyError(RuntimeError):
    """Live execution has no qualified implementation in this module."""


class _SourceError(Exception):
    pass


def _child_directory(parent_fd: int, name: str) -> int:
    metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if stat.S_ISLNK(metadata.st_mode):
        raise _SourceError("symlink_source")
    if not stat.S_ISDIR(metadata.st_mode):
        raise _SourceError("not_a_directory")
    return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                   dir_fd=parent_fd)


@contextmanager
def _root_directory(root: Path) -> Iterator[int]:
    if not isinstance(root, Path) or not root.is_absolute() or ".." in root.parts:
        raise _SourceError("invalid_root")
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
        raise _SourceError("unsupported_platform")
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in root.parts[1:]:
            next_descriptor = _child_directory(descriptor, part)
            os.close(descriptor)
            descriptor = next_descriptor
        yield descriptor
    finally:
        os.close(descriptor)


def _read_source(root_fd: int, relative_path: str) -> bytes:
    """Use no-follow directory descriptors, bounded reads, and no FIFO opens."""
    parts = Path(relative_path).parts
    if not parts or Path(relative_path).is_absolute() or ".." in parts:
        raise _SourceError("invalid_source_path")
    directory = os.dup(root_fd)
    source_fd = None
    try:
        for part in parts[:-1]:
            child = _child_directory(directory, part)
            os.close(directory)
            directory = child
        metadata = os.stat(parts[-1], dir_fd=directory, follow_symlinks=False)
        if stat.S_ISLNK(metadata.st_mode):
            raise _SourceError("symlink_source")
        if not stat.S_ISREG(metadata.st_mode):
            raise _SourceError("not_regular_source")
        source_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                            dir_fd=directory)
        before = os.fstat(source_fd)
        if not stat.S_ISREG(before.st_mode):
            raise _SourceError("not_regular_source")
        if before.st_size > _MAX_SOURCE_BYTES:
            raise _SourceError("source_too_large")
        output = bytearray()
        while chunk := os.read(source_fd, min(65536, _MAX_SOURCE_BYTES + 1 - len(output))):
            output.extend(chunk)
            if len(output) > _MAX_SOURCE_BYTES:
                raise _SourceError("source_too_large")
        after = os.fstat(source_fd)
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise _SourceError("source_changed_during_read")
        return bytes(output)
    finally:
        if source_fd is not None:
            os.close(source_fd)
        os.close(directory)


def _error_code(error: Exception) -> str:
    if isinstance(error, _SourceError):
        return str(error)
    if isinstance(error, FileNotFoundError):
        return "source_missing"
    if isinstance(error, UnicodeError):
        return "source_not_utf8"
    return "source_unreadable"


def _version(value: object) -> str | None:
    if type(value) is str and len(value) <= 64 and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?", value):
        return value
    return None


def inspect_host(openclaw_root: Path, codex_root: Path) -> dict:
    """Return a reproducible, non-authorizing report; all outcomes NOT_READY.

    Unknown, incomplete, modified, unreadable, or symlinked sources are not
    qualified. A recognized stock source set confirms known gaps only. This
    function never treats source inspection as live or account attestation.
    """
    sources, errors, texts = [], [], {}
    for component, root in (("openclaw", openclaw_root), ("codex", codex_root)):
        try:
            with _root_directory(root) as descriptor:
                for owner, relative_path, expected in _SOURCE_PINS:
                    if owner != component:
                        continue
                    try:
                        payload = _read_source(descriptor, relative_path)
                        digest = hashlib.sha256(payload).hexdigest()
                        sources.append({"component": component, "path": relative_path,
                                        "sha256": digest, "size_bytes": len(payload),
                                        "matches_observed_stock": digest == expected})
                        texts[component, relative_path] = payload.decode("utf-8")
                        if digest != expected:
                            errors.append({"component": component, "path": relative_path,
                                           "code": "source_hash_mismatch"})
                    except (OSError, ValueError, _SourceError) as error:
                        errors.append({"component": component, "path": relative_path,
                                       "code": _error_code(error)})
        except (OSError, ValueError, _SourceError) as error:
            errors.append({"component": component, "path": ".", "code": _error_code(error)})

    versions = {"openclaw": None, "codex_plugin": None,
                "codex_dependency_declared": None, "codex_binary_runtime": None}
    for component, expected_name, field in (("openclaw", "openclaw", "openclaw"),
                                             ("codex", "@openclaw/codex", "codex_plugin")):
        try:
            package = json.loads(texts.get((component, "package.json"), "{}"))
            if not isinstance(package, dict) or package.get("name") != expected_name:
                raise ValueError("package_identity")
            versions[field] = _version(package.get("version"))
            if component == "codex":
                dependency = package.get("dependencies", {})
                if not isinstance(dependency, dict):
                    raise ValueError("dependency_shape")
                versions["codex_dependency_declared"] = _version(dependency.get("@openai/codex"))
        except (ValueError, TypeError, RecursionError):
            errors.append({"component": component, "path": "package.json",
                           "code": "package_identity_or_version_unknown"})

    evidence = {}
    if not errors:
        for name, (component, relative_path, needle) in _ANCHORS.items():
            source = texts[component, relative_path]
            offset = source.find(needle)
            if offset < 0:
                errors.append({"component": component, "path": relative_path,
                               "code": "source_anchor_missing", "anchor": name})
            else:
                evidence[name] = {"component": component, "path": relative_path,
                                  "line": source.count("\n", 0, offset) + 1}
    recognized = not errors and versions == {
        "openclaw": "2026.9.2", "codex_plugin": "2026.9.2",
        "codex_dependency_declared": "0.153.4", "codex_binary_runtime": None,
    }
    missing = _stock_gaps() if recognized else [{
        "id": "host_source_contract_unrecognized",
        "detail": "Unknown, incomplete, changed, or unsafe sources cannot establish the inspected stock contract. No live implementation is qualified.",
        "evidence": [],
    }]
    return {
        "schema": SCHEMA, "inspection_mode": "source_only_no_inference",
        "verdict": "NOT_READY", "live_allowed": False,
        "host_recognition": "observed_stock" if recognized else "unknown_or_incomplete",
        "versions": versions, "sources": sources, "source_errors": errors,
        "evidence": evidence, "missing_capabilities": missing,
        "accepted_observability_boundaries": [
            "A reroute notification may arrive after some output was generated. The user requires immediate block stop on detection and retained ITT, not proof of zero pre-notification output.",
            "Common native prompt assembly, state management, retry and projected usage are permitted when conditions share them and limits remain enforceable.",
        ],
        "supported_surfaces": [
            {"surface": "agent exec --config: isolated public CLI with normal stored-auth ownership", "evidence": ["isolated_cli"]},
            {"surface": "api.runtime.agent.runEmbeddedAgent: normal public harness selection, upstream AbortSignal", "evidence": ["public_programmatic_run", "upstream_abort_signal", "pre_aborted_request_rejected"]},
            {"surface": "Dynamic tool hooks can mediate OpenClaw-owned tools", "evidence": ["dynamic_tool_hooks"]},
        ] if recognized else [],
        "not_verified": ["installed Codex binary runtime identity", "account model/effort availability",
                         "provider pre-generation model enforcement", "exclusive seven-tool live mediation",
                         "action/assistant-iteration budget enforcement", "complete source-read telemetry",
                         "project-document/context isolation"],
        "inspection_activity": {"agent_launches": 0, "model_generations": 0,
                                "platform_count_requests": 0, "auth_reads": 0, "config_reads": 0},
        "live_guard": "require_live_host always rejects; neither this report nor a source digest is admission authority",
    }


def _stock_gaps() -> list[dict]:
    return [
        {
            "id": "pre_inference_actual_model_effort_admission",
            "detail": "thread/start response.model is accepted into the private binding and used for turn/start. thread_ready omits model; turn_starting and ordinary llm_input report the requested model instead. turn_starting exposes resolved effort, but there is no public fail-closed combined actual-model/effort admission gate. Effort resolution may substitute another supported value.",
            "evidence": ["thread_response_model", "actual_turn_model", "thread_ready_omits_model",
                         "turn_starting_requested_model", "llm_input_requested_model", "effort_substitution",
                         "codex_input_gate_absent", "prepare_hook_not_wired"],
        },
        {
            "id": "predispatch_observer_cancellation_gate",
            "detail": "runtime.events exposes subscriptions, not scopeCancellation. llm_input is best effort and observer exceptions are isolated. SDK abortAgentHarnessRun exists, but the Codex active handle is registered only after turn/start acceptance. A caller-owned upstream AbortSignal can cancel before submission, but the missing actual-model observation prevents it from closing the attestation gap.",
            "evidence": ["runtime_events_api", "llm_input_type", "llm_input_best_effort",
                         "observer_exceptions_isolated", "sdk_abort_export", "abort_requires_active_handle",
                         "activation_after_start", "active_handle_registration", "upstream_abort_signal",
                         "pre_aborted_request_rejected"],
        },
    ]


def require_live_host(report: dict) -> NoReturn:
    """Reject even forged READY reports: there is no live adapter in this module."""
    del report
    raise HostNotReadyError("live_host_unavailable: source inspection is not live admission authority")
