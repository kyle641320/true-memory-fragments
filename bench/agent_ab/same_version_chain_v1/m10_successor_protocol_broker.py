"""Fixed fictional multi-turn actions through actual, bounded BrokerCore workers.

This is an offline known-answer plumbing adapter, not a model or provider
adapter. Its 6000 input / 32 output counts are invented for exercising durable
accounting. Each action has one absolute deadline and three worker exchanges;
there is no retry, replay probe, network client, credential lookup, or backend
selector. The existing private process I/O strips environment/cwd, but is not
an OS sandbox. Killing a worker does not prove upstream cancellation.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, replace
from pathlib import Path

from .m10_successor_adapter_contract import (
    PROTOCOL, BrokerContract, ContractError, _strict_json, accept_completion,
    admit_turn, canonical, check_capabilities, digest, prepare_turn, seal_contract,
)
from .m10_successor_process_io import ProcessCaps, ProcessTransportError, _exchange
from .m10_successor_protocol import AdapterRequest, LiveExecutionDisabled, _ProtocolFailure
from .m10_successor_token_budget import TokenBudgetError, TokenBudgetExceeded, TokenBudgetLedger, TokenLimits


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_KIND = "offline_broker_protocol_rehearsal"
MODEL_EXECUTION_ENABLED = False
SCENARIOS = ("ok", "wrong_model", "missing_usage", "backend_timeout", "invalid_action")
FAULT_TURN = 3
FICTIONAL_INPUT_TOKENS = 6000
FICTIONAL_OUTPUT_TOKENS = 32
PROCESS_CAPS = ProcessCaps(1_000_000, 64_000, 4096)
MATERIALS = (
    "bench/agent_ab/same_version_chain_v1/m10_successor_broker_core.py",
    "bench/agent_ab/same_version_chain_v1/m10_successor_adapter_contract.py",
    "bench/agent_ab/same_version_chain_v1/m10_successor_token_budget.py",
    "bench/agent_ab/same_version_chain_v1/m10_successor_process_io.py",
    "bench/agent_ab/same_version_chain_v1/m10_successor_protocol.py",
    "bench/agent_ab/same_version_chain_v1/m10_successor_protocol_broker.py",
    "bench/agent_ab/same_version_chain_v1/m10_successor_run_ledger.py",
    "bench/agent_ab/same_version_chain_v1/m10_successor_runner_bridge.py",
    "bench/agent_ab/same_version_chain_v1/guava_m10_successor_runner.py",
    "bench/agent_ab/same_version_chain_v1/m10_successor_fixture.py",
    "bench/agent_ab/same_version_chain_v1/m10_successor_scoring.py",
    "bench/agent_ab/same_version_chain_v1/m10_successor_fixture_spec.json",
    "docs/experiments/guava-m10-successor-adapter-contract.md",
    "docs/experiments/guava-m10-successor-broker-core.md",
    "docs/experiments/guava-m10-successor-protocol.md",
    "docs/experiments/guava-m10-successor-runner-bridge.md",
)
_BROKER_ERRORS = frozenset({
    "request_error", "capability_error", "count_error", "response_error",
    "backend_error", "timeout", "ledger_error", "duplicate_call",
    "budget_exceeded", "internal_error",
})


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def inventory() -> dict[str, str]:
    """Hash fixed source bytes without importing the bridge/ledger driver."""
    return {name: _hash((ROOT / name).read_bytes()) for name in MATERIALS}


def _runtime() -> dict:
    return {"executable_sha256": _hash(Path(sys.executable).resolve().read_bytes()),
            "implementation": platform.python_implementation(), "version": platform.python_version()}


def fixed_protocol_contract(experiment_seal_sha256: str, limits: TokenLimits) -> BrokerContract:
    """Only the explicit experiment seal and aggregate budgets are variable."""
    if type(limits) is not TokenLimits:
        raise ValueError("explicit token limits required")
    return BrokerContract(
        experiment_seal_sha256=experiment_seal_sha256,
        provider_id="tmf-protocol-fixture", endpoint="https://offline.invalid/v1/chat/completions",
        request_model="tmf-protocol-fixture", response_model="tmf-protocol-fixture-v1",
        deployment_revision="fictional-five-action-backend-v1",
        broker_build_sha256=digest(canonical(inventory())), broker_runtime_sha256=digest(canonical(_runtime())),
        tokenizer_id="fictional-count-v1", tokenizer_sha256=digest("fictional-count-6000-v1"),
        inference_json=canonical({"temperature": None, "top_p": None, "seed": None, "reasoning_effort": None}),
        limits=TokenLimits(**asdict(limits)), max_request_bytes=120_000,
        max_response_bytes=64_000, timeout_seconds=10.0,
    )


def _require_fixed(contract: BrokerContract) -> None:
    if (type(contract) is not BrokerContract or canonical(asdict(contract)) != canonical(asdict(
            fixed_protocol_contract(contract.experiment_seal_sha256, contract.limits)))):
        raise LiveExecutionDisabled("only the fixed fictional protocol backend is available")


def _script() -> tuple[dict, ...]:
    return (
        {"action": "list"},
        {"action": "read_range", "path": "Dispatcher.java", "start": 1, "end": 260},
        {"action": "edit", "path": "Dispatcher.java",
         "old": "      prepared.subscriber.dispatchEvent(prepared.event);",
         "new": "      hook();\n      prepared.subscriber.dispatchEvent(prepared.event);"},
        {"action": "compile"},
        {"action": "final", "answer": "Added one hook at the Dispatcher-to-Subscriber handoff.",
         "files": ["Dispatcher.java"]},
    )


def _action_from_history(messages: list[dict]) -> tuple[dict, int]:
    """The complete message history is the ONLY input choosing an action.

    No arm, opaque call/run ID, file-system path, evaluator, scenario, counter
    or ledger information participates. All prior assistant actions must be
    the exact known-answer prefix; tool feedback remains in the full payload.
    """
    actions = _script()
    previous = messages[2::2]
    if len(previous) >= len(actions):
        raise ValueError("fictional action script exhausted")
    for message, expected in zip(previous, actions):
        if message["role"] != "assistant" or json.loads(message["content"]) != expected:
            raise ValueError("fictional action history differs")
    return actions[len(previous)], len(previous) + 1


def _write_new(path: Path, raw: bytes) -> None:
    """Never replace evidence; a failed write is an adapter failure."""
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


class _FictionalProtocolBackend:
    """Only original response bytes are returned; BrokerCore wraps receipts."""

    def __init__(self, contract: BrokerContract, trace: Path, scenario: str):
        _require_fixed(contract)
        if type(scenario) is not str or scenario not in SCENARIOS:
            raise ValueError("unknown fixed fixture scenario")
        self.contract, self.trace, self.scenario = contract, trace, scenario

    def _event(self, operation: str, deadline: float, payload_json: str | None = None,
               **fields) -> None:
        payload = json.loads(payload_json) if payload_json is not None else None
        event = {"operation": operation, "fictional": True,
                 "deadline_monotonic": deadline, "payload_json": payload_json,
                 "payload_sha256": digest(payload_json) if payload_json is not None else None,
                 "output_cap": payload["max_completion_tokens"] if payload is not None else None,
                 "contract_output_per_turn": self.contract.limits.output_per_turn,
                 "max_response_bytes": self.contract.max_response_bytes, **fields}
        with self.trace.open("ab") as stream:
            stream.write((canonical(event) + "\n").encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())

    def capabilities(self, *, contract_sha256: str, deadline_monotonic: float) -> bytes:
        self._event("capabilities", deadline_monotonic)
        return canonical({
            "protocol": PROTOCOL, "op": "capabilities", "contract_sha256": contract_sha256,
            "identity": self.contract.identity(),
            "tokenizer": {"id": self.contract.tokenizer_id, "sha256": self.contract.tokenizer_sha256},
            "semantics": {"stateless": True, "native_tools": False, "network_owner": "broker",
                          "credential_owner": "broker", "max_attempts": 1, "fallback": False,
                          "truncation": False, "input_count": "exact_full_payload",
                          "output_parameter": "max_completion_tokens",
                          "usage": "all_provider_tokens_including_reasoning"},
        }).encode("utf-8")

    def count(self, *, payload_json: str, payload_sha256: str, contract_sha256: str,
              deadline_monotonic: float) -> bytes:
        self._event("count", deadline_monotonic, payload_json)
        return canonical({
            "protocol": PROTOCOL, "op": "count", "contract_sha256": contract_sha256,
            "payload_sha256": payload_sha256, "tokenizer_id": self.contract.tokenizer_id,
            "tokenizer_sha256": self.contract.tokenizer_sha256,
            "input_tokens": FICTIONAL_INPUT_TOKENS, "exact": True, "generation_calls": 0,
        }).encode("utf-8")

    def complete(self, *, payload_json: str, deadline_monotonic: float,
                 max_response_bytes: int) -> bytes:
        payload = json.loads(payload_json)
        action, turn = _action_from_history(payload["messages"])
        fault = self.scenario != "ok" and turn == FAULT_TURN
        self._event("complete", deadline_monotonic, payload_json,
                    turn_from_history=turn, fault_injected=fault,
                    original_response_cap=max_response_bytes)
        if fault and self.scenario == "backend_timeout":
            # A deterministic blocking callback, stopped only by bounded IPC.
            # This is never represented as proof of upstream cancellation.
            time.sleep(3600)
        if fault and self.scenario == "invalid_action":
            action = {"action": "not_a_permitted_action"}
        response = {
            "id": "fictional-original-five-action-response", "object": "chat.completion",
            "model": self.contract.response_model,
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": canonical(action)}}],
            "usage": {"prompt_tokens": FICTIONAL_INPUT_TOKENS,
                      "completion_tokens": FICTIONAL_OUTPUT_TOKENS,
                      "total_tokens": FICTIONAL_INPUT_TOKENS + FICTIONAL_OUTPUT_TOKENS},
            "fixture_provenance": "original_backend_field_not_added_by_broker",
        }
        if fault and self.scenario == "wrong_model":
            response["model"] = "wrong-fictional-model"
        if fault and self.scenario == "missing_usage":
            del response["usage"]
        # Deliberately noncanonical: retain exact original field/whitespace
        # bytes as well as the genuine broker's canonical wrapped receipt.
        raw = (json.dumps(response, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        _write_new(self.trace.parent / "original-response.bin", raw)
        return raw


def _worker_main(contract_data: dict, ledger_path: str, trace_path: str, scenario: str,
                 deadline_monotonic: float, max_request_frame_bytes: int) -> None:
    """Fixed sealed-source entry, not a CLI, loader or configurable backend."""
    from .m10_successor_broker_core import BrokerCore, BrokerError

    values = dict(contract_data)
    values["limits"] = TokenLimits(**values["limits"])
    contract = BrokerContract(**values)
    _require_fixed(contract)
    if max_request_frame_bytes != PROCESS_CAPS.max_request_bytes:
        raise ValueError("fixed frame budget required")
    raw = sys.stdin.buffer.read(max_request_frame_bytes + 1)
    with TokenBudgetLedger(ledger_path, contract.limits) as ledger:
        try:
            core = BrokerCore(contract, ledger, _FictionalProtocolBackend(contract, Path(trace_path), scenario),
                              max_request_frame_bytes=max_request_frame_bytes)
            response = core.handle(raw, deadline_monotonic=deadline_monotonic)
        except BrokerError as exc:
            response = canonical({"protocol": PROTOCOL, "error": exc.category}).encode("utf-8")
    sys.stdout.buffer.write(response)
    sys.stdout.buffer.flush()


def _worker_source(contract: BrokerContract, *, materials: dict[str, str],
                   broker_ledger_path: Path, trace_path: Path, scenario: str,
                   deadline_monotonic: float) -> bytes:
    source = (
        "import hashlib, pathlib, sys\n"
        f"root = pathlib.Path({str(ROOT)!r})\n"
        f"materials = {materials!r}\n"
        "for name, expected in materials.items():\n"
        "    if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:\n"
        "        sys.exit(73)\n"
        "sys.path.insert(0, str(root))\n"
        "from bench.agent_ab.same_version_chain_v1.m10_successor_protocol_broker import _worker_main\n"
        f"_worker_main({asdict(contract)!r}, {str(broker_ledger_path)!r}, {str(trace_path)!r}, "
        f"{scenario!r}, {deadline_monotonic!r}, {PROCESS_CAPS.max_request_bytes!r})\n"
    )
    return source.encode("utf-8")


class _BrokerReplyError(RuntimeError):
    def __init__(self, category: str):
        self.category = category
        super().__init__(category)


def _broker_error(raw: bytes, limit: int) -> None:
    reply = _strict_json(raw, limit)
    if "error" in reply:
        if (set(reply) != {"protocol", "error"} or reply["protocol"] != PROTOCOL
                or type(reply["error"]) is not str or reply["error"] not in _BROKER_ERRORS):
            raise ContractError("invalid broker error receipt")
        raise _BrokerReplyError(reply["error"])


def _reconciliation(client: dict | None, broker: dict | None, broker_state: str) -> str:
    if broker_state == "not_created":
        return "broker_not_created"
    if (client is None or broker is None or not client["journal_integrity_verified"]
            or not broker["journal_integrity_verified"]):
        return "unverified_ledger_state"
    if client["admitted_calls"] == broker["admitted_calls"] == 0:
        return "no_candidate_call_admitted"
    if client["admitted_calls"] != broker["admitted_calls"]:
        return "different_admission_boundaries"
    if broker["unknown_usage_calls"] < client["unknown_usage_calls"]:
        return "broker_known_client_unknown"
    same_charge = all(client[k] == broker[k] for k in
                      ("charged_input_tokens", "charged_output_tokens", "admitted_calls"))
    if same_charge and client["provider_usage"] == broker["provider_usage"]:
        return "matching_known_usage" if client["provider_usage"] is not None else "both_unknown_conservative"
    return "different_accounting_evidence"


class OfflineProtocolBroker:
    """Per-run facade over externally shared, persistent budget journals.

    Construct only after the caller durably admits the scientific run. The
    constructor performs local validation/evidence setup, NEVER transport.
    ``verify_before_dispatch`` is a trusted control-plane guard, not a backend;
    the scientific bridge supplies it for every exchange. Omitting it is only
    useful for isolated transport conformance tests, not joint-seal admission.
    ``close`` never owns/closes the supplied client ledger, and snapshots remain
    available after close. No callback/error details are fed to model messages.
    """

    def __init__(self, contract: BrokerContract, *, client_ledger: TokenBudgetLedger,
                 broker_ledger_path: Path, evidence_dir: Path, scenario: str = "ok",
                 verify_before_dispatch: Callable[[], None] | None = None):
        _require_fixed(contract)
        if type(scenario) is not str or scenario not in SCENARIOS:
            raise ValueError("unknown fixed fixture scenario")
        if type(client_ledger) is not TokenBudgetLedger or client_ledger.limits != contract.limits:
            raise TokenBudgetError("shared client ledger differs from contract")
        if verify_before_dispatch is not None and not callable(verify_before_dispatch):
            raise ValueError("dispatch guard must be callable")
        self._contract = replace(contract, limits=TokenLimits(**asdict(contract.limits)))
        self._client = client_ledger
        self._broker_path = Path(broker_ledger_path).resolve()
        self._evidence_dir = Path(evidence_dir).resolve()
        if (self._broker_path == client_ledger._path.resolve()
                or self._broker_path == self._evidence_dir or client_ledger._path.resolve() == self._evidence_dir):
            raise ValueError("journals and evidence must be separate")
        self._scenario, self._guard = scenario, verify_before_dispatch
        self._materials, self._runtime = inventory(), _runtime()
        self._contract_seal = seal_contract(self._contract)
        self._turns: list[dict] = []
        self._closed = False
        self._failed = False
        self._evidence_dir.mkdir(parents=True, exist_ok=True)
        if any(self._evidence_dir.iterdir()):
            raise ValueError("adapter evidence directory must be empty")

    def _verify_bound(self) -> None:
        try:
            _require_fixed(self._contract)
            if (inventory() != self._materials or _runtime() != self._runtime
                    or seal_contract(self._contract) != self._contract_seal):
                raise ContractError("fixed protocol broker material drift")
        except OSError:
            raise ContractError("fixed protocol broker material unavailable") from None

    def _ledgers(self) -> dict:
        try:
            client = self._client.snapshot()
        except TokenBudgetError:
            client = None
        broker = None
        broker_state = "not_created"
        if self._broker_path.exists():
            broker_state = "unverified"
            try:
                with TokenBudgetLedger(self._broker_path, self._contract.limits) as ledger:
                    broker = ledger.snapshot()
                if broker["journal_integrity_verified"]:
                    broker_state = "reopened"
            except TokenBudgetError:
                pass
        return {"client_ledger": client, "broker_ledger": broker, "broker_ledger_state": broker_state,
                "accounting_reconciliation": _reconciliation(client, broker, broker_state)}

    def _ready(self, pending_call_id: str | None = None) -> None:
        evidence = self._ledgers()
        for name in ("client_ledger", "broker_ledger"):
            ledger = evidence[name]
            if ledger is None and name == "broker_ledger" and evidence["broker_ledger_state"] == "not_created":
                continue
            expected_pending = pending_call_id if name == "client_ledger" else None
            if (ledger is None or not ledger["journal_integrity_verified"] or ledger["halted"]
                    or ledger["pending_call_id"] != expected_pending
                    or ledger["limits"] != asdict(self._contract.limits)):
                raise TokenBudgetError("shared ledger cannot admit another turn")

    def respond(self, request: AdapterRequest) -> str:
        started = time.monotonic()
        call_id = uuid.uuid4().hex
        record = {"turn": len(self._turns) + 1, "call_id": call_id, "status": "failed",
                  "phase": "preparation", "category": None, "completion": None,
                  "declared_timeout_seconds": None, "effective_timeout_seconds": None,
                  "payload_sha256": None, "payload_bytes": None, "source_request": None,
                  "process_attempts": [], "wire_frames": [], "backend_trace": [],
                  "candidate_call_admitted": False, "broker_call_admitted": False,
                  "original_response": None}
        self._turns.append(record)
        result = None
        directory = self._evidence_dir / f"turn-{record['turn']:04d}"
        trace = directory / "backend-events.jsonl"
        deadline = started + self._contract.timeout_seconds

        def check_deadline() -> None:
            if time.monotonic() >= deadline:
                raise ProcessTransportError("timeout")

        def exchange(message: dict | str, phase: str) -> bytes:
            record["phase"] = phase
            raw = (message if type(message) is str else canonical(message)).encode("utf-8")
            stem = f"{len(record['wire_frames']) + 1:02d}-{phase}"
            frame = {"phase": phase, "status": "not_dispatched", "request_sha256": _hash(raw),
                     "request_bytes": len(raw), "request_file": stem + ".request.bin",
                     "receipt_sha256": None, "receipt_bytes": None}
            record["wire_frames"].append(frame)
            _write_new(directory / frame["request_file"], raw)
            if self._guard is not None:
                try:
                    self._guard()
                except Exception:
                    raise ContractError("joint-seal dispatch guard rejected") from None
            self._verify_bound()
            self._ready(call_id if phase == "completion" else None)
            check_deadline()
            # The full wire frame and model payload have independent limits.
            if len(raw) > PROCESS_CAPS.max_request_bytes:
                raise ProcessTransportError("request_too_large")
            source = _worker_source(
                self._contract, materials=self._materials, broker_ledger_path=self._broker_path,
                trace_path=trace, scenario=self._scenario, deadline_monotonic=deadline,
            )
            check_deadline()
            attempt = {"phase": phase, "status": "attempted", "worker_source_sha256": _hash(source),
                       "request_sha256": frame["request_sha256"], "deadline_monotonic": deadline}
            record["process_attempts"].append(attempt)
            frame["status"] = "dispatched"
            try:
                reply = _exchange(source, raw, caps=PROCESS_CAPS,
                                  timeout_seconds=deadline - time.monotonic(), deadline_monotonic=deadline)
                frame.update(status="received", receipt_sha256=_hash(reply.stdout), receipt_bytes=len(reply.stdout),
                             receipt_file=stem + ".receipt.bin")
                _write_new(directory / frame["receipt_file"], reply.stdout)
                attempt.update(status="completed", stdout_bytes=len(reply.stdout), stderr_bytes=reply.stderr_bytes,
                               elapsed_seconds=reply.elapsed_seconds, receipt_sha256=frame["receipt_sha256"])
                check_deadline()
            except ProcessTransportError as exc:
                attempt.update(status="failed", category=exc.category)
                raise
            _broker_error(reply.stdout, self._contract.max_response_bytes)
            return reply.stdout

        try:
            if self._closed or self._failed:
                raise TokenBudgetError("adapter is closed or previously failed")
            self._verify_bound()
            self._ready()
            if (type(request) is not AdapterRequest or type(request.timeout_seconds) not in (int, float)
                    or not math.isfinite(request.timeout_seconds) or request.timeout_seconds <= 0):
                raise ContractError("invalid adapter request timeout")
            effective = replace(request, timeout_seconds=min(request.timeout_seconds, self._contract.timeout_seconds))
            deadline = started + effective.timeout_seconds
            record.update(declared_timeout_seconds=request.timeout_seconds,
                          effective_timeout_seconds=effective.timeout_seconds,
                          source_request=json.loads(canonical(asdict(request))))
            prepared = prepare_turn(self._contract, effective)
            record.update(payload_sha256=prepared.payload_sha256,
                          payload_bytes=len(prepared.payload_json.encode("utf-8")))
            directory.mkdir()
            _write_new(directory / "model-payload.json", prepared.payload_json.encode("utf-8"))
            _write_new(directory / "source-request.json", canonical(asdict(request)).encode("utf-8"))
            _write_new(directory / "effective-request.json", prepared.source_request_json.encode("utf-8"))
            check_deadline()
            capabilities = exchange({"protocol": PROTOCOL, "op": "capabilities",
                                     "contract_sha256": prepared.contract_sha256}, "capabilities")
            check_capabilities(self._contract, capabilities)
            count = exchange({"protocol": PROTOCOL, "op": "count",
                              "contract_sha256": prepared.contract_sha256,
                              "payload_json": prepared.payload_json, "payload_sha256": prepared.payload_sha256}, "count")
            record["phase"] = "admission"
            check_deadline()
            admitted = admit_turn(self._contract, prepared, capabilities=capabilities, count_receipt=count,
                                  ledger=self._client, call_id=call_id)
            raw = exchange(admitted.completion_request_json, "completion")
            self._verify_bound()
            check_deadline()
            completion = accept_completion(self._contract, admitted, raw, ledger=self._client)
            record["completion"] = asdict(completion)
            check_deadline()
            if not completion.usable_action_text:
                raise _BrokerReplyError("unusable_response")
            record["status"] = "ok"
            result = completion.text
        except Exception as exc:
            if isinstance(exc, (ProcessTransportError, _BrokerReplyError)):
                category = exc.category
            elif isinstance(exc, (ContractError, LiveExecutionDisabled)):
                category = "contract_error"
            elif isinstance(exc, TokenBudgetExceeded):
                category = "budget_exceeded"
            elif isinstance(exc, TokenBudgetError):
                category = "ledger_error"
            elif isinstance(exc, TimeoutError):
                category = "timeout"
            else:
                category = "internal_error"
            record["category"] = category
            record["status"] = "failed"
            # reserve/fsync may fail after an in-memory pending record exists.
            try:
                current = self._client.snapshot()
                if current["pending_call_id"] == call_id and not current["halted"]:
                    self._client.settle(call_id, usage=None, outcome="timeout" if category == "timeout" else "unknown")
            except TokenBudgetError:
                record["category"] = "ledger_error"
            result = None
            self._failed = True
        finally:
            record.update(self._ledgers())
            for owner, key in (("client", "candidate_call_admitted"), ("broker", "broker_call_admitted")):
                ledger = record[f"{owner}_ledger"]
                record[key] = None if ledger is None else any(r["call_id"] == call_id for r in ledger["records"])
            if record["broker_ledger_state"] == "not_created":
                record["broker_call_admitted"] = False
            if (record["client_ledger"] is None or not record["client_ledger"]["journal_integrity_verified"]
                    or record["broker_ledger_state"] == "unverified"):
                record.update(status="failed", category="ledger_error")
                result, self._failed = None, True
            try:
                record["backend_trace"] = [json.loads(line) for line in trace.read_bytes().splitlines()] if trace.exists() else []
                original = directory / "original-response.bin"
                if original.exists():
                    raw = original.read_bytes()
                    record["original_response"] = {"file": original.name, "sha256": _hash(raw), "bytes": len(raw)}
            except (OSError, ValueError):
                record.update(status="failed", category="evidence_error")
                result, self._failed = None, True
            record["elapsed_seconds"] = time.monotonic() - started
            if result is not None and time.monotonic() >= deadline:
                # Settlement/readback may finish late. Keep observed known
                # usage, but never release the action after its deadline.
                record.update(status="failed", category="timeout")
                result, self._failed = None, True
        # Sanitized exceptions are constructed outside handlers; no local file
        # paths, backend text, commands or upstream exception context escapes.
        if result is None:
            if record["category"] == "timeout":
                raise TimeoutError("offline broker action deadline elapsed")
            raise _ProtocolFailure("broker_" + record["category"])
        return result

    def snapshot(self) -> dict:
        accounting = self._ledgers()
        client, broker = accounting["client_ledger"], accounting["broker_ledger"]
        failed = (self._failed or client is None or not client["journal_integrity_verified"]
                  or client["halted"] or client["pending_call_id"] is not None
                  or accounting["broker_ledger_state"] == "unverified"
                  or broker is not None and (broker["halted"] or broker["pending_call_id"] is not None))
        result = {
            "evidence_kind": EVIDENCE_KIND, "scenario": self._scenario, "fault_turn": FAULT_TURN,
            "model_execution_enabled": False, "model_pilot_admitted": False,
            "provider_token_limits_verified": False, "model_calls": 0,
            "usage_origin": "fictional_fixture_not_provider",
            "fictional_usage_per_completion": {"input_tokens": FICTIONAL_INPUT_TOKENS,
                                                "output_tokens": FICTIONAL_OUTPUT_TOKENS},
            "provider_cancellation_confirmed": False, "os_sandbox_claimed": False,
            "joint_dispatch_guard_supplied": self._guard is not None,
            "closed": self._closed, "failed": failed,
            "contract_seal_sha256": self._contract_seal["seal_sha256"],
            "experiment_seal_sha256": self._contract.experiment_seal_sha256,
            "implementation_sha256": self._materials, "python_runtime": self._runtime,
            "process_caps": asdict(PROCESS_CAPS), "turns": self._turns, **accounting,
        }
        return json.loads(canonical(result))

    def close(self) -> None:
        self._closed = True
