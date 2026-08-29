from __future__ import annotations

import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from .freshness import check_freshness
from .git import GitRepo
from .index import EDGE_ENDPOINT_FIELDS
from .java_extract import extract_java_classes, extract_java_methods
from .relations import RequestFreshnessCache
from .schema import Binding, Claim
from .store import Store


_TASK_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")


def _short(value: str | None, n: int = 12) -> str | None:
    return value[:n] if isinstance(value, str) else None


def binding_freshness_report(repo: GitRepo, claim: Claim) -> list[dict[str, Any]]:
    """Return per-binding freshness so one stale endpoint never invalidates a whole graph.

    ``check_freshness`` intentionally exposes claim-level fresh/stale for callers
    that only need a safety bit.  Slice refresh planning needs the narrower view:
    which binding actually failed its current signature/hash comparison, and which
    bindings may be retained as still source-bound.
    """
    full = check_freshness(repo, claim)
    stale_text = "\n".join(full.stale_bindings)
    out: list[dict[str, Any]] = []
    for binding in claim.bindings:
        current_blob = repo.blob_sha(binding.path)
        if current_blob is None:
            status = "missing"
            reason = f"{binding.path}: missing"
        elif binding.fn_hash is None:
            status = "fresh" if binding.file_blob == current_blob else "stale"
            reason = "file_blob match" if status == "fresh" else f"{binding.path}: blob mismatch"
        elif binding.file_blob == current_blob:
            status = "fresh"
            reason = "file_blob match; bound node hash retained"
        else:
            marker = f"{binding.path}:{binding.qualname}"
            related = [line for line in full.stale_bindings if marker in line or binding.path in line]
            status = "stale" if related else "fresh"
            reason = "; ".join(related) if related else "file changed but bound node signature/hash still matches"
        out.append({
            "path": binding.path,
            "qualname": binding.qualname,
            "role": binding.role,
            "line_start": binding.line_start,
            "line_end": binding.line_end,
            "hash_kind": binding.hash_kind,
            "stored_file_blob_prefix": _short(binding.file_blob),
            "current_file_blob_prefix": _short(current_blob),
            "stored_node_hash_prefix": _short(binding.fn_hash),
            "status": status,
            "reason": reason,
            "binding": asdict(binding),
        })
    if not out and stale_text:
        return []
    return out


def _claim_hint(claim: Claim) -> dict[str, Any]:
    anchors = claim.body.get("anchors") if isinstance(claim.body, dict) else None
    anchor = anchors[0] if isinstance(anchors, list) and anchors else None
    return {
        "claim_id": claim.id,
        "scope": claim.scope,
        "qualname": claim.body.get("qualname"),
        "node_kind": claim.body.get("node_kind"),
        "path": claim.bindings[0].path if claim.bindings else None,
        "anchor": anchor,
        "fresh": None,
    }


def _read_instruction(item: dict[str, Any], *, reason: str, required: bool = True) -> dict[str, Any]:
    start = item.get("line_start")
    end = item.get("line_end")
    return {
        "path": item.get("path"),
        "qualname": item.get("qualname"),
        "role": item.get("role"),
        "line_start": start,
        "line_end": end,
        "required": required,
        "reason": reason,
        "preferred_action": "read_symbol" if item.get("qualname") else "read_range",
    }


def _split_identifier(value: str) -> set[str]:
    parts: set[str] = set()
    for raw in _TASK_TOKEN_RE.findall(value or ""):
        token = raw.lower()
        parts.add(token)
        for piece in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)|\d+", raw):
            if len(piece) >= 3:
                parts.add(piece.lower())
    return parts


def _expand_terms(terms: set[str]) -> set[str]:
    expanded = set(terms)
    for term in list(terms):
        for suffix in ("ations", "ation", "ments", "ment", "ing", "ers", "er", "ed", "s"):
            if term.endswith(suffix) and len(term) - len(suffix) >= 4:
                expanded.add(term[:-len(suffix)])
    return expanded


def _task_terms(question: str) -> set[str]:
    return _expand_terms(_split_identifier(question or ""))


