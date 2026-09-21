"""Standalone stdlib-only, fictional broker peer for process conformance.

Executed from a sealed source snapshot with Python -I -S -B. It has no network,
credential, repository import, model, or executable-selection path. All token
counts and model responses below are test fixtures, not provider measurements.
"""

import hashlib
import json
import sys
import time


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main():
    envelope = json.load(sys.stdin)
    contract = envelope["contract"]
    request = envelope["request"]
    scenario = envelope["scenario"]
    seal = envelope["contract_sha256"]
    assert contract["provider_id"] == "tmf-offline-fixture"
    assert contract["endpoint"] == "https://offline.invalid/v1/chat/completions"
    assert contract["request_model"] == "tmf-offline-fixture"
    assert contract["response_model"] == "tmf-offline-fixture-v1"
    assert contract["tokenizer_id"] == "fictional-count-v1"
    assert request["protocol"] == "tmf-successor-broker-v2"
    identity = {k: contract[k] for k in (
        "provider_id", "endpoint", "request_model", "response_model",
        "deployment_revision", "broker_build_sha256", "broker_runtime_sha256")}
    op = request["op"]
    if op == "capabilities":
        assert request["contract_sha256"] == seal
        reply = {
            "protocol": request["protocol"], "op": op, "contract_sha256": seal,
            "identity": identity,
            "tokenizer": {"id": contract["tokenizer_id"], "sha256": contract["tokenizer_sha256"]},
            "semantics": {"stateless": True, "native_tools": False,
                          "network_owner": "broker", "credential_owner": "broker",
                          "max_attempts": 1, "fallback": False, "truncation": False,
                          "input_count": "exact_full_payload",
                          "output_parameter": "max_completion_tokens",
                          "usage": "all_provider_tokens_including_reasoning"},
        }
        if scenario == "legacy_capabilities":
            reply["protocol"] = "tmf-agent-broker-v1"
    elif op == "count":
        assert request["contract_sha256"] == seal
        assert digest(request["payload_json"]) == request["payload_sha256"]
        assert json.loads(request["payload_json"])["model"] == contract["request_model"]
        if scenario == "count_timeout":
            time.sleep(3600)
        reply = {
            "protocol": request["protocol"], "op": op, "contract_sha256": seal,
            "payload_sha256": request["payload_sha256"], "tokenizer_id": contract["tokenizer_id"],
            "tokenizer_sha256": contract["tokenizer_sha256"],
            # A deliberately fictional count, labeled as such by the facade.
            "input_tokens": 6000, "exact": scenario != "estimated_count", "generation_calls": 0,
        }
    elif op == "complete":
        assert request["identity"] == identity
        prepared = request["prepared"]
        assert prepared["contract_sha256"] == seal
        assert digest(prepared["payload_json"]) == prepared["payload_sha256"]
        payload = json.loads(prepared["payload_json"])
        assert payload["model"] == contract["request_model"]
        assert payload["max_completion_tokens"] == prepared["max_output_tokens"]
        assert request["max_attempts"] == 1 and request["fallback"] is False
        if scenario == "timeout":
            time.sleep(3600)
        if scenario == "exit_before_reply":
            sys.stderr.write("offline fixture failed\n")
            return 4
        if scenario in ("stdout_flood", "stderr_flood"):
            stream = sys.stdout if scenario == "stdout_flood" else sys.stderr
            while True:
                stream.write("x" * 65536)
                stream.flush()
        reply = {
            "protocol": request["protocol"], "op": op, "call_id": request["call_id"],
            "request_sha256": digest(canonical(request)), "identity": identity,
            "submitted_payload_sha256": prepared["payload_sha256"],
            "submitted_max_completion_tokens": payload["max_completion_tokens"], "attempts": 1,
            "response": {
                "id": "offline-fixture-response", "object": "chat.completion",
                "model": contract["response_model"],
                "choices": [{"index": 0, "finish_reason": "stop", "message": {
                    "role": "assistant", "content": '{"action":"list"}'}}],
                "usage": {"prompt_tokens": 6000, "completion_tokens": 32, "total_tokens": 6032},
            },
        }
        if scenario == "wrong_identity":
            reply["response"]["model"] = "wrong-fixture-model"
        if scenario == "wrong_hash":
            reply["submitted_payload_sha256"] = "0" * 64
        if scenario == "missing_usage":
            del reply["response"]["usage"]
        if scenario == "length":
            reply["response"]["choices"][0]["finish_reason"] = "length"
        if scenario == "refusal":
            reply["response"]["choices"][0]["message"]["refusal"] = "offline fixture refusal"
        if scenario == "malformed_json":
            sys.stdout.write("{not-json\n")
            return 0
    else:
        raise ValueError("unsupported fixture operation")
    sys.stdout.write(canonical(reply) + "\n")
    sys.stdout.flush()
    if op == "complete" and scenario == "extra_frame":
        sys.stdout.write("{}\n")
    if op == "complete" and scenario == "reply_then_exit":
        return 4
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.stderr.write("offline fixture protocol error\n")
        sys.exit(2)
