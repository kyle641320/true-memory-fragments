"""Sealed successor execution with equal external limits and retained ITT.

Requested model/effort are controls, not provider-attested actual identity.
Native internal inference/retry consumption is runtime telemetry, not a
successor pre-reservation boundary. Offline evidence remains explicitly separate.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

from . import guava_m10_successor_runner as science
from .m10_successor_fixture import FILE, PKG_FILES, ROOT, compiler_environment, prepare_fixture, validate_fixture
from .m10_successor_protocol import BudgetCaps, RunRecord, aggregate_itt, _json
from .m10_successor_run_ledger import CODEX_OFFLINE_KIND, CODEX_PILOT_KIND, RunAdmissionLedger, ledger_policy
from .successor_codex_control import (
    EventJournal, RuntimeGuard, TOOL_NAME, digest, durable_directory,
    expected_identity, runtime_profile, verify_event_journal,
)
from .successor_codex_mediation import MediatedWorkspace, RuntimeViolation, bounded_call


SCHEMA = "tmf-successor-codex-joint.v1"
SCENARIOS = ("ok", "wrong_model", "wrong_effort", "missing_identity", "reroute", "effort_drift",
             "config_drift", "tool_bypass", "workspace_escape", "action_budget", "runtime_failure")
EXPECTED_FAILURES = {
    "wrong_model": "requested_configuration_mismatch",
    "wrong_effort": "requested_configuration_mismatch",
    "missing_identity": "requested_configuration_mismatch",
    "reroute": "model_rerouted", "effort_drift": "effort_drift",
    "config_drift": "configuration_drift", "tool_bypass": "tool_bypass",
    "workspace_escape": "invalid_action_schema",
    "action_budget": "action_budget_exceeded", "runtime_failure": "runtime_failure",
}
MODULE_NAMES = ("successor_codex_control.py", "successor_codex_mediation.py",
                "successor_codex_runner.py", "successor_codex_host.py", "successor_codex_live.py",
                "m10_successor_run_ledger.py")


def inventory() -> dict:
    paths = [Path(__file__).parent / name for name in MODULE_NAMES]
    paths += [ROOT / "docs/experiments/successor-codex-runtime.md"]
    paths += sorted((Path(__file__).parent / "successor_codex_live_host").glob("*.mjs"))
    paths += sorted((Path(__file__).parent / "successor_codex_live_host").glob("*.json"))
    return {p.relative_to(ROOT).as_posix(): science.sha256_bytes(p.read_bytes()) for p in paths}


def _content(scientific: dict, host_report: dict) -> dict:
    if scientific["randomization"]["blocks"] != 1 or len(scientific["randomization"]["schedule"]) != 6:
        raise RuntimeViolation("exactly_one_six_run_block_required")
    if scientific["execution"]["budgets"] != asdict(BudgetCaps()):
        raise RuntimeViolation("scientific_budget_drift")
    if scientific["action_schemas"] != science.ACTION_SCHEMAS:
        raise RuntimeViolation("scientific_tools_drift")
    profile = runtime_profile()
    return {"schema": SCHEMA, "scientific": deepcopy(scientific), "profile": profile,
            "control_implementation_sha256": inventory(), "host_qualification": deepcopy(host_report),
            "ledger_policy": ledger_policy(CODEX_OFFLINE_KIND),
            "live_ledger_policy": ledger_policy(CODEX_PILOT_KIND),
            "scope": "execution_layer_only_scientific_materials_unchanged",
            "live_admission": "requested_controls_observable_drift_stop_and_qualified_budget_mediation_not_provider_attestation",
            "live_admission_requires": ["qualified_public_host", "exact_independent_ready_receipt",
                                        "single_use_original_schedule_latch"],
            "model_calls_during_sealing": 0}


def build_manifest(scientific: dict, host_report: dict | None = None) -> dict:
    science.verify_sealed_manifest(scientific)
    if host_report is None:
        host_report = {"verdict": "NOT_READY", "kind": "no_live_host_selected",
                       "missing_capabilities": runtime_profile()["required_host_capabilities"]}
    content = _content(scientific, host_report)
    return {**content, "seal_sha256": digest(content)}


def verify_manifest(manifest: dict, *, full_preflight: bool = True, pinned: str | None = None) -> None:
    try:
        content = {k: v for k, v in manifest.items() if k != "seal_sha256"}
        if manifest["seal_sha256"] != digest(content):
            raise RuntimeViolation("joint_digest_mismatch")
        if not full_preflight and pinned != manifest["seal_sha256"]:
            raise RuntimeViolation("unverified_fast_guard")
        scientific = manifest["scientific"]
        if full_preflight:
            science.verify_sealed_manifest(scientific)
        elif (scientific["implementation_sha256"] != science._implementation_inventory()
              or scientific["dependencies"] != science._dependency_inventory()
              or scientific["preflight"]["compiler"] != compiler_environment()):
            raise RuntimeViolation("scientific_material_drift")
        if content != _content(scientific, manifest["host_qualification"]):
            raise RuntimeViolation("runtime_material_drift")
    except RuntimeViolation:
        raise
    except Exception:
        raise RuntimeViolation("invalid_joint_manifest") from None


def _fixed_actions() -> list[dict]:
    # Same known-answer infrastructure script for ALL arms; not a model result.
    return [{"action": "list"},
            {"action": "read_range", "path": FILE, "start": 1, "end": 260},
            {"action": "edit", "path": FILE,
             "old": "      prepared.subscriber.dispatchEvent(prepared.event);",
             "new": "      hook();\n      prepared.subscriber.dispatchEvent(prepared.event);"},
            {"action": "compile"},
            {"action": "final", "answer": "Added the hook at the handoff.", "files": [FILE]}]


class OfflinePeer:
    """No I/O, provider or configurable script. Cannot be relabelled live."""

    def __init__(self, scenario: str):
        if scenario not in SCENARIOS:
            raise RuntimeViolation("unknown_offline_scenario")
        self.scenario = scenario
        self.aborted = False

    def abort(self, reason: str) -> bool:
        self.aborted = True
        return True

    def run(self, guard: RuntimeGuard, workspace: MediatedWorkspace):
        requested = expected_identity(runtime_profile())
        if self.scenario == "wrong_model":
            requested["request_native_model"] = "other-model"
        if self.scenario == "wrong_effort":
            requested["request_effort"] = "high"
        if self.scenario == "missing_identity":
            requested.pop("request_native_model")
        actions = _fixed_actions()
        if self.scenario == "action_budget":
            actions = [{"action": "list"}] * (BudgetCaps().max_turns + 1)
        workspace.prepare_agent_turn()
        guard.before_agent_turn(requested)
        for index, action in enumerate(actions):
            if self.aborted:
                raise RuntimeViolation("peer_after_abort")
            if index == 1:
                events = {"reroute": "model/rerouted", "effort_drift": "effort_drift",
                          "config_drift": "configuration_drift", "runtime_failure": "runtime_failure"}
                if self.scenario in events:
                    guard.observe({"event": events[self.scenario]})
                if self.scenario == "tool_bypass":
                    guard.tool("exec_command")
                if self.scenario == "workspace_escape":
                    action = {"action": "read_range", "path": "../control.json", "start": 1, "end": 1}
            guard.tool(TOOL_NAME)
            workspace.call(action)
            # Native response completion is telemetry, not a new external turn.
            guard.observe({"event": "inference_completed"})
        guard.end_agent_turn()
        guard.observe({"event": "runtime_completed"})


def run_bounded_peer(peer, guard: RuntimeGuard, workspace: MediatedWorkspace):
    seconds = guard.deadline - time.monotonic()
    if seconds <= 0:
        guard.halt("run_timeout")
    try:
        bounded_call(lambda: peer.run(guard, workspace), seconds)
    except TimeoutError:
        guard.halt("run_timeout")


def _write_bytes(path: Path, data: bytes):
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)


def _write(path: Path, value: dict):
    _write_bytes(path, (_json(value) + "\n").encode("utf-8"))


def scenario_passes(summary: dict) -> bool:
    """Do not turn an unrelated infrastructure failure into a negative PASS."""
    if (summary.get("denominator") != 6 or summary.get("model_calls") != 0
            or summary.get("journal_integrity_verified") is not True):
        return False
    if summary.get("scenario") == "ok":
        return (summary.get("protocol_complete") == 6 and summary.get("joint_success") == 6
                and summary.get("started_runs") == 6 and summary.get("not_started_runs") == 0
                and summary.get("stopped_reason") is None)
    return (summary.get("scenario") in EXPECTED_FAILURES
            and summary.get("stopped_reason") == EXPECTED_FAILURES[summary["scenario"]]
            and summary.get("protocol_complete") == 0 and summary.get("started_runs") == 1
            and summary.get("not_started_runs") == 5)


def rehearse(manifest: dict, output: Path, *, scenario: str = "ok") -> dict:
    """One real-ledger, real-fixture block using a fixed zero-model peer."""
    if scenario not in SCENARIOS:
        raise RuntimeViolation("unknown_offline_scenario")
    return _run_batch(manifest, output, evidence_kind=CODEX_OFFLINE_KIND, scenario=scenario,
                      peer_factory=lambda runtime, diagnostic: OfflinePeer(scenario))


def _run_batch(manifest: dict, output: Path, *, evidence_kind: str, scenario: str,
               peer_factory) -> dict:
    """Shared immutable schedule/accounting/evaluator path; no restart support."""
    live = evidence_kind == CODEX_PILOT_KIND
    manifest = deepcopy(manifest)
    verify_manifest(manifest)
    pinned = manifest["seal_sha256"]
    output = Path(output).absolute()
    if output.exists():
        raise RuntimeViolation("no_resume_or_replacement")
    durable_directory(output)
    _write(output / "manifest.json", manifest)
    scientific = manifest["scientific"]
    rows = scientific["randomization"]["schedule"]
    ids = [row["run_id"] for row in rows]
    stopped = None
    with RunAdmissionLedger(output / "runs.jsonl", pinned, ids, evidence_kind=evidence_kind) as ledger:
        try:
            for row in rows:
                verify_manifest(manifest, full_preflight=False, pinned=pinned)
                if live:
                    from .successor_codex_host import verify_live_materials, HostNotReadyError
                    try:
                        verify_live_materials(manifest["host_qualification"])
                    except HostNotReadyError as exc:
                        raise RuntimeViolation("configuration_drift:" + str(exc)) from None
                ledger.start(row["run_id"])
                began = time.monotonic()
                record = asdict(RunRecord(run_id=row["run_id"], evidence_kind=evidence_kind,
                                           seal_sha256=pinned, durable_ledger=True,
                                           model_execution_enabled=live, model_pilot_admitted=live,
                                           budgets=asdict(BudgetCaps())))
                peer = None
                journal = None
                workspace = None
                guard = None
                with tempfile.TemporaryDirectory(prefix="tmf-codex-private-") as directory:
                    root = Path(directory) / "source"
                    try:
                        prepare_fixture(root, "t1")
                        validate_fixture(root, "t1")
                        journal = EventJournal(output / (row["run_id"] + ".events.jsonl"))
                        peer = peer_factory(Path(directory) / "runtime", output / (row["run_id"] + ".host.log"))
                        guard = RuntimeGuard(manifest["profile"], emit=journal.emit, abort=peer.abort)

                        def active():
                            journal.verify_live()
                            state = ledger.snapshot()
                            if (not state["journal_integrity_verified"] or state["halted"]
                                    or state["pending_run_id"] != row["run_id"]):
                                guard.halt("run_admission_unverified")
                            guard.check()

                        workspace = MediatedWorkspace(
                            root, budgets=BudgetCaps(), compile_fn=science.compile_check,
                            score_fn=lambda p: science.score_placement_ast((p / FILE).read_text()),
                            emit=journal.emit, verify_active=active,
                            initial_messages=scientific["inputs"][row["arm"]])
                        run_bounded_peer(peer, guard, workspace)
                        if not workspace.protocol_ok:
                            raise RuntimeViolation("no_final")
                    except Exception as exc:
                        record["failure_reason"] = exc.category if isinstance(exc, RuntimeViolation) else "runtime_failure:" + type(exc).__name__
                        if guard is not None:
                            try:
                                guard.halt(record["failure_reason"])
                            except RuntimeViolation:
                                pass
                    finally:
                        if workspace is not None:
                            evaluated = workspace.evaluate()
                            snapshot = workspace.snapshot()
                            prior_failure = record["failure_reason"]
                            record.update(snapshot, **evaluated)
                            record["failure_reason"] = prior_failure or snapshot["failure_reason"]
                        if guard is not None:
                            record["adapter_evidence"] = {
                                **(peer.snapshot() if live and peer is not None else {
                                    "kind": "offline_peer_not_native_host_attestation", "model_calls": 0}),
                                "guard": guard.snapshot(),
                            }
                        record["elapsed_seconds"] = time.monotonic() - began
                        if journal is not None:
                            try:
                                record["runtime_evidence_anchor"] = journal.verify_live()
                                verify_event_journal(journal.path, expected=record["runtime_evidence_anchor"])
                            except RuntimeViolation:
                                record["failure_reason"] = record["failure_reason"] or "runtime_evidence_invalid"
                            finally:
                                journal.close()
                        record["protocol_ok"] = bool(record["protocol_ok"] and record["failure_reason"] is None)
                        record["protocol_status"] = "completed" if record["protocol_ok"] else "failed"
                        if not record["protocol_ok"] and record["failure_reason"] is None:
                            record["failure_reason"] = "runtime_incomplete"
                        # Preserve the final artifact, including failed runs, outside model reach.
                        artifact = output / (row["run_id"] + ".Dispatcher.java")
                        if workspace is not None:
                            try:
                                _write_bytes(artifact, workspace.artifact_bytes())
                            except (OSError, RuntimeViolation):
                                record["failure_reason"] = record["failure_reason"] or "final_artifact_unavailable"
                                record["protocol_ok"], record["protocol_status"] = False, "failed"
                ledger.complete(record)
                _write(output / (row["run_id"] + ".json"), record)
                if not record["protocol_ok"]:
                    stopped = record["failure_reason"]
                    break
        except Exception as exc:
            stopped = exc.category if isinstance(exc, RuntimeViolation) else "controller_failure:" + type(exc).__name__
        state = ledger.snapshot()
    summary = aggregate_itt(state["records"])
    summary.update(evidence_kind=evidence_kind, model_calls=None if live else 0,
                   live_model_runs=None if live else 0, model_pilot_admitted=live,
                   scientific_seal_sha256=scientific["seal_sha256"], seal_sha256=pinned,
                   scenario=scenario, stopped_reason=stopped,
                   started_runs=state["started_runs"], not_started_runs=len(state["not_started_run_ids"]),
                   journal_integrity_verified=state["journal_integrity_verified"],
                   readiness="PILOT_STOPPED" if live else "NOT_READY_FOR_LIVE_HOST")
    _write(output / "accounting.json", state)
    _write(output / "summary.json", summary)
    return summary


def frozen_checkout() -> dict:
    """Bind the independent review to a clean, immutable execution checkout."""
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
    if git("status", "--porcelain"):
        raise RuntimeViolation("execution_checkout_not_clean")
    return {"commit": git("rev-parse", "HEAD"),
            "common_dir": str(Path(git("rev-parse", "--path-format=absolute", "--git-common-dir")))}


def check_live_readiness(manifest: dict, readiness: dict | None = None) -> dict:
    """Zero-inference qualification; an audit receipt is not host attestation."""
    from .successor_codex_host import require_live_host
    verify_manifest(manifest)
    require_live_host(manifest["host_qualification"])
    if readiness is None:
        raise RuntimeViolation("independent_readiness_receipt_required")
    checkout = frozen_checkout()
    expected = {"schema": "tmf.successor.independent-readiness.v1", "ready": True,
                "scope": "changed_execution_budget_and_live_bridge_only",
                "commit": checkout["commit"], "seal_sha256": manifest["seal_sha256"],
                "profile_sha256": digest(manifest["profile"]),
                "host_qualification_sha256": digest(manifest["host_qualification"]),
                "blocking_issues": []}
    if (type(readiness) is not dict or not isinstance(readiness.get("reviewer"), str)
            or not readiness["reviewer"].strip()
            or any(type(readiness.get(k)) is not type(v) or readiness.get(k) != v
                   for k, v in expected.items())):
        raise RuntimeViolation("independent_readiness_receipt_mismatch")
    return {"ready": True, "model_calls": 0, "admitted_runs": 0, **expected}


def _claim_original_block(manifest: dict, readiness: dict, output: Path) -> None:
    # The shared Git directory is stable across worktrees and output paths.
    # Claiming is exclusive + durable; it is never released, even on failure.
    checkout = frozen_checkout()
    schedule = manifest["scientific"]["randomization"]
    directory = Path(checkout["common_dir"]) / "successor-pilot-admissions"
    durable_directory(directory)
    claim = directory / (digest(schedule) + ".json")
    try:
        _write(claim, {"schedule": schedule, "seal_sha256": manifest["seal_sha256"],
                       "commit": checkout["commit"], "readiness_sha256": digest(readiness),
                       "output": str(output.absolute()), "no_retry_resume_replacement": True})
    except FileExistsError:
        raise RuntimeViolation("original_pilot_block_already_claimed") from None


def run_live_pilot(manifest: dict, output: Path, *, readiness: dict | None = None,
                   auth_profile_id: str | None = None):
    """Exactly one already-authorized block through the stock subscription host."""
    from .successor_codex_host import create_live_launch, _auth_profile_reference
    from .successor_codex_live import LivePeer
    check_live_readiness(manifest, readiness)
    if (type(auth_profile_id) is not str or _auth_profile_reference(auth_profile_id)
            != manifest["host_qualification"]["auth_profile_ref"]):
        raise RuntimeViolation("subscription_profile_reference_mismatch")
    output = Path(output).absolute()
    if output.exists():
        raise RuntimeViolation("no_resume_or_replacement")
    _claim_original_block(manifest, readiness, output)

    def peer_factory(runtime, diagnostic):
        launch = create_live_launch(runtime, auth_profile_id=auth_profile_id)
        return LivePeer(launch, runtime, diagnostic)

    return _run_batch(manifest, output, evidence_kind=CODEX_PILOT_KIND,
                      scenario="authorized_single_protocol_pilot", peer_factory=peer_factory)


def main(argv=None) -> int:
    from .successor_codex_host import HostNotReadyError
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare-seal", "verify-seal", "rehearse", "check-live-readiness", "run-pilot"))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--host-report", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--readiness", type=Path)
    parser.add_argument("--host-settings", type=Path)
    parser.add_argument("--scenario", choices=SCENARIOS, default="ok")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare-seal":
            scientific = science.build_sealed_manifest(science.run_freshness_preflight(), 1, 20260923)
            host = json.loads(args.host_report.read_text()) if args.host_report else None
            result = build_manifest(scientific, host)
        else:
            if args.manifest is None:
                parser.error("--manifest is required")
            manifest = json.loads(args.manifest.read_text())
            verify_manifest(manifest)
            if args.command == "verify-seal":
                result = {"ok": True, "seal_sha256": manifest["seal_sha256"], "live_admitted": False}
            elif args.command == "rehearse":
                if args.output is None:
                    parser.error("--output is required")
                result = rehearse(manifest, args.output, scenario=args.scenario)
                print(json.dumps(result, indent=2))
                return 0 if scenario_passes(result) else 1
            else:
                readiness = json.loads(args.readiness.read_text()) if args.readiness else None
                if args.command == "check-live-readiness":
                    result = check_live_readiness(manifest, readiness)
                else:
                    if args.output is None or args.host_settings is None:
                        parser.error("--output and --host-settings are required")
                    settings = json.loads(args.host_settings.read_text())
                    result = run_live_pilot(manifest, args.output, readiness=readiness,
                                            auth_profile_id=settings.get("auth_profile_id"))
                    print(json.dumps(result, indent=2))
                    return 0 if result["protocol_complete"] == 6 else 1
        if args.output:
            durable_directory(args.output.parent)
            _write(args.output, result)
        else:
            print(json.dumps(result, indent=2))
        return 0
    except (RuntimeViolation, science.PreflightInvariantError, HostNotReadyError) as exc:
        print(json.dumps({"ready": False, "reason": str(exc), "model_calls": 0,
                          "admitted_runs": 0}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
