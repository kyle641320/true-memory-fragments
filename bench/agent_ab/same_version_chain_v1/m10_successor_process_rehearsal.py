"""Fixed offline peer + real process I/O + the successor contract/ledger.

No public command, script, executable, provider or network callback is accepted.
The fictional peer tests IPC, not a live provider. The experiment runner and its
model-execution gates are unchanged and cannot consume this as a real adapter.
"""

from __future__ import annotations

import hashlib
import argparse
import json
import platform
import sys
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from .m10_successor_adapter_contract import (
    BrokerContract, ContractError, accept_completion, admit_turn, canonical,
    check_capabilities, prepare_turn, seal_contract,
)
from .m10_successor_process_io import ProcessCaps, ProcessTransportError, _exchange
from .m10_successor_protocol import AdapterRequest, LiveExecutionDisabled
from .m10_successor_token_budget import TokenBudgetError, TokenBudgetLedger, TokenLimits


EVIDENCE_KIND = "offline_process_contract_rehearsal"
MODEL_EXECUTION_ENABLED = False
SCENARIOS = (
    "ok", "legacy_capabilities", "estimated_count", "count_timeout", "timeout",
    "exit_before_reply", "reply_then_exit", "stdout_flood", "stderr_flood",
    "malformed_json", "extra_frame", "wrong_identity", "wrong_hash",
    "missing_usage", "length", "refusal",
)
_ROOT = Path(__file__).resolve().parents[3]
_PEER = Path(__file__).with_name("m10_successor_offline_peer.py")


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _runtime() -> dict:
    return {"executable_sha256": _hash(Path(sys.executable).resolve().read_bytes()),
            "implementation": platform.python_implementation(), "version": platform.python_version()}


def offline_contract(*, experiment_seal_sha256: str, limits: TokenLimits,
                     max_request_bytes: int, max_response_bytes: int,
                     timeout_seconds: float) -> BrokerContract:
    """Construct only fictional identities; no real model defaults are chosen."""
    return BrokerContract(
        experiment_seal_sha256=experiment_seal_sha256,
        provider_id="tmf-offline-fixture", endpoint="https://offline.invalid/v1/chat/completions",
        request_model="tmf-offline-fixture", response_model="tmf-offline-fixture-v1",
        deployment_revision="offline-scripted-v1", broker_build_sha256=_hash(_PEER.read_bytes()),
        broker_runtime_sha256=_hash(canonical(_runtime()).encode("utf-8")),
        tokenizer_id="fictional-count-v1", tokenizer_sha256=_hash(b"fictional-count-6000-v1"),
        inference_json=canonical({"temperature": None, "top_p": None, "seed": None, "reasoning_effort": None}),
        limits=limits, max_request_bytes=max_request_bytes, max_response_bytes=max_response_bytes,
        timeout_seconds=timeout_seconds,
    )


def _require_offline(contract: BrokerContract) -> None:
    if type(contract) is not BrokerContract:
        raise LiveExecutionDisabled("only the fixed offline peer is admitted")
    expected = offline_contract(
        experiment_seal_sha256=contract.experiment_seal_sha256, limits=contract.limits,
        max_request_bytes=contract.max_request_bytes, max_response_bytes=contract.max_response_bytes,
        timeout_seconds=contract.timeout_seconds,
    )
    if contract != expected:
        raise LiveExecutionDisabled("real/custom broker identities cannot use this offline facade")


def transport_seal(contract: BrokerContract, caps: ProcessCaps) -> dict:
    _require_offline(contract)
    files = (
        "bench/agent_ab/same_version_chain_v1/m10_successor_process_io.py",
        "bench/agent_ab/same_version_chain_v1/m10_successor_process_rehearsal.py",
        "bench/agent_ab/same_version_chain_v1/m10_successor_offline_peer.py",
        "docs/experiments/guava-m10-successor-process-rehearsal.md",
    )
    material = {
        "contract_seal": seal_contract(contract), "process_caps": asdict(caps),
        "implementation_sha256": {name: _hash((_ROOT / name).read_bytes()) for name in files},
        "python_runtime": _runtime(), "evidence_kind": EVIDENCE_KIND,
        "model_execution_enabled": False, "model_pilot_admitted": False,
        "provider_token_limits_verified": False,
    }
    return {**material, "seal_sha256": _hash(canonical(material).encode("utf-8"))}


