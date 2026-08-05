from __future__ import annotations

from dataclasses import asdict

from .freshness import Freshness, check_freshness
from .git import GitRepo
from .schema import Claim
from .store import Store
from .warm import warm_is_complete


def _verification(claim: Claim) -> str:
    return str(claim.body.get("model_candidate", {}).get("verification", "none"))


def trust_label(claim: Claim) -> dict[str, str]:
    verification = _verification(claim)
    if claim.evidence == "verified":
        return {"level": "hard_verified", "label": "硬验证", "description": "由真实运行/测试/反馈验证过"}
    if claim.endorsed_by:
        return {"level": "endorsed", "label": f"人工背书:{claim.endorsed_by}", "description": "有人认可，但仍应看绑定是否新鲜"}
    if claim.evidence == "observed" and verification == "source_support_literal":
        return {"level": "source_observed", "label": "代码可证", "description": "源码字面支持的结构/机制类 claim"}
    if claim.evidence == "observed":
        return {"level": "observed", "label": "源码观察", "description": "从源码观察得到，但验证方式较粗"}
    if claim.evidence == "inferred" and verification == "attributed_external_provenance":
        return {"level": "attributed", "label": "有出处归因", "description": "归因于 docstring/commit/PR 等文本；不是已验证行为"}
    if claim.evidence == "inferred" and verification == "intent_requires_external_provenance":
        return {"level": "unsupported_intent", "label": "模型推测、无出处", "description": "只能当线索，不能当事实"}
    if claim.evidence == "inferred" and verification in {"unsupported_or_unverifiable", "none"}:
        return {"level": "unsupported", "label": "无支持、低信", "description": "缺少可核依据"}
    return {"level": "unknown", "label": "未知信任档", "description": "需要人工检查"}


def action_hint(*, fresh: bool, trust: dict[str, str]) -> str:
    level = trust["level"]
    if not fresh:
        return "degrade_to_source_or_rederive"
    if level in {"hard_verified", "endorsed", "source_observed", "observed"}:
        return "can_use_with_source_anchor_for_precision"
    if level == "attributed":
        return "use_as_attributed_context_verify_behavior_in_source"
    if level in {"unsupported_intent", "unsupported"}:
        return "treat_as_hint_read_source_before_acting"
    return "inspect_manually"


def _provenance_items(claim: Claim) -> list[dict]:
    items = []
    for item in claim.body.get("provenance_evidence", []):
        items.append({
            "type": item.get("source_type"),
            "ref": item.get("commit") or item.get("url") or item.get("path"),
            "path": item.get("path"),
            "line_start": item.get("line_start"),
            "line_end": item.get("line_end"),
            "quoted_text_untrusted_data": item.get("text_untrusted_data"),
        })
    return items


def _short_hash(value: str | None, n: int = 12) -> str | None:
    if value is None:
        return None
    return value[:n]


def explain_claim(repo: GitRepo, claim: Claim) -> dict:
    freshness: Freshness = check_freshness(repo, claim)
    trust = trust_label(claim)
    model_candidate = claim.body.get("model_candidate", {})
    anchors = claim.body.get("anchors", [])
    bindings = [asdict(binding) for binding in claim.bindings]
    provenance = _provenance_items(claim)
    confidence = float(claim.confidence)
    raw_confidence = model_candidate.get("raw_confidence")
    graph = _graph_with_fresh_edges(repo, claim)
    return {
        "id": claim.id,
        "claim": claim.claim,
        "fresh": freshness.fresh,
        "stale_reasons": [] if freshness.fresh else freshness.stale_bindings,
        "trust": trust,
        "evidence": claim.evidence,
        "confidence": confidence,
        "raw_confidence": raw_confidence,
        "confidence_cap_applied": raw_confidence is not None and float(raw_confidence) > confidence,
        "verification": model_candidate.get("verification"),
        "kind": claim.kind,
        "scope": claim.scope,
        "model": claim.model,
        "last_verified": claim.last_verified,
        "endorsed_by": claim.endorsed_by,
        "qualname": claim.body.get("qualname"),
        "anchors": anchors,
        "belief_provenance": provenance,
        "freshness_bindings": bindings,
        "action_hint": action_hint(fresh=freshness.fresh, trust=trust),
        "feedback_events": claim.body.get("feedback_events", []),
        "hunches": claim.body.get("hunches", []),
        "graph": graph,
        "graph_coverage": "complete" if warm_is_complete(repo.root) else "partial",
        "warnings": _warnings(fresh=freshness.fresh, trust=trust, claim=claim),
    }


