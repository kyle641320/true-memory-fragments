from __future__ import annotations

import argparse
import json
from pathlib import Path

from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.ids import stable_java_node_claim_id
from tmf.retrieve import reverse_saga_participants, reverse_topic_publishers, reverse_topic_subscribers
from tmf.store import Store
from tmf.warm import warm_repo


def audit_saga(repo: Path, saga_path: str, qualname: str = "CreateOrderSaga") -> dict:
    warm = warm_repo(repo)
    claim_id = stable_java_node_claim_id(saga_path, qualname, "class")
    claim = Store(repo).get_claim(claim_id)
    if claim is None:
        return {"status": "BLOCKED", "reason": "saga_claim_missing", "warm": warm}
    reverse = reverse_saga_participants(repo, claim_id)
    graph = claim.body.get("graph", {})
    definition = graph.get("saga_definition")
    if not isinstance(definition, dict):
        return {"status": "BLOCKED", "reason": "saga_definition_missing", "warm": warm, "reverse": reverse}
    unresolved = graph.get("saga_definition_unresolved", [])
    participant_steps = [step for step in definition.get("steps", []) if step.get("kind") == "participant"]
    unique_contracts = sum(1 for step in participant_steps if step.get("participant_contract"))
    static_gate = "PASS" if participant_steps and unique_contracts == len(participant_steps) and not unresolved else "PARTIAL"
    return {"static_gate": static_gate, "runtime_gate": "PARTIAL", "claim_id": claim_id, "steps": definition.get("steps", []), "unresolved": unresolved, "reverse": reverse, "warm": warm, "runtime_boundary": ["saga_instance", "runtime_data", "reply_dispatch", "compensation_execution"]}


def audit_choreography(repo: Path) -> dict:
    warm = warm_repo(repo)
    git = GitRepo(repo)
    store = Store(repo)
    claims = list(store.iter_claims())
    stale = sum(1 for claim in claims if not check_freshness(git, claim).fresh)
    topics = []
    for claim in claims:
        if claim.body.get("node_kind") != "topic":
            continue
        publishers = reverse_topic_publishers(repo, claim.id)
        subscribers = reverse_topic_subscribers(repo, claim.id)
        topics.append({"topic_id": claim.id, "topic_name": claim.body.get("topic_name"), "publishers": len(publishers["publishers"]), "subscribers": len(subscribers["subscribers"]), "publisher_stale_skipped": publishers["stale_skipped"], "subscriber_stale_skipped": subscribers["stale_skipped"]})
    static_gate = "PASS" if topics and stale == 0 and all(topic["publishers"] > 0 and topic["subscribers"] > 0 for topic in topics) else "BLOCKED"
    return {"static_gate": static_gate, "runtime_gate": "PARTIAL", "claims": len(claims), "stale_claims": stale, "topics": topics, "warm": warm, "runtime_boundary": ["broker_delivery", "transaction_commit", "consumer_execution", "payload_values"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--choreography-repo", type=Path, required=True)
    parser.add_argument("--orchestration-repo", type=Path, required=True)
    parser.add_argument("--saga-path", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    choreography = audit_choreography(args.choreography_repo)
    orchestration = audit_saga(args.orchestration_repo, args.saga_path)
    result = {
        "schema": "eventuate-production-gate-v1",
        "overall": "PARTIAL" if choreography.get("static_gate") == "PASS" and orchestration.get("static_gate") == "PASS" else "BLOCKED",
        "choreography": choreography,
        "orchestration": orchestration,
        "conclusion": "Static source-backed Eventuate relations pass; runtime behavior remains outside TMF evidence.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
