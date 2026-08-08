from __future__ import annotations

import argparse
import hashlib
import json
import resource
import subprocess
import sys
import time
from pathlib import Path
from collections import defaultdict
from typing import Any, Iterable

from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.retrieve import reverse_saga_participants, reverse_topic_publishers, reverse_topic_subscribers
from tmf.store import Store
from tmf.warm import warm_repo


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = {
    "dubbo-cluster": "dubbo-cluster-pilot",
    "spring-microservices": "sample-spring-microservices-new",
    "jhipster": "jhipster-sample-app",
    "petclinic-modulith": "spring-petclinic-modulith",
    "eventuate-choreography": "eventuate-tram-customers-orders",
    "eventuate-orchestration": "eventuate-tram-sagas-customers-orders",
    "quarkus": "quarkus-quickstarts",
    "dropwizard": "dropwizard-example",
    "vertx": "vertx-examples",
    "guava": "guava",
}


def timed_warm(repo: Path) -> dict[str, Any]:
    start = time.monotonic()
    before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result = warm_repo(repo)
    after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {"result": result, "elapsed_seconds": round(time.monotonic() - start, 3), "maxrss_kb": max(before, after)}


def classify_runtime_boundary(claims: Iterable[Any]) -> dict[str, Any] | None:
    publishers: dict[str, list[dict[str, Any]]] = defaultdict(list)
    subscribers: dict[str, list[dict[str, Any]]] = defaultdict(list)
    topics: dict[str, str] = {}
    sagas: list[dict[str, Any]] = []

    for claim in claims:
        body = claim.body
        if body.get("node_kind") == "topic" and isinstance(body.get("topic_name"), str):
            topics[claim.id] = body["topic_name"]
        edge_kind = body.get("edge_kind")
        topic_id = body.get("topic_id")
        role_id = body.get("publisher_id") if edge_kind == "publishes_to" else body.get("subscriber_id")
        source_id = body.get("source_id") or role_id
        if edge_kind in {"publishes_to", "subscribes_to"} and isinstance(topic_id, str) and isinstance(source_id, str):
            evidence = {
                "claim_id": claim.id,
                "source_id": source_id,
                "source_path": body.get("source_path"),
                "resolution": body.get("resolution"),
            }
            (publishers if edge_kind == "publishes_to" else subscribers)[topic_id].append(evidence)

        graph = body.get("graph")
        definition = graph.get("saga_definition") if isinstance(graph, dict) else None
        if not isinstance(definition, dict) or definition.get("resolution") != "eventuate_simple_saga_literal_dsl":
            continue
        steps = definition.get("steps")
        if not isinstance(steps, list):
            continue
        participant_steps = [step for step in steps if isinstance(step, dict) and step.get("kind") == "participant"]
        compensation_steps = [step for step in steps if isinstance(step, dict) and isinstance(step.get("compensation"), str)]
        reply_steps = [step for step in participant_steps if isinstance(step.get("replies"), list) and step["replies"]]
        contracted_steps = [step for step in participant_steps if isinstance(step.get("participant_contract"), dict)]
        if participant_steps and contracted_steps and (compensation_steps or reply_steps):
            sagas.append({
                "claim_id": claim.id,
                "resolution": definition["resolution"],
                "participant_steps": len(participant_steps),
                "contracted_steps": len(contracted_steps),
                "reply_steps": len(reply_steps),
                "compensation_steps": len(compensation_steps),
            })

    shared_topics = []
    for topic_id in sorted(set(publishers) & set(subscribers)):
        publisher_ids = {item["source_id"] for item in publishers[topic_id]}
        subscriber_ids = {item["source_id"] for item in subscribers[topic_id]}
        if not publisher_ids or not subscriber_ids or publisher_ids == subscriber_ids:
            continue
        shared_topics.append({
            "topic_id": topic_id,
            "topic_name": topics.get(topic_id),
            "publishers": len(publishers[topic_id]),
            "subscribers": len(subscribers[topic_id]),
            "publisher_examples": publishers[topic_id][:3],
            "subscriber_examples": subscribers[topic_id][:3],
        })

    reasons = []
    unproven = []
    if shared_topics:
        reasons.append("Static claims connect distinct publishers and subscribers through the same message topic.")
        unproven.extend(["broker_delivery", "transaction_commit", "consumer_execution", "payload_values"])
    if sagas:
        reasons.append("Static claims describe a participant saga with reply or compensation control flow.")
        unproven.extend(["saga_instance", "runtime_data", "reply_dispatch", "compensation_execution"])
    if not reasons:
        return None
    return {
        "status": "PARTIAL",
        "classification": "runtime_proof_required",
        "reasons": reasons,
        "features": {
            "message_topology": {"shared_topics": len(shared_topics), "examples": shared_topics[:5]},
            "saga_control_flow": {"sagas": len(sagas), "examples": sagas[:5]},
        },
        "unproven": list(dict.fromkeys(unproven)),
    }


