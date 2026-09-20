"""Bounded POSIX pipe I/O for the sealed, bundled offline Python peer.

This is an internal transport primitive, not a general executable adapter.
Only the offline facade may choose its fixed source snapshot. Requests travel
on stdin, never through argv, a shell, an inherited environment, or a file.
An empty private cwd and stripped environment are *not* an OS filesystem or
network sandbox; the trusted bundled peer remains the no-live boundary.
"""

from __future__ import annotations

import math
import os
import selectors
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


_CHUNK_BYTES = 65_536
_EXIT_POLL_SECONDS = 0.05
_CLEANUP_SECONDS = 1.0
_CATEGORIES = frozenset({
    "timeout", "request_too_large", "stdout_limit", "stderr_limit",
    "process_exit", "spawn_error", "io_error", "unsupported_platform",
})


class ProcessTransportError(RuntimeError):
    """A fixed category only: never includes child text, source, or argv."""

    def __init__(self, category: str) -> None:
        if type(category) is not str or category not in _CATEGORIES:
            raise ValueError("invalid process error category")
        self.category = category
        super().__init__(category)


@dataclass(frozen=True)
class ProcessCaps:
    max_request_bytes: int
    max_stdout_bytes: int
    max_stderr_bytes: int

    def __post_init__(self) -> None:
        for name in ("max_request_bytes", "max_stdout_bytes", "max_stderr_bytes"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True)
class ProcessReply:
    stdout: bytes
    stderr_bytes: int
    elapsed_seconds: float


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ProcessTransportError("timeout")
    return remaining


def _stop_and_reap(process: subprocess.Popen) -> bool:
    """Kill the entire original group, including after its leader has exited.

    Cleanup has its own finite allowance; never use Popen's context manager
    or an unbounded wait. A kernel-uninterruptible child cannot be guaranteed
    reaped in finite time, so that exceptional case reports cleanup failure.
    """
    group_ok = True
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except OSError:
        group_ok = False
        # Still attempt to stop/reap the direct child if group signalling fails.
        try:
            process.kill()
        except OSError:
            pass
    for pipe in (process.stdin, process.stdout, process.stderr):
        if pipe is not None:
            try:
                pipe.close()
            except OSError:
                pass
    try:
        process.wait(timeout=_CLEANUP_SECONDS)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return group_ok


def _pump(process: subprocess.Popen, request: bytes, caps: ProcessCaps,
          deadline: float) -> tuple[bytes, int]:
    """Incrementally write stdin and fairly drain both output pipes."""
    stdout = bytearray()
    stderr_bytes = 0
    request_view = memoryview(request)
    written = 0
    with selectors.DefaultSelector() as selector:
        for pipe, role, event in (
            (process.stdin, "stdin", selectors.EVENT_WRITE),
            (process.stdout, "stdout", selectors.EVENT_READ),
            (process.stderr, "stderr", selectors.EVENT_READ),
        ):
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, event, role)

        def close_pipe(pipe) -> None:
            selector.unregister(pipe)
            pipe.close()

        if not request:
            close_pipe(process.stdin)

        while selector.get_map():
            remaining = _remaining(deadline)
            returncode = process.poll()
            if returncode is not None and returncode != 0:
                raise ProcessTransportError("process_exit")
            # Poll exit even if descendants keep all the pipes open but idle.
            events = selector.select(min(remaining, _EXIT_POLL_SECONDS))
            for key, _ in events:
                _remaining(deadline)
                pipe, role = key.fileobj, key.data
                if role == "stdin":
                    try:
                        count = os.write(pipe.fileno(), request_view[
                            written:written + _CHUNK_BYTES])
                    except (BlockingIOError, InterruptedError):
                        continue
                    except BrokenPipeError:
                        raise ProcessTransportError("io_error") from None
                    if count <= 0:
                        raise ProcessTransportError("io_error")
                    written += count
                    if written == len(request):
                        close_pipe(pipe)
                    continue

                used = len(stdout) if role == "stdout" else stderr_bytes
                limit = caps.max_stdout_bytes if role == "stdout" else caps.max_stderr_bytes
                # Read at most one excess byte. stderr content is never retained.
                try:
                    chunk = os.read(pipe.fileno(), min(_CHUNK_BYTES, limit - used + 1))
                except (BlockingIOError, InterruptedError):
                    continue
                if not chunk:
                    close_pipe(pipe)
                    continue
                if used + len(chunk) > limit:
                    raise ProcessTransportError(f"{role}_limit")
                if role == "stdout":
                    stdout.extend(chunk)
                else:
                    stderr_bytes += len(chunk)

        # EOF alone is insufficient: a child can close all its pipes and sleep.
        try:
            returncode = process.wait(timeout=_remaining(deadline))
        except subprocess.TimeoutExpired:
            raise ProcessTransportError("timeout") from None
        _remaining(deadline)
        if returncode != 0:
            raise ProcessTransportError("process_exit")
    return bytes(stdout), stderr_bytes


