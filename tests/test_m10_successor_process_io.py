from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import traceback
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from bench.agent_ab.same_version_chain_v1 import m10_successor_process_io as transport


_ECHO = b"import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"


@unittest.skipUnless(os.name == "posix", "transport is intentionally POSIX-only")
class SuccessorProcessIOTests(unittest.TestCase):
    def setUp(self) -> None:
        self.processes = []
        self.commands = []
        real_popen = subprocess.Popen

        def capture(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            self.processes.append(process)
            self.commands.append((args, kwargs))
            return process

        popen_patch = patch.object(transport.subprocess, "Popen", side_effect=capture)
        self.popen = popen_patch.start()
        self.addCleanup(popen_patch.stop)
        self.addCleanup(self._emergency_cleanup)

    def _emergency_cleanup(self) -> None:
        for process in self.processes:
            if process.returncode is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=2)

    def exchange(self, source: bytes | str = _ECHO, request: bytes = b"{}", *,
                 stdout_cap: int = 4_000_000, stderr_cap: int = 1_000_000,
                 request_cap: int = 4_000_000, timeout: float = 3,
                 deadline_monotonic: float | None = None) -> transport.ProcessReply:
        if isinstance(source, str):
            source = source.encode("utf-8")
        return transport._exchange(
            source, request, caps=transport.ProcessCaps(request_cap, stdout_cap, stderr_cap),
            timeout_seconds=timeout, deadline_monotonic=deadline_monotonic,
        )

    def assert_reaped_and_closed(self) -> None:
        self.assertTrue(self.processes)
        for process in self.processes:
            self.assertIsNotNone(process.returncode)
            for pipe in (process.stdin, process.stdout, process.stderr):
                self.assertTrue(pipe.closed)
            with self.assertRaises(ChildProcessError):
                os.waitpid(process.pid, os.WNOHANG)

    def assert_safe_error(self, category: str, source: bytes | str,
                          request: bytes = b"{}", **kwargs) -> transport.ProcessTransportError:
        with self.assertRaises(transport.ProcessTransportError) as caught:
            self.exchange(source, request, **kwargs)
        error = caught.exception
        self.assertEqual(category, error.category)
        self.assertEqual((category,), error.args)
        self.assertEqual(category, str(error))
        self.assertIsNone(error.__cause__)
        self.assertIsNone(error.__context__)
        self.assert_reaped_and_closed()
        return error

    def assert_not_running(self, pid: int) -> None:
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            # Orphans may briefly remain zombies until the host's init reaps.
            if sys.platform.startswith("linux"):
                try:
                    state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
                except FileNotFoundError:
                    return
                if state == "Z":
                    return
            time.sleep(0.01)
        self.fail("same-group descendant was left running")

    def test_caps_are_explicit_strict_positive_and_frozen(self):
        for field in ("max_request_bytes", "max_stdout_bytes", "max_stderr_bytes"):
            for bad in (0, -1, True, False, 1.0, "1", None):
                fields = dict(max_request_bytes=1, max_stdout_bytes=1, max_stderr_bytes=1)
                fields[field] = bad
                with self.subTest(field=field, bad=bad), self.assertRaises(ValueError):
                    transport.ProcessCaps(**fields)
        with self.assertRaises(TypeError):
            transport.ProcessCaps(1, 1)
        caps = transport.ProcessCaps(1, 1, 1)
        with self.assertRaises(FrozenInstanceError):
            caps.max_stdout_bytes = 2
        object.__setattr__(caps, "max_stdout_bytes", 0)
        with self.assertRaises(ValueError):
            transport._exchange(_ECHO, b"", caps=caps, timeout_seconds=1)
        self.popen.assert_not_called()

    def test_timeout_is_strict_positive_finite_before_spawn(self):
        for bad in (0, -1, True, False, float("nan"), float("inf"),
                    float("-inf"), "1", None, 10 ** 1000):
            with self.subTest(type=type(bad)), self.assertRaises(ValueError):
                self.exchange(timeout=bad)
        self.popen.assert_not_called()

    def test_absolute_deadline_is_finite_nonbool_numeric_before_spawn(self):
        for bad in (True, False, float("nan"), float("inf"), float("-inf"),
                    "1", [], 10 ** 1000):
            with self.subTest(type=type(bad)), self.assertRaisesRegex(ValueError, "deadline_monotonic"):
                self.exchange(deadline_monotonic=bad)
        self.popen.assert_not_called()

    def test_source_and_request_require_bytes_before_spawn(self):
        caps = transport.ProcessCaps(100, 100, 100)
        for source, request in (("print(1)", b""), (_ECHO, "{}"),
                                (bytearray(_ECHO), b""), (_ECHO, bytearray(b"{}"))):
            with self.subTest(source=type(source), request=type(request)), self.assertRaises(ValueError):
                transport._exchange(source, request, caps=caps, timeout_seconds=1)
        with self.assertRaises(ValueError):
            transport._exchange(b"\xff", b"", caps=caps, timeout_seconds=1)
        with self.assertRaises(ValueError):
            transport._exchange(_ECHO, b"", caps=None, timeout_seconds=1)
        self.popen.assert_not_called()

    def test_oversized_request_is_rejected_before_spawn(self):
        with self.assertRaises(transport.ProcessTransportError) as caught:
            self.exchange(request=b"x" * 101, request_cap=100)
        self.assertEqual("request_too_large", caught.exception.category)
        self.popen.assert_not_called()

    def test_expired_setup_budget_does_not_spawn(self):
        with self.assertRaises(transport.ProcessTransportError) as caught:
            self.exchange(timeout=5e-324)
        self.assertEqual("timeout", caught.exception.category)
        self.popen.assert_not_called()

    def test_inherited_expired_deadline_does_not_start_a_fresh_duration(self):
        for expired in (0, -1, time.monotonic() - 1):
            with self.subTest(deadline=expired), self.assertRaises(transport.ProcessTransportError) as caught:
                self.exchange(timeout=3, deadline_monotonic=expired)
            self.assertEqual("timeout", caught.exception.category)
        self.popen.assert_not_called()

    def test_delayed_validation_consumes_duration_budget_before_spawn(self):
        caps = transport.ProcessCaps(100, 100, 100)
        original_validation = transport.ProcessCaps.__post_init__

        def delayed_validation(instance):
            original_validation(instance)
            time.sleep(0.05)

        with patch.object(transport.ProcessCaps, "__post_init__", delayed_validation):
            with self.assertRaises(transport.ProcessTransportError) as caught:
                transport._exchange(_ECHO, b"{}", caps=caps, timeout_seconds=0.02)
        self.assertEqual("timeout", caught.exception.category)
        self.popen.assert_not_called()

    def test_delayed_setup_consumes_inherited_deadline_before_spawn(self):
        original_directory = transport.tempfile.TemporaryDirectory
        directories = []

        def delayed_directory(*args, **kwargs):
            directory = original_directory(*args, **kwargs)
            directories.append(Path(directory.name))
            time.sleep(0.05)
            return directory

        with patch.object(transport.tempfile, "TemporaryDirectory", side_effect=delayed_directory):
            with self.assertRaises(transport.ProcessTransportError) as caught:
                self.exchange(timeout=3, deadline_monotonic=time.monotonic() + 0.02)
        self.assertEqual("timeout", caught.exception.category)
        self.popen.assert_not_called()
        self.assertTrue(directories)
        self.assertTrue(all(not directory.exists() for directory in directories))

    def test_inherited_deadline_bounds_running_child(self):
        started = time.monotonic()
        self.assert_safe_error("timeout", "import time; time.sleep(10)", request=b"", timeout=3,
                               deadline_monotonic=started + 0.25)
        self.assertLess(time.monotonic() - started, 1.75)

    def test_later_absolute_deadline_cannot_extend_duration(self):
        started = time.monotonic()
        self.assert_safe_error("timeout", "import time; time.sleep(10)", request=b"", timeout=0.25,
                               deadline_monotonic=started + 3)
        self.assertLess(time.monotonic() - started, 1.75)

    def test_error_category_does_not_accept_arbitrary_text(self):
        for bad in ("CHILD_TEXT_SENTINEL", None, [], 1):
            with self.assertRaisesRegex(ValueError, "^invalid process error category$"):
                transport.ProcessTransportError(bad)

    def test_echo_is_binary_exact_and_reply_is_immutable(self):
        payload = b"\x00\xff\r\n\xe4\xb8\xad"
        reply = self.exchange(request=payload, request_cap=len(payload), stdout_cap=len(payload))
        self.assertEqual(payload, reply.stdout)
        self.assertIs(type(reply.stdout), bytes)
        self.assertEqual(0, reply.stderr_bytes)
        self.assertGreater(reply.elapsed_seconds, 0)
        self.assertLess(reply.elapsed_seconds, 3)
        with self.assertRaises(FrozenInstanceError):
            reply.stdout = b"changed"
        self.assert_reaped_and_closed()

    def test_empty_request_delivers_eof(self):
        self.assertEqual(b"", self.exchange(request=b"").stdout)
        self.assert_reaped_and_closed()

    def test_streaming_echo_larger_than_pipe_capacity(self):
        payload = bytes(range(256)) * 8192
        source = """
import sys
while True:
    chunk = sys.stdin.buffer.read1(8192)
    if not chunk:
        break
    sys.stdout.buffer.write(chunk)
    sys.stdout.buffer.flush()
"""
        reply = self.exchange(source, payload, request_cap=len(payload), stdout_cap=len(payload))
        self.assertEqual(payload, reply.stdout)
        self.assert_reaped_and_closed()

    def test_large_stdin_and_parallel_stdout_stderr_do_not_deadlock(self):
        source = """
import sys
import threading
def emit(stream, value):
    for _ in range(96):
        stream.write(value * 4096)
        stream.flush()
out = threading.Thread(target=emit, args=(sys.stdout.buffer, b'o'))
err = threading.Thread(target=emit, args=(sys.stderr.buffer, b'e'))
out.start()
err.start()
received = sys.stdin.buffer.read()
out.join()
err.join()
sys.stdout.buffer.write(str(len(received)).encode('ascii'))
"""
        reply = self.exchange(source, b"r" * 2_000_000)
        self.assertEqual(b"o" * (96 * 4096) + b"2000000", reply.stdout)
        self.assertEqual(96 * 4096, reply.stderr_bytes)
        self.assert_reaped_and_closed()

    def test_exact_output_limits_are_allowed(self):
        source = "import os; os.write(1, b'o' * 4096); os.write(2, b'e' * 4096)"
        reply = self.exchange(source, request=b"", stdout_cap=4096, stderr_cap=4096)
        self.assertEqual(b"o" * 4096, reply.stdout)
        self.assertEqual(4096, reply.stderr_bytes)
        self.assert_reaped_and_closed()

    def test_stdout_overflow_even_one_byte_fails(self):
        self.assert_safe_error("stdout_limit", "import os; os.write(1, b'x' * 4097)",
                               request=b"", stdout_cap=4096)

    def test_stderr_overflow_even_one_byte_fails_without_text(self):
        error = self.assert_safe_error(
            "stderr_limit", "import os; os.write(2, b'STDERR_PRIVATE_SENTINEL' * 1024)",
            request=b"", stderr_cap=10,
        )
        self.assertNotIn("STDERR_PRIVATE_SENTINEL", repr(error))

    def test_unending_stdout_flood_is_bounded_while_stdin_is_blocked(self):
        source = "import os\nwhile True: os.write(1, b'x' * 65536)"
        started = time.monotonic()
        self.assert_safe_error("stdout_limit", source, b"r" * 2_000_000, stdout_cap=4096)
        self.assertLess(time.monotonic() - started, 2)

    def test_unending_stderr_flood_is_bounded_while_stdin_is_blocked(self):
        source = "import os\nwhile True: os.write(2, b'x' * 65536)"
        started = time.monotonic()
        self.assert_safe_error("stderr_limit", source, b"r" * 2_000_000, stderr_cap=4096)
        self.assertLess(time.monotonic() - started, 2)

    def test_no_stdin_reader_obeys_deadline_and_is_reaped(self):
        started = time.monotonic()
        self.assert_safe_error("timeout", "import time; time.sleep(10)",
                               b"r" * 2_000_000, timeout=0.25)
        self.assertLess(time.monotonic() - started, 1.75)

    def test_deadline_applies_after_valid_stdout(self):
        source = "import os, time; os.write(1, b'{\"ok\":true}'); time.sleep(10)"
        self.assert_safe_error("timeout", source, request=b"", timeout=0.25)

    def test_deadline_applies_after_all_pipes_reach_eof(self):
        source = "import os, time; os.close(0); os.close(1); os.close(2); time.sleep(10)"
        self.assert_safe_error("timeout", source, request=b"", timeout=0.25)

    def test_early_closed_stdin_cannot_accept_an_unwritten_request(self):
        source = "import os, time; os.close(0); os.write(1, b'{}'); time.sleep(10)"
        self.assert_safe_error("io_error", source, b"r" * 2_000_000)

    def test_zero_exit_before_large_request_is_written_fails_closed(self):
        self.assert_safe_error("io_error", "import os; os._exit(0)", b"r" * 2_000_000)

    def test_valid_stdout_nonzero_exit_is_not_a_reply(self):
        source = """
import os
os.write(1, b'{"ok":true}')
os.write(2, b'STDERR_PRIVATE_SENTINEL')
os._exit(7)
"""
        error = self.assert_safe_error("process_exit", source, request=b"")
        formatted = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        for forbidden in ("STDERR_PRIVATE_SENTINEL", '{"ok":true}', "os._exit(7)"):
            self.assertNotIn(forbidden, str(error))
            self.assertNotIn(forbidden, repr(error))
            self.assertNotIn(forbidden, formatted)

    def test_signal_exit_is_not_a_reply(self):
        source = "import os, signal; os.kill(os.getpid(), signal.SIGTERM)"
        self.assert_safe_error("process_exit", source, request=b"")

    def test_descendant_held_pipes_obey_deadline_even_after_zero_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "pids.json"
            source = """
import json, os, sys, time
report = json.loads(sys.stdin.buffer.read())['report']
descendant = os.fork()
if descendant == 0:
    time.sleep(10)
    os._exit(0)
with open(report, 'w') as stream:
    json.dump({'descendant': descendant, 'leader': os.getpid()}, stream)
os._exit(0)
"""
            started = time.monotonic()
            self.assert_safe_error("timeout", source, json.dumps({"report": str(report)}).encode(),
                                   timeout=0.6)
            self.assertLess(time.monotonic() - started, 2.1)
            pids = json.loads(report.read_text())
            self.assertEqual(self.processes[-1].pid, pids["leader"])
            self.assertEqual(0, self.processes[-1].returncode)
            self.assert_not_running(pids["descendant"])

    def test_nonzero_leader_exit_kills_pipe_holding_descendant(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "pid.json"
            source = """
import json, os, sys, time
report = json.loads(sys.stdin.buffer.read())['report']
descendant = os.fork()
if descendant == 0:
    time.sleep(10)
    os._exit(0)
with open(report, 'w') as stream:
    json.dump(descendant, stream)
os._exit(8)
"""
            started = time.monotonic()
            self.assert_safe_error("process_exit", source, json.dumps({"report": str(report)}).encode())
            self.assertLess(time.monotonic() - started, 2)
            self.assert_not_running(json.loads(report.read_text()))

    def test_private_empty_cwd_minimal_env_and_isolated_interpreter(self):
        source = """
import json, os, stat, sys
print(json.dumps({
    'cwd': os.getcwd(), 'entries': os.listdir('.'),
    'cwd_mode': stat.S_IMODE(os.stat('.').st_mode), 'env': dict(os.environ),
    'isolated': sys.flags.isolated, 'no_site': sys.flags.no_site,
    'dont_write_bytecode': sys.dont_write_bytecode,
    'pid': os.getpid(), 'pgid': os.getpgrp(), 'sid': os.getsid(0), 'argv': sys.argv,
}))
"""
        with patch.dict(os.environ, {"M10_PROCESS_SENTINEL": "NEVER_INHERIT_SENTINEL",
                                     "PYTHONPATH": "/sentinel-python-path"}):
            body = json.loads(self.exchange(source, request=b"").stdout)
        self.assertEqual([], body["entries"])
        self.assertEqual(0o700, body["cwd_mode"])
        self.assertNotEqual(os.getcwd(), body["cwd"])
        self.assertFalse(Path(body["cwd"]).exists())
        self.assertEqual({"LC_ALL": "C", "LANG": "C"}, body["env"])
        self.assertEqual(1, body["isolated"])
        self.assertEqual(1, body["no_site"])
        self.assertTrue(body["dont_write_bytecode"])
        self.assertEqual(body["pid"], body["pgid"])
        self.assertEqual(body["pid"], body["sid"])
        self.assertEqual(["-c"], body["argv"])
        args, kwargs = self.commands[-1]
        self.assertEqual(str(Path(sys.executable).resolve(strict=True)), args[0][0])
        self.assertEqual(["-I", "-S", "-B", "-c"], args[0][1:5])
        self.assertFalse(kwargs["shell"])
        self.assertTrue(kwargs["close_fds"])
        self.assert_reaped_and_closed()

    def test_inheritable_nonstandard_file_descriptor_is_not_inherited(self):
        import fcntl

        with tempfile.TemporaryFile() as stream:
            descriptor = fcntl.fcntl(stream.fileno(), fcntl.F_DUPFD, 100)
            try:
                os.set_inheritable(descriptor, True)
                source = """
import json, os, sys
descriptor = json.loads(sys.stdin.buffer.read())['descriptor']
try:
    os.fstat(descriptor)
except OSError:
    print('closed')
else:
    print('inherited')
"""
                reply = self.exchange(source, json.dumps({"descriptor": descriptor}).encode())
            finally:
                os.close(descriptor)
        self.assertEqual(b"closed\n", reply.stdout)

    def test_request_shell_metacharacters_are_only_stdin_data(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "must-not-exist"
            request = json.dumps({"value": f"$(touch {marker}); `touch {marker}`; ${'{'}HOME{'}'}"}).encode()
            self.assertEqual(request, self.exchange(request=request).stdout)
            self.assertFalse(marker.exists())
        args, kwargs = self.commands[-1]
        self.assertNotIn(request.decode(), args[0])
        self.assertEqual(kwargs["stdin"], subprocess.PIPE)

    def test_spawn_failure_is_sanitized_without_exception_context(self):
        with patch.object(transport.subprocess, "Popen", side_effect=OSError("SPAWN_PRIVATE_SENTINEL")):
            with self.assertRaises(transport.ProcessTransportError) as caught:
                self.exchange()
        self.assertEqual("spawn_error", str(caught.exception))
        self.assertIsNone(caught.exception.__context__)
        self.assertNotIn("SPAWN_PRIVATE_SENTINEL", repr(caught.exception))
        self.assertEqual([], self.processes)

    def test_io_setup_failure_still_kills_and_reaps(self):
        with patch.object(transport.os, "set_blocking", side_effect=OSError("IO_PRIVATE_SENTINEL")):
            error = self.assert_safe_error("io_error", "import time; time.sleep(10)")
        self.assertNotIn("IO_PRIVATE_SENTINEL", repr(error))


if __name__ == "__main__":
    unittest.main()
