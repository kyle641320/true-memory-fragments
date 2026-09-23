"""Joint scientific/runtime sealing and offline qualification, never a live shim.

The installed Codex host lacks the required pre-inference actual-model gate.
Live admission therefore stops before a process, credential, or run is created.
Offline peers test the controller without substituting fake evidence for it.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

from . import guava_m10_successor_runner as science
from .m10_successor_fixture import FILE, PKG_FILES, ROOT, compiler_environment, prepare_fixture, validate_fixture
from .m10_successor_protocol import BudgetCaps, RunRecord, aggregate_itt, _json
from .m10_successor_run_ledger import CODEX_OFFLINE_KIND, RunAdmissionLedger, ledger_policy
from .successor_codex_control import (
    EventJournal, RuntimeGuard, TOOL_NAME, digest, durable_directory,
    expected_identity, runtime_profile, verify_event_journal,
)
from .successor_codex_mediation import MediatedWorkspace, RuntimeViolation, bounded_call


SCHEMA = "tmf-successor-codex-joint.v1"
SCENARIOS = ("ok", "wrong_model", "wrong_effort", "missing_identity", "reroute", "effort_drift",
             "config_drift", "tool_bypass", "workspace_escape", "action_budget", "runtime_failure")
EXPECTED_FAILURES = {
    "wrong_model": "actual_native_configuration_mismatch",
    "wrong_effort": "actual_native_configuration_mismatch",
    "missing_identity": "actual_native_configuration_mismatch",
    "reroute": "model_rerouted", "effort_drift": "effort_drift",
    "config_drift": "configuration_drift", "tool_bypass": "tool_bypass",
    "workspace_escape": "invalid_action_schema",
    "action_budget": "inference_budget_exceeded", "runtime_failure": "runtime_failure",
}
MODULE_NAMES = ("successor_codex_control.py", "successor_codex_mediation.py",
                "successor_codex_runner.py", "successor_codex_host.py", "m10_successor_run_ledger.py")


def inventory() -> dict:
    paths = [Path(__file__).parent / name for name in MODULE_NAMES]
    paths += [ROOT / "docs/experiments/successor-codex-runtime.md"]
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
            "scope": "execution_layer_only_scientific_materials_unchanged",
            "live_admission": "requires_independently_qualified_host_seam_not_offline_receipts",
            "live_execution_enabled": False, "model_calls": 0}


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
        actual = expected_identity(runtime_profile())
        if self.scenario == "wrong_model":
            actual["resolved_model"] = "other-model"
        if self.scenario == "wrong_effort":
            actual["effort"] = "high"
        if self.scenario == "missing_identity":
            actual.pop("resolved_model")
        actions = _fixed_actions()
        if self.scenario == "action_budget":
            actions = [{"action": "list"}] * (BudgetCaps().max_turns + 1)
        for index, action in enumerate(actions):
            if self.aborted:
                raise RuntimeViolation("peer_after_abort")
            workspace.prepare_inference()
            guard.before_inference(actual)
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
            guard.observe({"event": "inference_completed"})
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
    with RunAdmissionLedger(output / "runs.jsonl", pinned, ids, evidence_kind=CODEX_OFFLINE_KIND) as ledger:
        try:
            for row in rows:
                verify_manifest(manifest, full_preflight=False, pinned=pinned)
                ledger.start(row["run_id"])
                record = asdict(RunRecord(run_id=row["run_id"], evidence_kind=CODEX_OFFLINE_KIND,
                                           seal_sha256=pinned, durable_ledger=True,
                                           budgets=asdict(BudgetCaps())))
                peer = OfflinePeer(scenario)
                journal = None
                workspace = None
                guard = None
                with tempfile.TemporaryDirectory(prefix="tmf-codex-private-") as directory:
                    root = Path(directory)
                    try:
                        prepare_fixture(root, "t1")
                        validate_fixture(root, "t1")
                        journal = EventJournal(output / (row["run_id"] + ".events.jsonl"))
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
                            record["adapter_evidence"] = {"kind": "offline_peer_not_native_host_attestation",
                                                          "model_calls": 0, "guard": guard.snapshot()}
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
    summary.update(evidence_kind=CODEX_OFFLINE_KIND, model_calls=0, live_model_runs=0,
                   scientific_seal_sha256=scientific["seal_sha256"], seal_sha256=pinned,
                   scenario=scenario, stopped_reason=stopped,
                   started_runs=state["started_runs"], not_started_runs=len(state["not_started_run_ids"]),
                   journal_integrity_verified=state["journal_integrity_verified"],
                   readiness="NOT_READY_FOR_LIVE_HOST")
    _write(output / "accounting.json", state)
    _write(output / "summary.json", summary)
    return summary


def run_live_pilot(manifest: dict, output: Path):
    """Fail before batch admission. No hidden CLI switch enables a stock host."""
    from .successor_codex_host import require_live_host
    verify_manifest(manifest)
    require_live_host(manifest["host_qualification"])
    raise RuntimeViolation("qualified_live_driver_unavailable")


def main(argv=None) -> int:
    from .successor_codex_host import HostNotReadyError
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare-seal", "verify-seal", "rehearse", "check-live-readiness"))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--host-report", type=Path)
    parser.add_argument("--output", type=Path)
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
                run_live_pilot(manifest, args.output or Path("unused"))
                raise AssertionError("stock live path must never return")
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