def _exchange(script_bytes: bytes, request: bytes, *, caps: ProcessCaps,
              timeout_seconds: float, deadline_monotonic: float | None = None) -> ProcessReply:
    """Run one sealed-source exchange, without retries or response repair.

    The duration starts before validation and source decoding. An optional
    caller-owned absolute monotonic deadline can shorten, never extend, it.
    Both limits include setup, spawn, writing, output streams, and child exit.
    Error cleanup may take up to an additional ``_CLEANUP_SECONDS`` for
    reaping. A clean zero exit and EOF on both output pipes are mandatory.
    The caller must validate the response and seal the source/interpreter;
    this helper does not make arbitrary source safe or implement a broker.
    """
    started = time.monotonic()
    if type(script_bytes) is not bytes or type(request) is not bytes:
        raise ValueError("source and request must be bytes")
    if type(caps) is not ProcessCaps:
        raise ValueError("caps must be explicit ProcessCaps")
    # Copy/revalidate even a frozen instance tampered with through object.__setattr__.
    caps = ProcessCaps(caps.max_request_bytes, caps.max_stdout_bytes, caps.max_stderr_bytes)
    if type(timeout_seconds) not in (int, float):
        raise ValueError("timeout_seconds must be positive and finite")
    valid_timeout = False
    try:
        valid_timeout = math.isfinite(timeout_seconds) and timeout_seconds > 0
    except OverflowError:
        pass
    if not valid_timeout:
        raise ValueError("timeout_seconds must be positive and finite")
    deadline = started + timeout_seconds
    if deadline_monotonic is not None:
        valid_deadline = False
        if type(deadline_monotonic) in (int, float):
            try:
                valid_deadline = math.isfinite(deadline_monotonic)
            except OverflowError:
                pass
        if not valid_deadline:
            raise ValueError("deadline_monotonic must be finite numeric or None")
        deadline = min(deadline, deadline_monotonic)
    if len(request) > caps.max_request_bytes:
        raise ProcessTransportError("request_too_large")
    if os.name != "posix":
        raise ProcessTransportError("unsupported_platform")
    _remaining(deadline)

    source = None
    try:
        source = script_bytes.decode("utf-8")
    except UnicodeDecodeError:
        pass
    if source is None:
        raise ValueError("source must be UTF-8")

    category = None
    cleanup_ok = True
    try:
        _remaining(deadline)
        with tempfile.TemporaryDirectory(prefix="tmf-successor-offline-") as directory:
            try:
                interpreter = str(Path(sys.executable).resolve(strict=True))
                _remaining(deadline)
                process = subprocess.Popen(
                    [interpreter, "-I", "-S", "-B", "-c", source],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    cwd=directory, env={"LC_ALL": "C", "LANG": "C"},
                    close_fds=True, start_new_session=True, shell=False, bufsize=0,
                    umask=0o077,
                )
            except (OSError, ValueError, subprocess.SubprocessError):
                raise ProcessTransportError("spawn_error") from None
            try:
                output, stderr_bytes = _pump(process, request, caps, deadline)
                elapsed = time.monotonic() - started
            finally:
                # Also kill any same-group descendants on successful completion.
                cleanup_ok = _stop_and_reap(process)
    except ProcessTransportError as error:
        category = error.category
    except (OSError, ValueError, subprocess.SubprocessError):
        category = "io_error"

    # Construct a fresh exception outside handlers: no underlying exception
    # context (which could contain argv, paths, or child output) escapes.
    if category is not None:
        raise ProcessTransportError(category)
    if not cleanup_ok:
        raise ProcessTransportError("io_error")
    return ProcessReply(output, stderr_bytes, elapsed)