def _warnings(*, fresh: bool, trust: dict[str, str], claim: Claim) -> list[str]:
    warnings: list[str] = []
    if not fresh:
        warnings.append("STALE_BUT_STORED: this claim remains in storage but is not fresh for current worktree")
    if trust["level"] in {"hard_verified", "endorsed"}:
        warnings.append("HIGH_TRUST_IS_NOT_SOURCE: high trust can still be wrong; source remains authority for exact behavior")
    if trust["level"] in {"unsupported_intent", "unsupported"}:
        warnings.append("LOW_SUPPORT: use only as a search hint")
    if claim.body.get("available_provenance") and not claim.body.get("provenance_evidence"):
        warnings.append("PROVENANCE_AVAILABLE_NOT_MATCHED: external text existed but did not support this claim")
    return warnings


def _graph_with_fresh_edges(repo: GitRepo, claim: Claim) -> dict:
    graph = dict(claim.body.get("graph", {}))
    if claim.scope not in {"function", "declaration"}:
        return graph
    store = Store(repo.root)
    if claim.scope == "function":
        callees = list(graph.get("callees", []))
        callers = list(graph.get("callers", []))
        reads = list(graph.get("reads", []))
        seen_callees = {item.get("target_id") for item in callees if isinstance(item, dict)}
        seen_callers = {item.get("source_id") for item in callers if isinstance(item, dict)}
        seen_reads = {item.get("target_id") for item in reads if isinstance(item, dict)}
        for edge in store.iter_claims():
            if not check_freshness(repo, edge).fresh:
                continue
            if edge.body.get("edge_kind") == "calls":
                if edge.body.get("caller_id") == claim.id and edge.body.get("callee_id") not in seen_callees:
                    callees.append({"target_id": edge.body.get("callee_id"), "target_qualname": edge.body.get("callee_qualname"), "target_path": edge.body.get("callee_path"), "evidence": edge.evidence, "resolution": edge.body.get("resolution")})
                    seen_callees.add(edge.body.get("callee_id"))
                if edge.body.get("callee_id") == claim.id and edge.body.get("caller_id") not in seen_callers:
                    callers.append({"source_id": edge.body.get("caller_id"), "source_qualname": edge.bindings[0].qualname if edge.bindings else None, "source_path": edge.body.get("caller_path"), "evidence": edge.evidence, "resolution": edge.body.get("resolution")})
                    seen_callers.add(edge.body.get("caller_id"))
            elif edge.body.get("edge_kind") == "reads" and edge.body.get("reader_id") == claim.id and edge.body.get("declaration_id") not in seen_reads:
                reads.append({"target_id": edge.body.get("declaration_id"), "target_qualname": edge.body.get("declaration_qualname"), "target_path": edge.body.get("declaration_path"), "evidence": edge.evidence, "resolution": edge.body.get("resolution")})
                seen_reads.add(edge.body.get("declaration_id"))
        graph["callees"] = callees
        graph["callers"] = callers
        graph["unresolved_calls"] = list(graph.get("unresolved_calls", []))
        graph["reads"] = reads
        graph["reads_unresolved"] = list(graph.get("reads_unresolved", []))
        return graph
    read_by = list(graph.get("read_by", []))
    seen_readers = {item.get("source_id") for item in read_by if isinstance(item, dict)}
    for edge in store.iter_claims():
        if edge.body.get("edge_kind") != "reads" or not check_freshness(repo, edge).fresh:
            continue
        if edge.body.get("declaration_id") == claim.id and edge.body.get("reader_id") not in seen_readers:
            read_by.append({"source_id": edge.body.get("reader_id"), "source_path": edge.body.get("reader_path"), "evidence": edge.evidence, "resolution": edge.body.get("resolution")})
            seen_readers.add(edge.body.get("reader_id"))
    graph["read_by"] = read_by
    graph["read_by_coverage"] = "partial"
    return graph


