"""Fixed local backend for exercising the real broker core, never a provider.

The token counts and completions are fictional. No network, credential lookup,
plugin loader, or configurable executable/backend is provided here.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path

from .m10_successor_adapter_contract import BrokerContract, PROTOCOL, canonical, digest
from .m10_successor_token_budget import TokenBudgetLedger, TokenLimits


ROOT = Path(__file__).resolve().parents[3]
SCENARIOS = (
    "ok", "legacy_capabilities", "estimated_count", "count_timeout",
    "backend_timeout", "backend_exception", "malformed_response", "missing_usage",
    "wrong_model", "length", "refusal", "oversize_response",
)
MATERIALS = (
    "bench/agent_ab/same_version_chain_v1/m10_successor_broker_core.py",
    "bench/agent_ab/same_version_chain_v1/m10_successor_broker_fixture.py",
    "bench/agent_ab/same_version_chain_v1/m10_successor_broker_rehearsal.py",
    "bench/agent_ab/same_version_chain_v1/m10_successor_adapter_contract.py",
    "bench/agent_ab/same_version_chain_v1/m10_successor_token_budget.py",
    "bench/agent_ab/same_version_chain_v1/m10_successor_protocol.py",
    "bench/agent_ab/same_version_chain_v1/m10_successor_process_io.py",
    "docs/experiments/guava-m10-successor-adapter-contract.md",
    "docs/experiments/guava-m10-successor-broker-core.md",
)


def inventory() -> dict[str, str]:
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in MATERIALS}


def fixed_contract() -> BrokerContract:
    runtime = {
        "executable_sha256": hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest(),
        "implementation": platform.python_implementation(), "version": platform.python_version(),
    }
    return BrokerContract(
        experiment_seal_sha256="0" * 64,
        provider_id="tmf-broker-core-fixture", endpoint="https://offline.invalid/v1/chat/completions",
        request_model="tmf-broker-core-fixture", response_model="tmf-broker-core-fixture-v1",
        deployment_revision="fictional-local-backend-v1",
        broker_build_sha256=digest(canonical(inventory())), broker_runtime_sha256=digest(canonical(runtime)),
        tokenizer_id="fictional-count-v1", tokenizer_sha256=digest("fictional-count-6000-v1"),
        inference_json=canonical({"temperature": None, "top_p": None, "seed": None, "reasoning_effort": None}),
        limits=TokenLimits(10000, 4096, 14096, 30000, 12288, 24),
        max_request_bytes=120000, max_response_bytes=64000, timeout_seconds=3,
    )


class FixtureBackend:
    """Always fictional. The core, not this fixture, produces v2 completions."""

    def __init__(self, contract: BrokerContract, trace: Path, scenario: str):
        if contract != fixed_contract() or scenario not in SCENARIOS:
            raise ValueError("only the fixed fictional backend is available")
        self.contract, self.trace, self.scenario = contract, trace, scenario

    def _event(self, op: str, **fields) -> None:
        with self.trace.open("ab") as stream:
            stream.write((canonical({"operation": op, "fictional": True, **fields}) + "\n").encode())
            stream.flush()
            os.fsync(stream.fileno())

    def capabilities(self, *, contract_sha256: str, deadline_monotonic: float) -> bytes:
        self._event("capabilities")
        value = {
            "protocol": PROTOCOL, "op": "capabilities", "contract_sha256": contract_sha256,
            "identity": self.contract.identity(),
            "tokenizer": {"id": self.contract.tokenizer_id, "sha256": self.contract.tokenizer_sha256},
            "semantics": {"stateless": True, "native_tools": False, "network_owner": "broker",
                          "credential_owner": "broker", "max_attempts": 1, "fallback": False,
                          "truncation": False, "input_count": "exact_full_payload",
                          "output_parameter": "max_completion_tokens",
                          "usage": "all_provider_tokens_including_reasoning"},
        }
        if self.scenario == "legacy_capabilities":
            value["protocol"] = "tmf-agent-broker-v1"
        return canonical(value).encode()

    def count(self, *, payload_json: str, payload_sha256: str, contract_sha256: str,
              deadline_monotonic: float) -> bytes:
        self._event("count", payload_sha256=digest(payload_json))
        if self.scenario == "count_timeout":
            time.sleep(3600)
        return canonical({
            "protocol": PROTOCOL, "op": "count", "contract_sha256": contract_sha256,
            "payload_sha256": payload_sha256, "tokenizer_id": self.contract.tokenizer_id,
            "tokenizer_sha256": self.contract.tokenizer_sha256, "input_tokens": 6000,
            "exact": self.scenario != "estimated_count", "generation_calls": 0,
        }).encode()

    def complete(self, *, payload_json: str, deadline_monotonic: float,
                 max_response_bytes: int) -> bytes:
        payload = json.loads(payload_json)
        self._event("complete", payload_sha256=digest(payload_json),
                    request_model=payload["model"], output_cap=payload["max_completion_tokens"])
        if self.scenario == "backend_timeout":
            time.sleep(3600)
        if self.scenario == "backend_exception":
            raise RuntimeError("fictional backend detail must remain private")
        if self.scenario == "malformed_response":
            return b"{not-json"
        if self.scenario == "oversize_response":
            return b" " * (max_response_bytes + 1)
        response = {
            "id": "fictional-original-response", "object": "chat.completion",
            "model": self.contract.response_model,
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": '{"action":"list"}'}}],
            "usage": {"prompt_tokens": 6000, "completion_tokens": 32, "total_tokens": 6032},
            "fixture_provenance": "original_backend_field_not_added_by_broker",
        }
        if self.scenario == "missing_usage":
            del response["usage"]
        if self.scenario == "wrong_model":
            response["model"] = "wrong-fictional-model"
        if self.scenario == "length":
            response["choices"][0]["finish_reason"] = "length"
        if self.scenario == "refusal":
            response["choices"][0]["message"]["refusal"] = "fictional refusal"
        return canonical(response).encode()


def worker_main(contract_data: dict, ledger_path: str, trace_path: str, scenario: str,
                deadline_monotonic: float, max_request_frame_bytes: int) -> None:
    """Called only by the parent's fixed sealed script, not a CLI loader."""
    from .m10_successor_broker_core import BrokerCore, BrokerError

    contract_data = dict(contract_data)
    contract_data["limits"] = TokenLimits(**contract_data["limits"])
    contract = BrokerContract(**contract_data)
    if contract != fixed_contract():
        raise ValueError("fixture contract drift")
    if type(max_request_frame_bytes) is not int or max_request_frame_bytes <= 0:
        raise ValueError("invalid fixed worker frame budget")
    raw = sys.stdin.buffer.read(max_request_frame_bytes + 1)
    with TokenBudgetLedger(ledger_path, contract.limits) as ledger:
        try:
            core = BrokerCore(contract, ledger, FixtureBackend(contract, Path(trace_path), scenario),
                              max_request_frame_bytes=max_request_frame_bytes)
            response = core.handle(raw, deadline_monotonic=deadline_monotonic)
        except BrokerError as exc:
            response = canonical({"protocol": PROTOCOL, "error": exc.category}).encode()
    sys.stdout.buffer.write(response)
    sys.stdout.buffer.flush()