def rehearse_turn(contract: BrokerContract, request: AdapterRequest, *,
                   ledger: TokenBudgetLedger, caps: ProcessCaps, scenario: str = "ok") -> dict:
    """Three real child exchanges, one deadline, at most one reserved call.

    All output and usage are explicitly fictional. Admission errors and
    pre-admission process failures return records too, not a success-only subset.
    A failure after reservation becomes durable unknown; it never starts a
    replacement process. Raw stderr/exception text never enters the report.
    """
    _require_offline(contract)
    if type(scenario) is not str or scenario not in SCENARIOS:
        raise ValueError("unknown offline scenario")
    if type(caps) is not ProcessCaps:
        raise ValueError("explicit ProcessCaps required")
    prepared = prepare_turn(contract, request)
    seal = transport_seal(contract, caps)
    source = _PEER.read_bytes()
    if _hash(source) != contract.broker_build_sha256:
        raise ContractError("offline peer source drift")
    deadline = time.monotonic() + prepared.timeout_seconds
    call_id = uuid.uuid4().hex
    attempts: list[dict] = []
    phase = "capabilities"
    completion = None
    status, category = "ok", None

    def exchange(message: dict) -> bytes:
        if transport_seal(contract, caps) != seal:
            raise ContractError("transport material drift")
        envelope = canonical({"contract": asdict(contract), "contract_sha256": prepared.contract_sha256,
                              "request": message, "scenario": scenario}).encode("utf-8")
        # The IPC envelope includes metadata and escaping, not just model text.
        # Reject it before spawning; it must fit an independent frame budget.
        if len(envelope) > caps.max_request_bytes:
            raise ProcessTransportError("request_too_large")
        bounded = ProcessCaps(caps.max_request_bytes,
                              min(caps.max_stdout_bytes, contract.max_response_bytes), caps.max_stderr_bytes)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ProcessTransportError("timeout")
        attempt = {"phase": phase, "status": "attempted"}
        attempts.append(attempt)
        try:
            reply = _exchange(source, envelope, caps=bounded, timeout_seconds=remaining,
                              deadline_monotonic=deadline)
            if time.monotonic() >= deadline:
                raise ProcessTransportError("timeout")
        except ProcessTransportError as exc:
            attempt.update(status="failed", category=exc.category)
            raise
        attempt.update(status="completed", stdout_bytes=len(reply.stdout),
                       stderr_bytes=reply.stderr_bytes, elapsed_seconds=reply.elapsed_seconds)
        return reply.stdout

    try:
        initial = ledger.snapshot()
        if (initial["halted"] or initial["pending_call_id"] is not None
                or not initial["journal_integrity_verified"]):
            raise TokenBudgetError("ledger cannot admit another turn")
        if asdict(ledger.limits) != asdict(contract.limits):
            raise ContractError("ledger limits differ from contract")
        capabilities = exchange({"protocol": "tmf-successor-broker-v2", "op": "capabilities",
                                 "contract_sha256": prepared.contract_sha256})
        check_capabilities(contract, capabilities)
        phase = "count"
        count = exchange({"protocol": "tmf-successor-broker-v2", "op": "count",
                          "contract_sha256": prepared.contract_sha256,
                          "payload_json": prepared.payload_json, "payload_sha256": prepared.payload_sha256})
        phase = "admission"
        admitted = admit_turn(contract, prepared, capabilities=capabilities, count_receipt=count,
                              ledger=ledger, call_id=call_id)
        phase = "completion"
        raw = exchange(json.loads(admitted.completion_request_json))
        completion = accept_completion(contract, admitted, raw, ledger=ledger)
        if not completion.usable_action_text:
            status = "protocol_failed"
            category = "unusable_response" if completion.finish_reason == "stop" else completion.finish_reason
    except Exception as exc:
        if isinstance(exc, ProcessTransportError):
            category = exc.category
        elif isinstance(exc, ContractError):
            category = "contract_error"
        elif isinstance(exc, TokenBudgetError):
            category = "ledger_error"
        else:
            category = "internal_error"
        status = "failed"
        # admit_turn can itself fail during fsync, after creating a conservative
        # pending record. Inspect rather than assuming no returned handle=no call.
        try:
            snapshot = ledger.snapshot()
            if snapshot["pending_call_id"] == call_id and not snapshot["halted"]:
                ledger.settle(call_id, usage=None, outcome="timeout" if category == "timeout" else "unknown")
        except TokenBudgetError:
            status, category = "failed", "ledger_error"
    try:
        snapshot = ledger.snapshot()
    except TokenBudgetError:
        snapshot = None
    # Integrity failure is normally reported in the snapshot, not raised.
    # Keep the accounting/provenance, but never certify an action from a ledger
    # that changed between settlement and the final report.
    if snapshot is None or not snapshot["journal_integrity_verified"]:
        status, category = "failed", "ledger_error"
        completion = None
    admitted_flag = None if snapshot is None else any(r["call_id"] == call_id for r in snapshot["records"])
    return {
        "evidence_kind": EVIDENCE_KIND, "scenario": scenario,
        "model_execution_enabled": False, "model_pilot_admitted": False,
        "provider_token_limits_verified": False, "model_calls": 0,
        "usage_origin": "fictional_fixture_not_provider", "call_id": call_id,
        "status": status, "phase": phase, "category": category,
        "candidate_call_admitted": admitted_flag, "process_attempts": attempts,
        "transport_seal_sha256": seal["seal_sha256"], "payload_sha256": prepared.payload_sha256,
        "completion": asdict(completion) if completion is not None else None,
        "ledger": snapshot,
    }


