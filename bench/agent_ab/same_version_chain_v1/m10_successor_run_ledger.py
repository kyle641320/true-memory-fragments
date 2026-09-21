"""Durable, offline-only batch admission for the scientific action protocol.

The complete ordered schedule is a single hash-chained admission frame. A new
journal is fsynced before it is atomically published, then its parent directory
is fsynced before construction returns. No adapter work belongs in this module.
Once that boundary returns, *all* scheduled IDs are in the ITT denominator,
including runs never started and runs interrupted before a completion record.

Reopening is inspection-only, never permission to retry or resume a run. POSIX
flock, strict replay and readback detect accidental corruption or replacement;
the hash chain is not authentication against an owner rewriting the whole file.
The parent directory must already exist. Fixed bounds are structural safety
limits, not permission to enlarge the separately sealed experiment schedule.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
import tempfile
import threading
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .m10_successor_protocol import RunRecord


EVIDENCE_KIND = "offline_broker_protocol_rehearsal"
_SCHEMA = "m10_successor_run_admission.v1"
_ZERO_HASH = "0" * 64
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_RUN_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
_MAX_RUNS = 6_000
_MAX_LINE_BYTES = 4 * 1024 * 1024
_MAX_JOURNAL_BYTES = 128 * 1024 * 1024
_MAX_JSON_NODES = 200_000
_MAX_JSON_DEPTH = 64
_MAX_INTEGER_BITS = 64


def ledger_policy() -> dict[str, Any]:
    """Public seal material for this journal's fixed structural policy."""
    return {
        "schema": _SCHEMA, "evidence_kind": EVIDENCE_KIND,
        "max_runs": _MAX_RUNS, "max_event_bytes": _MAX_LINE_BYTES,
        "max_journal_bytes": _MAX_JOURNAL_BYTES, "max_json_nodes": _MAX_JSON_NODES,
        "max_json_depth": _MAX_JSON_DEPTH,
        "max_integer_bits": _MAX_INTEGER_BITS,
        "admission_boundary": "complete_ordered_schedule_atomically_published_and_fsynced",
        "reopen_policy": "inspection_only_no_resume_or_retry",
    }


class RunLedgerError(RuntimeError):
    """The run journal cannot safely be validated or made durable."""


class RunLedgerLocked(RunLedgerError):
    """Another owner holds the journal lock."""


class RunLedgerHalted(RunLedgerError):
    """This owner cannot execute or write further run transitions."""


class RunLedgerTransitionError(RunLedgerError):
    """A duplicate, reordered or inconsistent run transition was rejected."""


def _json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate journal key")
        result[key] = value
    return result


def _no_constant(value: str) -> None:
    raise ValueError("nonfinite journal number")


def _bounded_integer(value: str) -> int:
    # Reject enormous decimal tokens before Python 3.10's unbounded int parse.
    if len(value) > 21:
        raise ValueError("journal integer exceeds structural bound")
    result = int(value)
    if result.bit_length() > _MAX_INTEGER_BITS:
        raise ValueError("journal integer exceeds structural bound")
    return result


def _bounded_copy(value: Any) -> dict[str, Any]:
    """Bound even caller-created objects before canonical serialization."""
    if not isinstance(value, Mapping):
        raise RunLedgerTransitionError("completion must be a record mapping")
    value = dict(value)
    stack = [(value, 0)]
    nodes, text_size = 0, 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if depth > _MAX_JSON_DEPTH or nodes > _MAX_JSON_NODES:
            raise RunLedgerTransitionError("record exceeds JSON structural bounds")
        if type(item) is dict:
            if len(item) > _MAX_JSON_NODES - nodes - len(stack):
                raise RunLedgerTransitionError("record has too many fields")
            for key, child in item.items():
                if type(key) is not str:
                    raise RunLedgerTransitionError("record keys must be text")
                text_size += len(key)
                stack.append((child, depth + 1))
        elif type(item) in (list, tuple):
            if len(item) > _MAX_JSON_NODES - nodes - len(stack):
                raise RunLedgerTransitionError("record has too many items")
            stack.extend((child, depth + 1) for child in item)
        elif type(item) is str:
            text_size += len(item)
        elif type(item) is int and item.bit_length() > _MAX_INTEGER_BITS:
            raise RunLedgerTransitionError("record integer exceeds structural bound")
        elif item is not None and type(item) not in (bool, int, float):
            raise RunLedgerTransitionError("record contains a non-JSON value")
        if text_size > _MAX_LINE_BYTES:
            raise RunLedgerTransitionError("record exceeds text bound")
    try:
        data = _json(value)
        if len(data) > _MAX_LINE_BYTES - 1024:
            raise ValueError("record exceeds frame bound")
        return json.loads(data)
    except (TypeError, ValueError, RecursionError) as error:
        raise RunLedgerTransitionError("record is not bounded canonical JSON") from error


