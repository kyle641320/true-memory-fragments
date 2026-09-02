#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.stale_slice import plan_stale_slice
from bench.agent_ab.same_version_chain_v1 import outbox_m15_two_phase_runner as m15
from bench.agent_ab.same_version_chain_v1 import order_m16_complex_two_phase_runner as m16
from bench.agent_ab.same_version_chain_v1 import order_m21_stale_api_trap_runner as m21

RESULTS = HERE / "results"

CASES = [
    {
        "id": "M15",
        "module": m15,
        "question": "订单创建成功后事件处理状态不一致，修稳事件触发逻辑",
        "expected_required_any": {
            "src/main/java/com/example/order/OrderService.java::OrderService.createOrder",
            "src/main/java/com/example/order/EventPublisher.java::EventPublisher.publishAfterCommit",
        },
        "safe_extra_required": {
            "src/main/java/com/example/order/OrderService.java::OrderService.persistAndPublish",
            "src/main/java/com/example/order/OrderRepository.java::OrderRepository.save",
            "src/main/java/com/example/order/EventPublisher.java::EventPublisher.publish",
        },
        "noise_extra_required": {
            "src/main/java/com/example/order/OrderService.java::OrderService",
            "src/main/java/com/example/order/OrderService.java::OrderService.OrderService",
        },
        "expected_side_effect_kinds": {"event_publish", "persistence"},
    },
    {
        "id": "M16",
        "module": m16,
        "question": "线上有些订单在支付意图还在复核时就开始走履约了。帮我把创建链路修一下，别弄坏正常订单。",
        "expected_required_any": {
            "src/main/java/com/example/order/OrderService.java::OrderService.createOrder",
            "src/main/java/com/example/order/PaymentIntentService.java::PaymentIntentService.createIntent",
            "src/main/java/com/example/order/Order.java::Order.markAwaitingReview",
            "src/main/java/com/example/order/PaymentIntent.java::PaymentIntent.getStatus",
        },
        "safe_extra_required": {
            "src/main/java/com/example/order/PaymentIntentService.java::PaymentIntentService.requiresManualReview",
            "src/main/java/com/example/order/PaymentIntentRepository.java::PaymentIntentRepository.save",
            "src/main/java/com/example/order/PaymentIntent.java::PaymentIntent.getOrderId",
        },
        "noise_extra_required": set(),
        "expected_side_effect_kinds": {"event_publish", "state_transition", "persistence"},
    },
    {
        "id": "M21",
        "module": m21,
        "question": "线上有些订单在支付意图还在复核时就开始走履约了。帮我把创建链路修一下，别弄坏正常订单。",
        "expected_required_any": {
            "src/main/java/com/example/order/OrderService.java::OrderService.createOrder",
            "src/main/java/com/example/order/PaymentIntentService.java::PaymentIntentService.createIntent",
            "src/main/java/com/example/order/Order.java::Order.markAwaitingReview",
            "src/main/java/com/example/order/FulfillmentPolicy.java::FulfillmentPolicy.shouldPublishOrderCreated",
            "src/main/java/com/example/order/PaymentIntent.java::PaymentIntent.getStatus",
        },
        "safe_extra_required": {
            "src/main/java/com/example/order/PaymentIntentService.java::PaymentIntentService.requiresManualReview",
            "src/main/java/com/example/order/PaymentIntent.java::PaymentIntent.getOrderId",
        },
        "noise_extra_required": set(),
        "expected_side_effect_kinds": {"event_publish", "state_transition", "persistence"},
    },
]


def item_key(item: dict[str, Any]) -> str:
    return f"{item.get('path')}::{item.get('qualname')}"


def build_claim(mod: Any, root: Path):
    if hasattr(mod, "run_phase_a"):
        return mod.build_claim(root, {"summary": "deterministic direct oracle eval"})
    return mod.build_claim(root)