def expected_outcome(record: dict) -> bool:
    """Check the intended fault, not merely any failure in that scenario."""
    expectation = {
        "ok": ("ok", "completion", None, 3),
        "legacy_capabilities": ("failed", "capabilities", "contract_error", 1),
        "estimated_count": ("failed", "admission", "contract_error", 2),
        "count_timeout": ("failed", "count", "timeout", 2),
        "timeout": ("failed", "completion", "timeout", 3),
        "exit_before_reply": ("failed", "completion", "process_exit", 3),
        "reply_then_exit": ("failed", "completion", "process_exit", 3),
        "stdout_flood": ("failed", "completion", "stdout_limit", 3),
        "stderr_flood": ("failed", "completion", "stderr_limit", 3),
        "malformed_json": ("failed", "completion", "contract_error", 3),
        "extra_frame": ("failed", "completion", "contract_error", 3),
        "wrong_identity": ("failed", "completion", "contract_error", 3),
        "wrong_hash": ("failed", "completion", "contract_error", 3),
        "missing_usage": ("failed", "completion", "contract_error", 3),
        "length": ("protocol_failed", "completion", "length", 3),
        "refusal": ("protocol_failed", "completion", "unusable_response", 3),
    }
    try:
        scenario = record["scenario"]
        if (record["status"], record["phase"], record["category"], len(record["process_attempts"])) != expectation[scenario]:
            return False
        if (record["evidence_kind"] != EVIDENCE_KIND or type(record["model_calls"]) is not int
                or record["model_calls"] != 0 or record["usage_origin"] != "fictional_fixture_not_provider"
                or any(record[k] is not False for k in ("model_execution_enabled", "model_pilot_admitted",
                                                       "provider_token_limits_verified"))):
            return False
        snapshot = record["ledger"]
        if not snapshot["journal_integrity_verified"]:
            return False
        if scenario in {"legacy_capabilities", "estimated_count", "count_timeout"}:
            return record["candidate_call_admitted"] is False and snapshot["admitted_calls"] == 0
        if record["candidate_call_admitted"] is not True or snapshot["admitted_calls"] != 1:
            return False
        if scenario == "ok":
            return (record["completion"]["usable_action_text"] is True and not snapshot["halted"]
                    and snapshot["provider_usage"] == {"input_tokens": 6000, "output_tokens": 32, "total_tokens": 6032})
        if not snapshot["halted"]:
            return False
        if scenario in {"length", "refusal"}:
            return (record["completion"]["usable_action_text"] is False
                    and snapshot["provider_usage"] == {"input_tokens": 6000, "output_tokens": 32, "total_tokens": 6032})
        return (record["completion"] is None and snapshot["provider_usage"] is None
                and snapshot["charged_input_tokens"] == 6000 and snapshot["charged_output_tokens"] == 4096)
    except (KeyError, TypeError):
        return False


