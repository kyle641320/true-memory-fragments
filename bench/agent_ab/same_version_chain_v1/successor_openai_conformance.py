"""Sealed OpenAI Responses conformance, not a treatment-effect experiment.

No credential lookup on import. Offline commands cannot construct a transport.
Live execution has a separate reviewed admission gate; no pilot command exists.
"""
from __future__ import annotations

import argparse
import dataclasses
from decimal import Decimal
import http.client
import json
import os
import platform
import ssl
import sys
import time
import urllib.request
from pathlib import Path

from .guava_m10_successor_runner import (
    ARMS, ROOT, SOURCE_ONLY, STALE_WITHHELD_SILENT, build_arm_input,
    build_sealed_manifest, run_freshness_preflight,
)
from .m10_successor_protocol import ACTION_SCHEMAS
from .successor_openai_responses import (
    canonical, continuation_input, digest, prepare_request, profile, verify_prepared,
)

SCHEMA = "tmf-independent-successor-openai-responses-conformance-v1"
AUTHORIZATION_ID = "tmf-successor-responses-conformance-20260923-01"
LIVE_STATE_ROOT = Path.home() / ".local/state/tmf-successor/authorizations"
COMMON_NATIVE_PROMPT = """Request exactly one of the supplied local functions per turn.
Source paths are workspace-relative. Functions provide source inspection,
literal replacement edits, and compilation. Request final after compiling your
current edit. The final request must report all changed files and explain the
placement. Functions are executed locally, not by the model provider.
"""
FROZEN_LOCAL_RESULT = canonical({
    "ok": False, "error": "conformance_only_no_tool_execution",
    "probe": "固定回执 / Unicode: λ 雪 🧪; quote=\"; slash=\\; newline=\nend",
})
C3_INPUT = [{"role": "system", "content": "Follow the requested output format."},
            {"role": "user", "content":
             "Write the integers from 1 to 10000, in order, one integer per line. "
             "Do not abbreviate or summarize the list."}]


def plan():
    return {
        "schema": SCHEMA, "authorization_id": AUTHORIZATION_ID,
        "scientific_goal": "new internally controlled experiment, not M10 replication",
        "generation_order": ["C1", "C2", "C3"], "generation_limit": 3,
        "count_order": ["initial-" + str(i) for i in range(6)] +
                       [name + suffix for name in ("C1", "C2", "C3") for suffix in ("-count", "-recount")],
        "count_limit": 12, "input_tokens_per_generation": 10000,
        "total_generation_input_tokens": 30000,
        "output_caps": [4096, 4096, 64], "total_output_tokens": 8256,
        "total_generation_tokens": 38256, "request_timeout_seconds": 90,
        "C1": "SOURCE_ONLY initial scientific input with all seven native functions",
        "C2_rule": "all C1 input + every C1 output item unchanged + one matching function_call_output",
        "C2_preconditions": ["valid C1", "exactly one non-final function call",
                             "at least one reasoning item with nonempty encrypted_content"],
        "C2_local_result": FROZEN_LOCAL_RESULT,
        "C2_result_semantics": "frozen local mediation stub; no actual repository action executed",
        "C3": "last; no tools; same model/reasoning/tier/cache; cap 64",
        "stop": "first count, contract, identity, usage, transport, budget or evidence-insufficiency failure",
        "retry": 0, "fallback": False, "pilot_authorized": False,
        "repair": "test then reseal then independent audit; never reset lifetime authorization budget",
        "price": {"source": "https://developers.openai.com/api/docs/pricing",
                  "verified_date": "2026-09-23", "currency": "USD",
                  "per_million_input": 10, "per_million_cached": 1,
                  "per_million_cache_write": 12.5, "per_million_output": 50,
                  "count_request_price": "unknown", "assume_cache_discount": False,
                  "generation_maximum_including_all_input_cache_write": "0.7878",
                  "all_in_maximum_usd": "unknown: bounded generation plus up to 12 count requests"},
    }


def native_inputs(preflight):
    result = {}
    for arm in ARMS:
        old = build_arm_input(arm, preflight=preflight)
        result[arm] = dataclasses.replace(old, tools_prompt=COMMON_NATIVE_PROMPT).model_messages()
        rendered = canonical(result[arm])
        if any(label in rendered for label in ARMS) or str(ROOT) in rendered:
            raise ValueError("model_visible_identity_leak")
    if result[SOURCE_ONLY] != result[STALE_WITHHELD_SILENT]:
        raise ValueError("source_silent_differ")
    return result


def _inventory():
    here = Path(__file__).resolve().parent
    files = sorted(here.glob("successor_openai_*.py"))
    files += sorted(here.glob("successor_openai_*.json"))
    files += sorted((ROOT / "tests").glob("test_m10_successor_openai_*.py"))
    files += [ROOT / "docs/experiments/successor-openai-responses.md"]
    files += [ROOT / ".github/workflows/ci.yml"]
    return {str(path.relative_to(ROOT)): digest(path.read_bytes()) for path in files}