def audit(repo: Path, warm: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    git = GitRepo(repo)
    store = Store(repo)
    claims = list(store.iter_claims())
    ids = {claim.id for claim in claims}
    stale = sum(not check_freshness(git, claim).fresh for claim in claims)
    missing_endpoints = []
    for claim in claims:
        body = claim.body
        if body.get("edge_kind") not in {"calls", "reads", "writes", "uses_type", "publishes_to", "subscribes_to"}:
            continue
        for key in ("caller_id", "reader_id", "writer_id", "user_id", "type_id", "publisher_id", "subscriber_id", "topic_id"):
            value = body.get(key)
            if isinstance(value, str) and value not in ids:
                missing_endpoints.append({"claim_id": claim.id, "field": key, "target": value})
    java_files = sum(1 for path in repo.rglob("*.java") if ".git" not in path.parts and ".tmf" not in path.parts)
    failed = warm["result"].get("failed_files", {})
    noop = second["result"].get("derived") == 0 and not second["result"].get("failed_files")
    status = "PASS" if not failed and stale == 0 and not missing_endpoints and noop else "BLOCKED"
    runtime_boundary = classify_runtime_boundary(claims)
    if status == "PASS" and runtime_boundary is not None:
        status = "PARTIAL"
    return {
        "path": str(repo), "commit": git.head(), "java_files": java_files,
        "claims": len(claims), "warm": warm, "noop_warm": second,
        "failed_files": failed, "stale_claims": stale,
        "edge_endpoint_integrity": {"missing": len(missing_endpoints), "examples": missing_endpoints[:10]},
        "mutation_restore": {"status": "NOT_RUN", "reason": "No probe configured; cache validation is non-destructive."},
        "runtime_boundary": runtime_boundary,
        "status": status,
    }


def markdown(report: dict[str, Any]) -> str:
    lines = ["# Ten-repo TMF production gate", "", f"Generated: `{report['generated_at']}`", "", "| Repository | Java | Claims | Warm s | Noop s | Stale | Failed | Integrity | Status |", "|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    for name, item in report["repositories"].items():
        lines.append(f"| {name} | {item['java_files']} | {item['claims']} | {item['warm']['elapsed_seconds']} | {item['noop_warm']['elapsed_seconds']} | {item['stale_claims']} | {len(item['failed_files'])} | {item['edge_endpoint_integrity']['missing']} | {item['status']} |")
    lines += ["", "Mutation/restore is `NOT_RUN` unless an explicit safe probe is configured.", "Repositories with structured message or saga boundaries remain PARTIAL because static TMF evidence does not prove runtime behavior.", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Serial, cache-preserving ten-repository TMF gate")
    parser.add_argument("--experiments-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"schema": "ten-repo-production-gate-v1", "mode": "cache-validation", "repositories": {}}
    for name, directory in SAMPLES.items():
        repo = (args.experiments_root / directory).resolve()
        if not (repo / ".git").exists():
            report["repositories"][name] = {"status": "BLOCKED", "reason": "repository_missing", "path": str(repo)}
            continue
        print(f"[{name}] warm 1/2", flush=True)
        first = timed_warm(repo)
        print(f"[{name}] warm 2/2", flush=True)
        second = timed_warm(repo)
        report["repositories"][name] = audit(repo, first, second)
        report["repositories"][name]["warm_mode"] = "cache-validation"
    statuses = [item.get("status") for item in report["repositories"].values()]
    report["overall"] = "PASS" if statuses and all(value == "PASS" for value in statuses) else ("PARTIAL" if any(value == "PARTIAL" for value in statuses) else "BLOCKED")
    report["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json_path = output / "gate.json"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "README.md").write_text(markdown(report), encoding="utf-8")
    digest = hashlib.sha256(json_path.read_bytes()).hexdigest()
    (output / "SHA256SUMS").write_text(f"{digest}  gate.json\n", encoding="utf-8")
    print(json.dumps({"overall": report["overall"], "output": str(output), "statuses": statuses}, indent=2))
    return 0 if report["overall"] != "BLOCKED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
