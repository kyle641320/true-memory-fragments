"""Offline candidate wire contract for a future successor broker.

There is deliberately no socket, subprocess, HTTP client, credential lookup or
model execution path here. These codecs validate supplied bytes, not the truth
of a broker's assertions. The scripted runner still rejects real adapters.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .m10_successor_protocol import AdapterRequest, LiveExecutionDisabled
from .m10_successor_token_budget import TokenBudgetLedger, TokenLimits, TokenUsage


PROTOCOL = "tmf-successor-broker-v2"
RENDERING = "text-actions-chat-v1"
MODEL_EXECUTION_ENABLED = False
EVIDENCE_KIND = "offline_adapter_contract_conformance"
SCHEMA_PREFIX = "\nAction schemas (JSON):\n"
TOOL_RESULT_PREFIX = "Protocol tool result (JSON string):\n"
_ROOT = Path(__file__).resolve().parents[3]
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[0-9a-f]{32}\Z")


class ContractError(ValueError):
    """A request or receipt does not conform; never a reason to retry."""


def canonical(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ContractError("non-JSON value") from exc


def digest(value: str) -> str:
    try:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
    except UnicodeError as exc:
        raise ContractError("invalid UTF-8") from exc


def _integer(value: Any, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ContractError(f"invalid {name}")
    return value


def _keys(value: Any, expected: set[str], name: str) -> dict:
    if type(value) is not dict or set(value) != expected:
        raise ContractError(f"invalid {name} fields")
    return value


def _strict_json(raw: bytes, limit: int) -> dict:
    if type(raw) is not bytes or len(raw) > limit:
        raise ContractError("invalid or oversized receipt")

    def pairs(items: list[tuple[str, Any]]) -> dict:
        result = {}
        for key, value in items:
            if key in result:
                raise ContractError("duplicate JSON key")
            result[key] = value
        return result

    def constant(_: str) -> None:
        raise ContractError("nonfinite JSON number")

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                           parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ContractError("invalid receipt JSON") from exc
    if type(value) is not dict:
        raise ContractError("receipt is not an object")
    return value


@dataclass(frozen=True)
class BrokerContract:
    """Operator-selected pins; equality is not provider attestation.

    There is no default provider, model, tokenizer, context size or token
    budget. The experiment seal and this contract's local implementation seal
    are separate, and both must be retained. Secrets never belong here.
    """

    experiment_seal_sha256: str
    provider_id: str
    endpoint: str
    request_model: str
    response_model: str
    deployment_revision: str
    broker_build_sha256: str
    broker_runtime_sha256: str
    tokenizer_id: str
    tokenizer_sha256: str
    inference_json: str
    limits: TokenLimits
    max_request_bytes: int
    max_response_bytes: int
    timeout_seconds: float

    def __post_init__(self) -> None:
        for name in ("experiment_seal_sha256", "broker_build_sha256",
                     "broker_runtime_sha256", "tokenizer_sha256"):
            if type(getattr(self, name)) is not str or not _HEX.fullmatch(getattr(self, name)):
                raise ContractError(f"invalid {name}")
        for name in ("provider_id", "request_model", "response_model",
                     "deployment_revision", "tokenizer_id"):
            value = getattr(self, name)
            if (type(value) is not str or not value or len(value) > 200
                    or not re.fullmatch(r"[A-Za-z0-9_.:/-]+", value)):
                raise ContractError(f"invalid {name}")
        try:
            url = urlsplit(self.endpoint)
            valid_endpoint = (url.scheme == "https" and url.hostname
                              and url.path == "/v1/chat/completions"
                              and not url.username and not url.password
                              and not url.query and not url.fragment and url.port in (None, 443))
        except (ValueError, TypeError):
            valid_endpoint = False
        if not valid_endpoint:
            raise ContractError("endpoint must be a credential-free HTTPS chat endpoint")
        if type(self.limits) is not TokenLimits:
            raise ContractError("invalid token limits")
        self.limits.validate()
        _integer(self.max_request_bytes, "max_request_bytes", 1)
        _integer(self.max_response_bytes, "max_response_bytes", 1)
        if (type(self.timeout_seconds) not in (int, float)
                or not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0):
            raise ContractError("invalid timeout")
        if type(self.inference_json) is not str:
            raise ContractError("invalid inference JSON")
        try:
            params = _strict_json(self.inference_json.encode("utf-8"), 4096)
        except UnicodeError as exc:
            raise ContractError("invalid inference UTF-8") from exc
        _keys(params, {"temperature", "top_p", "seed", "reasoning_effort"}, "inference")
        for name, low, high in (("temperature", 0, 2), ("top_p", 0, 1)):
            value = params[name]
            if value is not None and (type(value) not in (int, float)
                                      or not math.isfinite(value) or not low <= value <= high):
                raise ContractError(f"invalid {name}")
        if params["seed"] is not None and type(params["seed"]) is not int:
            raise ContractError("invalid seed")
        if params["reasoning_effort"] not in (None, "none", "minimal", "low", "medium", "high", "xhigh", "max"):
            raise ContractError("invalid reasoning_effort")
        if canonical(params) != self.inference_json:
            raise ContractError("inference JSON must be canonical")

    def identity(self) -> dict:
        return {name: getattr(self, name) for name in (
            "provider_id", "endpoint", "request_model", "response_model",
            "deployment_revision", "broker_build_sha256", "broker_runtime_sha256")}


def implementation_inventory() -> dict[str, str]:
    files = [
        "bench/agent_ab/same_version_chain_v1/m10_successor_adapter_contract.py",
        "bench/agent_ab/same_version_chain_v1/m10_successor_token_budget.py",
        "bench/agent_ab/same_version_chain_v1/m10_successor_protocol.py",
        "docs/experiments/guava-m10-successor-adapter-contract.md",
    ]
    return {name: hashlib.sha256((_ROOT / name).read_bytes()).hexdigest() for name in files}


def seal_contract(contract: BrokerContract) -> dict:
    body = {"protocol": PROTOCOL, "rendering": RENDERING, "contract": asdict(contract),
            "implementation_sha256": implementation_inventory(),
            "python": {"implementation": platform.python_implementation(),
                       "version": platform.python_version()},
            "evidence_kind": EVIDENCE_KIND, "model_execution_enabled": False,
            "model_pilot_admitted": False, "provider_token_limits_verified": False}
    return {**body, "seal_sha256": digest(canonical(body))}


@dataclass(frozen=True)
class PreparedTurn:
    contract_sha256: str
    source_request_json: str
    payload_json: str
    payload_sha256: str
    max_output_tokens: int
    max_output_bytes: int
    timeout_seconds: float

    def binding(self) -> dict:
        return asdict(self)


def prepare_turn(contract: BrokerContract, request: AdapterRequest) -> PreparedTurn:
    """Freeze the full text-action history and schemas; never dispatch it.

    Protocol tool results lack native tool_call_id, so they are explicitly
    rendered as quoted user feedback, not falsely sent as native tool messages.
    This common representation is a new, sealed candidate for all conditions.
    """
    if type(request) is not AdapterRequest or request.budget_unit != "utf8_bytes_not_provider_tokens":
        raise ContractError("unsupported adapter request")
    _integer(request.max_output_tokens, "max_output_tokens", 1)
    _integer(request.max_output_bytes, "max_output_bytes", 1)
    if request.max_output_tokens > contract.limits.output_per_turn:
        raise ContractError("output tokens exceed contract")
    if (type(request.timeout_seconds) not in (int, float)
            or not math.isfinite(request.timeout_seconds)
            or not 0 < request.timeout_seconds <= contract.timeout_seconds):
        raise ContractError("timeout exceeds contract")
    if request.max_output_bytes > contract.max_response_bytes:
        raise ContractError("output bytes exceed contract")
    if type(request.action_schemas) is not dict or not request.action_schemas:
        raise ContractError("missing action schemas")
    schemas = canonical(request.action_schemas)
    messages = []
    # The existing protocol starts system/user and appends assistant/tool pairs.
    if len(request.messages) < 2 or len(request.messages) % 2:
        raise ContractError("invalid history sequence")
    for index, message in enumerate(request.messages):
        _keys(message, {"role", "content"}, "message")
        expected_role = "system" if index == 0 else "user" if index == 1 else "assistant" if index % 2 == 0 else "tool"
        if message["role"] != expected_role or type(message["content"]) is not str:
            raise ContractError("invalid history role/content")
        if expected_role == "system":
            messages.append({"role": "system", "content": message["content"] + SCHEMA_PREFIX + schemas})
        elif expected_role == "tool":
            messages.append({"role": "user", "content": TOOL_RESULT_PREFIX + canonical(message["content"])})
        else:
            messages.append(dict(message))
    params = json.loads(contract.inference_json)
    payload = {"model": contract.request_model, "messages": messages,
               "max_completion_tokens": request.max_output_tokens,
               "stream": False, "store": False, "n": 1,
               **{k: v for k, v in params.items() if v is not None}}
    payload_json = canonical(payload)
    if len(payload_json.encode("utf-8")) > contract.max_request_bytes:
        raise ContractError("serialized request exceeds byte cap")
    return PreparedTurn(seal_contract(contract)["seal_sha256"], canonical(asdict(request)), payload_json,
                        digest(payload_json), request.max_output_tokens,
                        request.max_output_bytes, request.timeout_seconds)


def check_capabilities(contract: BrokerContract, raw: bytes) -> None:
    """Structural compatibility only; a self-report cannot authorize a pilot."""
    reply = _strict_json(raw, contract.max_response_bytes)
    expected = {
        "protocol": PROTOCOL, "op": "capabilities",
        "contract_sha256": seal_contract(contract)["seal_sha256"],
        "identity": contract.identity(),
        "tokenizer": {"id": contract.tokenizer_id, "sha256": contract.tokenizer_sha256},
        "semantics": {"stateless": True, "native_tools": False,
                      "network_owner": "broker", "credential_owner": "broker",
                      "max_attempts": 1, "fallback": False, "truncation": False,
                      "input_count": "exact_full_payload",
                      "output_parameter": "max_completion_tokens",
                      "usage": "all_provider_tokens_including_reasoning"},
    }
    # Canonical comparison distinguishes bool from integer, unlike dict ==.
    if canonical(reply) != canonical(expected):
        raise ContractError("incompatible broker capabilities (v1 is not admitted)")


def _check_prepared(contract: BrokerContract, prepared: PreparedTurn) -> None:
    if (type(prepared) is not PreparedTurn
            or prepared.contract_sha256 != seal_contract(contract)["seal_sha256"]
            or digest(prepared.payload_json) != prepared.payload_sha256):
        raise ContractError("prepared request or implementation drift")
    # Re-render, rather than trusting a self-resigned modified provider body.
    try:
        source = _strict_json(prepared.source_request_json.encode("utf-8"),
                              contract.max_request_bytes * 2)
        _keys(source, {"messages", "action_schemas", "max_output_tokens", "max_output_bytes",
                       "timeout_seconds", "budget_unit"}, "source request")
        source["messages"] = tuple(source["messages"])
        expected = prepare_turn(contract, AdapterRequest(**source))
    except (TypeError, UnicodeError) as exc:
        raise ContractError("invalid source request") from exc
    if canonical(asdict(prepared)) != canonical(asdict(expected)):
        raise ContractError("prepared payload/caps/rendering drift")


@dataclass(frozen=True)
class AdmittedTurn:
    call_id: str
    prepared: PreparedTurn
    input_tokens: int
    request_sha256: str
    completion_request_json: str


def admit_turn(contract: BrokerContract, prepared: PreparedTurn, *,
               capabilities: bytes, count_receipt: bytes, ledger: TokenBudgetLedger,
               call_id: str) -> AdmittedTurn:
    """Append a durable reservation, then return broker request bytes only.

    Calling this with an invented count proves only offline ledger behavior.
    There is intentionally no dispatch helper accepting a transport callback.
    """
    _check_prepared(contract, prepared)
    check_capabilities(contract, capabilities)
    if type(call_id) is not str or not _ID.fullmatch(call_id):
        raise ContractError("call ID must be an opaque 32-hex correlation ID")
    if asdict(ledger.limits) != asdict(contract.limits):
        raise ContractError("ledger token limits differ")
    count = _strict_json(count_receipt, contract.max_response_bytes)
    _keys(count, {"protocol", "op", "contract_sha256", "payload_sha256",
                  "tokenizer_id", "tokenizer_sha256", "input_tokens", "exact",
                  "generation_calls"}, "count receipt")
    expected = {"protocol": PROTOCOL, "op": "count", "contract_sha256": prepared.contract_sha256,
                "payload_sha256": prepared.payload_sha256, "tokenizer_id": contract.tokenizer_id,
                "tokenizer_sha256": contract.tokenizer_sha256, "exact": True, "generation_calls": 0}
    if canonical({k: count[k] for k in expected}) != canonical(expected):
        raise ContractError("unbound, estimated or incompatible token count")
    tokens = _integer(count["input_tokens"], "input tokens", 1)
    complete = {"protocol": PROTOCOL, "op": "complete", "call_id": call_id,
                "identity": contract.identity(), "prepared": prepared.binding(),
                "input_tokens": tokens, "tokenizer_sha256": contract.tokenizer_sha256,
                "max_attempts": 1, "fallback": False}
    completion_json = canonical(complete)
    request_sha256 = digest(completion_json)
    ledger.reserve(call_id, input_tokens=tokens, max_output_tokens=prepared.max_output_tokens,
                   request_sha256=request_sha256)
    return AdmittedTurn(call_id, prepared, tokens, request_sha256, completion_json)


@dataclass(frozen=True)
class Completion:
    text: str
    finish_reason: str
    usage: TokenUsage
    response_id: str
    usable_action_text: bool


def accept_completion(contract: BrokerContract, admitted: AdmittedTurn, raw: bytes, *,
                      ledger: TokenBudgetLedger) -> Completion:
    """Settle exactly once; invalid/ambiguous receipts keep the reservation.

    Observed token-limit violations are handed to the ledger before any text
    can reach the action protocol. Known usage is separate from usable output.
    """
    if type(admitted) is not AdmittedTurn:
        raise ContractError("invalid admission")
    snapshot = ledger.snapshot()
    records = [r for r in snapshot["records"] if r["call_id"] == admitted.call_id]
    if (snapshot["pending_call_id"] != admitted.call_id or len(records) != 1
            or records[0]["request_sha256"] != admitted.request_sha256
            or records[0]["reservation"] != {"input_tokens": admitted.input_tokens,
                                             "max_output_tokens": admitted.prepared.max_output_tokens}
            or asdict(ledger.limits) != asdict(contract.limits)):
        raise ContractError("completion has no matching pending reservation")
    try:
        _check_prepared(contract, admitted.prepared)
        complete = {"protocol": PROTOCOL, "op": "complete", "call_id": admitted.call_id,
                    "identity": contract.identity(), "prepared": admitted.prepared.binding(),
                    "input_tokens": admitted.input_tokens, "tokenizer_sha256": contract.tokenizer_sha256,
                    "max_attempts": 1, "fallback": False}
        if (canonical(complete) != admitted.completion_request_json
                or digest(admitted.completion_request_json) != admitted.request_sha256):
            raise ContractError("admission bytes drift")
        reply = _strict_json(raw, contract.max_response_bytes)
        _keys(reply, {"protocol", "op", "call_id", "request_sha256", "identity",
                      "submitted_payload_sha256", "submitted_max_completion_tokens",
                      "attempts", "response"}, "completion receipt")
        expected = {"protocol": PROTOCOL, "op": "complete", "call_id": admitted.call_id,
                    "request_sha256": admitted.request_sha256, "identity": contract.identity(),
                    "submitted_payload_sha256": admitted.prepared.payload_sha256,
                    "submitted_max_completion_tokens": admitted.prepared.max_output_tokens, "attempts": 1}
        if canonical({k: reply[k] for k in expected}) != canonical(expected):
            raise ContractError("completion correlation/identity/cap/attempt mismatch")
        response = reply["response"]
        if (type(response) is not dict or response.get("model") != contract.response_model
                or response.get("object") != "chat.completion"
                or type(response.get("id")) is not str or not response["id"]):
            raise ContractError("missing original provider response identity")
        usage = response.get("usage")
        if type(usage) is not dict:
            raise ContractError("missing provider usage")
        prompt = _integer(usage.get("prompt_tokens"), "prompt tokens")
        output = _integer(usage.get("completion_tokens"), "completion tokens")
        total = _integer(usage.get("total_tokens"), "total tokens")
        if total != prompt + output:
            raise ContractError("provider token sum mismatch")
        for field, component, cap in (("prompt_tokens_details", "cached_tokens", prompt),
                                      ("completion_tokens_details", "reasoning_tokens", output)):
            if usage.get(field) is not None:
                details = usage[field]
                if type(details) is not dict:
                    raise ContractError("malformed provider usage details")
                if component in details and _integer(details[component], component) > cap:
                    raise ContractError("provider usage component exceeds total")
        token_usage = TokenUsage(prompt, output, total)
    except ContractError:
        ledger.settle(admitted.call_id, usage=None, outcome="unknown")
        raise
    # A valid usage receipt remains countable even for a refusal, truncation or
    # malformed content. None of these receives a replacement call or ITT drop.
    choices = response.get("choices")
    text, finish, usable = "", "invalid_response", False
    if type(choices) is list and len(choices) == 1 and type(choices[0]) is dict:
        choice = choices[0]
        message = choice.get("message")
        if (type(choice.get("index")) is int and choice["index"] == 0
                and type(message) is dict and message.get("role") == "assistant"):
            if choice.get("finish_reason") in ("stop", "length", "content_filter"):
                finish = choice["finish_reason"]
            if type(message.get("content")) is str:
                text = message["content"]
            try:
                within_bytes = len(text.encode("utf-8")) <= admitted.prepared.max_output_bytes
            except UnicodeError:
                within_bytes = False
            refusal = message.get("refusal")
            text_only = (refusal is None or type(refusal) is str and not refusal)
            text_only = text_only and message.get("tool_calls") is None and message.get("function_call") is None
            usable = bool(text.strip()) and within_bytes and finish == "stop" and text_only
    ledger.settle(admitted.call_id, usage=token_usage, outcome="success" if usable else "error")
    if prompt != admitted.input_tokens or output > admitted.prepared.max_output_tokens:
        raise ContractError("observed usage violates the reserved token contract")
    return Completion(text if usable else "", finish, token_usage, response["id"], usable)


def execute_model(*_: Any, **__: Any) -> None:
    """Explicit fail-closed boundary; there is no implementation behind it."""
    raise LiveExecutionDisabled("offline contract only; real transport and model pilot are not admitted")
