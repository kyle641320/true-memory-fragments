"""Source inspection and separately qualified public OpenClaw/Codex driver.

The source-only inspector is not an account probe or live admission token.
Only the listed package/source/documentation files are read. No module from
the inspected installation is imported, and no auth store, config, process,
network, or model is accessed. Exact hashes identify an observed stock build;
they do NOT attest provider behavior or make that build ready for a pilot.

Source inspection alone never permits execution. The separate public-plugin
qualifier below exercises registration without inference; independent readiness
and the runner's exact joint seal remain required before a live launch.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, NoReturn


SCHEMA = "tmf.successor.codex-host-inspection.v2"
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
    "diagnostic_unit_is_turn": ("codex", "dist/run-attempt-BzthFQSM.js", 'observationUnit: "turn",'),
    "input_hook_at_outer_turn": ("codex", "dist/run-attempt-BzthFQSM.js", 'runAgentHarnessLlmInputHook({\n\t\t\tevent: buildLlmInputEvent(),'),
    "internal_response_postreceipt": ("codex", "dist/run-attempt-BzthFQSM.js", 'case "rawResponse/completed":\n\t\t\t\tthis.usageProjection.record(params, this.params.hostCapabilities.reportOutputTokens);'),
    "public_extension_tool_result_only": ("openclaw", "dist/runtime-api-D4nuJwsj.d.ts", 'type CodexAppServerExtensionRuntime = {\n  on: (event: "tool_result",'),
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
        "admission_standard": "requested_controls_observed_drift_stop_equal_external_guardrails",
        "provider_attestation_required": False,
        "not_observable": ["provider_attested_pre_inference_actual_model",
                           "provider_attested_effective_reasoning_effort"],
        "accepted_observability_boundaries": [
            "Requested Sol/medium are frozen controls, not proof of provider actual model/effective effort. Missing provider pre-inference attestation is accepted, not a live blocker.",
            "A reroute notification may arrive after some output was generated. The user requires immediate block stop on detection and retained ITT, not proof of zero pre-notification output.",
            "Common native prompt assembly, state management, retry and projected usage are permitted when conditions share them and external limits remain enforceable; no per-internal-inference reservation is required.",
        ],
        "supported_surfaces": [
            {"surface": "agent exec --config: isolated public CLI with normal stored-auth ownership", "evidence": ["isolated_cli"]},
            {"surface": "api.runtime.agent.runEmbeddedAgent: normal public harness selection, upstream AbortSignal", "evidence": ["public_programmatic_run", "upstream_abort_signal", "pre_aborted_request_rejected"]},
            {"surface": "Dynamic tool hooks can mediate OpenClaw-owned tools", "evidence": ["dynamic_tool_hooks"]},
        ] if recognized else [],
        "not_verified": ["installed Codex binary runtime identity", "account model/effort availability",
                         "exclusive seven-tool live mediation",
                         "action/assistant-iteration budget enforcement", "complete source-read telemetry",
                         "project-document/context isolation"],
        "inspection_activity": {"agent_launches": 0, "model_generations": 0,
                                "platform_count_requests": 0, "auth_reads": 0, "config_reads": 0},
        "live_guard": "source-only reports are rejected; require_live_host separately recomputes public-driver qualification and hashes, never trusting a READY flag",
    }


def _stock_gaps() -> list[dict]:
    return [
        {
            "id": "source_inspection_not_external_guardrail_qualification",
            "detail": "Source inspection cannot qualify the executable external-turn/action/byte/deadline/ITT bridge. Internal inference/retry pre-reservation is explicitly not required; unavailable granular telemetry must remain unknown.",
            "evidence": ["diagnostic_unit_is_turn", "input_hook_at_outer_turn",
                         "internal_response_postreceipt", "public_extension_tool_result_only",
                         "llm_input_best_effort", "codex_input_gate_absent"],
        },
        {
            "id": "public_live_driver_requires_separate_qualification_and_audit",
            "detail": "The separate public CLI driver must pass actual no-inference plugin loading, deterministic transport/guardrail tests, source/driver hashes and independent exact-seal readiness. This source-only result is not evidence that those steps completed.",
            "evidence": ["public_programmatic_run", "dynamic_tool_hooks", "upstream_abort_signal",
                         "turn_starting_requested_model", "reroute_projection"],
        },
    ]


_OPENCLAW_ROOT = Path("/root/.local/share/pnpm/global/v11/13f326-18d39d7fb55ea4cc-0/node_modules/.pnpm/openclaw@2026.9.2/node_modules/openclaw")
_CODEX_ROOT = Path("/root/.openclaw/npm/projects/openclaw-codex-8902d781d4__openclaw-generation__g-e2e0de3303206c53/node_modules/@openclaw/codex")
_CODEX_BINARY = _CODEX_ROOT.parent.parent / "@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex"
_DRIVER_ROOT = Path(__file__).parent / "successor_codex_live_host"
_DRIVER_FILES = ("package.json", "openclaw.plugin.json", "index.mjs", "bridge.mjs")
_PUBLIC_SOURCE_FILES = {
    "openclaw": ("openclaw.mjs", "dist/entry.js", "dist/selection-CgLPGlZh.js",
                 "dist/extensions/openai/openclaw.plugin.json", "docs/plugins/manifest.md",
                 "docs/plugins/sdk-overview.md"),
    "codex": ("openclaw.plugin.json", "dist/dynamic-tools-BwpvTxaX.js"),
}


def driver_inventory() -> dict:
    with _root_directory(_DRIVER_ROOT.absolute()) as root:
        return {name: hashlib.sha256(_read_source(root, name)).hexdigest()
                for name in _DRIVER_FILES}


def public_source_inventory() -> dict:
    result = {}
    for component, root in (("openclaw", _OPENCLAW_ROOT), ("codex", _CODEX_ROOT)):
        with _root_directory(root) as descriptor:
            for name in _PUBLIC_SOURCE_FILES[component]:
                result[f"{component}/{name}"] = hashlib.sha256(_read_source(descriptor, name)).hexdigest()
    return result


def executable_inventory() -> dict:
    """Hash explicit executable bytes; no binary invocation or credential access."""
    result = {}
    for name, path in (("node", Path(shutil.which("node")).resolve()), ("codex", _CODEX_BINARY)):
        with _root_directory(path.parent) as parent:
            metadata = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 512_000_000:
                raise HostNotReadyError("runtime_binary_unqualified")
            descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
            try:
                content = hashlib.sha256()
                while chunk := os.read(descriptor, 65536):
                    content.update(chunk)
                after = os.fstat(descriptor)
                if (metadata.st_size, metadata.st_mtime_ns, metadata.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                    raise HostNotReadyError("runtime_binary_changed_during_read")
                result[name] = {"path": str(path), "sha256": content.hexdigest(), "size_bytes": metadata.st_size}
            finally:
                os.close(descriptor)
    return result


def _auth_profile_reference(profile_id: str) -> str:
    return hashlib.sha256(json.dumps(profile_id, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _scoped_config(root: Path, auth_profile_id: str) -> dict:
    """Exact nonsecret process-scoped recipe; per-run paths alone vary."""
    return {
        "auth": {"profiles": {auth_profile_id: {"provider": "openai", "mode": "oauth"}},
                 "order": {"openai": [auth_profile_id]}},
        "agents": {
            "defaults": {
                "model": {"primary": "openai/gpt-5.6-sol", "fallbacks": []},
                "models": {"openai/gpt-5.6-sol": {"agentRuntime": {"id": "codex"}}},
                "thinkingDefault": "medium", "fastModeDefault": False,
                "workspace": str(root / "carrier"), "cwd": str(root / "carrier"),
                "skipBootstrap": True, "skills": [], "timeoutSeconds": 300,
            },
            "entries": {"successor-pilot": {"agentDir": str(root / "agent"), "skills": []}},
        },
        "session": {"store": str(root / "sessions" / "sessions.json")},
        "tools": {"allow": ["successor_action"], "codeMode": {"enabled": False},
                  "web": {"search": {"enabled": False}, "fetch": {"enabled": False}}},
        "plugins": {
            "allow": ["openai", "codex", "tmf-successor-host"],
            "load": {"paths": [str(_CODEX_ROOT), str(_DRIVER_ROOT.absolute())]},
            "slots": {"memory": "none", "contextEngine": "legacy"},
            "entries": {
                "openai": {"enabled": True},
                "codex": {"enabled": True, "config": {
                    "codexDynamicToolsLoading": "direct", "sessionCatalog": {"enabled": False},
                    "discovery": {"enabled": False}, "computerUse": {"enabled": False},
                    "appServer": {"transport": "stdio", "homeScope": "agent",
                                  "command": str(_CODEX_BINARY), "args": ["app-server", "--listen", "stdio://"],
                                  "approvalPolicy": "never", "sandbox": "read-only"},
                }},
                "tmf-successor-host": {"enabled": True, "config": {
                    "runtimeDirectory": str(root), "authProfileId": auth_profile_id}},
            },
        },
    }


def create_live_launch(runtime_directory: Path, *, auth_profile_id: str) -> dict:
    """Author a private, nonsecret process-scoped config, never global host config.

    The caller supplies an already-known opaque profile identifier, never a
    credential. The normal host resolves its existing stored OAuth credentials.
    No auth store, ambient config, API key, token, or native login is read here.
    """
    from .successor_codex_control import durable_directory
    root = Path(runtime_directory).absolute()
    if (type(auth_profile_id) is not str or not auth_profile_id.startswith("openai:")
            or not re.fullmatch(r"[a-zA-Z0-9_:./@-]{1,256}", auth_profile_id)):
        raise HostNotReadyError("existing_subscription_profile_identifier_required")
    if root.exists() and any(root.iterdir()):
        raise HostNotReadyError("new_runtime_directory_required")
    durable_directory(root)
    for directory in ("carrier", "agent", "sessions"):
        durable_directory(root / directory)
    config = _scoped_config(root, auth_profile_id)
    config_path = root / "scoped-config.json"
    descriptor = os.open(config_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(config, stream, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    node = shutil.which("node")
    if not node:
        raise HostNotReadyError("node_runtime_missing")
    # The stock no-respawn launcher option preserves the inherited control FD.
    # It affects process wrapping only, never permission/native hook policy.
    return {"argv": [str(Path(node).resolve()), str(_OPENCLAW_ROOT / "openclaw.mjs"),
                     "successor-host", "--run"],
            "env": {"OPENCLAW_CONFIG_PATH": str(config_path), "OPENCLAW_NO_RESPAWN": "1",
                    "NODE_DISABLE_COMPILE_CACHE": "1"},
            "cwd": str(root / "carrier")}


def _validate_scoped_launch_config(launch: dict) -> str:
    # A caller-supplied report/config is never permission to load arbitrary code.
    # Check the full recipe before launching even the no-inference qualifier.
    config_path = Path(launch["env"]["OPENCLAW_CONFIG_PATH"])
    with _root_directory(config_path.parent) as directory:
        config = json.loads(_read_source(directory, config_path.name))
    profile_id = config.get("plugins", {}).get("entries", {}).get("tmf-successor-host", {}).get("config", {}).get("authProfileId")
    if (type(profile_id) is not str or not re.fullmatch(r"openai:[a-zA-Z0-9_:./@-]{1,256}", profile_id)
            or config != _scoped_config(config_path.parent, profile_id)):
        raise HostNotReadyError("scoped_host_configuration_drift")
    return _auth_profile_reference(profile_id)


def _qualify_launch(launch: dict) -> dict:
    _validate_scoped_launch_config(launch)
    argv = list(launch["argv"])
    if argv[-2:] != ["successor-host", "--run"]:
        raise HostNotReadyError("invalid_pinned_launch")
    argv[-1] = "--qualify"
    environment = os.environ.copy()
    environment.update(launch["env"])
    try:
        result = subprocess.run(argv, cwd=launch["cwd"], env=environment, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise HostNotReadyError("public_cli_qualification_failed") from None
    # Error text is not echoed; it may have been authored by a host component.
    if result.returncode != 0 or len(result.stdout) > 256_000 or len(result.stderr) > 256_000:
        raise HostNotReadyError("public_cli_qualification_failed")
    candidates = []
    for line in result.stdout.splitlines():
        try:
            value = json.loads(line)
        except (ValueError, UnicodeError):
            continue
        if type(value) is dict and value.get("schema") == "tmf.successor.public-host-qualification.v1":
            candidates.append(value)
    if len(candidates) != 1 or candidates[0].get("qualified") is not True or candidates[0].get("modelLaunches") != 0:
        raise HostNotReadyError("public_cli_qualification_missing")
    return {"result": candidates[0],
            "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
            "exit_code": result.returncode}


def qualify_live_host(runtime_directory: Path, *, auth_profile_id: str) -> dict:
    """Exercise the public loader/API registration, explicitly without inference."""
    inspection = inspect_host(_OPENCLAW_ROOT, _CODEX_ROOT)
    if inspection["host_recognition"] != "observed_stock":
        raise HostNotReadyError("stock_host_source_mismatch")
    launch = create_live_launch(runtime_directory, auth_profile_id=auth_profile_id)
    qualification = _qualify_launch(launch)
    return {"schema": "tmf.successor.codex-live-host.v1", "verdict": "READY_FOR_INDEPENDENT_AUDIT",
            "live_allowed": False, "source_inspection": inspection,
            "driver_sha256": driver_inventory(), "public_source_sha256": public_source_inventory(),
            "executables": executable_inventory(),
            "launch": launch, "qualification": qualification,
            "auth_profile_ref": _auth_profile_reference(auth_profile_id),
            "provider_attestation": False, "model_calls": 0,
            "readiness_scope": "public_cli_loader_capability_and_source_controls_not_live_result_or_audit"}


def verify_live_materials(report: dict) -> None:
    """Cheap per-arm source/binary/config verification; no process or inference."""
    try:
        if type(report) is not dict or report.get("schema") != "tmf.successor.codex-live-host.v1":
            raise HostNotReadyError("live_host_unavailable: source inspection is not live admission authority")
        inspection = inspect_host(_OPENCLAW_ROOT, _CODEX_ROOT)
        if inspection != report["source_inspection"] or inspection["host_recognition"] != "observed_stock":
            raise HostNotReadyError("stock_host_source_drift")
        if (driver_inventory() != report["driver_sha256"] or
                public_source_inventory() != report["public_source_sha256"] or
                executable_inventory() != report["executables"]):
            raise HostNotReadyError("live_host_driver_drift")
        launch = report["launch"]
        root = Path(launch["env"]["OPENCLAW_CONFIG_PATH"]).parent
        if launch["argv"] != [str(Path(shutil.which("node")).resolve()), str(_OPENCLAW_ROOT / "openclaw.mjs"), "successor-host", "--run"]:
            raise HostNotReadyError("live_host_launch_drift")
        if launch["cwd"] != str(root / "carrier") or launch["env"] != {
                "OPENCLAW_CONFIG_PATH": str(root / "scoped-config.json"),
                "OPENCLAW_NO_RESPAWN": "1", "NODE_DISABLE_COMPILE_CACHE": "1"}:
            raise HostNotReadyError("live_host_launch_drift")
        profile_ref = _validate_scoped_launch_config(launch)
        if profile_ref != report["auth_profile_ref"] or profile_ref != report["qualification"]["result"]["authProfileRef"]:
            raise HostNotReadyError("live_host_auth_profile_drift")
        with _root_directory(root) as directory:
            config_hash = hashlib.sha256(_read_source(directory, "scoped-config.json")).hexdigest()
        if config_hash != report["qualification"]["result"]["configSha256"]:
            raise HostNotReadyError("live_host_configuration_drift")
    except HostNotReadyError:
        raise
    except Exception:
        raise HostNotReadyError("invalid_live_host_report") from None


def require_live_host(report: dict) -> dict:
    """Revalidate sources and public CLI; no caller READY boolean is authority."""
    verify_live_materials(report)
    actual = _qualify_launch(report["launch"])
    if actual["result"] != report["qualification"]["result"]:
        raise HostNotReadyError("live_host_qualification_drift")
    return actual