def build_seal(preflight=None):
    if preflight is None:
        preflight = run_freshness_preflight()
    # Upstream dataclasses contain tuples; its own canonical JSON represents
    # these as arrays. Normalize once at this inter-contract boundary.
    scientific = json.loads(json.dumps(build_sealed_manifest(preflight, blocks=1, seed=20260923),
                                       ensure_ascii=False, allow_nan=False))
    inputs = native_inputs(preflight)
    prepared = {arm: prepare_request(items, ACTION_SCHEMAS) for arm, items in inputs.items()}
    c3 = prepare_request(C3_INPUT, ACTION_SCHEMAS, purpose="output_cap")
    seal = {"schema": SCHEMA, "profile": profile(), "plan": plan(),
            "scientific_materials": scientific,
            "scientific_materials_note": "upstream fixture/gate/oracle attestation, not an inherited provider contract",
            "initial_native_requests": {arm: dataclasses.asdict(p) for arm, p in prepared.items()},
            "cap_probe_request": dataclasses.asdict(c3),
            "native_common_prompt": COMMON_NATIVE_PROMPT,
            "implementation_sha256": _inventory(),
            "transport_runtime": {"python": platform.python_version(), "openssl": ssl.OPENSSL_VERSION,
                                  "module_sha256": {m.__name__: digest(Path(m.__file__).read_bytes())
                                                    for m in (urllib.request, http.client, ssl, json)},
                                  "sdk": "none; standard-library HTTPS with zero retries"},
            "live_pilot_enabled": False}
    seal["seal_sha256"] = digest(canonical(seal))
    return seal


def verify_seal(seal):
    if not isinstance(seal, dict):
        raise ValueError("invalid_seal")
    content = {k: v for k, v in seal.items() if k != "seal_sha256"}
    if seal.get("seal_sha256") != digest(canonical(content)):
        raise ValueError("seal_hash_mismatch")
    # Reacquire production freshness, source, compiler and every included file.
    if canonical(build_seal()) != canonical(seal):
        raise ValueError("seal_reconstruction_mismatch")
    return {"ok": True, "seal_sha256": seal["seal_sha256"], "pilot_authorized": False}


def _prepared(data):
    from .successor_openai_responses import PreparedRequest
    result = PreparedRequest(**data)
    verify_prepared(result)
    return result


def c2_request(c1, observation):
    # continuation_input revalidates raw response/config/provenance, not ok alone.
    items = continuation_input(c1, observation, FROZEN_LOCAL_RESULT)
    if observation["action"]["action"] == "final":
        raise ValueError("C1_final_cannot_test_continuation")
    if not any(item.get("type") == "reasoning" and item.get("encrypted_content")
               for item in observation["output_items"]):
        raise ValueError("C1_encrypted_state_evidence_insufficient")
    return prepare_request(items, ACTION_SCHEMAS)


def execute_sequence(seal, broker):
    """Internal fixed conformance sequence; caller must verify seal/admission.

    Fake tests use the identical path. There is no arm-generation loop: the six
    initial requests are counted only, to check uniform capacity, never sampled.
    """
    report = {"schema": SCHEMA, "seal_sha256": seal["seal_sha256"],
              "purpose": "provider_contract_only_not_experimental_outcome",
              "initial_counts": {}, "steps": {}, "ok": False,
              "live_pilot_executed": False}
    stage = "initial_counts"
    try:
        for index, arm in enumerate(ARMS):
            req = _prepared(seal["initial_native_requests"][arm])
            report["initial_counts"][arm] = broker.count(
                req, operation_id="initial-" + str(index), deadline_monotonic=time.monotonic() + 90)
        if (report["initial_counts"][SOURCE_ONLY] != report["initial_counts"][STALE_WITHHELD_SILENT]
                or any(v > 10000 for v in report["initial_counts"].values())):
            raise ValueError("initial_count_capacity_or_equivalence_failure")
        req = _prepared(seal["initial_native_requests"][SOURCE_ONLY])
        for name in ("C1", "C2", "C3"):
            stage = name
            count = broker.count(req, operation_id=name + "-count",
                                 deadline_monotonic=time.monotonic() + 90)
            observation = broker.complete(req, operation_id=name, expected_input_tokens=count,
                                          deadline_monotonic=time.monotonic() + 90,
                                          expect_cap=name == "C3")
            report["steps"][name] = {"request": dataclasses.asdict(req), "count": count,
                                      "observation": observation}
            if not observation["ok"]:
                raise ValueError("contract_failure")
            if name == "C1":
                req = c2_request(req, observation)
            elif name == "C2":
                req = _prepared(seal["cap_probe_request"])
        report["ok"] = True
    except Exception as exc:
        # Do not expose HTTP/auth exceptions or repair/retry here.
        category = getattr(exc, "category", None)
        if category is None:
            category = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        report["failure"] = {"stage": stage, "category": category}
        if getattr(exc, "receipt", None) is not None:
            report["failure"]["receipt"] = exc.receipt
        broker.journal.halt("conformance_failed")
    finally:
        report["accounting"] = broker.journal.snapshot()
        report["skipped"] = [name for name in ("C1", "C2", "C3") if name not in report["steps"]]
        report["cost"] = cost_summary(report)
    return report


