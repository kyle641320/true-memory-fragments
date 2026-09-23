"""Bounded socket bridge to the stock OpenClaw-owned Codex host plugin.

No provider client, token, secret-store read or alternate login lives here.
The runner obtains the launch recipe from the pinned public-host integration;
there is no user-provided command or paid API escape hatch.
"""
from __future__ import annotations

import hashlib
import json
import os
import selectors
import signal
import socket
import subprocess
import time
from pathlib import Path

from .m10_successor_protocol import _json
from .successor_codex_control import (
    MAX_EVENT_BYTES, MAX_EVIDENCE_BYTES, TOOL_NAME, expected_identity,
)
from .successor_codex_mediation import RuntimeViolation


def _decode_frame(raw: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result
    def constant(_):
        raise ValueError("non-finite number")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError):
        raise RuntimeViolation("invalid_host_frame") from None
    if type(value) is not dict or type(value.get("kind")) is not str:
        raise RuntimeViolation("invalid_host_frame")
    return value


class LivePeer:
    """One external Agent turn; internal inference/retry is never pre-reserved."""

    def __init__(self, launch: dict, runtime_directory: Path, diagnostics: Path):
        self.launch = launch
        self.runtime_directory = Path(runtime_directory)
        self.diagnostics = Path(diagnostics)
        self.process = None
        self.control = None
        self.guard = None
        self.aborted = False
        self.result = None
        self.agent_dispatches = 0
        self.runtime_events = 0
        self.tool_result_dispatches = 0
        self.termination_reason = None
        self.elapsed_seconds = None
        self.diagnostic_bytes = 0
        self.diagnostic_sha256 = None
        self._used_action_ids = set()

    def _send(self, frame: dict):
        data = (_json(frame) + "\n").encode("utf-8")
        if len(data) > MAX_EVENT_BYTES:
            raise RuntimeViolation("host_frame_budget_exceeded")
        if self.control is None or self.guard is None:
            raise RuntimeViolation("host_channel_unavailable")
        remaining = self.guard.deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeViolation("run_timeout")
        self.control.settimeout(min(remaining, 5.0))
        try:
            self.control.sendall(data)
        except (OSError, TimeoutError):
            raise RuntimeViolation("host_channel_write_failed") from None
        finally:
            self.control.setblocking(False)

    def abort(self, reason: str) -> bool:
        self.aborted = True
        self.termination_reason = self.termination_reason or reason
        if self.control is not None:
            # A sent cancellation is not an acknowledged upstream cancellation.
            try:
                self.control.send((_json({"kind": "halt", "reason": reason}) + "\n").encode())
            except OSError:
                pass
        return False

    def _runtime_event(self, event: dict):
        if type(event) is not dict:
            raise RuntimeViolation("invalid_host_runtime_event")
        self.runtime_events += 1
        # The host emits normalized control events, preserving its raw public
        # event in a separate field. Request echoes are never provider proof.
        self.guard.observe(event)

    def _frame(self, frame: dict, workspace):
        if self.result is not None:
            raise RuntimeViolation("event_after_host_completion")
        kind = frame["kind"]
        if kind == "event":
            self._runtime_event(frame.get("event"))
        elif kind == "action":
            identifier = frame.get("id")
            if (type(identifier) is not str or not identifier or len(identifier) > 256
                    or identifier in self._used_action_ids):
                raise RuntimeViolation("invalid_or_duplicate_tool_call")
            self._used_action_ids.add(identifier)
            self.guard.tool(TOOL_NAME)
            result = workspace.call(frame.get("args"))
            self._send({"kind": "action_result", "id": identifier, "result": result})
            self.tool_result_dispatches += 1
            self.guard.observe({"event": "runtime_event", "source": "successor_control_socket",
                                "data": {"tool_call_id": identifier, "result_dispatched": True,
                                         "provider_consumption_attested": False}})
        elif kind == "completed":
            if self.result is not None or type(frame.get("result")) is not dict:
                raise RuntimeViolation("invalid_host_completion")
            self.result = frame["result"]
            self.guard.observe({"event": "runtime_event", "source": "openclaw_host_completion",
                                "data": self.result})
            # No more requests are valid after completion. Send FIN so an
            # orderly host socket close cannot wait forever on our write half.
            if self.control is not None:
                self.control.shutdown(socket.SHUT_WR)
        elif kind == "failed":
            reason = frame.get("reason")
            self.guard.observe({"event": "runtime_event", "source": "openclaw_host_failure",
                                "data": frame})
            raise RuntimeViolation("host_failure:" + (reason[:200] if type(reason) is str else "unknown"))
        else:
            raise RuntimeViolation("unknown_host_frame")

    def run(self, guard, workspace):
        self.guard = guard
        started = time.monotonic()
        parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        self.control = parent
        parent.setblocking(False)
        selector = selectors.DefaultSelector()
        buffered = bytearray()
        evidence_size = 0
        log_hash = hashlib.sha256()
        log = None
        try:
            self.runtime_directory.mkdir(mode=0o700, exist_ok=True)
            log = self.diagnostics.open("xb")
            # No credential is obtained, interpolated or moved. Ordinary host
            # credential ownership remains with the OpenClaw loader/runtime.
            env = os.environ.copy()
            env.update(self.launch.get("env", {}))
            env["SUCCESSOR_CONTROL_FD"] = str(child.fileno())
            self.process = subprocess.Popen(
                self.launch["argv"], cwd=self.launch.get("cwd", self.runtime_directory),
                env=env, pass_fds=(child.fileno(),), stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
            )
            child.close()
            selector.register(parent, selectors.EVENT_READ, "control")
            for stream, name in ((self.process.stdout, "stdout"), (self.process.stderr, "stderr")):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, name)
            workspace.prepare_agent_turn()
            guard.before_agent_turn(expected_identity(guard.profile))
            self._send({"kind": "start", "profile": guard.profile,
                        "scientific_messages": workspace.messages,
                        "tool": guard.profile["native_tool"],
                        "timeout_ms": max(1, int((guard.deadline - time.monotonic()) * 1000))})
            self.agent_dispatches = 1
            while selector.get_map():
                guard.check()
                remaining = guard.deadline - time.monotonic()
                if remaining <= 0:
                    guard.halt("run_timeout")
                for key, _ in selector.select(min(0.2, remaining)):
                    try:
                        data = os.read(key.fileobj.fileno(), 65536)
                    except BlockingIOError:
                        continue
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    evidence_size += len(data)
                    if evidence_size > MAX_EVIDENCE_BYTES:
                        guard.halt("runtime_evidence_budget_exceeded")
                    if key.data != "control":
                        block = ("[" + key.data + "] ").encode() + data
                        log.write(block)
                        log.flush()
                        os.fsync(log.fileno())
                        log_hash.update(block)
                        self.diagnostic_bytes += len(block)
                        continue
                    buffered.extend(data)
                    while b"\n" in buffered:
                        raw, _, rest = buffered.partition(b"\n")
                        buffered[:] = rest
                        if not raw or len(raw) + 1 > MAX_EVENT_BYTES:
                            guard.halt("host_frame_budget_exceeded")
                        self._frame(_decode_frame(raw), workspace)
                    if len(buffered) > MAX_EVENT_BYTES:
                        guard.halt("host_frame_budget_exceeded")
                if self.process.poll() is not None and not selector.get_map():
                    break
            if buffered:
                guard.halt("truncated_host_frame")
            if self.result is None or self.process.wait(timeout=1) != 0:
                guard.halt("host_incomplete_or_nonzero_exit")
            guard.end_agent_turn()
            guard.observe({"event": "runtime_completed"})
            self.termination_reason = "completed"
        except RuntimeViolation as exc:
            self.abort(exc.category)
            raise
        except TimeoutError:
            self.abort("run_timeout")
            raise
        except BaseException:
            self.abort("host_bridge_interrupted")
            raise
        finally:
            self.elapsed_seconds = time.monotonic() - started
            self.diagnostic_sha256 = log_hash.hexdigest()
            selector.close()
            child.close()
            parent.close()
            self.control = None
            if log is not None:
                log.close()
            self.close()

    def close(self):
        process = self.process
        if process is None:
            return
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except OSError:
                    pass
                process.wait(timeout=2)
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                stream.close()

    def snapshot(self) -> dict:
        return {"kind": "openclaw_codex_public_runtime", "agent_dispatches": self.agent_dispatches,
                "native_model_calls": None, "internal_retry_count": None,
                "cost_usd": None, "cost_basis": "subscription_usage_not_reliably_usd_convertible",
                "runtime_events": self.runtime_events, "runtime_result": self.result,
                "tool_results_dispatched_to_host": self.tool_result_dispatches,
                "elapsed_seconds": self.elapsed_seconds, "termination_reason": self.termination_reason,
                "abort_requested": self.aborted, "upstream_abort_acknowledged": None,
                "diagnostic_bytes": self.diagnostic_bytes, "diagnostic_sha256": self.diagnostic_sha256}
