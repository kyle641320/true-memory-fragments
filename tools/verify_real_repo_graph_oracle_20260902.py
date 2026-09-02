#!/usr/bin/env python3
"""Real-repo graph query oracle for TMF.

Uses pinned Petclinic/JHipster repositories from java_real_v2 and hand-checked
relations visible in source. This is bounded real-repo evidence for reverse graph
queries; it avoids agent runs and does not modify TMF engine code.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.retrieve import refresh_path, reverse_callers, reverse_implementors, reverse_subtypes, reverse_used_by_types, reverse_writers
from tmf.store import Store

PETCLINIC = Path("/root/.openclaw/workspace/experiments/tmf-java-validation-20260806/spring-petclinic-modulith")
JHIPSTER = Path("/root/.openclaw/workspace/experiments/tmf-java-validation-20260806/jhipster-sample-app")
PETCLINIC_COMMIT = "58c3310e36c7d827959df6af4d64bdeb8d81f1ea"
JHIPSTER_COMMIT = "f8da577c944ecc4db46fc961a1ba022d5bbf8964"
OUT_JSON = ROOT / "reports" / "real-repo-graph-oracle-20260902.json"
OUT_MD = ROOT / "TMF_REAL_REPO_GRAPH_ORACLE_20260902.md"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip()


def rel(repo: Path, path: str) -> str:
    return path


def warm_files(repo: Path, paths: list[str]) -> None:
    for p in paths:
        refresh_path(repo, p)


def eval_set(actual: set[str], expected: set[str]) -> dict[str, Any]:
    tp = sorted(actual & expected)
    fp = sorted(actual - expected)
    fn = sorted(expected - actual)
    precision = len(tp) / len(actual) if actual else (1.0 if not expected else 0.0)
    recall = len(tp) / len(expected) if expected else (1.0 if not actual else 0.0)
    return {"expected": sorted(expected), "actual": sorted(actual), "tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "pass": precision == 1.0 and recall == 1.0}


def claim_id_by_qualname(
    repo: Path,
    qualname: str,
    node_kind: str,
    *,
    prefer_callee_qualname: str | None = None,
    prefer_uses_type_qualname: str | None = None,
) -> str:
    git_repo = GitRepo(repo)
    matches = []
    for claim in Store(repo).iter_claims():
        body = claim.body if isinstance(claim.body, dict) else {}
        if claim.id.startswith("claim_java_") and body.get("qualname") == qualname and body.get("node_kind") == node_kind and check_freshness(git_repo, claim).fresh:
            graph = body.get("graph", {})
            if prefer_callee_qualname:
                callees = graph.get("callees", [])
                if not any(edge.get("target_qualname") == prefer_callee_qualname for edge in callees):
                    continue
            if prefer_uses_type_qualname:
                uses_type = graph.get("uses_type", [])
                if not any(edge.get("target_qualname") == prefer_uses_type_qualname for edge in uses_type):
                    continue
            matches.append(claim.id)
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one fresh claim for {qualname}/{node_kind}, got {matches}")
    return matches[0]


def ids_petclinic() -> dict[str, str]:
    return {
        "vet_listener_on_call_assign": claim_id_by_qualname(PETCLINIC, "VetEventListener.on", "method", prefer_callee_qualname="VetRoster.assignVet"),
        "vet_roster_assign": claim_id_by_qualname(PETCLINIC, "VetRoster.assignVet", "method"),
        "visit_booked": claim_id_by_qualname(PETCLINIC, "VisitBooked", "class"),
        "owner_repo": claim_id_by_qualname(PETCLINIC, "OwnerRepository", "interface"),
    }


def ids_jhipster() -> dict[str, str]:
    return {
        "operation_repo": claim_id_by_qualname(JHIPSTER, "OperationRepository", "interface"),
        "operation_bag_iface": claim_id_by_qualname(JHIPSTER, "OperationRepositoryWithBagRelationships", "interface"),
        "operation_bag_impl": claim_id_by_qualname(JHIPSTER, "OperationRepositoryWithBagRelationshipsImpl", "class"),
        "operation_resource": claim_id_by_qualname(JHIPSTER, "OperationResource", "class"),
    }


def main() -> None:
    checks: list[dict[str, Any]] = []
    if git(PETCLINIC, "rev-parse", "HEAD") != PETCLINIC_COMMIT:
        raise SystemExit("petclinic commit mismatch")
    if git(JHIPSTER, "rev-parse", "HEAD") != JHIPSTER_COMMIT:
        raise SystemExit("jhipster commit mismatch")

    pet_paths = [
        "src/main/java/org/springframework/samples/petclinic/owner/VisitBooked.java",
        "src/main/java/org/springframework/samples/petclinic/owner/application/VisitScheduler.java",
        "src/main/java/org/springframework/samples/petclinic/vet/internal/VetEventListener.java",
        "src/main/java/org/springframework/samples/petclinic/vet/internal/VetRoster.java",
        "src/main/java/org/springframework/samples/petclinic/owner/domain/OwnerRepository.java",
        "src/main/java/org/springframework/samples/petclinic/owner/domain/Owner.java",
    ]
    jh_paths = [
        "src/main/java/io/github/jhipster/sample/repository/OperationRepository.java",
        "src/main/java/io/github/jhipster/sample/repository/OperationRepositoryWithBagRelationships.java",
        "src/main/java/io/github/jhipster/sample/repository/OperationRepositoryWithBagRelationshipsImpl.java",
        "src/main/java/io/github/jhipster/sample/web/rest/OperationResource.java",
        "src/main/java/io/github/jhipster/sample/domain/Operation.java",
    ]
    warm_files(PETCLINIC, pet_paths)
    warm_files(JHIPSTER, jh_paths)
    pi = ids_petclinic()
    ji = ids_jhipster()

    # Petclinic: VetEventListener.on directly calls VetRoster.assignVet(event).
    callers_assign = {x.get("caller_id") for x in reverse_callers(PETCLINIC, pi["vet_roster_assign"])["callers"] if x.get("caller_id")}
    checks.append({"name": "petclinic_callers_vetroster_assignVet", **eval_set(callers_assign, {pi["vet_listener_on_call_assign"]})})

    # Petclinic: VisitBooked record is used as a parameter type by listener/roster methods.
    # The publication constructor call is tracked separately as event/type publication, not as used_by_types.
    users_visit_booked = {x.get("user_id") for x in reverse_used_by_types(PETCLINIC, pi["visit_booked"])["used_by_types"] if x.get("user_id")}
    expected_visit_users = {
        # Expected from source: VetEventListener.on has VisitBooked parameter and VetRoster.assignVet has VisitBooked parameter.
        # Current retained store/index returns a dangling historical listener id for the first relation, which this oracle should expose.
        claim_id_by_qualname(PETCLINIC, "VetEventListener.on", "method", prefer_callee_qualname="VetRoster.assignVet"),
        pi["vet_roster_assign"],
    }
    checks.append({"name": "petclinic_used_by_type_visit_booked", **eval_set(users_visit_booked, expected_visit_users)})

    # JHipster: OperationRepository extends OperationRepositoryWithBagRelationships.
    subtypes_bag = {x.get("child_id") for x in reverse_subtypes(JHIPSTER, ji["operation_bag_iface"])["subtypes"] if x.get("child_id")}
    impls_bag = {x.get("child_id") for x in reverse_implementors(JHIPSTER, ji["operation_bag_iface"])["implementors"] if x.get("child_id")}
    checks.append({"name": "jhipster_subtypes_operation_bag_relationships", **eval_set(subtypes_bag | impls_bag, {ji["operation_repo"], ji["operation_bag_impl"]})})

    # Negative controls: no known callers/writers for top-level interface/class targets in this warmed subset.
    checks.append({"name": "petclinic_no_callers_owner_repository_type", **eval_set({x.get("caller_id") for x in reverse_callers(PETCLINIC, pi["owner_repo"])["callers"] if x.get("caller_id")}, set())})
    checks.append({"name": "jhipster_no_writers_operation_resource_type", **eval_set({x.get("writer_id") for x in reverse_writers(JHIPSTER, ji["operation_resource"])["writers"] if x.get("writer_id")}, set())})

    tp = sum(len(c["tp"]) for c in checks)
    fp = sum(len(c["fp"]) for c in checks)
    fn = sum(len(c["fn"]) for c in checks)
    summary = {
        "checks": len(checks),
        "passed": sum(1 for c in checks if c["pass"]),
        "failed": sum(1 for c in checks if not c["pass"]),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "micro_precision": tp / (tp + fp) if (tp + fp) else 1.0,
        "micro_recall": tp / (tp + fn) if (tp + fn) else 1.0,
        "macro_precision": sum(c["precision"] for c in checks) / len(checks),
        "macro_recall": sum(c["recall"] for c in checks) / len(checks),
    }
    summary["verdict"] = "PASS" if summary["failed"] == 0 else "FAIL"
    result = {
        "schema": "tmf.real_repo_graph_oracle.v1",
        "repos": {"petclinic": str(PETCLINIC), "jhipster": str(JHIPSTER)},
        "commits": {"petclinic": PETCLINIC_COMMIT, "jhipster": JHIPSTER_COMMIT},
        "summary": summary,
        "checks": checks,
    }
    OUT_JSON.parent.mkdir(exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    lines = [
        "# TMF Real-Repo Graph Oracle — 2026-09-02",
        "",
        f"Verdict: **{summary['verdict']}**.",
        "",
        "Scope: bounded hand-checked reverse graph oracle over pinned real Petclinic and JHipster repositories from `bench/agent_ab/java_real_v2`. It warms only selected source files and evaluates callers/used-by-type/subtypes/implementors plus negative controls. This is larger real-repo graph evidence, not a complete enterprise graph certification.",
        "",
        "## Summary",
        "",
        f"- Checks: {summary['passed']}/{summary['checks']} pass.",
        f"- Micro precision/recall: {summary['micro_precision']:.3f} / {summary['micro_recall']:.3f}.",
        f"- Macro precision/recall: {summary['macro_precision']:.3f} / {summary['macro_recall']:.3f}.",
        f"- TP/FP/FN: {tp}/{fp}/{fn}.",
        "",
        "## Checks",
        "",
    ]
    for c in checks:
        lines.append(f"- {c['name']}: {'PASS' if c['pass'] else 'FAIL'}; precision={c['precision']:.3f}; recall={c['recall']:.3f}; tp={len(c['tp'])}; fp={len(c['fp'])}; fn={len(c['fn'])}.")
    lines += ["", "## Interpretation", "", "This upgrades graph query evidence beyond a synthetic fixture into pinned real Java repositories. Any failed case should be treated as either oracle mismatch or a real extraction/query gap after source inspection; dynamic/reflection/DI runtime behavior remains out of scope."]
    OUT_MD.write_text("\n".join(lines) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
