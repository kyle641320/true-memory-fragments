"""Bounded, single-attempt Responses transport and durable operation accounting.

Importing this module does not inspect credentials or access a network. The
credential callback is invoked only by an explicitly dispatched HTTP request.
Every count request is admitted before dispatch too: its price is unknown, not
zero. Reopening a journal is inspection-only, including after a clean shutdown.
The hash chain detects corruption; it is not authentication against its owner.
Timeout is NOT evidence that the provider stopped processing or charging.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import queue
import re
import stat
import tempfile
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import successor_openai_responses as codec


COUNT_URL = "https://api.openai.com/v1/responses/input_tokens"
GENERATION_URL = "https://api.openai.com/v1/responses"
MAX_REQUEST_BYTES = 120_000
MAX_RESPONSE_BYTES = 262_144
MAX_COUNTS = 12
MAX_GENERATIONS = 3
MAX_INPUT_PER_CALL = 10_000
MAX_INPUT_TOTAL = 30_000
MAX_OUTPUT_TOTAL = 8_256
OUTPUT_CAPS = (4096, 4096, 64)
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ZERO = "0" * 64
_MAX_JOURNAL_BYTES = 1_048_576
_MAX_EVENT_BYTES = 32_768
_SAFE_HEADERS = frozenset({"x-request-id", "openai-processing-ms", "date", "content-type"})


def operation_policy() -> dict:
    """Frozen public material; changing a bound requires a new reviewed seal."""
    return {
        "schema": "tmf_openai_operations.v1", "max_count_requests": MAX_COUNTS,
        "max_generation_requests": MAX_GENERATIONS,
        "max_input_tokens_per_generation": MAX_INPUT_PER_CALL,
        "max_input_tokens_total": MAX_INPUT_TOTAL, "max_output_tokens_total": MAX_OUTPUT_TOTAL,
        "generation_output_caps": list(OUTPUT_CAPS), "count_pricing": "unknown",
        "attempts_per_operation": 1, "reopen": "inspection_only",
        "unknown_generation_charge": "full_admitted_input_and_output_reservation",
        "admission": "fsynced_before_post", "retry": False, "redirect": False,
        "request_bytes": MAX_REQUEST_BYTES, "response_bytes": MAX_RESPONSE_BYTES,
    }


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _strict(raw: bytes) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def integer(value):
        if len(value) > 18:
            raise ValueError("oversized integer")
        return int(value)

    def invalid(value):
        raise ValueError("nonfinite JSON number")

    return json.loads(raw, object_pairs_hook=pairs, parse_int=integer, parse_constant=invalid)


def _uint(value: Any, upper: int = 10**15) -> bool:
    return type(value) is int and 0 <= value <= upper


def _valid_usage(value: Any) -> bool:
    return (type(value) is dict and set(value) == {"input_tokens", "output_tokens", "total_tokens"}
            and all(_uint(v) for v in value.values())
            and value["input_tokens"] + value["output_tokens"] == value["total_tokens"])


class JournalError(RuntimeError):
    """Durability, integrity or a fixed operation budget failed."""


class BrokerFailure(RuntimeError):
    """Sanitized failure with an auditable receipt, never a raw exception text."""

    def __init__(self, category: str, receipt: dict | None = None):
        super().__init__(category)
        self.category = category
        self.receipt = receipt or {"ok": False, "category": category}


class OperationJournal:
    """One authorization, one seal, one owner, no replacement or restart budget."""

    def __init__(self, path: Path, *, authorization_id: str, seal_sha256: str):
        if type(authorization_id) is not str or not _ID.fullmatch(authorization_id):
            raise JournalError("invalid authorization ID")
        if type(seal_sha256) is not str or not _HASH.fullmatch(seal_sha256):
            raise JournalError("invalid seal")
        self.path = Path(path).absolute()
        self.authorization_id, self.seal_sha256 = authorization_id, seal_sha256
        self._pid, self._fd = os.getpid(), -1
        self._mutex = threading.RLock()
        self._inspection_only = False
        self._poisoned = False
        self._raw = b""
        self._last_hash, self._sequence = _ZERO, 0
        self._state = {"authorization_id": authorization_id, "seal_sha256": seal_sha256,
                       "count_requests": 0, "generation_requests": 0,
                       "input_reserved": 0, "output_reserved": 0,
                       "known_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                       "charged_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                       "pending": None, "halt_reason": None, "operations": {},
                       "count_pricing": "unknown"}
        temporary = None
        try:
            if self.path.parent.resolve() != self.path.parent:
                raise JournalError("journal parent must not use symlinks")
            try:
                self._fd = os.open(self.path, os.O_RDWR | os.O_APPEND | os.O_CLOEXEC
                                   | os.O_NOFOLLOW | os.O_NONBLOCK)
                self._inspection_only = True
            except FileNotFoundError:
                self._fd, temporary = tempfile.mkstemp(prefix=f".{self.path.name}.",
                                                       dir=self.path.parent)
                fcntl.fcntl(self._fd, fcntl.F_SETFL, os.O_APPEND)
            if not stat.S_ISREG(os.fstat(self._fd).st_mode):
                raise JournalError("journal must be a regular file")
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if self._inspection_only:
                self._replay(self._read())
            else:
                self._append({"kind": "initialized", "authorization_id": authorization_id,
                              "seal_sha256": seal_sha256, "policy": operation_policy()}, initial=True)
                os.link(temporary, self.path, follow_symlinks=False)
                os.unlink(temporary)
                temporary = None
                self._fsync_parent()
            self._verify()
        except BaseException as exc:
            self.close()
            if not isinstance(exc, Exception):
                raise
            raise JournalError("cannot initialize or verify operation journal") from None
        finally:
            if temporary is not None:
                os.unlink(temporary)

    def _fsync_parent(self):
        fd = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def __enter__(self):
        self._ensure_open()
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        with self._mutex:
            if self._fd >= 0:
                os.close(self._fd)
                self._fd = -1

    def _ensure_open(self):
        if self._fd < 0 or os.getpid() != self._pid:
            raise JournalError("journal closed or ownership changed")

    def _read(self) -> bytes:
        self._ensure_open()
        size = os.fstat(self._fd).st_size
        if size > _MAX_JOURNAL_BYTES:
            raise JournalError("journal too large")
        return os.pread(self._fd, size + 1, 0)

    def _verify(self):
        self._ensure_open()
        try:
            held, named = os.fstat(self._fd), os.lstat(self.path)
            if (not stat.S_ISREG(named.st_mode) or held.st_ino != named.st_ino
                    or held.st_dev != named.st_dev or self._read() != self._raw):
                raise ValueError("changed journal")
        except Exception:
            self._poisoned = True
            raise JournalError("journal integrity failed") from None

    def _replay(self, raw: bytes):
        if not raw or not raw.endswith(b"\n"):
            raise JournalError("truncated journal")
        for line in raw.splitlines():
            if not line or len(line) > _MAX_EVENT_BYTES:
                raise JournalError("invalid journal frame")
            frame = _strict(line)
            if (type(frame) is not dict or set(frame) != {"sequence", "previous", "event", "sha256"}
                    or type(frame["sequence"]) is not int or frame["sequence"] != self._sequence
                    or frame["previous"] != self._last_hash):
                raise JournalError("invalid journal chain")
            core = {key: frame[key] for key in ("sequence", "previous", "event")}
            if frame["sha256"] != _sha(_canonical(core)) or _canonical(frame) != line:
                raise JournalError("invalid journal digest")
            self._apply(frame["event"])
            self._sequence += 1
            self._last_hash = frame["sha256"]
        self._raw = raw

    def _apply(self, event: dict):
        if type(event) is not dict:
            raise JournalError("invalid event")
        state, kind = self._state, event.get("kind")
        if self._sequence == 0:
            if event != {"kind": "initialized", "authorization_id": self.authorization_id,
                         "seal_sha256": self.seal_sha256, "policy": operation_policy()}:
                raise JournalError("authorization, seal or policy changed")
            return
        if kind == "admitted":
            required = {"kind", "operation_id", "operation", "request_sha256", "scientific_sha256",
                        "input_tokens", "max_output_tokens"}
            if (set(event) != required or type(event["operation_id"]) is not str
                    or not _ID.fullmatch(event["operation_id"])
                    or event["operation_id"] in state["operations"]
                    or state["pending"] is not None or state["halt_reason"] is not None
                    or state["generation_requests"] >= MAX_GENERATIONS
                    or any(type(event[k]) is not str or not _HASH.fullmatch(event[k])
                           for k in ("request_sha256", "scientific_sha256"))):
                raise JournalError("invalid or duplicate admission")
            inp, out = event["input_tokens"], event["max_output_tokens"]
            if event["operation"] == "count":
                if inp != 0 or out != 0 or type(inp) is not int or type(out) is not int or state["count_requests"] >= MAX_COUNTS:
                    raise JournalError("count budget exceeded")
                state["count_requests"] += 1
            elif event["operation"] == "generation":
                if (not _uint(inp, MAX_INPUT_PER_CALL) or type(out) is not int
                        or out != OUTPUT_CAPS[state["generation_requests"]]
                        or state["input_reserved"] + inp > MAX_INPUT_TOTAL
                        or state["output_reserved"] + out > MAX_OUTPUT_TOTAL):
                    raise JournalError("generation budget exceeded")
                state["generation_requests"] += 1
                state["input_reserved"] += inp
                state["output_reserved"] += out
            else:
                raise JournalError("unknown operation")
            state["pending"] = event["operation_id"]
            state["operations"][event["operation_id"]] = dict(event)
        elif kind == "settled":
            if (set(event) != {"kind", "operation_id", "ok", "category", "usage", "input_count"}
                    or type(event["ok"]) is not bool or event["operation_id"] != state["pending"]
                    or type(event["category"]) is not str or not _ID.fullmatch(event["category"])
                    or event["ok"] != (event["category"] == "ok")):
                raise JournalError("invalid settlement")
            op = state["operations"][state["pending"]]
            usage, count = event["usage"], event["input_count"]
            if op["operation"] == "count":
                if usage is not None or (count is not None and not _uint(count, MAX_INPUT_PER_CALL)) or (event["ok"] and count is None):
                    raise JournalError("invalid count settlement")
            else:
                if count is not None or (usage is not None and not _valid_usage(usage)) or (event["ok"] and usage is None):
                    raise JournalError("invalid generation settlement")
                if event["ok"] and (usage["input_tokens"] != op["input_tokens"]
                                    or usage["output_tokens"] > op["max_output_tokens"]):
                    raise JournalError("successful usage exceeds admitted contract")
                charged = usage or {"input_tokens": op["input_tokens"], "output_tokens": op["max_output_tokens"],
                                    "total_tokens": op["input_tokens"] + op["max_output_tokens"]}
                for key in state["known_usage"]:
                    state["known_usage"][key] += usage[key] if usage is not None else 0
                    state["charged_usage"][key] += charged[key]
            op["settlement"] = dict(event)
            state["pending"] = None
            if not event["ok"]:
                state["halt_reason"] = event["category"]
        elif kind == "halted":
            if (set(event) != {"kind", "category"} or type(event["category"]) is not str
                    or not _ID.fullmatch(event["category"]) or state["halt_reason"] is not None):
                raise JournalError("invalid halt")
            state["halt_reason"] = event["category"]
        else:
            raise JournalError("unknown journal transition")

    def _append(self, event: dict, *, initial=False):
        if not initial:
            self._verify()
        if self._inspection_only or self._poisoned:
            raise JournalError("reopened or poisoned journal cannot dispatch")
        # Validate a proposed transition without retaining a partial mutation.
        before = _strict(_canonical(self._state))
        try:
            self._apply(event)
        except Exception:
            self._state = before
            raise
        core = {"sequence": self._sequence, "previous": self._last_hash, "event": event}
        digest = _sha(_canonical(core))
        raw = _canonical({**core, "sha256": digest}) + b"\n"
        if len(raw) > _MAX_EVENT_BYTES or len(self._raw) + len(raw) > _MAX_JOURNAL_BYTES:
            self._poisoned = True
            raise JournalError("journal structural limit")
        try:
            written = 0
            while written < len(raw):
                count = os.write(self._fd, raw[written:])
                if count <= 0:
                    raise OSError("short journal write")
                written += count
            os.fsync(self._fd)
        except Exception:
            self._poisoned = True
            raise JournalError("journal write failed") from None
        self._raw += raw
        self._sequence += 1
        self._last_hash = digest
        if not initial:
            self._verify()

    def admit(self, operation_id: str, operation: str, *, request_sha256: str,
              scientific_sha256: str, input_tokens: int = 0, max_output_tokens: int = 0):
        with self._mutex:
            self._append({"kind": "admitted", "operation_id": operation_id, "operation": operation,
                          "request_sha256": request_sha256, "scientific_sha256": scientific_sha256,
                          "input_tokens": input_tokens, "max_output_tokens": max_output_tokens})

    def settle(self, operation_id: str, *, ok: bool, category: str,
               usage: dict | None = None, input_count: int | None = None):
        with self._mutex:
            self._append({"kind": "settled", "operation_id": operation_id, "ok": ok,
                          "category": category, "usage": usage, "input_count": input_count})

    def halt(self, category: str):
        with self._mutex:
            if self._state["halt_reason"] is None:
                self._append({"kind": "halted", "category": category})

    def snapshot(self) -> dict:
        with self._mutex:
            self._verify()
            state = _strict(_canonical(self._state))
            pending = state["operations"].get(state["pending"])
            if pending and pending["operation"] == "generation":
                # An admitted call without a durable settlement may have run.
                state["charged_usage"]["input_tokens"] += pending["input_tokens"]
                state["charged_usage"]["output_tokens"] += pending["max_output_tokens"]
                state["charged_usage"]["total_tokens"] += pending["input_tokens"] + pending["max_output_tokens"]
            state.update(inspection_only=self._inspection_only, journal_sha256=_sha(self._raw),
                         complete=state["generation_requests"] == MAX_GENERATIONS and state["pending"] is None
                         and state["halt_reason"] is None)
            return state


@dataclass(frozen=True)
class PostResult:
    status: int
    headers: dict
    body: bytes


def _remaining(deadline: float) -> float:
    if type(deadline) not in (int, float) or not math.isfinite(deadline):
        raise BrokerFailure("invalid_deadline")
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise BrokerFailure("deadline_exceeded")
    return remaining


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _safe_headers(headers) -> dict:
    result = {}
    for key, value in headers.items():
        if type(key) is str and key.lower() in _SAFE_HEADERS and type(value) is str:
            result[key.lower()] = value[:1024]
    return result


class SinglePostTransport:
    """Exactly one stdlib POST; no redirect/retry/fallback or SDK defaults.

    A daemon worker bounds total observed wall time, including DNS/header reads
    that socket timeouts alone cannot bound. On timeout it may still be running;
    the broker halts and conservatively settles, never dispatches another call.
    No request/authorization headers are retained in evidence or exceptions.
    The stdlib opener retains normal HTTPS proxy support for protected egress.
    """

    def __init__(self, credential_provider: Callable[[], str], *, opener=None):
        if not callable(credential_provider):
            raise ValueError("credential callback required")
        self._credential_provider = credential_provider
        self._opener = opener or urllib.request.build_opener(_NoRedirect())

    def post(self, url: str, body: bytes, *, deadline_monotonic: float) -> PostResult:
        if url not in (COUNT_URL, GENERATION_URL):
            raise BrokerFailure("endpoint_not_allowed")
        if type(body) is not bytes or len(body) > MAX_REQUEST_BYTES:
            raise BrokerFailure("request_size")
        _remaining(deadline_monotonic)
        result_queue: queue.Queue = queue.Queue(maxsize=1)

        def perform():
            try:
                _remaining(deadline_monotonic)
                credential = self._credential_provider()
                if type(credential) is not str or not credential or "\r" in credential or "\n" in credential:
                    raise BrokerFailure("credential_unavailable")
                request = urllib.request.Request(url, data=body, method="POST", headers={
                    "Authorization": "Bearer " + credential, "Content-Type": "application/json",
                    "Accept": "application/json", "User-Agent": "tmf-successor-conformance/1",
                })
                # There is exactly one invocation of open. HTTPError is itself
                # the received response, not permission to repeat the request.
                try:
                    response = self._opener.open(request, timeout=_remaining(deadline_monotonic))
                except urllib.error.HTTPError as exc:
                    response = exc
                with response:
                    status = response.status
                    headers = _safe_headers(response.headers)
                    chunks, size = [], 0
                    while True:
                        _remaining(deadline_monotonic)
                        chunk = response.read1(min(65_536, MAX_RESPONSE_BYTES + 1 - size))
                        if not chunk:
                            break
                        chunks.append(chunk)
                        size += len(chunk)
                        if size > MAX_RESPONSE_BYTES:
                            raise BrokerFailure("response_size")
                    _remaining(deadline_monotonic)
                    result_queue.put(PostResult(status, headers, b"".join(chunks)))
            except Exception as exc:
                category = exc.category if type(exc) is BrokerFailure else "transport_uncertain"
                result_queue.put(BrokerFailure(category))

        threading.Thread(target=perform, daemon=True, name="tmf-single-post").start()
        try:
            result = result_queue.get(timeout=_remaining(deadline_monotonic))
        except queue.Empty:
            raise BrokerFailure("transport_timeout") from None
        if isinstance(result, BrokerFailure):
            raise result
        return result


def _write_new(path: Path, raw: bytes):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(fd)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


class CountedBroker:
    """Admission, exact same bytes, original evidence, and known/unknown usage."""

    def __init__(self, sender, journal: OperationJournal, evidence_dir: Path):
        self.sender, self.journal = sender, journal
        self.evidence_dir = Path(evidence_dir).absolute()
        self.evidence_dir.mkdir(mode=0o700, exist_ok=True)
        if (self.evidence_dir.resolve() != self.evidence_dir
                or not stat.S_ISDIR(os.lstat(self.evidence_dir).st_mode)):
            raise JournalError("evidence directory must not use symlinks")
        self._mutex = threading.RLock()

    def _receipt(self, operation_id, category, observation=None):
        receipt = {"ok": False, "category": category, "operation_id": operation_id,
                   "evidence_dir": str(self.evidence_dir), "observation": observation}
        try:
            receipt["journal"] = self.journal.snapshot()
        except JournalError:
            receipt["journal_integrity"] = "failed"
        return receipt

    def _fail_before(self, operation_id, category):
        try:
            self.journal.halt(category)
        except JournalError:
            pass
        raise BrokerFailure(category, self._receipt(operation_id, category)) from None

    def _precheck(self, prepared, operation_id, deadline):
        try:
            if type(operation_id) is not str or not _ID.fullmatch(operation_id):
                raise BrokerFailure("invalid_operation_id")
            codec.verify_prepared(prepared)
            _remaining(deadline)
        except Exception as exc:
            category = exc.category if type(exc) is BrokerFailure else "invalid_prepared_request"
            self._fail_before(operation_id, category)

    def _dispatch(self, prepared, operation_id, operation, body, url, deadline,
                  *, input_tokens=0, max_output_tokens=0) -> PostResult:
        if type(body) is not bytes or len(body) > MAX_REQUEST_BYTES:
            self._fail_before(operation_id, "request_size")
        response = None
        try:
            self.journal.admit(operation_id, operation, request_sha256=_sha(body),
                               scientific_sha256=prepared.scientific_sha256,
                               input_tokens=input_tokens, max_output_tokens=max_output_tokens)
            _write_new(self.evidence_dir / f"{operation_id}.request.json", body)
            _write_new(self.evidence_dir / f"{operation_id}.admission.json", _canonical({
                "operation": operation, "endpoint": url, "admitted_unix_ns": time.time_ns(),
                "deadline_monotonic": deadline, "request_sha256": _sha(body),
                "scientific_sha256": prepared.scientific_sha256,
                "input_reservation": input_tokens, "output_reservation": max_output_tokens,
            }))
            _remaining(deadline)
            response = self.sender.post(url, body, deadline_monotonic=deadline)
            if (type(response) is not PostResult or type(response.body) is not bytes
                    or len(response.body) > MAX_RESPONSE_BYTES or type(response.status) is not int
                    or not 100 <= response.status <= 599 or type(response.headers) is not dict):
                raise BrokerFailure("invalid_transport_response")
            _write_new(self.evidence_dir / f"{operation_id}.response.bin", response.body)
            _write_new(self.evidence_dir / f"{operation_id}.metadata.json", _canonical({
                "operation": operation, "endpoint": url, "http_status": response.status,
                "headers": _safe_headers(response.headers), "received_unix_ns": time.time_ns(),
                "request_sha256": _sha(body), "response_sha256": _sha(response.body),
                "scientific_sha256": prepared.scientific_sha256,
            }))
            return response
        except Exception as exc:
            category = exc.category if type(exc) is BrokerFailure else (
                "journal_error" if isinstance(exc, JournalError) else "transport_or_evidence_failure")
            # A received valid aggregate remains known even if persisting its
            # accompanying evidence fails. Raw-byte evidence failure still
            # halts; accounting is not an excuse to discard observed usage.
            usage = None
            if operation == "generation" and type(response) is PostResult and type(response.body) is bytes:
                try:
                    candidate = codec.inspect_response(response.body, prepared,
                                                       expected_input_tokens=input_tokens).get("usage")
                    usage = candidate if _valid_usage(candidate) else None
                except Exception:
                    pass
            try:
                state = self.journal.snapshot()
                if state["pending"] == operation_id:
                    self.journal.settle(operation_id, ok=False, category=category, usage=usage)
                else:
                    self.journal.halt(category)
            except JournalError:
                pass
            raise BrokerFailure(category, self._receipt(operation_id, category)) from None

    def count(self, prepared, *, operation_id: str, deadline_monotonic: float) -> int:
        with self._mutex:
            self._precheck(prepared, operation_id, deadline_monotonic)
            response = self._dispatch(prepared, operation_id, "count", prepared.count_json.encode("utf-8"),
                                      COUNT_URL, deadline_monotonic)
            count, category = None, "ok"
            try:
                _remaining(deadline_monotonic)
                if response.status != 200:
                    raise BrokerFailure("http_status")
                count = codec.parse_count(response.body)
                if not _uint(count, MAX_INPUT_PER_CALL):
                    count = None
                    raise BrokerFailure("input_count_limit")
            except Exception as exc:
                category = exc.category if type(exc) is BrokerFailure else "invalid_count_response"
            try:
                self.journal.settle(operation_id, ok=category == "ok", category=category, input_count=count)
            except JournalError:
                category = "journal_error"
            if category != "ok":
                raise BrokerFailure(category, self._receipt(operation_id, category)) from None
            return count

    def complete(self, prepared, *, operation_id: str, expected_input_tokens: int,
                 deadline_monotonic: float, expect_cap: bool = False) -> dict:
        with self._mutex:
            self._precheck(prepared, operation_id, deadline_monotonic)
            if not _uint(expected_input_tokens, MAX_INPUT_PER_CALL) or type(expect_cap) is not bool:
                self._fail_before(operation_id, "invalid_expected_count")
            if expect_cap != (prepared.purpose == "output_cap"):
                self._fail_before(operation_id, "response_purpose_mismatch")
            observed = self.count(prepared, operation_id=operation_id + "-recount",
                                  deadline_monotonic=deadline_monotonic)
            if observed != expected_input_tokens:
                self._fail_before(operation_id, "count_mismatch")
            response = self._dispatch(prepared, operation_id, "generation",
                                      prepared.generation_json.encode("utf-8"), GENERATION_URL,
                                      deadline_monotonic, input_tokens=observed,
                                      max_output_tokens=prepared.max_output_tokens)
            observation, usage, category = None, None, "ok"
            try:
                observation = codec.inspect_response(response.body, prepared,
                                                     expected_input_tokens=observed, expect_cap=expect_cap)
                candidate = observation.get("usage")
                usage = candidate if _valid_usage(candidate) else None
                _remaining(deadline_monotonic)
                if response.status != 200:
                    raise BrokerFailure("http_status")
                if not observation.get("ok") or usage is None:
                    raise BrokerFailure("response_contract_failure")
            except Exception as exc:
                category = exc.category if type(exc) is BrokerFailure else "invalid_generation_response"
            try:
                self.journal.settle(operation_id, ok=category == "ok", category=category, usage=usage)
            except JournalError:
                category = "journal_error"
            if category != "ok":
                raise BrokerFailure(category, self._receipt(operation_id, category, observation)) from None
            return observation