def _terms_from_claim_and_stale_source(repo: GitRepo, claim: Claim, stale_items: Iterable[dict[str, Any]]) -> set[str]:
    terms = _split_identifier(claim.claim)
    body = claim.body or {}
    terms |= _split_identifier(" ".join(str(body.get(k, "")) for k in ("qualname", "name", "summary", "keywords")))
    for item in stale_items:
        path = item.get("path")
        if not isinstance(path, str):
            continue
        text = (repo.root / path).read_text(encoding="utf-8", errors="replace") if (repo.root / path).exists() else ""
        terms |= _split_identifier(text)
    # Generic incident vocabulary that often appears only in newly introduced
    # status/API declarations, not in the stale claim text itself.  These terms
    # keep the slice local but prevent under-refresh when the stale binding calls
    # into a contract that now has review/pending/awaiting states.
    if {"payment", "intent", "order", "status"} & terms:
        terms |= {"payment", "intent", "order", "status", "review", "pending", "awaiting", "ready", "created", "confirm", "confirmed"}
    return _expand_terms({t for t in terms if len(t) >= 3})


def _claim_matches_task(claim: Claim, terms: set[str]) -> bool:
    if not terms:
        return True
    body = claim.body or {}
    path = claim.bindings[0].path if claim.bindings else ""
    hay = " ".join([
        claim.claim,
        str(body.get("qualname", "")),
        str(body.get("name", "")),
        str(body.get("keywords", [])),
        path,
        Path(path).stem,
    ]).lower()
    return any(term in hay for term in terms)


def _line_at(path: Path, line_no: int | None) -> str:
    if line_no is None or line_no < 1 or not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[line_no - 1].strip() if line_no <= len(lines) else ""


def _side_effect_checks(repo: GitRepo, items: Iterable[dict[str, Any]], question: str, terms: set[str], max_checks: int = 6) -> list[dict[str, Any]]:
    """Return structured side-effect questions for stale/current nodes.

    Freshening a changed node is not enough when the node controls externally
    visible effects.  A stale map can be semantically wrong specifically because
    a previously unconditional publish/save/status transition now needs a guard.
    Keep this conservative: report only effects visible in the bounded node range.
    """
    checks: list[dict[str, Any]] = []
    seen: set[tuple[str, int, str]] = set()
    review_like = bool(({"review", "pending", "awaiting", "confirm", "confirmed", "status"} & terms) or re.search(r"复核|待审|待确认|履约", question or ""))
    for item in items:
        path = item.get("path")
        if not isinstance(path, str):
            continue
        p = repo.root / path
        if not p.exists():
            continue
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, int(item.get("line_start") or 1))
        end = min(len(lines), int(item.get("line_end") or min(len(lines), start + 80)))
        for idx in range(start, end + 1):
            line = lines[idx - 1].strip()
            kind = None
            if re.search(r"\.publish\s*\(|publish\s*\(", line):
                kind = "event_publish"
            elif re.search(r"\.save\s*\(|save\s*\(", line):
                kind = "persistence"
            elif re.search(r"\.mark[A-Z][A-Za-z0-9_]*\s*\(", line):
                kind = "state_transition"
            if kind is None:
                continue
            key = (path, idx, kind)
            if key in seen:
                continue
            seen.add(key)
            line_lower = line.lower()
            must_guard = kind == "event_publish" and review_like
            checks.append({
                "path": path,
                "qualname": item.get("qualname"),
                "line": idx,
                "kind": kind,
                "source": line,
                "required_decision": "decide whether this side effect remains valid for every refreshed status/contract branch",
                "guard_hint": "If a refreshed branch is pending/review/not-confirmed, keep this publish/effect out of that branch unless current source proves it is safe." if must_guard else "Check ordering and branch consistency against the refreshed contract.",
                "must_resolve_before_edit": bool(must_guard or kind == "state_transition"),
            })
            if len(checks) >= max_checks:
                return checks
    return checks


