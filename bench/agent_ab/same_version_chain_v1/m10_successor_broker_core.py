"""Server-side v2 broker execution core, without a provider or a live loader.

The server supplies the contract, an independently owned durable ledger, and
an internal backend object. Client frames cannot select an endpoint, model,
tokenizer, token budget, executable, retry policy, or credential source. This
module neither configures a backend nor opens a network/process connection;
the scientific runner and ``execute_model`` remain disabled.

Backend capability/count receipts are validated assertions, not attestation.
A fictional test backend cannot establish provider identity, exact counting,
or real token-cap enforcement. Any real backend and its deployment need a
separate review. In particular, synchronous Python callbacks (and filesystem
operations) cannot be preempted here: deadlines are checked at the boundaries,
and a deployment must supply an external process deadline/isolation guard.
No timeout starts a replacement attempt. Already-durable usage evidence is
never erased just because the accounting/return path runs past its deadline.
"""

from __future__ import annotations

import math
import re
import threading
import time
from dataclasses import asdict, dataclass, replace
from typing import Any, Callable, Protocol

from . import m10_successor_adapter_contract as codec
from .m10_successor_token_budget import (
    TokenBudgetError, TokenBudgetExceeded, TokenBudgetLedger, TokenLimits, TokenUsage,
)


MODEL_EXECUTION_ENABLED = False
_CALL_ID = re.compile(r"[0-9a-f]{32}\Z")
_CATEGORIES = frozenset({
    "request_error", "capability_error", "count_error", "response_error",
    "backend_error", "timeout", "ledger_error", "duplicate_call",
    "budget_exceeded", "internal_error",
})


class BrokerError(RuntimeError):
    """A fixed category, never upstream text, source text, paths, or secrets."""

    def __init__(self, category: str) -> None:
        if type(category) is not str or category not in _CATEGORIES:
            raise ValueError("invalid broker error category")
        self.category = category
        super().__init__(category)


class BrokerBackend(Protocol):
    """Internal seam, not a public plugin/CLI or a verified live backend.

    ``capabilities`` and ``count`` return original v2 receipt bytes. Counting
    must not generate. ``complete`` gets only the canonical upstream payload,
    must make at most one attempt with no fallback, and returns ORIGINAL chat
    completion JSON bytes; it must not repair model/usage or wrap a v2 receipt.
    All methods receive the same effective absolute monotonic deadline.
    """

    def capabilities(self, *, contract_sha256: str,
                     deadline_monotonic: float) -> bytes: ...

    def count(self, *, payload_json: str, payload_sha256: str,
              contract_sha256: str, deadline_monotonic: float) -> bytes: ...

    def complete(self, *, payload_json: str, deadline_monotonic: float,
                 max_response_bytes: int) -> bytes: ...


@dataclass
class _Attempt:
    call_id: str | None = None
    reservation_started: bool = False


def _encoded(value: Any) -> bytes:
    return codec.canonical(value).encode("utf-8")


