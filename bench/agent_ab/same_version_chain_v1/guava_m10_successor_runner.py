#!/usr/bin/env python3
"""Frozen M10 successor preparation and zero-model protocol rehearsal.

No paid/live adapter is available. A valid offline seal is neither permission to
call a model nor evidence that a model/provider token contract has been tested.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import random
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from bench.agent_ab.same_version_chain_v1.m10_successor_fixture import (
    FILE, PKG_FILES, ROOT, SPEC_PATH, TARGET_QUALNAME, BoundMemory,
    FreshnessPreflight, PreflightInvariantError, canonical_json, compile_check,
    load_fixture_spec, mutate_dispatcher, prepare_fixture,
    run_freshness_preflight, sha256_bytes, sha256_text, source_base,
    validate_fixture, validate_preflight,
)
from bench.agent_ab.same_version_chain_v1.m10_successor_protocol import (
    ACTION_SCHEMAS, WORKSPACE_LABEL, BudgetCaps, ScriptedAdapter,
    aggregate_itt, records_from_ledger, run_one,
)
from bench.agent_ab.same_version_chain_v1.m10_successor_scoring import (
    PlacementScore, score_placement_ast as _score_placement_ast,
)

SCHEMA = "guava-m10-successor-v2"
SOURCE_ONLY = "SOURCE_ONLY"
STALE_WITHHELD_VISIBLE_RECEIPT = "STALE_WITHHELD_VISIBLE_RECEIPT"
PREREAD_STALE_SOURCE = "PREREAD_STALE_SOURCE"
STALE_DOC_CONTROL = "STALE_DOC_CONTROL"
STALE_WARNING_ONLY = "STALE_WARNING_ONLY"
STALE_WITHHELD_SILENT = "STALE_WITHHELD_SILENT"
ARMS = (
    SOURCE_ONLY, STALE_WITHHELD_VISIBLE_RECEIPT, PREREAD_STALE_SOURCE,
    STALE_DOC_CONTROL, STALE_WARNING_ONLY, STALE_WITHHELD_SILENT,
)

COMMON_SYSTEM_PROMPT = """You are a stateless Java coding agent.
Edit only the permitted source file under the supplied workspace. The available
source files are authoritative for the workspace you are modifying. Compile
before finishing. Report the files changed and the reason for your placement.
"""
COMMON_TASK_PROMPT = """Add exactly one call to the existing no-op hook() at the
last handoff out of the queued per-thread Dispatcher implementation into the
Subscriber implementation. This is the Dispatcher-to-Subscriber boundary, not
the later invocation of the user's listener within Subscriber.
Only Dispatcher.java may be edited. Do not add or remove hook definitions or
change any other executable code. Ordinary comments and whitespace are allowed;
Java Unicode escape sequences are outside this task's accepted source subset.
The result must compile.
"""
COMMON_TOOL_PROMPT = """Respond with exactly one JSON action object per turn,
using the supplied action schemas. Source paths are workspace-relative. Tools
provide source inspection, literal replacement edits, and compilation. Submit a
final action after compiling your current edit. The final action must report
all changed files and explain the placement.
"""
# Declarative historical representation, not a patch-site instruction.
STALE_DOC_TEXT = (
    "Historical dispatcher instrumentation note: the queued per-thread "
    "Dispatcher-to-Subscriber.dispatchEvent handoff was the direct "
    "nextEvent.subscribers.next().dispatchEvent(nextEvent.event) call inside "
    "the PerThreadQueuedDispatcher.dispatch queue-drain loop."
)
PROTOCOL_DOC = ROOT / "docs/experiments/guava-m10-successor-protocol.md"


@dataclass(frozen=True)
class ArmInput:
    arm: str  # evaluator metadata; never serialized into model_messages
    system_prompt: str
    task_prompt: str
    tools_prompt: str
    evidence: dict[str, Any] | None

    def model_messages(self) -> list[dict[str, str]]:
        user = f"Workspace: {WORKSPACE_LABEL}\n{self.task_prompt}\n{self.tools_prompt}"
        if self.evidence is not None:
            user += "\nEvidence envelope:\n" + canonical_json(self.evidence)
        return [{"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user}]


def _arm_input(arm: str, preflight: FreshnessPreflight) -> ArmInput:
    """Internal formatter; callers must validate the complete preflight first."""
    if arm not in ARMS:
        raise PreflightInvariantError("unknown information condition")
    memory = preflight.bound_memory
    receipt = json.loads(canonical_json(preflight.gate_t1["receipt"]))
    if arm in (SOURCE_ONLY, STALE_WITHHELD_SILENT):
        evidence = None
    elif arm == STALE_WITHHELD_VISIBLE_RECEIPT:
        evidence = receipt
    elif arm in (PREREAD_STALE_SOURCE, STALE_WARNING_ONLY):
        evidence = {"status": "trusted", "provenance": "prior_source_read", **memory.payload}
        if arm == STALE_WARNING_ONLY:
            evidence["status"] = "stale_untrusted"
            evidence["changed_bindings"] = receipt["changed_bindings"]
    else:
        evidence = {"status": "trusted", "provenance": "internal_documentation",
                    "document": STALE_DOC_TEXT,
                    "boundary_conclusion": memory.payload["boundary_conclusion"]}
    return ArmInput(arm, COMMON_SYSTEM_PROMPT, COMMON_TASK_PROMPT, COMMON_TOOL_PROMPT, evidence)


def build_arm_input(arm: str, *, preflight: FreshnessPreflight) -> ArmInput:
    # No default stale receipt or independently supplied payload is admitted.
    validate_preflight(preflight)
    return _arm_input(arm, preflight)


def validate_arm_inputs(preflight: FreshnessPreflight) -> dict[str, bool]:
    validate_preflight(preflight)
    inputs = {arm: _arm_input(arm, preflight) for arm in ARMS}
    if inputs[SOURCE_ONLY].model_messages() != inputs[STALE_WITHHELD_SILENT].model_messages():
        raise PreflightInvariantError("source and silent withholding differ")
    trusted = dict(inputs[PREREAD_STALE_SOURCE].evidence or {})
    warning = dict(inputs[STALE_WARNING_ONLY].evidence or {})
    if warning.pop("changed_bindings") != preflight.t1["stale_bindings"]:
        raise PreflightInvariantError("warning locator is not the actual freshness result")
    warning["status"] = "trusted"
    if warning != trusted:
        raise PreflightInvariantError("warning treatment changed more than status/locator")
    visible = inputs[STALE_WITHHELD_VISIBLE_RECEIPT].evidence
    if visible != preflight.gate_t1["receipt"] or visible["payload"] is not None:
        raise PreflightInvariantError("visible withholding is detached from actual gate")
    for item in inputs.values():
        if (item.system_prompt != COMMON_SYSTEM_PROMPT or item.task_prompt != COMMON_TASK_PROMPT
                or item.tools_prompt != COMMON_TOOL_PROMPT):
            raise PreflightInvariantError("common instructions differ")
        rendered = canonical_json(item.model_messages())
        if any(label in rendered for label in ARMS) or str(ROOT) in rendered:
            raise PreflightInvariantError("condition identity or absolute path leaked")
    document = inputs[STALE_DOC_CONTROL].evidence["document"].lower()
    for phrase in ("place the", "must trust", "do not move", "required patch", "prefer", "reread"):
        if phrase in document:
            raise PreflightInvariantError("document contains treatment-specific instruction")
    return {"source_equals_silent": True, "warning_payload_identical": True,
            "common_instructions_identical": True, "receipt_from_actual_gate": True,
            "harness_labels_hidden": True, "declarative_document": True}


def reference_source() -> str:
    return mutate_dispatcher((source_base() / FILE).read_text(encoding="utf-8"))


def score_placement_ast(source: str) -> PlacementScore:
    return _score_placement_ast(source, reference_source=reference_source())


def validate_scorer_fixtures() -> dict[str, bool]:
    reference = reference_source()
    target = "      prepared.subscriber.dispatchEvent(prepared.event);"
    def at_target(replacement: str) -> str:
        if reference.count(target) != 1:
            raise PreflightInvariantError("oracle target is not unique")
        return reference.replace(target, replacement, 1)
    good = at_target("      hook();\n" + target)
    obsolete = reference.replace(
        "              dispatchQueuedSubscriber(nextEvent.event, nextSubscriber);",
        "              hook();\n              dispatchQueuedSubscriber(nextEvent.event, nextSubscriber);", 1)
    fixtures = {
        "correct": (good, True),
        "comments_and_spacing": (at_target("      hook(); // trivia\n"
                                             "      prepared.subscriber.dispatchEvent( prepared.event );"), True),
        "obsolete": (obsolete, False),
        "no_effect": (reference, False),
        "deferred_lambda": (at_target("      hook();\n      Runnable deferred = () -> "
                                      "prepared.subscriber.dispatchEvent(prepared.event);"), False),
        "dead_branch": (at_target("      hook();\n      if (false) "
                                  "prepared.subscriber.dispatchEvent(prepared.event);"), False),
        "comment_argument_spoof": (at_target("      hook();\n      prepared.subscriber.dispatchEvent("
                                             "/* prepared.subscriber.dispatchEvent(prepared.event) */ null);"), False),
        "hook_after_target": (at_target(target + "\n      hook();"), False),
        "unicode_comment_live_code": (at_target("      hook(); // " + chr(92) + "u000a return;\n" + target), False),
    }
    checks = {name: score_placement_ast(source).semantic_pass is expected
              for name, (source, expected) in fixtures.items()}
    checks["obsolete_classification"] = score_placement_ast(obsolete).obsolete_queue_loop
    checks["after_is_other"] = score_placement_ast(fixtures["hook_after_target"][0]).other_incorrect_placement
    if not all(checks.values()):
        raise PreflightInvariantError("oracle counterexample failed: " + ", ".join(k for k, v in checks.items() if not v))
    return checks


def build_randomized_schedule(blocks: int, seed: int) -> list[dict[str, Any]]:
    if type(blocks) is not int or not 1 <= blocks <= 1000 or type(seed) is not int:
        raise PreflightInvariantError("schedule requires 1..1000 blocks and an integer seed")
    rng = random.Random(seed)
    rows = []
    for block in range(1, blocks + 1):
        order = list(ARMS)
        rng.shuffle(order)
        for position, arm in enumerate(order, 1):
            run_id = sha256_text(canonical_json([SCHEMA, seed, block, position, arm]))[:24]
            rows.append({"block": block, "position": position, "run_id": run_id, "arm": arm})
    return rows


def _dependency_inventory() -> dict[str, Any]:
    distributions = {}
    for name in ("tree_sitter", "tree_sitter_java"):
        distribution = importlib.metadata.distribution(name)
        files = {}
        for entry in distribution.files or ():
            # Exclude installation paths/bytecode while binding native parser and Python code.
            if entry.suffix in (".py", ".so", ".pyd", ".dll") or entry.name == "METADATA":
                path = Path(distribution.locate_file(entry))
                if not path.is_file():
                    raise PreflightInvariantError(f"missing parser distribution file: {entry}")
                files[entry.as_posix()] = sha256_bytes(path.read_bytes())
        if not files:
            raise PreflightInvariantError(f"empty parser inventory: {name}")
        distributions[name] = {"version": distribution.version, "files": files}
    return {"python_version": platform.python_version(), "python_implementation": platform.python_implementation(),
            "python_executable_sha256": sha256_bytes(Path(sys.executable).resolve().read_bytes()),
            "platform": {"system": platform.system(), "machine": platform.machine()},
            "parsers": distributions}


def _implementation_inventory() -> dict[str, str]:
    files = set((ROOT / "tmf").rglob("*.py"))
    here = Path(__file__).resolve().parent
    files.update(here / name for name in (
        "guava_m10_successor_runner.py", "m10_successor_fixture.py", "m10_successor_fixture_spec.json",
        "m10_successor_protocol.py", "m10_successor_scoring.py"))
    files.update((PROTOCOL_DOC, ROOT / "pyproject.toml"))
    files.update((ROOT / "tests").glob("test_*m10_successor*.py"))
    files.update(source_base() / name for name in PKG_FILES)
    return {path.relative_to(ROOT).as_posix(): sha256_bytes(path.read_bytes()) for path in sorted(files)}


def build_sealed_manifest(
    preflight: FreshnessPreflight, blocks: int, seed: int, budgets: BudgetCaps = BudgetCaps(),
) -> dict[str, Any]:
    # No weak prepare-seal path: all scientific preconditions run before sealing.
    budgets.validate()
    chain = validate_preflight(preflight)
    arm_checks = validate_arm_inputs(preflight)
    oracle_checks = validate_scorer_fixtures()
    schedule = build_randomized_schedule(blocks, seed)
    manifest = {
        "schema": SCHEMA,
        "execution": {"kind": "offline_scripted_protocol_rehearsal", "paid_execution_enabled": False,
                      "model_execution_enabled": False, "model_pilot_admitted": False,
                      "provider_token_limits_verified": False, "model": None,
                      "budget_unit": "utf8_bytes_not_provider_tokens", "budgets": asdict(budgets)},
        "preflight": asdict(preflight),
        "checks": {"freshness": chain, "arms": arm_checks, "oracle": oracle_checks},
        "inputs": {arm: _arm_input(arm, preflight).model_messages() for arm in ARMS},
        "action_schemas": ACTION_SCHEMAS,
        "source_files": list(PKG_FILES), "allowed_edit_paths": [FILE],
        "implementation_sha256": _implementation_inventory(),
        "dependencies": _dependency_inventory(),
        "randomization": {"algorithm": "python.random.Random.shuffle blocked-six", "blocks": blocks,
                          "seed": seed, "schedule": schedule},
        "claim_limits": {"bounded_insertion_task": True, "single_mutation": True,
                         "host_reflex_end_to_end": False, "freshness_is_truth": False,
                         "scripted_results_are_model_evidence": False},
    }
    manifest["seal_sha256"] = sha256_text(canonical_json(manifest))
    return manifest


def verify_sealed_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    try:
        content = {key: value for key, value in manifest.items() if key != "seal_sha256"}
        if manifest["seal_sha256"] != sha256_text(canonical_json(content)):
            raise PreflightInvariantError("seal digest mismatch")
        randomization = manifest["randomization"]
        budgets = BudgetCaps(**manifest["execution"]["budgets"])
        # Reacquire reality, not a self-attested collection of PASS booleans.
        preflight = run_freshness_preflight()
        expected = build_sealed_manifest(preflight, randomization["blocks"], randomization["seed"], budgets)
        if canonical_json(expected) != canonical_json(manifest):
            raise PreflightInvariantError("sealed content differs from current verified inputs or implementation")
    except (KeyError, ValueError, TypeError) as exc:
        raise PreflightInvariantError("incomplete or invalid sealed manifest") from exc
    return {"ok": True, "seal_sha256": manifest["seal_sha256"], "model_pilot_admitted": False}


def verify_run_admission(
    manifest: dict[str, Any], *, root: Path, arm: str, run_id: str,
    messages: list[dict[str, str]], budgets: BudgetCaps,
) -> dict[str, Any]:
    receipt = verify_sealed_manifest(manifest)
    validate_fixture(root, "t1")
    rows = [row for row in manifest["randomization"]["schedule"] if row["run_id"] == run_id]
    if len(rows) != 1 or rows[0]["arm"] != arm:
        raise PreflightInvariantError("run does not match sealed schedule")
    if (messages != manifest["inputs"][arm] or asdict(budgets) != manifest["execution"]["budgets"]
            or ACTION_SCHEMAS != manifest["action_schemas"]):
        raise PreflightInvariantError("run inputs/tools/budgets differ from seal")
    return receipt


def rehearse_protocol(manifest: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    """Run the same known-answer script in every condition. Not a model result."""
    verify_sealed_manifest(manifest)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise PreflightInvariantError("rehearsal output directory must be empty; never replace prior runs")
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    budgets = BudgetCaps(**manifest["execution"]["budgets"])
    ledger = output_dir / "ledger.jsonl"
    with tempfile.TemporaryDirectory(prefix="m10-template-") as directory:
        root = Path(directory)
        prepare_fixture(root, "t1")
        for row in manifest["randomization"]["schedule"]:
            arm, run_id = row["arm"], row["run_id"]
            messages = manifest["inputs"][arm]
            # The fixture-specific answer exists ONLY in the scripted adapter;
            # real model execution is unavailable. It checks plumbing, not H1/H2/H3.
            adapter = ScriptedAdapter([
                {"action": "list"},
                {"action": "read_range", "path": FILE, "start": 1, "end": 260},
                {"action": "edit", "path": FILE,
                 "old": "      prepared.subscriber.dispatchEvent(prepared.event);",
                 "new": "      hook();\n      prepared.subscriber.dispatchEvent(prepared.event);"},
                {"action": "compile"},
                {"action": "final", "answer": "Added one hook at the Dispatcher-to-Subscriber handoff.",
                 "files": [FILE]},
            ])
            record = run_one(root, messages, adapter, budgets=budgets, compile_fn=compile_check,
                             score_fn=lambda current: score_placement_ast((current / FILE).read_text(encoding="utf-8")),
                             verify=lambda: verify_run_admission(manifest, root=root, arm=arm, run_id=run_id,
                                                                messages=messages, budgets=budgets),
                             source_files=PKG_FILES, allowed_edit_paths=(FILE,), ledger_path=ledger, run_id=run_id)
            (output_dir / f"{run_id}.json").write_text(json.dumps(asdict(record), indent=2) + "\n", encoding="utf-8")
    records = records_from_ledger(ledger)
    summary = aggregate_itt(records)
    summary["offline_protocol_ready"] = summary["joint_success"] == len(manifest["randomization"]["schedule"])
    summary["seal_sha256"] = manifest["seal_sha256"]
    summary["model_calls"] = 0
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "validate-scorer-fixtures", "prepare-seal",
                                           "validate-all", "verify-seal", "protocol-rehearsal"))
    parser.add_argument("--blocks", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20260920)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-scorer-fixtures":
            result = validate_scorer_fixtures()
        elif args.command == "preflight":
            result = asdict(run_freshness_preflight())
        elif args.command == "verify-seal":
            if args.manifest is None:
                parser.error("verify-seal requires --manifest")
            result = verify_sealed_manifest(json.loads(args.manifest.read_text(encoding="utf-8")))
        else:
            manifest = (json.loads(args.manifest.read_text(encoding="utf-8")) if args.manifest else
                        build_sealed_manifest(run_freshness_preflight(), args.blocks, args.seed))
            if args.command == "protocol-rehearsal":
                if args.output is None:
                    parser.error("protocol-rehearsal requires an empty --output directory")
                result = rehearse_protocol(manifest, args.output)
                print(json.dumps(result, indent=2))
                return 0 if result["offline_protocol_ready"] else 1
            if args.manifest:
                verify_sealed_manifest(manifest)
            result = manifest
        serialized = json.dumps(result, indent=2) + "\n"
        if args.output is not None:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(serialized)
        else:
            print(serialized, end="")
        return 0
    except (PreflightInvariantError, OSError) as exc:
        print(f"Preflight rejected before any adapter call: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