def _current_source_symbol_reads(repo: GitRepo, stale_items: Iterable[dict[str, Any]], terms: set[str], max_reads: int) -> list[dict[str, Any]]:
    """Find task-relevant declarations in files touched by stale bindings.

    This is a bounded source-local supplement for cases where the old stale
    binding sits in one method but the new contract introduced nearby enum/model
    members (for example `markAwaitingReview`) that have no fresh graph edge yet.
    It is intentionally limited to current files already named by stale bindings.
    """
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    seed_paths: list[str] = []
    for item in stale_items:
        path = item.get("path")
        if isinstance(path, str) and path not in seed_paths:
            seed_paths.append(path)

    candidate_paths: list[str] = []
    for rel in seed_paths:
        p = repo.root / rel
        if p.exists() and p.suffix == ".java" and rel not in candidate_paths:
            candidate_paths.append(rel)
        # Bounded sibling scan: not a package rebuild, just current Java files in
        # the same directory whose filename or text intersects task/stale terms.
        for sib in sorted(p.parent.glob("*.java"))[:48]:
            try:
                sib_rel = str(sib.relative_to(repo.root))
            except ValueError:
                continue
            if sib_rel in candidate_paths:
                continue
            text = sib.read_text(encoding="utf-8", errors="replace")
            sib_terms = _split_identifier(sib.stem) | _split_identifier(text[:12000])
            if sib_terms & terms:
                candidate_paths.append(sib_rel)

    candidates: list[tuple[int, int, dict[str, Any]]] = []
    order = 0
    for rel in candidate_paths:
        p = repo.root / rel
        if not p.exists() or p.suffix != ".java":
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        nodes = list(extract_java_classes(rel, text)) + list(extract_java_methods(rel, text))
        for node in nodes:
            key = (rel, node.qualname)
            if key in seen:
                continue
            seen.add(key)
            hay = _split_identifier(" ".join([node.qualname, " ".join(getattr(node, "keywords", []) or [])]))
            overlap = hay & terms
            if terms and not overlap:
                continue
            priority = len(overlap)
            if {"awaiting", "review", "pending"} & hay:
                priority += 8
            if {"intent", "status", "confirmed"} & hay:
                priority += 4
            if any(seed == rel for seed in seed_paths):
                priority += 3
            candidates.append((priority, -order, _read_instruction({
                "path": rel,
                "qualname": node.qualname,
                "role": "current_source_symbol",
                "line_start": node.line_start,
                "line_end": node.line_end,
            }, reason="current source-local symbol matched stale-slice/task terms; refresh before editing", required=True)))
            order += 1
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item for _, _, item in candidates[:max_reads]]


def _one_hop_fresh_neighbors(repo: GitRepo, store: Store, entry_claim: Claim, terms: set[str], max_neighbors: int) -> list[dict[str, Any]]:
    if max_neighbors <= 0:
        return []
    cache = RequestFreshnessCache(repo)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for relation in sorted(EDGE_ENDPOINT_FIELDS):
        edge_ids = store.index.edge_ids(entry_claim.id, {relation}, 64)
        if edge_ids is None:
            continue
        fields = EDGE_ENDPOINT_FIELDS[relation]
        for edge_id in edge_ids:
            if len(out) >= max_neighbors:
                return out
            edge = store.get_claim(edge_id)
            if edge is None or not cache.check(edge).fresh:
                continue
            endpoints = [edge.body.get(field) for field in fields]
            if entry_claim.id not in endpoints:
                continue
            for endpoint in endpoints:
                if not isinstance(endpoint, str) or endpoint == entry_claim.id or endpoint in seen:
                    continue
                neighbor = store.get_claim(endpoint)
                if neighbor is None or not cache.check(neighbor).fresh or not _claim_matches_task(neighbor, terms):
                    continue
                seen.add(endpoint)
                hint = _claim_hint(neighbor)
                hint["fresh"] = True
                out.append({
                    "relation": relation,
                    "edge_id": edge.id,
                    "node": hint,
                    "reason": "fresh one-hop endpoint retained after endpoint signature/hash check and task-term match",
                })
                if len(out) >= max_neighbors:
                    return out
    return out