class RunAdmissionLedger:
    """Single-owner fixed-denominator journal with no restart capability."""

    def __init__(self, path: str | Path, joint_seal_sha256: str,
                 run_ids: Sequence[str]) -> None:
        if type(joint_seal_sha256) is not str or _HASH.fullmatch(joint_seal_sha256) is None:
            raise ValueError("joint seal must be 64 lowercase hex characters")
        if (not isinstance(run_ids, Sequence) or isinstance(run_ids, (str, bytes))
                or not 1 <= len(run_ids) <= _MAX_RUNS):
            raise ValueError("schedule must contain 1..6000 ordered run IDs")
        identifiers = tuple(run_ids)
        if any(type(value) is not str or _RUN_ID.fullmatch(value) is None for value in identifiers):
            raise ValueError("run IDs must be opaque text of at most 128 characters")
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("scheduled run IDs must be unique")
        self._path = Path(path).absolute()
        self._seal = joint_seal_sha256
        self._run_ids = identifiers
        self._owner_pid = os.getpid()
        self._mutex = threading.Lock()
        self._fd = -1
        self._seq = 0
        self._last_hash = _ZERO_HASH
        self._file_size = 0
        self._file_digest = hashlib.sha256(b"").hexdigest()
        self._completed: dict[str, dict[str, Any]] = {}
        self._started_count = 0
        self._pending: str | None = None
        self._inspection_only = False
        self._halt_reason: str | None = None
        temporary: str | None = None
        flags = os.O_RDWR | os.O_APPEND | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
        try:
            try:
                self._fd = os.open(self._path, flags)
                self._inspection_only = True
            except FileNotFoundError:
                self._fd, temporary = tempfile.mkstemp(
                    prefix=f".{self._path.name}.", suffix=".pending", dir=self._path.parent,
                )
                # mkstemp is exclusive, mode 0600, and non-inheritable. Explicit
                # append mode keeps the same write semantics as a reopened fd.
                fcntl.fcntl(self._fd, fcntl.F_SETFL, os.O_APPEND)
            if not stat.S_ISREG(os.fstat(self._fd).st_mode):
                raise RunLedgerError("journal must be a regular file")
            try:
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RunLedgerLocked("journal already has an owner") from error
            if self._inspection_only:
                self._replay()
            else:
                self._append({
                    "event": "batch_admitted", "joint_seal_sha256": self._seal,
                    "run_ids": list(self._run_ids), "evidence_kind": EVIDENCE_KIND,
                    "admitted": True, "itt_included": True,
                })
                # link is atomic and refuses to replace an existing path; the
                # complete admission set, never an initialization prefix, is
                # published. A concurrent creator cannot overwrite a batch.
                os.link(temporary, self._path, follow_symlinks=False)
                os.unlink(temporary)
                temporary = None
                directory_fd = os.open(self._path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            self._verify_unchanged()
        except BaseException as error:
            self.close()
            if not isinstance(error, Exception):
                raise
            if isinstance(error, RunLedgerError):
                raise
            raise RunLedgerError("cannot initialize run admission journal") from error
        finally:
            if temporary is not None:
                os.unlink(temporary)

    def __enter__(self) -> RunAdmissionLedger:
        self._ensure_open()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def close(self) -> None:
        """Release ownership without fabricating completion or unlocking a fork."""
        with self._mutex:
            if self._fd >= 0:
                os.close(self._fd)
                self._fd = -1

    def _ensure_open(self) -> None:
        if self._fd < 0:
            raise RunLedgerError("journal is closed")
        if os.getpid() != self._owner_pid:
            raise RunLedgerError("journal ownership cannot cross a fork")

    def _ensure_writable(self) -> None:
        if self._inspection_only:
            raise RunLedgerHalted("reopened journal is inspection-only; no resume or retry")
        if self._halt_reason is not None:
            raise RunLedgerHalted(self._halt_reason)

    def _contents(self) -> bytes:
        if os.fstat(self._fd).st_size > _MAX_JOURNAL_BYTES:
            raise ValueError("journal exceeds total byte bound")
        os.lseek(self._fd, 0, os.SEEK_SET)
        data = bytearray()
        while chunk := os.read(self._fd, min(65_536, _MAX_JOURNAL_BYTES + 1 - len(data))):
            data.extend(chunk)
            if len(data) > _MAX_JOURNAL_BYTES:
                raise ValueError("journal exceeds total byte bound")
        return bytes(data)

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
            raise RunLedgerError("run journal changed while owned") from error

    def _append(self, payload: dict[str, Any]) -> None:
        body = {"schema": _SCHEMA, "seq": self._seq,
                "prev_sha256": self._last_hash, **payload}
        digest = hashlib.sha256(_json(body)).hexdigest()
        line = _json({**body, "sha256": digest}) + b"\n"
        if (len(line) > _MAX_LINE_BYTES or self._file_size + len(line) > _MAX_JOURNAL_BYTES
                or self._seq >= 1 + 2 * len(self._run_ids)):
            self._halt_reason = "journal_write_failed"
            raise RunLedgerError("journal exceeds fixed frame, total or event bound")
        try:
            offset = 0
            while offset < len(line):
                written = os.write(self._fd, line[offset:])
                if written <= 0:
                    raise OSError("journal write made no progress")
                offset += written
            os.fsync(self._fd)
            data = self._contents()
            if (len(data) != self._file_size + len(line) or not data.endswith(line)
                    or hashlib.sha256(data[:-len(line)]).hexdigest() != self._file_digest):
                raise ValueError("journal changed during append")
        except (OSError, ValueError) as error:
            self._halt_reason = "journal_write_failed"
            raise RunLedgerError("run journal append not confirmed durable; halt") from error
        self._seq += 1
        self._last_hash = digest
        self._file_size += len(line)
        self._file_digest = hashlib.sha256(data).hexdigest()

    def _validate_start(self, run_id: str) -> None:
        if (type(run_id) is not str or self._pending is not None
                or self._started_count >= len(self._run_ids)
                or run_id != self._run_ids[self._started_count]):
            raise RunLedgerTransitionError("run start must be unique and in the admitted order")

    def start(self, run_id: str) -> None:
        """Fsync the next scheduled start before any adapter is constructed."""
        with self._mutex:
            self._verify_unchanged()
            self._ensure_writable()
            self._validate_start(run_id)
            self._append({"event": "started", "run_id": run_id})
            self._pending = run_id
            self._started_count += 1

    def _validate_record(self, record: dict[str, Any]) -> None:
        run_id = record.get("run_id")
        if type(run_id) is not str or run_id != self._pending:
            raise RunLedgerTransitionError("completion must match the unique pending run")
        if record.get("seal_sha256") != self._seal or record.get("evidence_kind") != EVIDENCE_KIND:
            raise RunLedgerTransitionError("completion identity or evidence kind differs from admission")
        for key in ("admitted", "itt_included", "durable_ledger"):
            if record.get(key) is not True:
                raise RunLedgerTransitionError("admitted run must remain durably included in ITT")
        for key in ("model_execution_enabled", "model_pilot_admitted", "provider_token_limits_verified"):
            if record.get(key) is not False:
                raise RunLedgerTransitionError("offline evidence cannot certify live model execution")
        if type(record.get("protocol_ok")) is not bool or type(record.get("final_received")) is not bool:
            raise RunLedgerTransitionError("completion status must use strict booleans")
        if record["protocol_ok"]:
            if (record.get("protocol_status") != "completed" or record.get("failure_reason") is not None
                    or record["final_received"] is not True):
                raise RunLedgerTransitionError("successful completion has inconsistent protocol status")
        elif (record.get("protocol_status") != "failed"
              or type(record.get("failure_reason")) is not str or not record["failure_reason"]
              or len(record["failure_reason"]) > 1024):
            raise RunLedgerTransitionError("failed completion requires a bounded failure reason")
        for key, status in (("semantic", "semantic_pass"), ("compilation", "ok")):
            evaluation = record.get(key)
            if type(evaluation) is not dict or not any(evaluation.get(status) is value for value in (True, False, None)):
                raise RunLedgerTransitionError("independent evaluation status is invalid")

    def complete(self, record_dict: Mapping[str, Any]) -> None:
        """Append one terminal record; neither failure nor unknown is filtered."""
        with self._mutex:
            self._verify_unchanged()
            self._ensure_writable()
            record = _bounded_copy(record_dict)
            self._validate_record(record)
            run_id = record["run_id"]
            self._append({"event": "completed", "run_id": run_id, "record": record})
            self._completed[run_id] = record
            self._pending = None

    def _rows(self, integrity_verified: bool) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for run_id in self._run_ids:
            if run_id in self._completed:
                row = json.loads(_json(self._completed[run_id]))
                state = "completed"
            else:
                state = "started" if run_id == self._pending else "not_started"
                row = asdict(RunRecord(
                    run_id=run_id, seal_sha256=self._seal, evidence_kind=EVIDENCE_KIND,
                    durable_ledger=True, protocol_status="failed",
                    failure_reason=("missing_completion_record" if state == "started"
                                    else "not_started_after_batch_admission"),
                ))
            row["run_ledger_state"] = state
            row["run_ledger_integrity_verified"] = integrity_verified
            if not integrity_verified:
                row["run_ledger_prior_protocol"] = {
                    key: row.get(key) for key in ("protocol_status", "protocol_ok", "failure_reason")
                }
                row.update(protocol_status="failed", protocol_ok=False,
                           failure_reason="run_journal_integrity_unverified")
            rows.append(row)
        return rows

    def snapshot(self) -> dict[str, Any]:
        """Recheck disk integrity; uncertainty never drops the planned IDs."""
        with self._mutex:
            self._ensure_open()
            try:
                self._verify_unchanged()
                verified = self._halt_reason is None
            except RunLedgerError:
                verified = False
            return {
                "evidence_kind": EVIDENCE_KIND, "joint_seal_sha256": self._seal,
                "run_ids": list(self._run_ids), "admitted_runs": len(self._run_ids),
                "denominator": len(self._run_ids), "started_runs": self._started_count,
                "completed_runs": len(self._completed), "pending_run_id": self._pending,
                "not_started_run_ids": list(self._run_ids[self._started_count:]),
                "inspection_only": self._inspection_only,
                "halted": self._inspection_only or self._halt_reason is not None,
                "halt_reason": self._halt_reason or ("inspection_only" if self._inspection_only else None),
                "journal_integrity_verified": verified, "records": self._rows(verified),
            }

    def records(self) -> list[dict[str, Any]]:
        return self.snapshot()["records"]

    def _replay(self) -> None:
        data = self._contents()
        if not data or not data.endswith(b"\n"):
            raise RunLedgerError("empty or truncated run admission journal")
        try:
            lines = data.splitlines(keepends=True)
            if len(lines) > 1 + 2 * len(self._run_ids):
                raise ValueError("too many journal events")
            for line in lines:
                if len(line) > _MAX_LINE_BYTES or not line.endswith(b"\n"):
                    raise ValueError("oversized or truncated journal record")
                event = json.loads(line, object_pairs_hook=_no_duplicates,
                                   parse_constant=_no_constant, parse_int=_bounded_integer)
                if type(event) is not dict or _json(event) + b"\n" != line:
                    raise ValueError("noncanonical journal record")
                fields = {
                    "batch_admitted": {"joint_seal_sha256", "run_ids", "evidence_kind", "admitted", "itt_included"},
                    "started": {"run_id"}, "completed": {"run_id", "record"},
                }
                kind = event.get("event")
                if type(kind) is not str or kind not in fields:
                    raise ValueError("unknown journal event")
                if set(event) != {"schema", "seq", "prev_sha256", "sha256", "event"} | fields[kind]:
                    raise ValueError("unexpected journal fields")
                digest = event.pop("sha256")
                if (event["schema"] != _SCHEMA or type(event["seq"]) is not int
                        or event["seq"] != self._seq or event["prev_sha256"] != self._last_hash
                        or type(digest) is not str or _HASH.fullmatch(digest) is None
                        or hashlib.sha256(_json(event)).hexdigest() != digest):
                    raise ValueError("invalid journal hash chain")
                if self._seq == 0:
                    if (kind != "batch_admitted" or event["joint_seal_sha256"] != self._seal
                            or event["run_ids"] != list(self._run_ids)
                            or event["evidence_kind"] != EVIDENCE_KIND
                            or event["admitted"] is not True or event["itt_included"] is not True):
                        raise ValueError("batch admission does not match the sealed schedule")
                elif kind == "started":
                    self._validate_start(event["run_id"])
                    self._pending = event["run_id"]
                    self._started_count += 1
                elif kind == "completed":
                    record = _bounded_copy(event["record"])
                    self._validate_record(record)
                    if event["run_id"] != record["run_id"]:
                        raise ValueError("completion event and record identity differ")
                    self._completed[record["run_id"]] = record
                    self._pending = None
                else:
                    raise ValueError("duplicate batch admission")
                self._seq += 1
                self._last_hash = digest
        except (ValueError, TypeError, KeyError, RecursionError, RunLedgerError) as error:
            raise RunLedgerError("invalid run journal; no scheduled IDs or events were skipped") from error
        self._file_size = len(data)
        self._file_digest = hashlib.sha256(data).hexdigest()
