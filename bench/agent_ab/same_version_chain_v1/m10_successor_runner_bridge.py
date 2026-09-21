"""Jointly sealed, zero-model scientific runner / real broker-core rehearsal.

Only a fixed fictional multi-turn backend is available. Batch run admission,
client call accounting and broker call accounting are separate durable facts.
No function here authorizes or selects a provider, credential or live model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from dataclasses import asdict, replace
from pathlib import Path

from . import guava_m10_successor_runner as scientific
from .m10_successor_adapter_contract import canonical, digest, prepare_turn, seal_contract
from .m10_successor_fixture import (
    FILE, PKG_FILES, PreflightInvariantError, compiler_environment, prepare_fixture,
    validate_fixture,
)
from .m10_successor_protocol import AdapterRequest, BudgetCaps, _run_one_with_factory, aggregate_itt
from .m10_successor_protocol_broker import (
    PROCESS_CAPS as ACTUAL_PROCESS_CAPS, OfflineProtocolBroker, fixed_protocol_contract, inventory,
)
from .m10_successor_run_ledger import RunAdmissionLedger, ledger_policy
from .m10_successor_token_budget import TokenBudgetLedger, TokenLimits


SCHEMA = "m10-successor-runner-broker-joint.v1"
EVIDENCE_KIND = "offline_broker_protocol_rehearsal"
MODEL_EXECUTION_ENABLED = False
SCENARIOS = ("ok", "wrong_model", "missing_usage", "backend_timeout", "invalid_action", "budget_exhaustion")
GLOBAL_LIMITS = TokenLimits(10000, 4096, 14096, 300000, 50000, 144)
EXPECTED_FAILURES = {
    "wrong_model": ("broker_response_error", "completion", "response_error"),
    "missing_usage": ("broker_response_error", "completion", "response_error"),
    "backend_timeout": ("adapter_timeout", "completion", "timeout"),
    "invalid_action": ("invalid_action", "completion", None),
    "budget_exhaustion": ("broker_budget_exceeded", "admission", "budget_exceeded"),
}


def _copy(value):
    return json.loads(canonical(value))


def _limits(scenario: str) -> TokenLimits:
    return (TokenLimits(10000, 4096, 14096, 12000, 50000, 144)
            if scenario == "budget_exhaustion" else GLOBAL_LIMITS)


def _content(experiment: dict, scenario: str) -> dict:
    if type(scenario) is not str or scenario not in SCENARIOS:
        raise PreflightInvariantError("unknown offline bridge scenario")
    if experiment["randomization"]["blocks"] != 1 or len(experiment["randomization"]["schedule"]) != 6:
        raise PreflightInvariantError("bridge rehearsal is exactly one sealed six-run block")
    contract = fixed_protocol_contract(experiment["seal_sha256"], _limits(scenario))
    return {
        "schema": SCHEMA, "evidence_kind": EVIDENCE_KIND,
        "model_execution_enabled": False, "model_pilot_admitted": False,
        "provider_token_limits_verified": False, "model_calls": 0,
        "usage_origin": "fictional_fixture_not_provider", "experiment": _copy(experiment),
        "scenario": scenario, "broker_contract": asdict(contract),
        "broker_contract_seal": seal_contract(contract), "process_caps": asdict(ACTUAL_PROCESS_CAPS),
        "implementation_sha256": inventory(), "run_ledger_policy": ledger_policy(),
        "admission_policy": "atomic_whole_schedule_before_any_adapter_state",
        "failure_policy": "stop_batch_keep_all_admitted_runs_no_resume_or_replacement",
        "timeout_policy": "min_scientific_request_and_fixed_broker_cap_includes_guards",
        "guard_policy": "full_preflight_per_run_current_joint_materials_before_each_frame",
    }


def build_joint_manifest(experiment: dict, scenario: str = "ok") -> dict:
    scientific.verify_sealed_manifest(experiment)
    content = _content(experiment, scenario)
    return {**content, "seal_sha256": digest(canonical(content))}


def verify_joint_manifest(joint: dict, *, full_preflight: bool = True,
                          admitted_joint_sha256: str | None = None) -> dict:
    """Reacquire actual local materials; never accept a rehashed altered plan."""
    try:
        content = {k: v for k, v in joint.items() if k != "seal_sha256"}
        if joint["seal_sha256"] != digest(canonical(content)):
            raise PreflightInvariantError("joint digest mismatch")
        if not full_preflight and joint["seal_sha256"] != admitted_joint_sha256:
            raise PreflightInvariantError("dispatch joint seal differs from verified admission")
        experiment = joint["experiment"]
        scientific_content = {k: v for k, v in experiment.items() if k != "seal_sha256"}
        if experiment["seal_sha256"] != scientific.sha256_text(scientific.canonical_json(scientific_content)):
            raise PreflightInvariantError("scientific digest mismatch")
        if full_preflight:
            scientific.verify_sealed_manifest(experiment)
        else:
            # Full deterministic proof was checked before admission. Bind all
            # its real inputs on every frame; do not trust only saved PASS flags.
            if (experiment["implementation_sha256"] != scientific._implementation_inventory()
                    or experiment["dependencies"] != scientific._dependency_inventory()
                    or experiment["preflight"]["compiler"] != compiler_environment()):
                raise PreflightInvariantError("scientific material drift")
        if canonical(content) != canonical(_content(experiment, joint["scenario"])):
            raise PreflightInvariantError("joint contract or controls differ from actual fixed bridge")
    except PreflightInvariantError:
        raise
    except Exception as exc:
        raise PreflightInvariantError("invalid joint manifest") from exc
    return {"ok": True, "seal_sha256": joint["seal_sha256"], "model_pilot_admitted": False}


def _run_binding(joint: dict, root: Path, row: dict, messages: list, budgets: BudgetCaps,
                 *, full_preflight: bool, admitted_joint_sha256: str) -> dict:
    if joint["seal_sha256"] != admitted_joint_sha256:
        raise PreflightInvariantError("run joint seal differs from admitted batch")
    receipt = verify_joint_manifest(joint, full_preflight=full_preflight,
                                    admitted_joint_sha256=admitted_joint_sha256)
    experiment = joint["experiment"]
    validate_fixture(root, "t1")
    matches = [r for r in experiment["randomization"]["schedule"] if r["run_id"] == row["run_id"]]
    if (matches != [row] or messages != experiment["inputs"][row["arm"]]
            or asdict(budgets) != experiment["execution"]["budgets"]
            or scientific.ACTION_SCHEMAS != experiment["action_schemas"]):
        raise PreflightInvariantError("run inputs, schedule, schemas or budgets differ from joint seal")
    return receipt


def _dispatch_guard(joint: dict, pinned: str, runs: RunAdmissionLedger,
                    root: Path, row: dict, messages: list, budgets: BudgetCaps) -> None:
    state = runs.snapshot()
    if (not state["journal_integrity_verified"] or state["halted"]
            or state["joint_seal_sha256"] != pinned or state["pending_run_id"] != row["run_id"]):
        raise PreflightInvariantError("no intact active experiment admission")
    _run_binding(joint, root, row, messages, budgets, full_preflight=False,
                 admitted_joint_sha256=pinned)


def _snapshot_token_journal(path: Path, limits: TokenLimits) -> dict | None:
    if not path.exists():
        return None
    with TokenBudgetLedger(path, limits) as ledger:
        return ledger.snapshot()


def run_joint_batch(joint: dict, output: Path) -> dict:
    """One sealed six-run batch; failure stops dispatch, never shrinks ITT."""
    joint = _copy(joint)
    verify_joint_manifest(joint)
    pinned_joint_sha256 = joint["seal_sha256"]
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "joint-manifest.json").write_text(canonical(joint) + "\n")
    experiment, scenario = joint["experiment"], joint["scenario"]
    schedule = experiment["randomization"]["schedule"]
    run_ids = [row["run_id"] for row in schedule]
    budgets = BudgetCaps(**experiment["execution"]["budgets"])
    limits = _limits(scenario)
    contract = fixed_protocol_contract(experiment["seal_sha256"], limits)
    stopped = None
    client_snapshot = None
    broker_snapshot = None
    integrity_observations = []

    def observe(boundary, snapshot):
        # Fresh readback can corroborate but never erase prior uncertainty.
        verified = snapshot is not None and snapshot.get("journal_integrity_verified") is True
        integrity_observations.append({"boundary": boundary, "journal_integrity_verified": verified})
        return verified

    with tempfile.TemporaryDirectory(prefix="m10-bridge-template-") as directory:
        template = Path(directory)
        prepare_fixture(template, "t1")
        validate_fixture(template, "t1")
        # Constructor publishes the complete schedule atomically and fsyncs it.
        # There is no client ledger or adapter state before this boundary.
        with RunAdmissionLedger(output / "runs.jsonl", joint["seal_sha256"], run_ids) as runs:
            try:
                with TokenBudgetLedger(output / "client-tokens.jsonl", limits) as client:
                    for row in schedule:
                        current = client.snapshot()
                        if not observe("client_before_run:" + row["run_id"], current):
                            stopped = "token_ledger_integrity_failure"
                            break
                        if current["halted"]:
                            stopped = "shared_client_ledger_halted"
                            break
                        messages = _copy(experiment["inputs"][row["arm"]])
                        guard = lambda: _dispatch_guard(joint, pinned_joint_sha256, runs,
                                                        template, row, messages, budgets)
                        factory = lambda: OfflineProtocolBroker(
                            contract, client_ledger=client,
                            broker_ledger_path=output / "broker-tokens.jsonl",
                            evidence_dir=output / "transport" / row["run_id"],
                            scenario="ok" if scenario == "budget_exhaustion" else scenario,
                            verify_before_dispatch=guard,
                        )
                        record = _run_one_with_factory(
                            template, messages, adapter_factory=factory, budgets=budgets,
                            compile_fn=scientific.compile_check,
                            score_fn=lambda current: scientific.score_placement_ast((current / FILE).read_text()),
                            verify=lambda: _run_binding(joint, template, row, messages, budgets,
                                                        full_preflight=True, admitted_joint_sha256=pinned_joint_sha256),
                            source_files=PKG_FILES, allowed_edit_paths=(FILE,),
                            run_id=row["run_id"], evidence_kind=EVIDENCE_KIND,
                            on_admit=lambda: runs.start(row["run_id"]),
                            adapter_evidence=lambda adapter: adapter.snapshot(),
                        )
                        evidence = record.adapter_evidence
                        for owner in ("client", "broker"):
                            key = owner + "_ledger"
                            if key in evidence:
                                observe(key + "_after_run:" + row["run_id"], evidence[key])
                        # Snapshot failure is evaluator-visible, not an action.
                        # Do not allow a successful action loop to certify a
                        # failed/uncertain final transport lifecycle.
                        if record.protocol_ok and (
                                evidence.get("failed") is not False
                                or evidence.get("closed") is not True
                                or any(evidence.get(owner + "_ledger") is None or
                                       evidence[owner + "_ledger"].get("journal_integrity_verified") is not True
                                       for owner in ("client", "broker"))):
                            record.protocol_ok = False
                            record.protocol_status = "failed"
                            record.failure_reason = "adapter_final_state_unverified"
                        runs.complete(asdict(record))
                        (output / (row["run_id"] + ".json")).write_text(canonical(asdict(record)) + "\n")
                        if not record.protocol_ok:
                            stopped = "protocol_failure"
                            break
                    client_snapshot = client.snapshot()
                    observe("client_before_close", client_snapshot)
            except Exception as exc:
                # The atomic plan remains the denominator even when no record
                # could be returned or the completion write became uncertain.
                stopped = "bridge_error:" + type(exc).__name__
            run_snapshot = runs.snapshot()
            # One atomic snapshot supplies both flags and records; a second
            # read must not discover uncertainty hidden by a cached first flag.
            records = run_snapshot["records"]
            observe("run_ledger_final", run_snapshot)
            if not run_snapshot["journal_integrity_verified"]:
                stopped = "run_ledger_integrity_failure"
    live_client_snapshot = client_snapshot
    try:
        client_snapshot = _snapshot_token_journal(output / "client-tokens.jsonl", limits)
        observe("client_reopened", client_snapshot)
        broker_snapshot = _snapshot_token_journal(output / "broker-tokens.jsonl", limits)
        observe("broker_reopened", broker_snapshot)
    except Exception:
        observe("token_reopen_failed", None)
        stopped = "token_ledger_integrity_failure"
    integrity = bool(integrity_observations) and all(
        item["journal_integrity_verified"] for item in integrity_observations)
    if not integrity:
        stopped = stopped or "journal_integrity_unverified"
    summary = aggregate_itt(records)
    summary.update(
        evidence_kind=EVIDENCE_KIND, scenario=scenario, seal_sha256=joint["seal_sha256"],
        scheduled_runs=len(schedule), retained_run_ids=[r["run_id"] for r in records],
        all_scheduled_runs_retained=len(records) == len(schedule) and {r["run_id"] for r in records} == set(run_ids),
        stop_reason=stopped, journal_integrity_verified=bool(integrity),
        model_calls=0, model_execution_enabled=False, model_pilot_admitted=False,
        provider_token_limits_verified=False, usage_origin="fictional_fixture_not_provider",
        offline_bridge_complete=bool(integrity) and stopped is None and summary["joint_success"] == len(schedule),
    )
    (output / "run-records.json").write_text(canonical(records) + "\n")
    (output / "accounting.json").write_text(canonical({"runs": run_snapshot, "client": client_snapshot,
                                                       "broker": broker_snapshot,
                                                       "client_before_close": live_client_snapshot,
                                                       "integrity_observations": integrity_observations}) + "\n")
    (output / "summary.json").write_text(canonical(summary) + "\n")
    return summary


def verify_batch_evidence(output: Path) -> dict:
    """Check exact positive/negative paths, raw evidence and reopened journals.

    A generic early failure must never stand in for the intended third-turn
    fault. This is a known-answer infrastructure oracle, not a model scorer.
    """
    output = Path(output)

    def require(condition, reason):
        if not condition:
            raise ValueError("bridge evidence: " + reason)

    def read(name):
        return json.loads((output / name).read_bytes())

    def raw_file(directory, name, expected_hash, expected_size):
        require(type(name) is str and Path(name).name == name, "unsafe evidence filename")
        raw = (directory / name).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == expected_hash and len(raw) == expected_size,
                "raw evidence hash/size")
        return raw

    joint, summary, records, accounting = (read(name) for name in
        ("joint-manifest.json", "summary.json", "run-records.json", "accounting.json"))
    verify_joint_manifest(joint)
    scenario = joint["scenario"]
    success, exhausted = scenario == "ok", scenario == "budget_exhaustion"
    schedule = joint["experiment"]["randomization"]["schedule"]
    run_ids = [row["run_id"] for row in schedule]
    require(len(records) == 6 and [r["run_id"] for r in records] == run_ids, "complete ordered ITT")
    require(summary["denominator"] == summary["scheduled_runs"] == 6
            and summary["all_scheduled_runs_retained"]
            and summary["retained_run_ids"] == run_ids
            and summary["journal_integrity_verified"], "summary admission/integrity")
    calculated = aggregate_itt(records)
    for key, value in calculated.items():
        if key != "evidence_kind":
            require(summary[key] == value, "independently aggregated " + key)
    for value in (joint, summary):
        require(value["model_calls"] == 0 and value["model_execution_enabled"] is False
                and value["model_pilot_admitted"] is False
                and value["provider_token_limits_verified"] is False, "offline flags")
    require(summary["offline_bridge_complete"] is success
            and summary["stop_reason"] == (None if success else "protocol_failure"), "exact stop boundary")
    require(summary["protocol_complete"] == (6 if success else 0)
            and summary["semantic_pass"] == (6 if success else 0)
            and summary["compile_pass"] == (6 if success else 1)
            and summary["semantic_unknown"] == (0 if success else 5)
            and summary["compile_unknown"] == (0 if success else 5), "independent evaluation outcomes")
    runs = accounting["runs"]
    require(accounting["integrity_observations"] and
            all(item["journal_integrity_verified"] is True for item in accounting["integrity_observations"]),
            "monotonic integrity observations")
    require(runs["admitted_runs"] == runs["denominator"] == 6
            and runs["started_runs"] == runs["completed_runs"] == (6 if success else 1)
            and runs["pending_run_id"] is None
            and runs["not_started_run_ids"] == ([] if success else run_ids[1:]), "run journal boundaries")
    with RunAdmissionLedger(output / "runs.jsonl", joint["seal_sha256"], run_ids) as recovered:
        require(recovered.snapshot()["inspection_only"] is True
                and recovered.snapshot()["journal_integrity_verified"]
                and recovered.records() == records, "reopened run journal")
    for owner in ("client", "broker"):
        reopened = _snapshot_token_journal(output / (owner + "-tokens.jsonl"), _limits(scenario))
        require(reopened == accounting[owner], "reopened " + owner + " journal")
        require(reopened["journal_integrity_verified"], owner + " integrity")
    limits = _limits(scenario)
    contract = fixed_protocol_contract(joint["experiment"]["seal_sha256"], limits)
    by_arm, attempts, completions, raw_files = {}, 0, 0, 0
    for index, (row, record) in enumerate(zip(schedule, records)):
        require(record["admitted"] is True and record["itt_included"] is True
                and record["durable_ledger"] is True and record["seal_sha256"] == joint["seal_sha256"]
                and record["evidence_kind"] == EVIDENCE_KIND, "record admission binding")
        if not success and index > 0:
            require(record["run_ledger_state"] == "not_started"
                    and record["failure_reason"] == "not_started_after_batch_admission"
                    and not record.get("adapter_evidence"), "not-started runs retained without execution")
            continue
        evidence = record["adapter_evidence"]
        require(evidence["closed"] and evidence["joint_dispatch_guard_supplied"]
                and evidence["model_calls"] == 0 and not evidence["model_execution_enabled"]
                and not evidence["model_pilot_admitted"] and not evidence["provider_token_limits_verified"],
                "adapter offline lifecycle")
        turns = evidence["turns"]
        require(len(turns) == record["usage"]["turns"] == (5 if success else 3), "exact fault turn")
        if not success:
            reason, phase, category = EXPECTED_FAILURES[scenario]
            require(record["failure_reason"] == reason and turns[-1]["phase"] == phase
                    and turns[-1]["category"] == category, "intended failure, not incidental failure")
        trajectory = []
        messages = _copy(joint["experiment"]["inputs"][row["arm"]])
        for number, turn in enumerate(turns, 1):
            final_fault = not success and number == 3
            budget_fault = final_fault and exhausted
            timeout_fault = final_fault and scenario == "backend_timeout"
            require(turn["turn"] == number and turn["status"] ==
                    ("failed" if final_fault and scenario != "invalid_action" else "ok"), "turn status")
            directory = output / "transport" / row["run_id"] / f"turn-{number:04d}"
            source = turn["source_request"]
            require(source["messages"] == messages, "full prior action and tool history")
            request = AdapterRequest(**{**source, "messages": tuple(source["messages"])})
            effective = replace(request, timeout_seconds=min(request.timeout_seconds, contract.timeout_seconds))
            prepared = prepare_turn(contract, effective)
            payload = raw_file(directory, "model-payload.json", turn["payload_sha256"], turn["payload_bytes"])
            require(payload.decode() == prepared.payload_json, "canonical full payload")
            require((directory / "source-request.json").read_text() == canonical(source)
                    and (directory / "effective-request.json").read_text() == prepared.source_request_json,
                    "declared and effective request evidence")
            require(turn["effective_timeout_seconds"] == effective.timeout_seconds
                    and turn["declared_timeout_seconds"] == request.timeout_seconds, "deadline cap")
            for hidden in (*run_ids, *scientific.ARMS, turn["call_id"], str(output.resolve()), joint["seal_sha256"]):
                require(hidden not in payload.decode(), "control plane identity leak")
            trajectory.append(payload)
            phases = ["capabilities", "count"] + ([] if budget_fault else ["completion"])
            require([f["phase"] for f in turn["wire_frames"]] == phases
                    and [a["phase"] for a in turn["process_attempts"]] == phases, "no retry or missing phase")
            deadlines = {a["deadline_monotonic"] for a in turn["process_attempts"]}
            require(len(deadlines) == 1, "one absolute deadline")
            attempts += len(phases)
            trace = [json.loads(line) for line in (directory / "backend-events.jsonl").read_bytes().splitlines()]
            operations = ["capabilities", "count"] + ([] if budget_fault else ["capabilities", "count", "complete"])
            require(trace == turn["backend_trace"] and [e["operation"] for e in trace] == operations,
                    "independent backend trace")
            completions += sum(e["operation"] == "complete" for e in trace)
            for event in trace:
                require(event["fictional"] is True and event["deadline_monotonic"] in deadlines, "backend deadline")
                if event["operation"] != "capabilities":
                    require(event["payload_json"] == prepared.payload_json
                            and event["payload_sha256"] == turn["payload_sha256"]
                            and event["output_cap"] == contract.limits.output_per_turn, "backend count/cap/full history")
            for frame in turn["wire_frames"]:
                raw_file(directory, frame["request_file"], frame["request_sha256"], frame["request_bytes"])
                raw_files += 1
                if frame.get("receipt_file"):
                    raw_file(directory, frame["receipt_file"], frame["receipt_sha256"], frame["receipt_bytes"])
                    raw_files += 1
            require(turn["candidate_call_admitted"] is not budget_fault
                    and turn["broker_call_admitted"] is not budget_fault, "call admission boundary")
            original = turn["original_response"]
            if timeout_fault or budget_fault:
                require(original is None and not (directory / "original-response.bin").exists(), "no invented original")
            else:
                raw = raw_file(directory, original["file"], original["sha256"], original["bytes"])
                raw_files += 1
                body = json.loads(raw)
                require(body["fixture_provenance"] == "original_backend_field_not_added_by_broker", "original fields")
                require(body["model"] == ("wrong-fictional-model" if final_fault and scenario == "wrong_model"
                                         else contract.response_model), "original identity")
                if final_fault and scenario == "missing_usage":
                    require("usage" not in body, "missing usage fault")
                else:
                    require(body["usage"] == {"prompt_tokens": 6000, "completion_tokens": 32,
                                             "total_tokens": 6032}, "original known usage")
                if turn["status"] == "ok":
                    receipt = json.loads((directory / "03-completion.receipt.bin").read_bytes())
                    require(receipt["response"] == body, "original response not rewritten")
            if number <= len(record["transcript"]):
                entry = record["transcript"][number - 1]
                if "action" in entry:
                    messages.append({"role": "assistant", "content": entry["response"]})
                    if "result" in entry:
                        messages.append({"role": "tool", "content": canonical(entry["result"])})
        if success:
            require([entry["action"]["action"] for entry in record["transcript"]] ==
                    ["list", "read_range", "edit", "compile", "final"], "fixed five actions")
        by_arm[row["arm"]] = trajectory
    calls = 30 if success else 2 if exhausted else 3
    require(attempts == (90 if success else 8 if exhausted else 9) and completions == calls, "exact worker/call totals")
    for owner in ("client", "broker"):
        ledger = accounting[owner]
        unknown = scenario in ("missing_usage", "backend_timeout") or owner == "client" and scenario == "wrong_model"
        expected_output = 4160 if unknown else 32 * calls
        require(ledger["admitted_calls"] == calls and ledger["charged_input_tokens"] == 6000 * calls
                and ledger["charged_output_tokens"] == expected_output
                and ledger["unknown_usage_calls"] == int(unknown), owner + " preserved global accounting")
        require(ledger["halted"] is (scenario in ("wrong_model", "missing_usage", "backend_timeout")),
                owner + " terminal halt")
        require(ledger["provider_usage"] == (None if unknown else {
            "input_tokens": 6000 * calls, "output_tokens": 32 * calls, "total_tokens": 6032 * calls}),
            owner + " known usage not invented")
        require(ledger["pending_call_id"] == (records[0]["adapter_evidence"]["turns"][-1]["call_id"]
                if owner == "broker" and scenario == "backend_timeout" else None), owner + " pending recovery")
    if success:
        require(by_arm[scientific.SOURCE_ONLY] == by_arm[scientific.STALE_WITHHELD_SILENT],
                "source-only / silent full trajectory identity")
    return {"ok": True, "scenario": scenario, "admitted_runs": 6, "worker_attempts": attempts,
            "fictional_completions": completions, "raw_files_verified": raw_files,
            "journals_reopened": 3, "model_calls": 0}


def conformance_rehearsal(experiment: dict, output: Path) -> dict:
    """All fixed cases, all plan IDs retained; no result-dependent filtering."""
    if tuple(SCENARIOS) != ("ok", *EXPECTED_FAILURES) or len(set(SCENARIOS)) != 6:
        raise PreflightInvariantError("fixed scenario coverage altered")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    checks, summaries, verifications = {}, [], []
    for scenario in SCENARIOS:
        summary = run_joint_batch(build_joint_manifest(experiment, scenario), output / scenario)
        summaries.append(summary)
        try:
            verification = verify_batch_evidence(output / scenario)
        except Exception as exc:
            verification = {"ok": False, "scenario": scenario, "error": type(exc).__name__,
                            "reason": str(exc)}
        verifications.append(verification)
        (output / scenario / "verification.json").write_text(canonical(verification) + "\n")
        checks[scenario] = verification["ok"] is True
    result = {"evidence_kind": EVIDENCE_KIND, "checks": checks, "batches": len(summaries),
              "all_expected_outcomes": len(checks) == len(SCENARIOS) and all(checks.values()),
              "admitted_runs": sum(s["denominator"] for s in summaries), "model_calls": 0,
              "verifications": verifications,
              "model_pilot_admitted": False, "provider_token_limits_verified": False}
    (output / "summary.json").write_text(canonical(result) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True, help="verified scientific manifest")
    parser.add_argument("--output", type=Path, required=True, help="new evidence directory")
    args = parser.parse_args()
    experiment = json.loads(args.manifest.read_text())
    summary = conformance_rehearsal(experiment, args.output)
    print(canonical(summary))
    raise SystemExit(0 if summary["all_expected_outcomes"] else 1)


if __name__ == "__main__":
    main()