def _check_deadline(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise BrokerError("timeout")


def _finite(value: Any) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _observed_usage(response: dict) -> TokenUsage | None:
    """Validate original usage independently of output/model acceptability.

    A broker observes bounded upstream bytes even when a wrong identity makes
    those bytes unusable as a client receipt. Keep that known cost; do not
    manufacture usage or repair identity in order to pass the client codec.
    """
    try:
        usage = response.get("usage")
        if type(usage) is not dict:
            return None
        prompt = codec._integer(usage.get("prompt_tokens"), "prompt tokens")
        output = codec._integer(usage.get("completion_tokens"), "completion tokens")
        total = codec._integer(usage.get("total_tokens"), "total tokens")
        if total != prompt + output:
            return None
        for field, component, cap in (("prompt_tokens_details", "cached_tokens", prompt),
                                      ("completion_tokens_details", "reasoning_tokens", output)):
            if usage.get(field) is not None:
                details = usage[field]
                if type(details) is not dict:
                    return None
                if component in details and codec._integer(details[component], component) > cap:
                    return None
        return TokenUsage(prompt, output, total)
    except (codec.ContractError, ValueError, TypeError):
        return None


class BrokerCore:
    """Bounded canonical request bytes -> validated v2 receipt bytes.

    The explicit server-owned ``max_request_frame_bytes`` bounds the whole
    v2 frame independently of the contract's model ``max_request_bytes``.
    ``max_response_bytes`` bounds both original backend bytes and
    the final wrapped receipt; wrapping may therefore reject a near-cap
    upstream response. No truncation is performed. ``max_output_bytes`` is
    independently checked by the client codec during settlement.

    Keep this ledger for the lifetime of its budget, including across process
    restarts. Completed/replayed IDs and uncertain/pending journals cannot be
    used for another backend attempt. A refusal/length receipt can be returned
    with known usage, but its terminal ledger status forbids further calls;
    receipt delivery is not authorization to execute its content as an action.
    """

    def __init__(self, contract: codec.BrokerContract, ledger: TokenBudgetLedger,
                 backend: BrokerBackend, *, max_request_frame_bytes: int) -> None:
        category = None
        try:
            if type(contract) is not codec.BrokerContract:
                raise BrokerError("request_error")
            if type(max_request_frame_bytes) is not int or max_request_frame_bytes <= 0:
                raise BrokerError("request_error")
            self._max_request_frame_bytes = max_request_frame_bytes
            # Own a validated copy, including limits, not a caller-mutable alias.
            self._contract = replace(contract, limits=TokenLimits(**asdict(contract.limits)))
            if type(ledger) is not TokenBudgetLedger:
                raise BrokerError("ledger_error")
            self._ledger = ledger
            self._backend = backend
            self._contract_sha256 = codec.seal_contract(self._contract)["seal_sha256"]
            self._mutex = threading.Lock()
            self._snapshot()
        except BrokerError as error:
            category = error.category
        except TokenBudgetError:
            category = "ledger_error"
        except Exception:
            category = "request_error"
        if category is not None:
            # Outside the handler: no raw exception __context__ or cause leaks.
            raise BrokerError(category)

    def _snapshot(self) -> dict:
        snapshot = self._ledger.snapshot()
        if (not snapshot["journal_integrity_verified"]
                or _encoded(snapshot["limits"]) != _encoded(asdict(self._contract.limits))
                or _encoded(asdict(self._ledger.limits)) != _encoded(asdict(self._contract.limits))):
            raise BrokerError("ledger_error")
        return snapshot

    def _ready(self, call_id: str | None = None) -> dict:
        snapshot = self._snapshot()
        if snapshot["halted"] or snapshot["pending_call_id"] is not None:
            raise BrokerError("ledger_error")
        if call_id is not None and any(r["call_id"] == call_id for r in snapshot["records"]):
            raise BrokerError("duplicate_call")
        if codec.seal_contract(self._contract)["seal_sha256"] != self._contract_sha256:
            raise BrokerError("request_error")
        return snapshot

    def _pending(self, admitted: codec.AdmittedTurn) -> dict:
        snapshot = self._snapshot()
        records = [r for r in snapshot["records"] if r["call_id"] == admitted.call_id]
        if (snapshot["halted"] or snapshot["pending_call_id"] != admitted.call_id
                or len(records) != 1 or records[0]["status"] != "pending"
                or records[0]["request_sha256"] != admitted.request_sha256
                or records[0]["reservation"] != {
                    "input_tokens": admitted.input_tokens,
                    "max_output_tokens": admitted.prepared.max_output_tokens}):
            raise BrokerError("ledger_error")
        return snapshot

    def _invoke(self, method: Callable[..., bytes], *, deadline: float,
                call_id: str | None = None, admitted: codec.AdmittedTurn | None = None,
                **kwargs: Any) -> bytes:
        # Recheck before EVERY callback, not merely once at request entry.
        if admitted is None:
            self._ready(call_id)
        else:
            self._pending(admitted)
        _check_deadline(deadline)
        try:
            raw = method(deadline_monotonic=deadline, **kwargs)
        except TimeoutError:
            raise BrokerError("timeout") from None
        except Exception:
            raise BrokerError("backend_error") from None
        # Completion bytes returned late can still contain known provider
        # usage. The caller records it without accepting/delivering the text.
        if admitted is None:
            _check_deadline(deadline)
        return raw

    def _capabilities(self, deadline: float, call_id: str | None = None) -> bytes:
        raw = self._invoke(self._backend.capabilities, deadline=deadline, call_id=call_id,
                           contract_sha256=self._contract_sha256)
        try:
            codec.check_capabilities(self._contract, raw)
        except Exception:
            raise BrokerError("capability_error") from None
        return raw

    def _payload(self, payload_json: Any, payload_sha256: Any) -> tuple[dict, int]:
        if type(payload_json) is not str or type(payload_sha256) is not str:
            raise BrokerError("request_error")
        try:
            raw = payload_json.encode("utf-8")
            body = codec._strict_json(raw, self._contract.max_request_bytes)
            if _encoded(body) != raw or codec.digest(payload_json) != payload_sha256:
                raise ValueError
            params = codec._strict_json(self._contract.inference_json.encode("utf-8"), 4096)
            expected = {"model": self._contract.request_model, "messages": body.get("messages"),
                        "max_completion_tokens": body.get("max_completion_tokens"),
                        "stream": False, "store": False, "n": 1,
                        **{k: v for k, v in params.items() if v is not None}}
            if _encoded(body) != _encoded(expected):
                raise ValueError
            output = codec._integer(body["max_completion_tokens"], "output", 1)
            if output > self._contract.limits.output_per_turn:
                raise ValueError
            messages = body["messages"]
            if type(messages) is not list or len(messages) < 2 or len(messages) % 2:
                raise ValueError
            for index, message in enumerate(messages):
                codec._keys(message, {"role", "content"}, "message")
                role = "system" if index == 0 else "user" if index % 2 else "assistant"
                if message["role"] != role or type(message["content"]) is not str:
                    raise ValueError
        except Exception:
            raise BrokerError("request_error") from None
        return body, output

    def _count(self, payload_json: str, payload_sha256: str, output: int,
               deadline: float, call_id: str | None = None) -> tuple[bytes, int]:
        raw = self._invoke(self._backend.count, deadline=deadline, call_id=call_id,
                           payload_json=payload_json, payload_sha256=payload_sha256,
                           contract_sha256=self._contract_sha256)
        try:
            count = codec._strict_json(raw, self._contract.max_response_bytes)
            expected = {"protocol": codec.PROTOCOL, "op": "count",
                        "contract_sha256": self._contract_sha256,
                        "payload_sha256": payload_sha256,
                        "tokenizer_id": self._contract.tokenizer_id,
                        "tokenizer_sha256": self._contract.tokenizer_sha256,
                        "input_tokens": count.get("input_tokens"),
                        "exact": True, "generation_calls": 0}
            if _encoded(count) != _encoded(expected):
                raise ValueError
            tokens = codec._integer(count["input_tokens"], "input tokens", 1)
        except Exception:
            raise BrokerError("count_error") from None
        limits = self._contract.limits
        if tokens > limits.input_per_turn or tokens + output > limits.context_window:
            raise BrokerError("budget_exceeded")
        return raw, tokens

    def _complete(self, message: dict, deadline: float, started: float,
                  attempt: _Attempt) -> bytes:
        try:
            codec._keys(message, {"protocol", "op", "call_id", "identity", "prepared",
                                  "input_tokens", "tokenizer_sha256", "max_attempts", "fallback"},
                        "complete request")
            call_id = message["call_id"]
            if type(call_id) is not str or not _CALL_ID.fullmatch(call_id):
                raise ValueError
            binding = codec._keys(message["prepared"], {
                "contract_sha256", "source_request_json", "payload_json", "payload_sha256",
                "max_output_tokens", "max_output_bytes", "timeout_seconds"}, "prepared")
            prepared = codec.PreparedTurn(**binding)
            codec._check_prepared(self._contract, prepared)
            _, output = self._payload(prepared.payload_json, prepared.payload_sha256)
            supplied_tokens = codec._integer(message["input_tokens"], "input tokens", 1)
            expected = {"protocol": codec.PROTOCOL, "op": "complete", "call_id": call_id,
                        "identity": self._contract.identity(), "prepared": prepared.binding(),
                        "input_tokens": supplied_tokens, "tokenizer_sha256": self._contract.tokenizer_sha256,
                        "max_attempts": 1, "fallback": False}
            if _encoded(message) != _encoded(expected):
                raise ValueError
        except Exception:
            raise BrokerError("request_error") from None
        attempt.call_id = call_id
        deadline = min(deadline, started + prepared.timeout_seconds)
        self._ready(call_id)
        caps = self._capabilities(deadline, call_id)
        count, tokens = self._count(prepared.payload_json, prepared.payload_sha256,
                                    output, deadline, call_id)
        if tokens != supplied_tokens:
            raise BrokerError("count_error")
        self._ready(call_id)
        _check_deadline(deadline)
        # admit_turn independently re-renders and validates the receipts. Its
        # reservation returns only after fsync; failure must never dispatch.
        attempt.reservation_started = True
        admitted = codec.admit_turn(self._contract, prepared, capabilities=caps,
                                   count_receipt=count, ledger=self._ledger, call_id=call_id)
        if admitted.completion_request_json != codec.canonical(message):
            raise BrokerError("request_error")
        upstream = self._invoke(self._backend.complete, deadline=deadline, admitted=admitted,
                               payload_json=prepared.payload_json,
                               max_response_bytes=self._contract.max_response_bytes)
        late = time.monotonic() >= deadline
        try:
            response = codec._strict_json(upstream, self._contract.max_response_bytes)
        except Exception:
            raise BrokerError("timeout" if late else "response_error") from None
        self._pending(admitted)
        if late:
            self._reject_observed(admitted, response, "timeout")
        if (response.get("model") != self._contract.response_model
                or response.get("object") != "chat.completion"
                or type(response.get("id")) is not str or not response["id"]
                or "error" in response):
            self._reject_observed(admitted, response, "response_error")
        try:
            receipt = _encoded({
                "protocol": codec.PROTOCOL, "op": "complete", "call_id": call_id,
                "request_sha256": admitted.request_sha256, "identity": self._contract.identity(),
                "submitted_payload_sha256": prepared.payload_sha256,
                "submitted_max_completion_tokens": prepared.max_output_tokens,
                "attempts": 1, "response": response,
            })
            if len(receipt) > self._contract.max_response_bytes:
                raise ValueError
        except Exception:
            self._reject_observed(admitted, response, "response_error")
        self._pending(admitted)
        if time.monotonic() >= deadline:
            self._reject_observed(admitted, response, "timeout")
        try:
            completion = codec.accept_completion(self._contract, admitted, receipt, ledger=self._ledger)
        except codec.ContractError:
            raise BrokerError("response_error") from None
        snapshot = self._snapshot()
        records = [r for r in snapshot["records"] if r["call_id"] == call_id]
        if (snapshot["pending_call_id"] is not None or len(records) != 1
                or records[0]["request_sha256"] != admitted.request_sha256
                or records[0]["status"] != ("completed" if completion.usable_action_text else "failed")
                or records[0]["provider_usage"] != asdict(completion.usage)
                or snapshot["halted"] != (not completion.usable_action_text)):
            raise BrokerError("ledger_error")
        _check_deadline(deadline)
        return receipt

    def _reject_observed(self, admitted: codec.AdmittedTurn, response: dict,
                         category: str) -> None:
        usage = _observed_usage(response)
        self._ledger.settle(admitted.call_id, usage=usage,
                            outcome="error" if usage is not None else
                            "timeout" if category == "timeout" else "unknown")
        self._snapshot()
        raise BrokerError(category)

    def _abandon(self, attempt: _Attempt, category: str) -> str:
        if not attempt.reservation_started:
            return category
        try:
            snapshot = self._snapshot()
            if snapshot["pending_call_id"] == attempt.call_id and not snapshot["halted"]:
                self._ledger.settle(attempt.call_id, usage=None,
                                    outcome="timeout" if category == "timeout" else "unknown")
            self._snapshot()
        except Exception:
            return "ledger_error"
        return category

    def handle(self, request: bytes, *, deadline_monotonic: float) -> bytes:
        """Handle one frame, or raise only a sanitized ``BrokerError``.

        One effective absolute deadline covers all callbacks. A throwing
        completion callback is unknown, preserves the full reservation,
        and halts the journal. A late callback returning valid observed usage
        retains that cost as a terminal error, without delivering its output.
        If expiry happens after a valid receipt has already been durably settled,
        no receipt is returned but known accounting is preserved. Concurrent/
        reentrant use fails closed without queueing.
        """
        started = time.monotonic()
        attempt = _Attempt()
        category = None
        result = None
        locked = False
        try:
            if not _finite(deadline_monotonic):
                raise BrokerError("request_error")
            deadline = min(deadline_monotonic, started + self._contract.timeout_seconds)
            _check_deadline(deadline)
            locked = self._mutex.acquire(blocking=False)
            if not locked:
                raise BrokerError("ledger_error")
            try:
                message = codec._strict_json(request, self._max_request_frame_bytes)
                if _encoded(message) != request or message.get("protocol") != codec.PROTOCOL:
                    raise ValueError
                op = message.get("op")
                if type(op) is not str or op not in {"capabilities", "count", "complete"}:
                    raise ValueError
            except Exception:
                raise BrokerError("request_error") from None
            if op == "complete":
                result = self._complete(message, deadline, started, attempt)
            else:
                expected = {"protocol", "op", "contract_sha256"}
                if op == "count":
                    expected |= {"payload_json", "payload_sha256"}
                if set(message) != expected or message["contract_sha256"] != self._contract_sha256:
                    raise BrokerError("request_error")
                self._ready()
                if op == "capabilities":
                    result = self._capabilities(deadline)
                else:
                    _, output = self._payload(message["payload_json"], message["payload_sha256"])
                    result, _ = self._count(message["payload_json"], message["payload_sha256"],
                                            output, deadline)
                self._ready()
                _check_deadline(deadline)
        except BrokerError as error:
            category = error.category
        except TokenBudgetExceeded:
            category = "budget_exceeded"
        except TokenBudgetError:
            category = "ledger_error"
        except codec.ContractError:
            category = "request_error"
        except Exception:
            category = "internal_error"
        finally:
            if locked:
                if category is not None:
                    category = self._abandon(attempt, category)
                self._mutex.release()
        if category is not None:
            # Deliberately outside all exception handlers, including cleanup.
            raise BrokerError(category)
        return result
