"""Actual child-process broker execution with a fixed, fictional backend.

The client codec/ledger run here; each worker reopens an independent broker
ledger and invokes BrokerCore. There is no provider, credential, network,
arbitrary executable or backend loader. Call admissions are NOT scientific
run admission or an experiment's intent-to-treat denominator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from .m10_successor_adapter_contract import (
    PROTOCOL, BrokerContract, ContractError, _strict_json, accept_completion,
    admit_turn, canonical, check_capabilities, digest, prepare_turn, seal_contract,
)
from .m10_successor_broker_fixture import ROOT, SCENARIOS, fixed_contract, inventory
from .m10_successor_process_io import ProcessCaps, ProcessTransportError, _exchange
from .m10_successor_protocol import ACTION_SCHEMAS, AdapterRequest, LiveExecutionDisabled
from .m10_successor_token_budget import TokenBudgetError, TokenBudgetLedger


EVIDENCE_KIND = "offline_broker_core_conformance"
MODEL_EXECUTION_ENABLED = False
_BROKER_ERRORS = frozenset({
    "request_error", "capability_error", "count_error", "response_error",
    "backend_error", "timeout", "ledger_error", "duplicate_call",
    "budget_exceeded", "internal_error",
})
_USAGE = {"input_tokens": 6000, "output_tokens": 32, "total_tokens": 6032}


class _BrokerReplyError(RuntimeError):
    def __init__(self, category: str):
        self.category = category
        super().__init__(category)


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _runtime() -> dict:
    return {"executable_sha256": _hash(Path(sys.executable).resolve().read_bytes()),
            "implementation": platform.python_implementation(), "version": platform.python_version()}


def _require_fixture(contract: BrokerContract) -> None:
    if type(contract) is not BrokerContract or contract != fixed_contract():
        raise LiveExecutionDisabled("only the fixed fictional broker backend is available")


def broker_core_seal(contract: BrokerContract, caps: ProcessCaps) -> dict:
    _require_fixture(contract)
    if type(caps) is not ProcessCaps:
        raise ValueError("explicit process caps required")
    caps = ProcessCaps(**asdict(caps))
    material = {
        "name": "broker-core-seal", "contract_seal": seal_contract(contract),
        "process_caps": asdict(caps), "implementation_sha256": inventory(),
        "python_runtime": _runtime(), "evidence_kind": EVIDENCE_KIND,
        "model_execution_enabled": False, "model_pilot_admitted": False,
        "provider_token_limits_verified": False,
    }
    return {**material, "seal_sha256": digest(canonical(material))}


def _worker_source(contract: BrokerContract, *, materials: dict[str, str],
                   broker_ledger_path: Path, trace_path: Path, scenario: str,
                   deadline_monotonic: float, max_request_frame_bytes: int) -> bytes:
    """Fixed launch program: trusted parent choices, never stdin-selected code.

    -I/-S/-B and the private cwd are supplied by _exchange. This is a trusted
    source rehearsal, NOT an OS filesystem/network sandbox or an attestation.
    All repository materials are checked before the first repository import.
    """
    source = (
        "import hashlib, pathlib, sys\n"
        f"root = pathlib.Path({str(ROOT)!r})\n"
        f"materials = {materials!r}\n"
        "for name, expected in materials.items():\n"
        "    if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:\n"
        "        sys.exit(73)\n"
        "sys.path.insert(0, str(root))\n"
        "from bench.agent_ab.same_version_chain_v1.m10_successor_broker_fixture import worker_main\n"
        f"worker_main({asdict(contract)!r}, {str(broker_ledger_path)!r}, {str(trace_path)!r}, "
        f"{scenario!r}, {deadline_monotonic!r}, {max_request_frame_bytes!r})\n"
    )
    return source.encode("utf-8")


def _broker_error(raw: bytes, limit: int) -> None:
    value = _strict_json(raw, limit)
    if "error" in value:
        if (set(value) != {"protocol", "error"} or value["protocol"] != PROTOCOL
                or type(value["error"]) is not str or value["error"] not in _BROKER_ERRORS):
            raise ContractError("invalid broker error receipt")
        raise _BrokerReplyError(value["error"])


def _read_broker(path: Path, contract: BrokerContract) -> dict | None:
    if not path.exists():
        return None
    try:
        with TokenBudgetLedger(path, contract.limits) as ledger:
            return ledger.snapshot()
    except TokenBudgetError:
        return None


def _trace(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_bytes().splitlines()] if path.exists() else []


def _reconciliation(client: dict | None, broker: dict | None) -> str:
    if (client is None or broker is None or not client["journal_integrity_verified"]
            or not broker["journal_integrity_verified"]):
        return "unverified_ledger_state"
    if client["admitted_calls"] == broker["admitted_calls"] == 0:
        return "no_candidate_call_admitted"
    if client["admitted_calls"] != broker["admitted_calls"]:
        return "different_admission_boundaries"
    if broker["provider_usage"] is not None and client["provider_usage"] is None:
        return "broker_known_client_unknown"
    same_charge = all(client[k] == broker[k] for k in
                      ("charged_input_tokens", "charged_output_tokens", "admitted_calls"))
    if same_charge and client["provider_usage"] == broker["provider_usage"]:
        return "matching_known_usage" if client["provider_usage"] is not None else "both_unknown_conservative"
    return "different_accounting_evidence"


def rehearse_turn(contract: BrokerContract, request: AdapterRequest, *,
                  ledger: TokenBudgetLedger, broker_ledger_path: Path, trace_path: Path,
                  caps: ProcessCaps, scenario: str = "ok", evidence_dir: Path | None = None) -> dict:
    """Three exchanges and, for success, a duplicate-ID probe in a fresh worker.

    One absolute deadline includes source/material checks and frame encoding.
    Errors before admission remain records. Errors after client reservation
    retain unknown/full charges; independent known broker usage is untouched.
    A killed worker is never called evidence of upstream cancellation.
    """
    started = time.monotonic()
    _require_fixture(contract)
    if type(scenario) is not str or scenario not in SCENARIOS:
        raise ValueError("unknown fixed fixture scenario")
    if type(caps) is not ProcessCaps:
        raise ValueError("explicit process caps required")
    caps = ProcessCaps(**asdict(caps))
    broker_ledger_path, trace_path = Path(broker_ledger_path).absolute(), Path(trace_path).absolute()
    if broker_ledger_path == trace_path:
        raise ValueError("journal and backend trace must be separate")
    prepared = prepare_turn(contract, request)
    deadline = started + prepared.timeout_seconds
    seal = broker_core_seal(contract, caps)
    call_id = uuid.uuid4().hex
    frames, attempts = [], []
    completion, replay = None, None
    phase, status, category = "capabilities", "ok", None
    if evidence_dir is not None:
        evidence_dir = Path(evidence_dir)
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "model-payload.json").write_bytes(prepared.payload_json.encode("utf-8"))

    def exchange(message: dict | str, exchange_phase: str) -> bytes:
        raw = (message if type(message) is str else canonical(message)).encode("utf-8")
        stem = f"{len(frames) + 1:02d}-{exchange_phase}"
        frame = {"phase": exchange_phase, "request_sha256": _hash(raw), "request_bytes": len(raw),
                 "receipt_sha256": None, "receipt_bytes": None, "status": "not_dispatched"}
        frames.append(frame)
        if evidence_dir is not None:
            frame["request_file"] = stem + ".request.bin"
            (evidence_dir / frame["request_file"]).write_bytes(raw)
        if broker_core_seal(contract, caps) != seal:
            raise ContractError("broker rehearsal material drift")
        # The provider payload and full prepared v2 frame have DIFFERENT caps.
        if len(raw) > caps.max_request_bytes:
            raise ProcessTransportError("request_too_large")
        source = _worker_source(
            contract, materials=seal["implementation_sha256"], broker_ledger_path=broker_ledger_path,
            trace_path=trace_path, scenario=scenario, deadline_monotonic=deadline,
            max_request_frame_bytes=caps.max_request_bytes,
        )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ProcessTransportError("timeout")
        attempt = {"phase": exchange_phase, "status": "attempted", "worker_source_sha256": _hash(source),
                   "request_sha256": frame["request_sha256"]}
        attempts.append(attempt)
        frame["status"] = "dispatched"
        bounded = ProcessCaps(caps.max_request_bytes,
                              min(caps.max_stdout_bytes, contract.max_response_bytes), caps.max_stderr_bytes)
        try:
            reply = _exchange(source, raw, caps=bounded, timeout_seconds=remaining,
                              deadline_monotonic=deadline)
            frame.update(receipt_sha256=_hash(reply.stdout), receipt_bytes=len(reply.stdout), status="received")
            if evidence_dir is not None:
                frame["receipt_file"] = stem + ".receipt.bin"
                (evidence_dir / frame["receipt_file"]).write_bytes(reply.stdout)
            if time.monotonic() >= deadline:
                raise ProcessTransportError("timeout")
        except ProcessTransportError as exc:
            attempt.update(status="failed", category=exc.category)
            raise
        attempt.update(status="completed", stdout_bytes=len(reply.stdout), stderr_bytes=reply.stderr_bytes,
                       elapsed_seconds=reply.elapsed_seconds, receipt_sha256=frame["receipt_sha256"])
        _broker_error(reply.stdout, contract.max_response_bytes)
        return reply.stdout

    try:
        initial = ledger.snapshot()
        if (initial["halted"] or initial["pending_call_id"] is not None
                or not initial["journal_integrity_verified"] or ledger.limits != contract.limits):
            raise TokenBudgetError("client ledger cannot admit another turn")
        capabilities = exchange({"protocol": PROTOCOL, "op": "capabilities",
                                 "contract_sha256": prepared.contract_sha256}, phase)
        check_capabilities(contract, capabilities)
        phase = "count"
        count = exchange({"protocol": PROTOCOL, "op": "count",
                          "contract_sha256": prepared.contract_sha256,
                          "payload_json": prepared.payload_json, "payload_sha256": prepared.payload_sha256}, phase)
        phase = "admission"
        admitted = admit_turn(contract, prepared, capabilities=capabilities, count_receipt=count,
                              ledger=ledger, call_id=call_id)
        phase = "completion"
        raw = exchange(admitted.completion_request_json, phase)
        completion = accept_completion(contract, admitted, raw, ledger=ledger)
        if not completion.usable_action_text:
            status = "protocol_failed"
            category = "unusable_response" if completion.finish_reason == "stop" else completion.finish_reason
        elif scenario == "ok":
            before, events_before = _read_broker(broker_ledger_path, contract), _trace(trace_path)
            replay = {"verified": False, "category": None, "backend_events_before": len(events_before)}
            phase = "replay"
            try:
                exchange(admitted.completion_request_json, phase)
            except _BrokerReplyError as error:
                replay["category"] = error.category
            after, events_after = _read_broker(broker_ledger_path, contract), _trace(trace_path)
            replay.update(backend_events_after=len(events_after), broker_ledger_unchanged=before == after,
                          backend_trace_unchanged=events_before == events_after)
            replay["verified"] = (replay["category"] == "duplicate_call" and before == after
                                  and events_before == events_after and before is not None)
            if not replay["verified"]:
                raise ContractError("completed replay was not rejected without backend work")
            phase = "completion"
    except Exception as exc:
        if isinstance(exc, (ProcessTransportError, _BrokerReplyError)):
            category = exc.category
        elif isinstance(exc, (ContractError, LiveExecutionDisabled)):
            category = "contract_error"
        elif isinstance(exc, TokenBudgetError):
            category = "ledger_error"
        else:
            category = "internal_error"
        status = "failed"
        # reserve/fsync can fail after creating a pending in-memory record.
        # Never assume no returned admission handle means no reservation.
        try:
            current = ledger.snapshot()
            if current["pending_call_id"] == call_id and not current["halted"]:
                ledger.settle(call_id, usage=None, outcome="timeout" if category == "timeout" else "unknown")
        except TokenBudgetError:
            category = "ledger_error"
    try:
        client = ledger.snapshot()
    except TokenBudgetError:
        client = None
    broker = _read_broker(broker_ledger_path, contract)
    broker_created = broker_ledger_path.exists()
    if (client is None or not client["journal_integrity_verified"]
            or broker_created and (broker is None or not broker["journal_integrity_verified"])):
        status, category, completion = "failed", "ledger_error", None
    trace = _trace(trace_path)
    admitted_client = None if client is None else any(r["call_id"] == call_id for r in client["records"])
    admitted_broker = (False if not broker_created else None) if broker is None else any(
        r["call_id"] == call_id for r in broker["records"])
    return {
        "evidence_kind": EVIDENCE_KIND, "scenario": scenario, "call_id": call_id,
        "model_execution_enabled": False, "model_pilot_admitted": False,
        "provider_token_limits_verified": False, "model_calls": 0,
        "usage_origin": "fictional_fixture_not_provider", "scientific_run_admitted": False,
        "experiment_itt_admission": False, "provider_cancellation_confirmed": False,
        "status": status, "phase": phase, "category": category,
        "candidate_call_admitted": admitted_client, "broker_call_admitted": admitted_broker,
        "process_attempts": attempts, "wire_frames": frames,
        "broker_core_seal_sha256": seal["seal_sha256"], "payload_sha256": prepared.payload_sha256,
        "payload_bytes": len(prepared.payload_json.encode("utf-8")),
        "completion": asdict(completion) if completion is not None else None,
        "client_ledger": client, "broker_ledger": broker, "broker_ledger_reopened": broker is not None,
        "broker_ledger_state": "not_created" if not broker_created else "reopened" if broker is not None else "unverified",
        "accounting_reconciliation": _reconciliation(client, broker) if broker_created else "broker_not_created",
        "backend_trace": trace, "replay": replay,
    }


def expected_outcome(record: dict) -> bool:
    """Require the intended fault, exact phase/trace and independent ledgers."""
    expected = {
        "ok": ("ok", "completion", None, 4),
        "legacy_capabilities": ("failed", "capabilities", "capability_error", 1),
        "estimated_count": ("failed", "count", "count_error", 2),
        "count_timeout": ("failed", "count", "timeout", 2),
        "backend_timeout": ("failed", "completion", "timeout", 3),
        "backend_exception": ("failed", "completion", "backend_error", 3),
        "malformed_response": ("failed", "completion", "response_error", 3),
        "missing_usage": ("failed", "completion", "response_error", 3),
        "wrong_model": ("failed", "completion", "response_error", 3),
        "length": ("protocol_failed", "completion", "length", 3),
        "refusal": ("protocol_failed", "completion", "unusable_response", 3),
        "oversize_response": ("failed", "completion", "response_error", 3),
    }
    try:
        scenario = record["scenario"]
        attempts = record["process_attempts"]
        if (record["status"], record["phase"], record["category"], len(attempts)) != expected[scenario]:
            return False
        if (record["evidence_kind"] != EVIDENCE_KIND or type(record["model_calls"]) is not int
                or record["model_calls"] != 0 or record["usage_origin"] != "fictional_fixture_not_provider"
                or any(record[k] is not False for k in (
                    "model_execution_enabled", "model_pilot_admitted", "provider_token_limits_verified",
                    "scientific_run_admitted", "experiment_itt_admission", "provider_cancellation_confirmed"))):
            return False
        phases = ["capabilities", "count", "completion", "replay"][:len(attempts)]
        if [a["phase"] for a in attempts] != phases:
            return False
        timeout = scenario in {"count_timeout", "backend_timeout"}
        for index, attempt in enumerate(attempts):
            if timeout and index == len(attempts) - 1:
                if attempt["status"] != "failed" or attempt["category"] != "timeout":
                    return False
            elif attempt["status"] != "completed":
                return False
        frames = record["wire_frames"]
        if len(frames) != len(attempts) or [f["phase"] for f in frames] != phases:
            return False
        for frame, attempt in zip(frames, attempts):
            if frame["request_sha256"] != attempt["request_sha256"] or frame["request_bytes"] <= 0:
                return False
            if attempt["status"] == "completed" and (
                    frame["receipt_sha256"] != attempt["receipt_sha256"] or frame["receipt_bytes"] <= 0):
                return False
        client, broker = record["client_ledger"], record["broker_ledger"]
        if (not client["journal_integrity_verified"] or not broker["journal_integrity_verified"]
                or record["broker_ledger_reopened"] is not True
                or record["accounting_reconciliation"] != _reconciliation(client, broker)):
            return False
        early = scenario in {"legacy_capabilities", "estimated_count", "count_timeout"}
        operations = (["capabilities"] if scenario == "legacy_capabilities" else
                      ["capabilities", "count"] if early else
                      ["capabilities", "count", "capabilities", "count", "complete"])
        trace = record["backend_trace"]
        if [event["operation"] for event in trace] != operations or any(e["fictional"] is not True for e in trace):
            return False
        for event in trace:
            if event["operation"] in {"count", "complete"} and event["payload_sha256"] != record["payload_sha256"]:
                return False
            if event["operation"] == "complete" and (
                    event["request_model"] != "tmf-broker-core-fixture" or event["output_cap"] != 4096):
                return False
        if early:
            return (record["candidate_call_admitted"] is False and record["broker_call_admitted"] is False
                    and client["admitted_calls"] == broker["admitted_calls"] == 0
                    and not client["halted"] and not broker["halted"]
                    and record["completion"] is None and record["replay"] is None)
        if (record["candidate_call_admitted"] is not True or record["broker_call_admitted"] is not True
                or client["admitted_calls"] != 1 or broker["admitted_calls"] != 1):
            return False
        for journal in (client, broker):
            if (len(journal["records"]) != 1 or journal["records"][0]["call_id"] != record["call_id"]
                    or journal["records"][0]["itt_included"] is not True
                    or journal["records"][0]["request_sha256"] != frames[2]["request_sha256"]):
                return False
        known = scenario in {"ok", "length", "refusal"}
        for journal, known_usage in ((client, known), (broker, known or scenario == "wrong_model")):
            if known_usage:
                if (journal["provider_usage"] != _USAGE or journal["charged_input_tokens"] != 6000
                        or journal["charged_output_tokens"] != 32 or journal["pending_call_id"] is not None):
                    return False
            elif (journal["provider_usage"] is not None or journal["charged_input_tokens"] != 6000
                  or journal["charged_output_tokens"] != 4096):
                return False
            if journal["halted"] is not (scenario != "ok"):
                return False
        if known:
            completion = record["completion"]
            if (completion["usage"] != _USAGE or completion["usable_action_text"] is not (scenario == "ok")
                    or completion["text"] != ('{"action":"list"}' if scenario == "ok" else "")):
                return False
        elif record["completion"] is not None:
            return False
        if scenario == "backend_timeout" and (
                broker["pending_call_id"] != record["call_id"]
                or broker["halt_reason"] != "unsettled_reservation_after_reopen"
                or client["pending_call_id"] is not None):
            return False
        if scenario == "ok":
            replay = record["replay"]
            return (replay["verified"] is True and replay["category"] == "duplicate_call"
                    and replay["broker_ledger_unchanged"] is True and replay["backend_trace_unchanged"] is True
                    and replay["backend_events_before"] == replay["backend_events_after"] == 5
                    and frames[2]["request_sha256"] == frames[3]["request_sha256"])
        return record["replay"] is None
    except (KeyError, TypeError, ValueError, IndexError):
        return False


def conformance_rehearsal(output: Path) -> dict:
    """Retain every fixed case, including pre-admission failures, in NEWDIR."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    contract, caps = fixed_contract(), ProcessCaps(1000000, 64000, 4096)
    request = AdapterRequest(
        ({"role": "system", "content": "Use the supplied JSON action schemas."},
         {"role": "user", "content": "List the relative source paths in <workspace>."}),
        ACTION_SCHEMAS, 4096, 16000, 3,
    )
    (output / "broker-core-seal.json").write_text(canonical(broker_core_seal(contract, caps)) + "\n")
    records, outcomes = [], {}
    for scenario in SCENARIOS:
        directory = output / scenario
        directory.mkdir()
        with TokenBudgetLedger(directory / "client-ledger.jsonl", contract.limits) as ledger:
            record = rehearse_turn(
                contract, request, ledger=ledger, broker_ledger_path=directory / "broker-ledger.jsonl",
                trace_path=directory / "backend-events.jsonl", caps=caps, scenario=scenario,
                evidence_dir=directory,
            )
        records.append(record)
        (directory / "record.json").write_text(canonical(record) + "\n")
        outcomes[scenario] = record.get("scenario") == scenario and expected_outcome(record)
    coverage = (len(records) == len(SCENARIOS) == len(set(SCENARIOS))
                and tuple(r.get("scenario") for r in records) == SCENARIOS and tuple(outcomes) == SCENARIOS)
    identifiers = [r.get("call_id") for r in records]
    unique = (all(type(value) is str and len(value) == 32 for value in identifiers)
              and len(set(identifiers)) == len(SCENARIOS))
    summary = {
        "evidence_kind": EVIDENCE_KIND, "scenarios": len(records), "checks": outcomes,
        "coverage_verified": coverage, "unique_call_ids": unique,
        "all_expected_outcomes": coverage and unique and all(outcomes.values()),
        "model_calls": 0, "usage_origin": "fictional_fixture_not_provider",
        "model_execution_enabled": False, "model_pilot_admitted": False,
        "provider_token_limits_verified": False, "scientific_run_admitted": False,
        "experiment_itt_admission": False,
    }
    (output / "summary.json").write_text(canonical(summary) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new local evidence directory")
    args = parser.parse_args()
    summary = conformance_rehearsal(args.output)
    print(canonical(summary))
    raise SystemExit(0 if summary["all_expected_outcomes"] else 1)


if __name__ == "__main__":
    main()