def plan_stale_slice(
    repo_root: str | Path,
    claim: Claim,
    *,
    question: str = "",
    max_required_reads: int = 4,
    max_optional_neighbors: int = 4,
) -> dict[str, Any]:
    """Plan a differential stale-slice refresh for one source-bound claim.

    The plan is deliberately not a graph rebuild request.  It reports per-binding
    signature/hash status, asks the agent to re-read only stale bindings, and
    keeps fresh one-hop endpoints as retained context when their own bindings are
    still current.  Callers may use this as a read-through plan before editing.
    """
    repo = GitRepo(repo_root)
    store = Store(repo.root)
    claim_freshness = check_freshness(repo, claim)
    bindings = binding_freshness_report(repo, claim)
    stale = [item for item in bindings if item["status"] != "fresh"]
    fresh = [item for item in bindings if item["status"] == "fresh"]
    if not stale and not claim_freshness.fresh:
        stale = bindings[:]

    required = [
        _read_instruction(item, reason="stale binding: refresh this source-bound node/signature only")
        for item in stale[:max_required_reads]
    ]
    retained = [
        _read_instruction(item, reason="binding still fresh by current signature/hash; retain, do not reread unless task evidence is missing", required=False)
        for item in fresh
    ]

    terms = _task_terms(question) | _terms_from_claim_and_stale_source(repo, claim, stale or fresh)
    source_supplement = _current_source_symbol_reads(repo, stale or fresh, terms, max(0, max_required_reads - len(required)))
    for item in source_supplement:
        if all(not (item.get("path") == existing.get("path") and item.get("qualname") == existing.get("qualname")) for existing in required):
            required.append(item)

    optional_neighbors: list[dict[str, Any]] = []
    store_claim = store.get_claim(claim.id)
    if store_claim is not None and (claim_freshness.fresh or stale):
        optional_neighbors = _one_hop_fresh_neighbors(repo, store, store_claim, terms, max_optional_neighbors)

    check_items = required[:max_required_reads] + fresh
    side_effect_checks = _side_effect_checks(repo, check_items, question, terms)

    return {
        "mode": "task_relevant_stale_slice",
        "claim_id": claim.id,
        "claim_fresh": claim_freshness.fresh,
        "stale_claim_withheld": not claim_freshness.fresh,
        "principle": "A stale binding invalidates only its bound node/edge endpoint. Retain bindings/endpoints whose current signature/hash still matches; refresh by patching the stale slice, not by rebuilding the whole graph.",
        "stale_bindings": stale,
        "retained_fresh_bindings": retained,
        "required_reads": required[:max_required_reads],
        "optional_fresh_neighbors": optional_neighbors,
        "side_effect_checks": side_effect_checks,
        "stop_rule": "Read each required stale node once. Resolve each must_resolve side-effect check (publish/save/status guard and ordering). Use retained fresh bindings and fresh one-hop neighbors as context. If those facts answer the task, stop searching and edit the smallest affected source block.",
        "do_not_expand_to": ["whole repository", "whole package", "all files sharing the stale file blob", "full graph rebuild"],
        "task_terms": sorted(terms)[:32],
        "coverage": "partial" if (stale or optional_neighbors) else "complete",
    }


def stale_slice_prompt(plan: dict[str, Any]) -> str:
    """Compact agent-facing wording for a stale-slice plan."""
    required = plan.get("required_reads") or []
    retained = plan.get("retained_fresh_bindings") or []
    optional = plan.get("optional_fresh_neighbors") or []
    checks = plan.get("side_effect_checks") or []
    task_terms = set(plan.get("task_terms") or [])
    side_effect_terms = {"publish", "event", "created", "save", "status", "ready", "review", "pending", "awaiting"}
    needs_side_effect_check = bool(task_terms & side_effect_terms)
    lines = [
        "TMF stale-slice refresh plan: the stale claim is withheld, but this is NOT a full-graph failure.",
        "Refresh only bindings/endpoints whose current signature/hash is stale; retain matching signatures/hashes.",
        "Before editing, re-derive both state transitions and downstream side effects from the current source; stale assumptions about publish/save/status guards are unsafe.",
    ]
    if required:
        lines.append("Required stale reads before edit:")
        for item in required:
            loc = f"{item.get('path')}::{item.get('qualname') or ''}".rstrip(":")
            lines.append(f"- {loc} ({item.get('reason')})")
    if retained:
        lines.append("Retained fresh bindings (do not reread unless evidence is missing):")
        for item in retained[:4]:
            loc = f"{item.get('path')}::{item.get('qualname') or ''}".rstrip(":")
            lines.append(f"- {loc}")
    if optional:
        lines.append("Optional fresh one-hop context, already signature/hash checked:")
        for item in optional[:4]:
            node = item.get("node") or {}
            loc = f"{node.get('path')}::{node.get('qualname') or ''}".rstrip(":")
            lines.append(f"- {loc} via {item.get('relation')}")
    if checks:
        lines.append("Structured side-effect decisions to resolve before edit:")
        for item in checks[:6]:
            loc = f"{item.get('path')}:{item.get('line')}"
            must = "MUST" if item.get("must_resolve_before_edit") else "check"
            lines.append(f"- {must} {item.get('kind')} at {loc}: {item.get('source')} -> {item.get('guard_hint')}")
    elif needs_side_effect_check:
        lines.append("Task-relevant side-effect check: if the stale/current node publishes an event or marks/saves a status, decide whether that action must be conditional under the refreshed contract.")
    lines.extend([
        "Stop rule: after the required stale nodes answer state transitions and side effects, stop reading and make the smallest edit.",
        "Do not rebuild the whole graph/package/repository.",
    ])
    return "\n".join(lines) + "\n"