def score(case: dict[str, Any]) -> dict[str, Any]:
    mod = case["module"]
    with tempfile.TemporaryDirectory(prefix=f"tmf-direct-{case['id']}-") as td:
        root = Path(td) / case["id"]
        mod.make_repo(root)
        claim = build_claim(mod, root)
        mod.mutate_to_phase_b(root)
        fresh = check_freshness(GitRepo(root), claim)
        plan = plan_stale_slice(root, claim, question=case["question"], max_required_reads=8, max_optional_neighbors=8)
        required = {item_key(x) for x in plan.get("required_reads", [])}
        expected = set(case["expected_required_any"])
        safe_extra = set(case.get("safe_extra_required", set()))
        noise_extra = set(case.get("noise_extra_required", set()))
        extra = required - expected
        unclassified_extra = extra - safe_extra - noise_extra
        useful = expected | safe_extra
        tp = len(required & expected)
        useful_tp = len(required & useful)
        precision = tp / len(required) if required else 0.0
        tiered_precision = useful_tp / len(required) if required else 0.0
        recall = tp / len(expected) if expected else 1.0
        side_kinds = {x.get("kind") for x in plan.get("side_effect_checks", [])}
        expected_side = set(case["expected_side_effect_kinds"])
        side_recall = len(side_kinds & expected_side) / len(expected_side) if expected_side else 1.0
        return {
            "case": case["id"],
            "claim_fresh": fresh.fresh,
            "stale_bindings": fresh.stale_bindings,
            "stale_claim_withheld": bool(plan.get("stale_claim_withheld")),
            "required_count": len(required),
            "expected_required": sorted(expected),
            "required_reads": sorted(required),
            "tp_required": sorted(required & expected),
            "missing_required": sorted(expected - required),
            "extra_required": sorted(extra),
            "safe_extra_required": sorted(extra & safe_extra),
            "noise_extra_required": sorted(extra & noise_extra),
            "unclassified_extra_required": sorted(unclassified_extra),
            "required_precision": round(precision, 4),
            "tiered_useful_precision": round(tiered_precision, 4),
            "required_recall": round(recall, 4),
            "side_effect_kinds": sorted(k for k in side_kinds if k),
            "expected_side_effect_kinds": sorted(expected_side),
            "side_effect_recall": round(side_recall, 4),
            "pass": bool((not fresh.fresh) and plan.get("stale_claim_withheld") and recall >= 0.8 and side_recall >= 0.67),
            "plan": plan,
        }


def main() -> None:
    rows = [score(c) for c in CASES]
    summary = {
        "cases": len(rows),
        "pass": sum(1 for r in rows if r["pass"]),
        "stale_withheld": sum(1 for r in rows if r["stale_claim_withheld"]),
        "avg_required_precision": round(sum(r["required_precision"] for r in rows) / len(rows), 4),
        "avg_tiered_useful_precision": round(sum(r["tiered_useful_precision"] for r in rows) / len(rows), 4),
        "avg_required_recall": round(sum(r["required_recall"] for r in rows) / len(rows), 4),
        "avg_side_effect_recall": round(sum(r["side_effect_recall"] for r in rows) / len(rows), 4),
    }
    out = {"schema": "tmf_direct_refresh_oracle_eval_v1", "summary": summary, "rows": rows}
    RESULTS.mkdir(exist_ok=True)
    json_path = RESULTS / "tmf_direct_refresh_oracle_eval_20260901.json"
    md_path = RESULTS / "TMF_DIRECT_REFRESH_ORACLE_EVAL_20260901.md"
    json_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = ["# TMF Direct Refresh Oracle Evaluation — 2026-09-01", "", "This evaluates TMF freshness/stale-slice planning directly, before any agent edit loop. Off-track M22–M25 artifacts are excluded.", "", "## Summary", "", "```json", json.dumps(summary, ensure_ascii=False, indent=2), "```", "", "## Cases"]
    for r in rows:
        md += ["", f"### {r['case']}", f"- pass: {r['pass']}", f"- stale withheld: {r['stale_claim_withheld']}", f"- strict required precision/recall: {r['required_precision']} / {r['required_recall']}", f"- tiered useful precision: {r['tiered_useful_precision']}", f"- side-effect recall: {r['side_effect_recall']}", f"- missing required: {r['missing_required']}", f"- safe extra required: {r['safe_extra_required']}", f"- noise extra required: {r['noise_extra_required']}", f"- unclassified extra required: {r['unclassified_extra_required']}"]
    md += ["", "## Interpretation", "", "This is closer to TMF's design intent than hidden-JUnit agent tasks: it checks stale invalidation, localized reread planning, and side-effect awareness directly. Strict precision counts only oracle-essential symbols; tiered useful precision also counts safety-relevant side-effect/contract reads. In this retained set, the remaining clear noise is M15's class/constructor reads, which suggests the next optimization target is ranking/filtering current-source symbol supplements rather than changing stale invalidation."]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json_path)
    print(md_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
