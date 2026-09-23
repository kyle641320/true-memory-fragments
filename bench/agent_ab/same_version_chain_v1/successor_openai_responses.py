"""Versioned, pure-data OpenAI Responses profile for the independent successor.

This module does not import a provider SDK, open sockets, read credentials, run
tools, or execute experiments.  It renders one immutable request pair and
inspects raw provider evidence.  Hashes authenticate local artifacts only: they
are not evidence of an immutable provider deployment or tokenizer revision.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any

from .m10_successor_protocol import ACTION_SCHEMAS, _parse_action


PROFILE_VERSION = "tmf-successor-openai-responses-v1"
MODEL = "gpt-6-astra"
ENDPOINT = "https://api.openai.com/v1/responses"
COUNT_ENDPOINT = "https://api.openai.com/v1/responses/input_tokens"
MAX_REQUEST_BYTES = 120_000
MAX_RESPONSE_BYTES = 262_144
MAX_ACTION_BYTES = 16_000
MAX_TOOL_RESULT_BYTES = 24_000
MAX_INPUT_TOKENS = 10_000
SCIENTIFIC_OUTPUT_TOKENS = 4_096
CAP_PROBE_OUTPUT_TOKENS = 64
SCIENTIFIC_FIELDS = (
    "input", "model", "parallel_tool_calls", "reasoning", "text",
    "tool_choice", "tools", "truncation",
)
GENERATION_ONLY_FIELDS = (
    "background", "max_output_tokens", "prompt_cache_options", "service_tier",
    "store", "stream",
)
_ACTION_NAMES = frozenset(("list", "search", "read_range", "read_symbol", "edit", "compile", "final"))


class ResponsesContractError(ValueError):
    """Sanitized local contract violation; never contains provider text."""


def _fail(category: str) -> None:
    raise ResponsesContractError(category)


def _json_value(value: Any) -> None:
    if value is None or type(value) in (bool, int):
        return
    if type(value) is float:
        if math.isfinite(value):
            return
        _fail("nonfinite_json")
    if type(value) is str:
        try:
            value.encode("utf-8")
        except UnicodeError:
            _fail("invalid_unicode")
        return
    if type(value) is list:
        for item in value:
            _json_value(item)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for key, item in value.items():
            _json_value(key)
            _json_value(item)
        return
    _fail("non_json_value")


def canonical(value: Any) -> str:
    """UTF-8 canonical JSON: exact types, finite numbers, no surrogate repair."""
    try:
        _json_value(value)
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False)
    except RecursionError:
        _fail("json_depth_exceeded")


def digest(value: str | bytes) -> str:
    if type(value) is str:
        try:
            value = value.encode("utf-8")
        except UnicodeError:
            _fail("invalid_unicode")
    if type(value) is not bytes:
        _fail("invalid_digest_input")
    return hashlib.sha256(value).hexdigest()


def _load(raw: bytes | str, *, limit: int) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                _fail("duplicate_json_key")
            result[key] = value
        return result

    def constant(_: str) -> None:
        _fail("nonfinite_json")

    if type(raw) is str:
        try:
            raw = raw.encode("utf-8")
        except UnicodeError:
            _fail("invalid_unicode")
    if type(raw) is not bytes:
        _fail("invalid_json_input")
    if len(raw) > limit:
        _fail("json_byte_limit")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                           parse_constant=constant)
        _json_value(value)
        return value
    except ResponsesContractError:
        raise
    except (ValueError, TypeError, UnicodeError, RecursionError):
        _fail("invalid_json")


def _clone(value: Any) -> Any:
    return json.loads(canonical(value))


# The imported historical module exposes a mutable mapping. Snapshot it once so
# later caller mutation cannot silently redefine this provider's tool contract.
_FROZEN_ACTION_SCHEMAS_JSON = canonical(ACTION_SCHEMAS)


def _reasoning() -> dict[str, str]:
    return {"effort": "medium", "context": "all_turns", "mode": "standard"}


def _text() -> dict[str, Any]:
    return {"format": {"type": "text"}, "verbosity": "medium"}


def _generation_controls(cap: int) -> dict[str, Any]:
    return {
        "background": False, "max_output_tokens": cap,
        "prompt_cache_options": {"mode": "implicit", "prewarm": False, "ttl": "30m"},
        "service_tier": "default", "store": False, "stream": False,
    }


def profile() -> dict[str, Any]:
    """Return fresh profile data; mutation cannot alter module configuration."""
    return {
        "profile_version": PROFILE_VERSION,
        "experiment_identity": "independent_successor_not_m10_replication",
        "provider": "openai", "endpoint": ENDPOINT, "count_endpoint": COUNT_ENDPOINT,
        "request_model": MODEL, "response_model": MODEL,
        "reasoning": _reasoning(), "text": _text(),
        "generation_controls": _generation_controls(SCIENTIFIC_OUTPUT_TOKENS),
        "scientific_fields": list(SCIENTIFIC_FIELDS),
        "generation_only_fields": list(GENERATION_ONLY_FIELDS),
        "counted_scientific_request_equals_generated_scientific_request": True,
        "count_mechanism": "official_responses_input_tokens_receipt",
        "count_pricing": "unknown",
        "native_functions": sorted(_ACTION_NAMES),
        "action_schemas_sha256": digest(_FROZEN_ACTION_SCHEMAS_JSON),
        "function_strict": False, "parallel_tool_calls": False,
        "scientific_tool_choice": "required", "truncation": "disabled",
        "provider_hosted_tools": False, "prompt_cache_key": "omitted",
        "explicit_cache_breakpoints": False,
        "response_cache_options": {
            "required": {"mode": "implicit", "ttl": "30m"},
            "optional_null": ["comparison_response_id"],
            "request_only_not_echoed": ["prewarm"],
        },
        "encrypted_reasoning": "require_and_replay_all_returned_items_unchanged",
        "history": {
            "scientific_history": "local_frozen_messages_and_function_results",
            "provider_required_state": "all_original_response_output_items_in_order",
            "transport_metadata": "evidence_only_not_model_input",
            "previous_response_id": "forbidden", "conversation": "forbidden",
        },
        "limits": {
            "max_request_bytes": MAX_REQUEST_BYTES, "max_response_bytes": MAX_RESPONSE_BYTES,
            "max_action_bytes": MAX_ACTION_BYTES, "max_tool_result_bytes": MAX_TOOL_RESULT_BYTES,
            "max_input_tokens": MAX_INPUT_TOKENS,
            "scientific_max_output_tokens": SCIENTIFIC_OUTPUT_TOKENS,
            "output_cap_probe_max_output_tokens": CAP_PROBE_OUTPUT_TOKENS,
            "max_generation_calls": 3, "max_count_requests": 12,
            "max_conformance_input_tokens": 30_000,
            "max_conformance_output_tokens": 8_256,
            "max_attempts_per_request": 1,
        },
        "output_cap_probe": {"purpose": "output_cap", "tools": [], "tool_choice": "none",
                             "required_status": "incomplete", "required_reason": "max_output_tokens"},
        "usage": {
            "settlement": "provider_input_output_total_no_reasoning_double_count",
            "cache_write_missing": "unknown_halt_preserve_aggregate_usage",
            "raw_response": "unmodified_bytes_retained_by_transport",
        },
        "observability": {
            "immutable_deployment_revision": "unavailable",
            "tokenizer_material_revision": "unavailable",
            "local_hashes": "artifact_integrity_not_provider_internal_attestation",
            "exact_count": "provider_claim_with_payload_equality_and_usage_crosscheck",
            "encrypted_reasoning_contents": "opaque_unverifiable",
        },
        "automatic_retry": False, "fallback": False, "automatic_compaction": False,
        "pilot_execution_authorized": False,
    }


def native_tools(action_schemas: dict[str, Any]) -> list[dict[str, Any]]:
    """Lossless native-function projection of the frozen seven local actions."""
    if type(action_schemas) is not dict or set(action_schemas) != _ACTION_NAMES:
        _fail("action_schema_set_mismatch")
    if canonical(action_schemas) != _FROZEN_ACTION_SCHEMAS_JSON:
        _fail("action_schema_drift")
    tools = []
    for name in sorted(action_schemas):
        parameters = _clone(action_schemas[name])
        description = parameters.pop("description")
        del parameters["properties"]["action"]
        parameters["required"].remove("action")
        tools.append({"type": "function", "name": name, "description": description,
                      "parameters": parameters, "strict": False})
    return tools


def _nonempty(value: Any) -> bool:
    return type(value) is str and bool(value.strip())


def _status(item: dict[str, Any], *, allow_incomplete: bool) -> None:
    if "status" in item and item["status"] not in (
        ("completed", "incomplete") if allow_incomplete else ("completed",)
    ):
        _fail("invalid_item_status")


def _output_item(item: Any, *, allow_incomplete: bool = False) -> None:
    if type(item) is not dict:
        _fail("invalid_output_item")
    kind = item.get("type")
    _status(item, allow_incomplete=allow_incomplete)
    if kind == "reasoning":
        if set(item) - {"type", "id", "summary", "content", "encrypted_content", "status"}:
            _fail("unknown_reasoning_field")
        if not _nonempty(item.get("id")) or not _nonempty(item.get("encrypted_content")):
            _fail("missing_encrypted_reasoning")
        for field, expected_type in (("summary", "summary_text"), ("content", "reasoning_text")):
            if field == "content" and item.get(field) is None:
                continue
            if type(item.get(field)) is not list:
                _fail("invalid_reasoning_content")
            for content in item[field]:
                if (type(content) is not dict or set(content) != {"type", "text"}
                        or content["type"] != expected_type or type(content["text"]) is not str):
                    _fail("invalid_reasoning_content")
    elif kind == "message":
        if set(item) - {"type", "id", "role", "content", "status", "phase"}:
            _fail("unknown_message_field")
        if (not _nonempty(item.get("id")) or item.get("role") != "assistant"
                or type(item.get("content")) is not list or "status" not in item):
            _fail("invalid_output_message")
        if "phase" in item and item["phase"] not in ("commentary", "final_answer", None):
            _fail("invalid_message_phase")
        for content in item["content"]:
            if (type(content) is not dict or content.get("type") != "output_text"
                    or type(content.get("text")) is not str
                    or type(content.get("annotations")) is not list
                    or set(content) - {"type", "text", "annotations", "logprobs"}
                    or ("logprobs" in content and type(content["logprobs"]) is not list)):
                _fail("refusal_or_unsupported_output_content")
    elif kind == "function_call":
        if set(item) - {"type", "id", "name", "arguments", "call_id", "status", "async", "caller", "namespace"}:
            _fail("unknown_function_call_field")
        if (not _nonempty(item.get("call_id")) or not _nonempty(item.get("name"))
                or type(item.get("arguments")) is not str
                or ("id" in item and not _nonempty(item["id"]))):
            _fail("invalid_function_call")
        if (item.get("async") is not None and item["async"] is not False) or (
            item.get("caller") is not None and item["caller"] != {"type": "direct"}
        ) or item.get("namespace") is not None:
            _fail("nonlocal_function_execution")
    else:
        _fail("unsupported_output_item")


def _action(call: dict[str, Any], schemas: dict[str, Any]) -> dict[str, Any]:
    if call["name"] not in schemas:
        _fail("unknown_function_name")
    arguments = _load(call["arguments"], limit=MAX_ACTION_BYTES)
    if type(arguments) is not dict or "action" in arguments:
        _fail("invalid_function_arguments")
    action = {"action": call["name"], **arguments}
    action_json = canonical(action)
    if len(action_json.encode("utf-8")) > MAX_ACTION_BYTES:
        _fail("action_byte_limit")
    try:
        return _parse_action(action_json, schemas)
    except (ValueError, TypeError, KeyError, RuntimeError):
        _fail("invalid_function_action_schema")


def _validate_history(items: Any, schemas: dict[str, Any]) -> None:
    if type(items) is not list or not items:
        _fail("empty_or_invalid_input")
    pending: str | None = None
    seen_calls: set[str] = set()
    seen_ids: set[str] = set()
    for item in items:
        if type(item) is not dict:
            _fail("invalid_input_item")
        kind = item.get("type", "message")
        if kind == "message" and item.get("role") in ("system", "developer", "user"):
            if pending is not None:
                _fail("unanswered_function_call")
            if set(item) - {"type", "role", "content"}:
                _fail("unsupported_input_message_field")
            content = item.get("content")
            if type(content) is str:
                continue
            if type(content) is not list or not content:
                _fail("invalid_input_content")
            for block in content:
                if (type(block) is not dict or set(block) != {"type", "text"}
                        or block["type"] != "input_text" or type(block["text"]) is not str):
                    _fail("unsupported_input_content")
        elif kind == "function_call_output":
            if (set(item) != {"type", "call_id", "output"} or pending is None
                    or item.get("call_id") != pending or type(item.get("output")) is not str):
                _fail("invalid_function_result")
            if len(item["output"].encode("utf-8")) > MAX_TOOL_RESULT_BYTES:
                _fail("tool_result_byte_limit")
            pending = None
        else:
            _output_item(item)
            if "id" in item:
                if item["id"] in seen_ids:
                    _fail("duplicate_provider_item_id")
                seen_ids.add(item["id"])
            if kind == "function_call":
                _action(item, schemas)
                if pending is not None or item["call_id"] in seen_calls:
                    _fail("duplicate_or_parallel_function_call")
                pending = item["call_id"]
                seen_calls.add(pending)
    if pending is not None:
        _fail("unanswered_function_call")
    if items[0].get("role") not in ("system", "developer"):
        _fail("missing_common_instruction_message")


@dataclass(frozen=True)
class PreparedRequest:
    count_json: str
    generation_json: str
    scientific_sha256: str
    generation_sha256: str
    action_schemas_json: str
    purpose: str
    max_output_tokens: int


def prepare_request(input_items: list[dict[str, Any]], action_schemas: dict[str, Any],
                    *, purpose: str = "scientific") -> PreparedRequest:
    if purpose not in ("scientific", "output_cap"):
        _fail("invalid_request_purpose")
    schemas = _clone(action_schemas)
    tools = native_tools(schemas)
    items = _clone(input_items)
    _validate_history(items, schemas)
    if purpose == "output_cap" and any(item.get("role") not in ("system", "user") for item in items):
        _fail("output_cap_must_not_reuse_provider_state")
    scientific = {
        "model": MODEL, "input": items,
        "tools": tools if purpose == "scientific" else [],
        "tool_choice": "required" if purpose == "scientific" else "none",
        "parallel_tool_calls": False, "reasoning": _reasoning(),
        "text": _text(), "truncation": "disabled",
    }
    cap = SCIENTIFIC_OUTPUT_TOKENS if purpose == "scientific" else CAP_PROBE_OUTPUT_TOKENS
    count_json = canonical(scientific)
    generation_json = canonical({**scientific, **_generation_controls(cap)})
    if len(generation_json.encode("utf-8")) > MAX_REQUEST_BYTES:
        _fail("request_byte_limit")
    return PreparedRequest(count_json=count_json, generation_json=generation_json,
                           scientific_sha256=digest(count_json), generation_sha256=digest(generation_json),
                           action_schemas_json=canonical(schemas), purpose=purpose, max_output_tokens=cap)


def verify_prepared(prepared: PreparedRequest) -> None:
    """Re-render independently: re-signing a forbidden config does not admit it."""
    if type(prepared) is not PreparedRequest or type(prepared.max_output_tokens) is not int:
        _fail("invalid_prepared_request")
    count = _load(prepared.count_json, limit=MAX_REQUEST_BYTES)
    generation = _load(prepared.generation_json, limit=MAX_REQUEST_BYTES)
    schemas = _load(prepared.action_schemas_json, limit=MAX_REQUEST_BYTES)
    if type(count) is not dict or type(generation) is not dict:
        _fail("invalid_request_object")
    if set(count) != set(SCIENTIFIC_FIELDS) or set(generation) != set(SCIENTIFIC_FIELDS + GENERATION_ONLY_FIELDS):
        _fail("request_field_set_mismatch")
    if {key: generation[key] for key in SCIENTIFIC_FIELDS} != count:
        _fail("count_generation_scientific_mismatch")
    fresh = prepare_request(count["input"], schemas, purpose=prepared.purpose)
    if prepared != fresh:
        _fail("prepared_request_integrity_mismatch")


def parse_count(raw: bytes) -> int:
    """Validate a receipt, not an unavailable independent tokenizer proof."""
    if type(raw) is not bytes:
        _fail("count_must_be_raw_bytes")
    value = _load(raw, limit=MAX_RESPONSE_BYTES)
    if (type(value) is not dict or set(value) != {"object", "input_tokens"}
            or value["object"] != "response.input_tokens"
            or type(value["input_tokens"]) is not int or value["input_tokens"] < 0):
        _fail("invalid_count_receipt")
    return value["input_tokens"]


def _usage(response: dict[str, Any], errors: list[str]) -> tuple[dict[str, int] | None, dict[str, int | None] | None]:
    raw = response.get("usage")
    if type(raw) is not dict:
        errors.append("missing_usage")
        return None, None
    fields = ("input_tokens", "output_tokens", "total_tokens")
    if any(type(raw.get(key)) is not int or raw[key] < 0 for key in fields):
        errors.append("invalid_aggregate_usage")
        return None, None
    usage = {key: raw[key] for key in fields}
    if usage["input_tokens"] + usage["output_tokens"] != usage["total_tokens"]:
        errors.append("contradictory_aggregate_usage")
        return None, None
    if set(raw) - set(fields) - {"input_tokens_details", "output_tokens_details"}:
        errors.append("unknown_usage_semantics")
    for field, allowed in (("input_tokens_details", {"cached_tokens", "cache_write_tokens"}),
                           ("output_tokens_details", {"reasoning_tokens"})):
        if type(raw.get(field)) is dict and set(raw[field]) - allowed:
            errors.append("unknown_usage_detail_semantics")
    details: dict[str, int | None] = {}
    for source, key in (("input_tokens_details", "cached_tokens"),
                        ("input_tokens_details", "cache_write_tokens"),
                        ("output_tokens_details", "reasoning_tokens")):
        source_value = raw.get(source)
        number = source_value.get(key) if type(source_value) is dict else None
        if type(number) is not int or number < 0:
            details[key] = None
            errors.append("missing_or_invalid_" + key)
        else:
            details[key] = number
    cached, writes, reasoning = (details[key] for key in ("cached_tokens", "cache_write_tokens", "reasoning_tokens"))
    if ((cached is not None and cached > usage["input_tokens"])
            or (writes is not None and writes > usage["input_tokens"])
            or (cached is not None and writes is not None and cached + writes > usage["input_tokens"])):
        errors.append("contradictory_input_usage_details")
    if reasoning is not None and reasoning > usage["output_tokens"]:
        errors.append("contradictory_reasoning_usage")
    return usage, details


def inspect_response(raw: bytes, prepared: PreparedRequest, *, expected_input_tokens: int,
                     expect_cap: bool = False) -> dict[str, Any]:
    """Inspect without repairing evidence or discarding known usage on rejection.

    ``ok`` is contract acceptance, not scientific correctness. ``cap_observed``
    records raw termination fields and alone is not an acceptance verdict.
    """
    result: dict[str, Any] = {
        "ok": False, "errors": [], "response": None, "usage": None,
        "usage_details": None, "action": None, "output_items": None,
        "response_id": None, "cap_observed": False,
        "request_sha256": getattr(prepared, "generation_sha256", None),
        "response_sha256": digest(raw) if type(raw) is bytes else None,
        "response_canonical_sha256": None, "expected_input_tokens": expected_input_tokens,
    }
    errors = result["errors"]
    try:
        if type(raw) is not bytes:
            _fail("response_must_be_raw_bytes")
        response = _load(raw, limit=MAX_RESPONSE_BYTES)
        if type(response) is not dict:
            _fail("invalid_response_object")
    except ResponsesContractError as exc:
        errors.append(str(exc))
        return result
    result["response"] = response
    result["response_canonical_sha256"] = digest(canonical(response))
    result["usage"], result["usage_details"] = _usage(response, errors)
    if _nonempty(response.get("id")):
        result["response_id"] = response["id"]
    incomplete = response.get("incomplete_details")
    result["cap_observed"] = response.get("status") == "incomplete" and (
        type(incomplete) is dict and incomplete.get("reason") == "max_output_tokens"
    )
    try:
        verify_prepared(prepared)
    except ResponsesContractError as exc:
        errors.append(str(exc))
        return result
    if type(expected_input_tokens) is not int or not 0 <= expected_input_tokens <= MAX_INPUT_TOKENS:
        errors.append("invalid_expected_input_count")
    if type(expect_cap) is not bool or expect_cap != (prepared.purpose == "output_cap"):
        errors.append("response_purpose_mismatch")
    if response.get("object") != "response":
        errors.append("response_object_mismatch")
    if response.get("model") != MODEL:
        errors.append("response_model_mismatch")
    if result["response_id"] is None:
        errors.append("missing_response_id")
    stamp = response.get("created_at")
    if (type(stamp) not in (int, float) or (type(stamp) is float and not math.isfinite(stamp))
            or stamp < 0):
        errors.append("invalid_response_timestamp")
    generation = json.loads(prepared.generation_json)
    for field in ("parallel_tool_calls", "tool_choice", "tools", "text", "truncation", "background"):
        # Canonical equality distinguishes False from integer 0 as well.
        if field not in response or canonical(response[field]) != canonical(generation[field]):
            errors.append("response_" + field + "_mismatch")
    # The official response schema is not the request schema: prewarm is
    # request-only. Validate observable applied options without inventing an
    # echo for it, or silently dropping unknown response fields.
    cache = response.get("prompt_cache_options")
    if (type(cache) is not dict or set(cache) - {"mode", "ttl", "comparison_response_id"}
            or cache.get("mode") != generation["prompt_cache_options"]["mode"]
            or cache.get("ttl") != generation["prompt_cache_options"]["ttl"]
            or cache.get("comparison_response_id") is not None):
        errors.append("response_prompt_cache_options_mismatch")
    for field in ("store", "stream"):
        if field in response and response[field] is not False:
            errors.append("response_" + field + "_mismatch")
    if response.get("service_tier") != "default":
        errors.append("response_service_tier_mismatch")
    if type(response.get("max_output_tokens")) is not int or response["max_output_tokens"] != prepared.max_output_tokens:
        errors.append("response_output_cap_mismatch")
    reasoning = response.get("reasoning")
    if (type(reasoning) is not dict or any(reasoning.get(key) != value for key, value in _reasoning().items())
            or set(reasoning) - {"effort", "context", "mode", "summary", "generate_summary"}
            or reasoning.get("summary") is not None or reasoning.get("generate_summary") is not None):
        errors.append("response_reasoning_mismatch")
    for field in ("conversation", "previous_response_id", "context_management", "prompt", "prompt_cache_key", "instructions"):
        if response.get(field) is not None:
            errors.append("forbidden_response_" + field)
    if response.get("error") is not None:
        errors.append("provider_response_error")
    if expect_cap:
        if not result["cap_observed"]:
            errors.append("output_cap_evidence_insufficient")
    elif response.get("status") != "completed" or incomplete is not None:
        errors.append("scientific_response_not_completed")
    usage = result["usage"]
    if usage is not None:
        if usage["input_tokens"] != expected_input_tokens:
            errors.append("count_usage_mismatch")
        if usage["output_tokens"] > prepared.max_output_tokens:
            errors.append("output_usage_exceeds_cap")
    output = response.get("output")
    if type(output) is not list:
        errors.append("missing_output_items")
    else:
        result["output_items"] = _clone(output)
        calls: list[dict[str, Any]] = []
        prior_input = json.loads(prepared.count_json)["input"]
        ids: set[str] = {item["id"] for item in prior_input if "id" in item}
        call_ids = {item["call_id"] for item in prior_input if item.get("type") == "function_call"}
        for item in output:
            try:
                _output_item(item, allow_incomplete=expect_cap)
                if "id" in item:
                    if item["id"] in ids:
                        _fail("duplicate_provider_item_id")
                    ids.add(item["id"])
                if item["type"] == "function_call":
                    if item["call_id"] in call_ids:
                        _fail("replayed_function_call_id")
                    call_ids.add(item["call_id"])
                    calls.append(item)
            except ResponsesContractError as exc:
                errors.append(str(exc))
        if expect_cap:
            if calls:
                errors.append("function_call_in_output_cap_probe")
        elif len(calls) != 1:
            errors.append("expected_exactly_one_function_call")
        else:
            try:
                result["action"] = _action(calls[0], json.loads(prepared.action_schemas_json))
            except ResponsesContractError as exc:
                errors.append(str(exc))
    result["errors"] = list(dict.fromkeys(errors))
    result["ok"] = not result["errors"]
    if not result["ok"]:
        result["action"] = None
    return result


def continuation_input(prepared: PreparedRequest, observation: dict[str, Any],
                       frozen_local_result: str) -> list[dict[str, Any]]:
    """C2's deterministic F: complete original history + all output + one result.

    This pure function never executes the proposed tool or selects a convenient
    subset of provider state. The caller freezes the result and rule before C1.
    """
    verify_prepared(prepared)
    if prepared.purpose != "scientific" or type(observation) is not dict or observation.get("ok") is not True:
        _fail("unusable_continuation_observation")
    if observation.get("request_sha256") != prepared.generation_sha256:
        _fail("continuation_request_provenance_mismatch")
    response = observation.get("response")
    response_json = canonical(response)
    if digest(response_json) != observation.get("response_canonical_sha256"):
        _fail("continuation_response_integrity_mismatch")
    checked = inspect_response(response_json.encode("utf-8"), prepared,
                               expected_input_tokens=observation.get("expected_input_tokens"))
    if not checked["ok"] or any(observation.get(field) != checked[field] for field in (
        "errors", "usage", "usage_details", "action", "output_items", "response_id", "cap_observed"
    )):
        _fail("continuation_observation_mismatch")
    if type(frozen_local_result) is not str:
        _fail("invalid_frozen_local_result")
    canonical(frozen_local_result)
    if len(frozen_local_result.encode("utf-8")) > MAX_TOOL_RESULT_BYTES:
        _fail("tool_result_byte_limit")
    calls = [item for item in checked["output_items"] if item["type"] == "function_call"]
    result = _clone(json.loads(prepared.count_json)["input"]) + _clone(checked["output_items"]) + [{
        "type": "function_call_output", "call_id": calls[0]["call_id"], "output": frozen_local_result,
    }]
    # This also enforces total bytes and complete, uniquely paired history.
    prepare_request(result, json.loads(prepared.action_schemas_json))
    return result