def conformance_rehearsal(output: Path) -> dict:
    """Run fixed fault scenarios, retaining all records in a new evidence dir."""
    from .m10_successor_protocol import ACTION_SCHEMAS

    output.mkdir(parents=True, exist_ok=False)
    contract = offline_contract(
        experiment_seal_sha256="0" * 64,  # No scientific run is being admitted.
        limits=TokenLimits(10000, 4096, 14096, 30000, 12288, 24),
        max_request_bytes=120000, max_response_bytes=64000, timeout_seconds=3,
    )
    caps = ProcessCaps(1000000, 64000, 4096)
    request = AdapterRequest(
        ({"role": "system", "content": "Use the supplied JSON action schemas."},
         {"role": "user", "content": "List the relative source paths in <workspace>."}),
        ACTION_SCHEMAS, 4096, 16000, 3,
    )
    records = []
    outcomes = {}
    (output / "transport-seal.json").write_text(canonical(transport_seal(contract, caps)) + "\n")
    for scenario in SCENARIOS:
        with TokenBudgetLedger(output / (scenario + ".jsonl"), contract.limits) as ledger:
            record = rehearse_turn(contract, request, ledger=ledger, caps=caps, scenario=scenario)
        records.append(record)
        (output / (scenario + ".json")).write_text(canonical(record) + "\n")
        # Key by the requested scenario, never by untrusted returned identity:
        # a duplicate result must not overwrite a missing negative case.
        outcomes[scenario] = record.get("scenario") == scenario and expected_outcome(record)
    coverage_verified = (len(records) == len(SCENARIOS) == len(set(SCENARIOS))
                         and tuple(record.get("scenario") for record in records) == SCENARIOS
                         and tuple(outcomes) == SCENARIOS)
    call_ids = [record.get("call_id") for record in records]
    unique_call_ids = (all(type(value) is str and bool(value) for value in call_ids)
                       and len(set(call_ids)) == len(SCENARIOS))
    summary = {
        "evidence_kind": EVIDENCE_KIND, "scenarios": len(records), "checks": outcomes,
        "coverage_verified": coverage_verified, "unique_call_ids": unique_call_ids,
        "all_expected_outcomes": coverage_verified and unique_call_ids and all(outcomes.values()), "model_calls": 0,
        "model_pilot_admitted": False, "provider_token_limits_verified": False,
        "candidate_calls_admitted": sum(r["candidate_call_admitted"] is True for r in records),
        "usage_origin": "fictional_fixture_not_provider",
    }
    (output / "summary.json").write_text(canonical(summary) + "\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Fixed offline peer process conformance; no model calls")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = conformance_rehearsal(args.output)
    print(canonical(summary))
    return 0 if summary["all_expected_outcomes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
