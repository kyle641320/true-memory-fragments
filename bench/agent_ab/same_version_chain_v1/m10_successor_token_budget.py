"""Offline token-accounting contract; this module has no transport or retry path.

Each reservation is append-only and fsynced before it is returned to a caller.
The caller must reserve *before* a possible dispatch, and settle at most once.
An unclosed reservation recovered from disk is an unknown outcome, not a free
retry. Conservative budget charges are deliberately separate from provider
usage: a charge never substitutes for missing usage evidence.

The JSONL journal uses a hash chain and strict replay under a nonblocking POSIX
flock. It detects corrupt records, partial writes, and invalid transitions; it
is not an authenticated archive against an owner rewriting the entire file.
The parent directory must already exist. Keep the same journal for a budget's
lifetime; creating another file is not a continuation of that budget.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
import threading
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


_SCHEMA = "m10_successor_token_budget.v1"
_ZERO_HASH = "0" * 64
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_CALL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_OUTCOMES = frozenset({"success", "error", "timeout", "unknown"})
_MAX_LINE_BYTES = 65_536


class TokenBudgetError(RuntimeError):
    """Base error; a rejected admission must never be dispatched."""


class TokenBudgetExceeded(TokenBudgetError):
    """The requested reservation exceeds an explicit token or call limit."""


class TokenLedgerError(TokenBudgetError):
    """The journal cannot safely be opened, verified, or made durable."""


class TokenLedgerLocked(TokenLedgerError):
    """Another owner holds the journal lock."""


class TokenLedgerHalted(TokenBudgetError):
    """Further admissions or settlements would risk an unknown outcome."""


class TokenSettlementError(TokenBudgetError):
    """Duplicate, unknown, or out-of-order settlement; accounting is unchanged."""


def _integer(value: Any, name: str, *, positive: bool = False) -> None:
    if type(value) is not int or value < (1 if positive else 0):
        raise ValueError(f"{name} must be a {'positive' if positive else 'nonnegative'} integer")


@dataclass(frozen=True)
class TokenLimits:
    """All six limits are explicit, positive integers; no token defaults."""

    input_per_turn: int
    output_per_turn: int
    context_window: int
    total_input: int
    total_output: int
    max_calls: int

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        for name, value in asdict(self).items():
            _integer(value, name, positive=True)


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            _integer(value, name)
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise ValueError("total_tokens must equal input_tokens + output_tokens")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> TokenUsage:
        if set(value) != {"input_tokens", "output_tokens", "total_tokens"}:
            raise ValueError("usage must contain exactly the three token counts")
        return cls(value["input_tokens"], value["output_tokens"], value["total_tokens"])


@dataclass(frozen=True)
class TokenReservation:
    call_id: str
    request_sha256: str
    input_tokens: int
    max_output_tokens: int


def _json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate journal key")
        result[key] = value
    return result


def _no_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _usage(value: Any) -> TokenUsage:
    if type(value) is TokenUsage:
        # Revalidate even dataclasses supplied by a caller.
        return TokenUsage(**asdict(value))
    if isinstance(value, Mapping):
        return TokenUsage.from_mapping(value)
    raise ValueError("usage is not a token-count mapping")


class TokenBudgetLedger:
    """Single-owner, append-only ledger. No provider/model is called here.

    ``reserve`` returns only after the admission is durable. ``settle`` returns
    a detached record, including terminal failures; it does not raise merely
    because the provider's valid usage disagrees with the reservation.
    """

    def __init__(self, path: str | Path, limits: TokenLimits) -> None:
        if type(limits) is not TokenLimits:
            raise ValueError("limits must be an explicit TokenLimits")
        self._limits = TokenLimits(**asdict(limits))
        self._path = Path(path).absolute()
        self._fd = -1
        self._owner_pid = os.getpid()
        self._mutex = threading.Lock()
        self._records: dict[str, dict[str, Any]] = {}
        self._pending: str | None = None
        self._halt_reason: str | None = None
        self._seq = 0
        self._last_hash = _ZERO_HASH
        self._file_digest = hashlib.sha256(b"").hexdigest()
        self._file_size = 0
        flags = os.O_RDWR | os.O_APPEND | os.O_CLOEXEC | os.O_NOFOLLOW
        try:
            try:
                self._fd = os.open(self._path, flags | os.O_CREAT | os.O_EXCL, 0o600)
                created = True
            except FileExistsError:
                self._fd = os.open(self._path, flags)
                created = False
            if not stat.S_ISREG(os.fstat(self._fd).st_mode):
                raise TokenLedgerError("journal must be a regular file")
            try:
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise TokenLedgerLocked("journal already has an owner") from error
            if created:
                self._append({"event": "limits", "limits": asdict(self._limits)})
                directory_fd = os.open(self._path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            else:
                self._replay()
                if self._pending is not None:
                    self._halt_reason = "unsettled_reservation_after_reopen"
                    self._records[self._pending]["status"] = "unknown"
                    self._records[self._pending]["failure_reason"] = self._halt_reason
            self._verify_unchanged()
        except Exception as error:
            self.close()
            if isinstance(error, TokenBudgetError):
                raise
            raise TokenLedgerError("cannot initialize token journal") from error

    @property
    def limits(self) -> TokenLimits:
        return self._limits

    def __enter__(self) -> TokenBudgetLedger:
        self._ensure_open()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def close(self) -> None:
        """Release ownership; never refund or synthesize a completion."""
        with self._mutex:
            if self._fd >= 0:
                # Closing releases this fd's lock. No explicit LOCK_UN: a child
                # after fork must not release the parent's shared open-file lock.
                os.close(self._fd)
                self._fd = -1

    def _ensure_open(self) -> None:
        if self._fd < 0:
            raise TokenLedgerError("journal is closed")
        if os.getpid() != self._owner_pid:
            raise TokenLedgerError("journal ownership cannot cross a fork")

    def _ensure_active(self) -> None:
        if self._halt_reason is not None:
            raise TokenLedgerHalted(self._halt_reason)

    def _contents(self) -> bytes:
        if os.fstat(self._fd).st_size > (1 + 2 * self._limits.max_calls) * _MAX_LINE_BYTES:
            raise ValueError("journal exceeds the maximum event count and record size")
        os.lseek(self._fd, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        while chunk := os.read(self._fd, 65_536):
            chunks.append(chunk)
        return b"".join(chunks)

    def _verify_unchanged(self) -> None:
        self._ensure_open()
        try:
            opened = os.fstat(self._fd)
            linked = os.stat(self._path, follow_symlinks=False)
            if (opened.st_dev, opened.st_ino) != (linked.st_dev, linked.st_ino):
                raise ValueError("journal path was replaced")
            if opened.st_size != self._file_size:
                raise ValueError("journal size changed outside its owner")
            if hashlib.sha256(self._contents()).hexdigest() != self._file_digest:
                raise ValueError("journal bytes changed outside its owner")
        except (OSError, ValueError) as error:
            self._halt_reason = self._halt_reason or "journal_changed"
            raise TokenLedgerError("journal changed while owned") from error

    def _append(self, payload: dict[str, Any]) -> None:
        body = {"schema": _SCHEMA, "seq": self._seq,
                "prev_sha256": self._last_hash, **payload}
        digest = hashlib.sha256(_json(body)).hexdigest()
        line = _json({**body, "sha256": digest}) + b"\n"
        if len(line) > _MAX_LINE_BYTES:
            self._halt_reason = "journal_write_failed"
            raise TokenLedgerError("journal record exceeds structural bound")
        try:
            offset = 0
            while offset < len(line):
                written = os.write(self._fd, line[offset:])
                if written <= 0:
                    raise OSError("journal write made no progress")
                offset += written
            os.fsync(self._fd)
            contents = self._contents()
            if (len(contents) != self._file_size + len(line) or not contents.endswith(line)
                    or hashlib.sha256(contents[:-len(line)]).hexdigest() != self._file_digest):
                raise ValueError("journal changed during append")
        except (OSError, ValueError) as error:
            self._halt_reason = "journal_write_failed"
            raise TokenLedgerError("journal append was not confirmed durable; halt") from error
        self._seq += 1
        self._last_hash = digest
        self._file_size += len(line)
        self._file_digest = hashlib.sha256(contents).hexdigest()

    def _totals(self) -> tuple[int, int]:
        return (sum(r["charged_input_tokens"] for r in self._records.values()),
                sum(r["charged_output_tokens"] for r in self._records.values()))

    def _validate_reservation(self, call_id: str, request_sha256: str,
                              input_tokens: int, max_output_tokens: int) -> None:
        if type(call_id) is not str or _CALL_ID.fullmatch(call_id) is None:
            raise ValueError("call_id must be a nonempty opaque ID of at most 128 characters")
        if type(request_sha256) is not str or _HASH.fullmatch(request_sha256) is None:
            raise ValueError("request_sha256 must be 64 lowercase hex characters")
        _integer(input_tokens, "input_tokens")
        _integer(max_output_tokens, "max_output_tokens", positive=True)
        if call_id in self._records:
            raise TokenSettlementError("call_id was already admitted; retries are forbidden")
        if self._pending is not None:
            raise TokenLedgerHalted("a reservation is still pending")
        consumed_input, consumed_output = self._totals()
        checks = {
            "input_per_turn": input_tokens <= self._limits.input_per_turn,
            "output_per_turn": max_output_tokens <= self._limits.output_per_turn,
            "context_window": input_tokens + max_output_tokens <= self._limits.context_window,
            "total_input": consumed_input + input_tokens <= self._limits.total_input,
            "total_output": consumed_output + max_output_tokens <= self._limits.total_output,
            "max_calls": len(self._records) < self._limits.max_calls,
        }
        for name, allowed in checks.items():
            if not allowed:
                raise TokenBudgetExceeded(name)

    def _admit(self, call_id: str, request_sha256: str,
               input_tokens: int, max_output_tokens: int) -> None:
        self._records[call_id] = {
            "call_id": call_id, "request_sha256": request_sha256, "itt_included": True,
            "reservation": {"input_tokens": input_tokens, "max_output_tokens": max_output_tokens},
            "status": "pending", "outcome": None, "provider_usage": None,
            "charged_input_tokens": input_tokens, "charged_output_tokens": max_output_tokens,
            "failure_reason": None,
        }
        self._pending = call_id

    def reserve(self, call_id: str, *, request_sha256: str,
                input_tokens: int, max_output_tokens: int) -> TokenReservation:
        """Reserve exact input plus the requested output cap before dispatch.

        A write failure raises and forbids dispatch. Its possibly written
        admission remains conservatively charged in this halted owner.
        """
        with self._mutex:
            self._verify_unchanged()
            self._ensure_active()
            self._validate_reservation(call_id, request_sha256, input_tokens, max_output_tokens)
            self._admit(call_id, request_sha256, input_tokens, max_output_tokens)
            self._append({"event": "admitted", "call_id": call_id,
                          "request_sha256": request_sha256, "input_tokens": input_tokens,
                          "max_output_tokens": max_output_tokens, "itt_included": True})
            return TokenReservation(call_id, request_sha256, input_tokens, max_output_tokens)

    def _completion(self, call_id: str, outcome: str, usage: TokenUsage | None,
                    usage_error: str | None) -> dict[str, Any]:
        record = dict(self._records[call_id])
        record["outcome"] = outcome
        reserved = record["reservation"]
        if usage is None:
            record.update(status="unknown", failure_reason=usage_error, provider_usage=None)
        elif usage.input_tokens != reserved["input_tokens"] or usage.output_tokens > reserved["max_output_tokens"]:
            record.update(status="usage_mismatch", failure_reason="usage_reservation_mismatch",
                          provider_usage=asdict(usage),
                          charged_input_tokens=max(reserved["input_tokens"], usage.input_tokens),
                          charged_output_tokens=max(reserved["max_output_tokens"], usage.output_tokens))
        else:
            record.update(status="completed" if outcome == "success" else "failed",
                          failure_reason=None if outcome == "success" else "adapter_error",
                          provider_usage=asdict(usage), charged_input_tokens=usage.input_tokens,
                          charged_output_tokens=usage.output_tokens)
        return record

    def settle(self, call_id: str, *, usage: TokenUsage | Mapping[str, Any] | None,
               outcome: str = "success") -> dict[str, Any]:
        """Append a completion, preserving terminal/unknown calls in ITT.

        Timeout/unknown ignores any supplied usage, since that outcome is not
        verified. Malformed/missing usage is durably unknown, not zero. A known
        failed response counts actual usage but still halts future admissions.
        """
        with self._mutex:
            self._verify_unchanged()
            if type(call_id) is not str or call_id != self._pending:
                raise TokenSettlementError("no matching pending admission")
            self._ensure_active()
            if type(outcome) is not str or outcome not in _OUTCOMES:
                raise ValueError("unsupported settlement outcome")
            validated: TokenUsage | None = None
            if outcome in {"timeout", "unknown"}:
                usage_error = "timeout" if outcome == "timeout" else "unknown_outcome"
            elif usage is None:
                usage_error = "missing_usage"
            else:
                try:
                    validated = _usage(usage)
                    usage_error = None
                except (ValueError, TypeError, KeyError):
                    usage_error = "invalid_usage"
            record = self._completion(call_id, outcome, validated, usage_error)
            try:
                self._append({"event": "completed", "call_id": call_id, "outcome": outcome,
                              "usage": asdict(validated) if validated is not None else None,
                              "usage_error": usage_error})
            except TokenLedgerError:
                # A failed completion write cannot release a reservation, even
                # if the caller has supplied otherwise valid actual usage.
                previous = self._records[call_id]
                for key in ("charged_input_tokens", "charged_output_tokens"):
                    previous[key] = max(previous[key], record[key])
                raise
            self._records[call_id] = record
            self._pending = None
            if record["failure_reason"] is not None:
                self._halt_reason = record["failure_reason"]
            return json.loads(_json(record))

    def snapshot(self) -> dict[str, Any]:
        """Recheck integrity; still report conservative memory totals on failure.

        ``journal_integrity_verified=False`` is terminal, never certified disk
        evidence. Unknown provider usage is never inferred from budget charge.
        """
        with self._mutex:
            self._ensure_open()
            try:
                self._verify_unchanged()
                journal_verified = self._halt_reason != "journal_write_failed"
            except TokenLedgerError:
                journal_verified = False
            total_input, total_output = self._totals()
            unknown = sum(r["provider_usage"] is None for r in self._records.values())
            known = [r["provider_usage"] for r in self._records.values() if r["provider_usage"] is not None]
            aggregate = None if unknown else {
                key: sum(u[key] for u in known)
                for key in ("input_tokens", "output_tokens", "total_tokens")
            }
            return json.loads(_json({
                "limits": asdict(self._limits), "admitted_calls": len(self._records),
                "charged_input_tokens": total_input, "charged_output_tokens": total_output,
                "charged_total_tokens": total_input + total_output,
                "provider_usage": aggregate, "unknown_usage_calls": unknown,
                "halted": self._halt_reason is not None, "halt_reason": self._halt_reason,
                "journal_integrity_verified": journal_verified,
                "pending_call_id": self._pending, "records": list(self._records.values()),
            }))

    def _replay(self) -> None:
        data = self._contents()
        if not data or not data.endswith(b"\n"):
            raise TokenLedgerError("empty or truncated token journal")
        try:
            for line in data.splitlines(keepends=True):
                if len(line) > _MAX_LINE_BYTES or not line.endswith(b"\n"):
                    raise ValueError("oversized or truncated journal record")
                event = json.loads(line, object_pairs_hook=_no_duplicate_keys,
                                   parse_constant=_no_constant)
                if type(event) is not dict or _json(event) + b"\n" != line:
                    raise ValueError("noncanonical journal record")
                expected_keys = {"schema", "seq", "prev_sha256", "sha256", "event"}
                event_kind = event.get("event")
                fields = {
                    "limits": {"limits"},
                    "admitted": {"call_id", "request_sha256", "input_tokens", "max_output_tokens", "itt_included"},
                    "completed": {"call_id", "outcome", "usage", "usage_error"},
                }
                if type(event_kind) is not str or event_kind not in fields:
                    raise ValueError("unknown journal event")
                if set(event) != expected_keys | fields[event_kind]:
                    raise ValueError("unexpected journal fields")
                digest = event.pop("sha256")
                if (event["schema"] != _SCHEMA or type(event["seq"]) is not int
                        or event["seq"] != self._seq or event["prev_sha256"] != self._last_hash
                        or type(digest) is not str or _HASH.fullmatch(digest) is None
                        or hashlib.sha256(_json(event)).hexdigest() != digest):
                    raise ValueError("invalid journal hash chain")
                if self._seq == 0:
                    if event_kind != "limits" or event["limits"] != asdict(self._limits):
                        raise ValueError("journal limits do not match")
                    if type(event["limits"]) is not dict or TokenLimits(**event["limits"]) != self._limits:
                        raise ValueError("invalid journal limits")
                elif event_kind == "limits":
                    raise ValueError("duplicate limits event")
                else:
                    self._ensure_active()
                    if event_kind == "admitted":
                        if event["itt_included"] is not True:
                            raise ValueError("admitted call must remain in ITT")
                        self._validate_reservation(event["call_id"], event["request_sha256"],
                                                   event["input_tokens"], event["max_output_tokens"])
                        self._admit(event["call_id"], event["request_sha256"],
                                    event["input_tokens"], event["max_output_tokens"])
                    else:
                        self._replay_completion(event)
                self._seq += 1
                self._last_hash = digest
        except (ValueError, TypeError, KeyError, TokenBudgetError) as error:
            raise TokenLedgerError("invalid token journal; no records were skipped") from error
        self._file_size = len(data)
        self._file_digest = hashlib.sha256(data).hexdigest()

    def _replay_completion(self, event: dict[str, Any]) -> None:
        call_id, outcome = event["call_id"], event["outcome"]
        if type(call_id) is not str or call_id != self._pending:
            raise ValueError("settlement has no matching pending admission")
        if type(outcome) is not str or outcome not in _OUTCOMES:
            raise ValueError("unsupported settlement outcome")
        usage = None if event["usage"] is None else _usage(event["usage"])
        usage_error = event["usage_error"]
        if outcome in {"timeout", "unknown"}:
            expected = "timeout" if outcome == "timeout" else "unknown_outcome"
            if usage is not None or usage_error != expected:
                raise ValueError("unknown outcome cannot claim verified usage")
        elif usage is None:
            if type(usage_error) is not str or usage_error not in {"missing_usage", "invalid_usage"}:
                raise ValueError("missing or invalid usage was not marked")
        elif usage_error is not None:
            raise ValueError("known usage cannot have a usage error")
        record = self._completion(call_id, outcome, usage, usage_error)
        self._records[call_id] = record
        self._pending = None
        if record["failure_reason"] is not None:
            self._halt_reason = record["failure_reason"]