def thin_view(explained: dict) -> dict:
    """Thin graph view for default retrieval.

    Enough for judge+locate+branch; excludes thick body, untrusted quoted text,
    full bindings, feedback history, and available provenance.
    """
    provenance_refs = []
    for item in explained.get("belief_provenance", []):
        provenance_refs.append({
            "type": item.get("type"),
            "ref": item.get("ref"),
            "path": item.get("path"),
            "line_start": item.get("line_start"),
            "line_end": item.get("line_end"),
        })
    binding_refs = []
    for binding in explained.get("freshness_bindings", []):
        binding_refs.append({
            "path": binding.get("path"),
            "file_blob_prefix": _short_hash(binding.get("file_blob")),
            "fn_hash_prefix": _short_hash(binding.get("fn_hash")),
            "commit_anchor_prefix": _short_hash(binding.get("commit")),
        })
    return {
        "id": explained["id"],
        "claim": explained["claim"],
        "kind": explained["kind"],
        "scope": explained["scope"],
        "qualname": explained.get("qualname"),
        "trust": {"level": explained["trust"]["level"], "label": explained["trust"]["label"]},
        "fresh": explained["fresh"],
        "stale_reasons": explained["stale_reasons"],
        "confidence": explained["confidence"],
        "confidence_cap_applied": explained["confidence_cap_applied"],
        "anchors": explained["anchors"],
        "action_hint": explained["action_hint"],
        "belief_provenance_refs": provenance_refs,
        "freshness_binding_refs": binding_refs,
        "callees": explained.get("graph", {}).get("callees", []),
        "callers": explained.get("graph", {}).get("callers", []),
        "unresolved_calls": explained.get("graph", {}).get("unresolved_calls", []),
        "unresolved_call_count": len(explained.get("graph", {}).get("unresolved_calls", [])),
        "reads": explained.get("graph", {}).get("reads", []),
        "reads_unresolved": explained.get("graph", {}).get("reads_unresolved", []),
        "unresolved_read_count": len(explained.get("graph", {}).get("reads_unresolved", [])),
        "read_by": explained.get("graph", {}).get("read_by", []),
        "read_by_coverage": explained.get("graph", {}).get("read_by_coverage"),
        "graph_coverage": explained.get("graph_coverage", "partial"),
    }


def full_view(repo: GitRepo, claim: Claim) -> dict:
    explained = explain_claim(repo, claim)
    payload = dict(explained)
    payload["claim_record"] = claim.to_dict()
    return payload


def render_reviewer_text(explained: dict) -> str:
    fresh_mark = "FRESH" if explained["fresh"] else "STALE"
    trust = explained["trust"]
    lines = [
        f"[{fresh_mark}] {trust['label']} ({explained['confidence']:.2f}) :: {explained['claim']}",
        f"action_hint: {explained['action_hint']}",
    ]
    if explained.get("raw_confidence") is not None:
        cap = " capped" if explained.get("confidence_cap_applied") else ""
        lines.append(f"model_confidence: raw={explained['raw_confidence']} -> stored={explained['confidence']:.2f}{cap}")
    if explained["stale_reasons"]:
        lines.append("stale_reasons: " + "; ".join(explained["stale_reasons"]))
    lines.append("trust_basis: " + trust["description"])
    if explained["belief_provenance"]:
        lines.append("belief_provenance:")
        for item in explained["belief_provenance"]:
            ref = item.get("ref") or "unknown"
            loc = f" {item.get('path')}:{item.get('line_start')}-{item.get('line_end')}" if item.get("path") else ""
            lines.append(f"  - {item.get('type')} {ref}{loc}")
            quote = item.get("quoted_text_untrusted_data")
            if quote:
                one_line = " ".join(str(quote).split())[:240]
                lines.append(f"    quoted_untrusted_data: {one_line}")
    else:
        lines.append("belief_provenance: none")
    graph = explained.get("graph", {})
    if graph.get("callees") or graph.get("callers") or graph.get("unresolved_calls"):
        lines.append("graph:")
        if graph.get("callees"):
            lines.append("  callees:")
            for item in graph.get("callees", []):
                lines.append(f"    - {item.get('target_qualname')} {item.get('target_id')} ({item.get('evidence')})")
        if graph.get("callers"):
            lines.append("  callers:")
            for item in graph.get("callers", []):
                lines.append(f"    - {item.get('source_id')} ({item.get('evidence')})")
        if graph.get("unresolved_calls"):
            lines.append("  unresolved_calls:")
            for item in graph.get("unresolved_calls", []):
                lines.append(f"    - {item.get('expr')} :: {item.get('reason')}")
    if explained["freshness_bindings"]:
        lines.append("freshness_bindings:")
        for binding in explained["freshness_bindings"]:
            lines.append(f"  - {binding.get('path')} file_blob={binding.get('file_blob')} fn_hash={binding.get('fn_hash')} commit_anchor={binding.get('commit')}")
    if explained["anchors"]:
        lines.append("source_anchors:")
        for anchor in explained["anchors"]:
            lines.append(f"  - {anchor.get('path')}:{anchor.get('line_start')}-{anchor.get('line_end')}")
    if explained["warnings"]:
        lines.append("warnings:")
        for warning in explained["warnings"]:
            lines.append(f"  - {warning}")
    lines.append(f"model: {explained['model']} | evidence: {explained['evidence']} | verification: {explained.get('verification')}")
    return "\n".join(lines)