def cost_summary(report):
    observations = [step["observation"] for step in report["steps"].values()]
    rejected = report.get("failure", {}).get("receipt", {}).get("observation")
    if rejected is not None:
        observations.append(rejected)
    known = Decimal(0)
    priced = 0
    for observation in observations:
        usage, details = observation.get("usage"), observation.get("usage_details")
        if not usage or not details:
            continue
        i, o = usage.get("input_tokens"), usage.get("output_tokens")
        c, w = details.get("cached_tokens"), details.get("cache_write_tokens")
        if any(type(n) is not int or n < 0 for n in (i, o, c, w)) or c + w > i:
            continue
        known += (Decimal(i - c - w) * 10 + Decimal(c) + Decimal(w) * Decimal("12.5")
                  + Decimal(o) * 50) / 1_000_000
        priced += 1
    calls = report["accounting"]["generation_requests"]
    return {"currency": "USD", "known_generation_at_frozen_rates": str(known),
            "priced_generation_responses": priced, "generation_attempts": calls,
            "generation_cost_complete": priced == calls,
            "count_attempts": report["accounting"]["count_requests"],
            "count_cost": "unknown" if report["accounting"]["count_requests"] else "0",
            "all_in_cost": "unknown" if report["accounting"]["count_requests"] or priced != calls else str(known),
            "not_invoice": True, "maximum_generation_exposure": "0.7878"}


def validate_audit_receipt(receipt, seal):
    """Human/agent attestation bound to exact bytes; not provider attestation."""
    if (not isinstance(receipt, dict) or receipt.get("verdict") != "READY"
            or receipt.get("seal_sha256") != seal["seal_sha256"]
            or receipt.get("independent_reviewer") in (None, "", "parent")
            or receipt.get("offline_tests_passed") is not True
            or receipt.get("no_blocking_findings") is not True
            or receipt.get("authorization_id") != AUTHORIZATION_ID):
        raise ValueError("independent_audit_not_ready_for_this_seal")


def run_authorized_conformance(seal, audit, *, credential_provider):
    """Only live entry point: exact-seal audit, fixed lifetime ledger, no resume.

    The host supplies a protected credential callback. This module never reads
    a key from configuration, environment, CLI, chat or an evidence file. An
    operator must establish protected egress before supplying that callback.
    No caller-selectable budget/model/prompt/state/output path is accepted.
    """
    from .successor_openai_transport import CountedBroker, OperationJournal, SinglePostTransport

    verify_seal(seal)
    validate_audit_receipt(audit, seal)
    if not callable(credential_provider):
        raise ValueError("protected_credential_callback_required")
    state = LIVE_STATE_ROOT / AUTHORIZATION_ID
    for parent in (state, *state.parents):
        if parent.is_symlink():
            raise ValueError("authorization_state_symlink")
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Exclusive lifetime latch precedes transport construction/credential access.
    # Crashes or a different worktree/output location cannot admit a fresh run.
    admission = {"authorization_id": AUTHORIZATION_ID, "seal_sha256": seal["seal_sha256"],
                 "audit": audit, "created_unix_ns": time.time_ns()}
    latch = state / "admission.json"
    fd = os.open(latch, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(canonical(admission).encode("utf-8"))
        out.flush()
        os.fsync(out.fileno())
    parent_fd = os.open(state, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
    with OperationJournal(state / "operations.jsonl", authorization_id=AUTHORIZATION_ID,
                          seal_sha256=seal["seal_sha256"]) as journal:
        sender = SinglePostTransport(credential_provider)
        broker = CountedBroker(sender, journal, state / "raw")
        report = execute_sequence(seal, broker)
        report["execution"] = "live_openai_provider_conformance"
        report["audit"] = audit
        report["finished_unix_ns"] = time.time_ns()
        with (state / "report.json").open("x", encoding="utf-8") as output:
            output.write(canonical(report) + "\n")
            output.flush()
            os.fsync(output.fileno())
        return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare-seal", "verify-seal"))
    parser.add_argument("--seal", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare-seal":
        result = build_seal()
        args.seal.parent.mkdir(parents=True, exist_ok=True)
        with args.seal.open("x", encoding="utf-8") as output:
            output.write(canonical(result) + "\n")
        print(canonical({"ok": True, "seal_sha256": result["seal_sha256"], "model_calls": 0}))
    else:
        print(canonical(verify_seal(json.loads(args.seal.read_text(encoding="utf-8")))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
