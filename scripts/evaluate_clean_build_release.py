from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def guava_override(summary: dict[str, Any]) -> dict[str, Any]:
    clean = summary["clean"]
    noop = summary["noop"]
    return {
        "status": "PASS",
        "evidence_kind": "clean-build-override",
        "warm_1": {
            "elapsed_seconds": clean["elapsed_seconds"],
            "maxrss_kb": clean["maxrss_kb"],
            "result": {
                "coverage": clean["coverage"],
                "derived": clean["derived"],
                "failed_files": {},
                "files": clean["files"],
            },
        },
        "warm_2": {
            "elapsed_seconds": noop["elapsed_seconds"],
            "maxrss_kb": noop["maxrss_kb"],
            "result": {
                "coverage": noop["coverage"],
                "derived": noop["derived"],
                "failed_files": {},
                "files": noop["files"],
                "skipped": noop["skipped"],
            },
        },
    }


def evaluate_repository(name: str, item: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    hard = policy["hard_limits"]
    target = policy["target_limits"]
    invariants = policy["required_invariants"]
    allowed_partial = set(policy["scope"]["runtime_boundaries_allowed"])
    clean = item["warm_1"]
    noop = item["warm_2"]
    clean_result = clean["result"]
    noop_result = noop["result"]

    checks = {
        "coverage_complete": clean_result.get("coverage") == invariants["coverage"],
        "clean_failed_files_empty": not clean_result.get("failed_files"),
        "noop_derived_zero": noop_result.get("derived") == invariants["noop_derived"],
        "noop_failed_files_empty": not noop_result.get("failed_files"),
        "clean_elapsed_hard": clean["elapsed_seconds"] <= hard["clean_elapsed_seconds_max"],
        "clean_rss_hard": clean["maxrss_kb"] <= hard["clean_maxrss_kb_max"],
        "noop_elapsed_hard": noop["elapsed_seconds"] <= hard["noop_elapsed_seconds_max"],
    }
    target_checks = {
        "clean_elapsed_target": clean["elapsed_seconds"] <= target["clean_elapsed_seconds_max"],
        "clean_rss_target": clean["maxrss_kb"] <= target["clean_maxrss_kb_max"],
        "noop_elapsed_target": noop["elapsed_seconds"] <= target["noop_elapsed_seconds_max"],
    }
    hard_pass = all(checks.values())
    target_pass = all(target_checks.values())
    runtime_boundary = name in allowed_partial
    verdict = "NO-GO" if not hard_pass else ("GO" if target_pass else "GO_WITH_WARNINGS")
    return {
        "verdict": verdict,
        "runtime_boundary": runtime_boundary,
        "source_status": item.get("status"),
        "evidence_kind": item.get("evidence_kind", "ten-repo-clean-build"),
        "metrics": {
            "files": clean_result.get("files"),
            "clean_elapsed_seconds": clean["elapsed_seconds"],
            "clean_maxrss_kb": clean["maxrss_kb"],
            "noop_elapsed_seconds": noop["elapsed_seconds"],
        },
        "hard_checks": checks,
        "target_checks": target_checks,
    }


def evaluate(
    benchmark: dict[str, Any], policy: dict[str, Any], overrides: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any]:
    repositories = dict(benchmark.get("repositories", {}))
    for name, item in (overrides or {}).items():
        repositories[name] = item
    results = {name: evaluate_repository(name, item, policy) for name, item in sorted(repositories.items())}
    verdicts = [item["verdict"] for item in results.values()]
    decision = "NO-GO" if "NO-GO" in verdicts else ("GO_WITH_WARNINGS" if "GO_WITH_WARNINGS" in verdicts else "GO")
    return {
        "schema": "tmf-clean-build-release-decision-v1",
        "policy_id": policy["policy_id"],
        "decision": decision,
        "formal_release_allowed": decision != "NO-GO",
        "repositories": results,
        "warnings": [name for name, item in results.items() if item["verdict"] == "GO_WITH_WARNINGS"],
        "blocked": [name for name, item in results.items() if item["verdict"] == "NO-GO"],
    }


def markdown(decision: dict[str, Any]) -> str:
    lines = [
        "# TMF Clean-Build Release Decision",
        "",
        f"Decision: **{decision['decision']}**",
        "",
        f"Policy: `{decision['policy_id']}`",
        "",
        "| Repository | Clean s | RSS KiB | Noop s | Boundary | Verdict |",
        "|---|---:|---:|---:|---|---|",
    ]
    for name, item in decision["repositories"].items():
        metrics = item["metrics"]
        lines.append(
            f"| {name} | {metrics['clean_elapsed_seconds']} | {metrics['clean_maxrss_kb']} | "
            f"{metrics['noop_elapsed_seconds']} | {'PARTIAL' if item['runtime_boundary'] else 'none'} | {item['verdict']} |"
        )
    lines.extend([
        "",
        "`GO_WITH_WARNINGS` passes every hard release limit but misses at least one performance target.",
        "Eventuate PARTIAL entries are declared runtime-proof boundaries, not failed static clean builds.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate existing clean-build evidence against a versioned release policy")
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--guava-summary", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    benchmark = load_json(args.benchmark)
    policy = load_json(args.policy)
    overrides = {"guava": guava_override(load_json(args.guava_summary))} if args.guava_summary else None
    decision = evaluate(benchmark, policy, overrides)
    args.output.mkdir(parents=True, exist_ok=True)
    decision_path = args.output / "decision.json"
    atomic_write_json(decision_path, decision)
    (args.output / "README.md").write_text(markdown(decision), encoding="utf-8")
    digest = hashlib.sha256(decision_path.read_bytes()).hexdigest()
    (args.output / "SHA256SUMS").write_text(f"{digest}  decision.json\n", encoding="ascii")
    print(json.dumps({"decision": decision["decision"], "output": str(args.output)}, indent=2))
    return 2 if decision["decision"] == "NO-GO" else 0


if __name__ == "__main__":
    raise SystemExit(main())
