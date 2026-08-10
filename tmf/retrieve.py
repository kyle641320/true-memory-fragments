from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .derive import derive_claims_for_path, derive_file_claim
from .embeddings import rank_by_embedding
from .freshness import check_freshness
from .git import GitRepo
from .router import route_claim_ids
from .schema import Claim
from .store import Store


def _is_unverified_foreign(claim: Claim) -> bool:
    return (claim.body or {}).get("source_provenance", {}).get("trust") == "unverified_foreign"
from .metrics import log_event
from .warm import COMPLETE_NOTE, PARTIAL_NOTE, load_complete_reverse_index


@dataclass
class RetrievedClaim:
    claim: Claim
    fresh: bool
    reason: str


@dataclass
class RetrieveResult:
    query: str
    claims: list[RetrievedClaim]
    source_fallback: dict[str, str]


def _fresh_item(repo: GitRepo, claim: Claim) -> RetrievedClaim:
    freshness = check_freshness(repo, claim)
    return RetrievedClaim(claim=claim, fresh=freshness.fresh, reason="fresh" if freshness.fresh else "; ".join(freshness.stale_bindings))


def _put_claims(store: Store, claims: list[Claim]) -> None:
    for claim in claims:
        store.put_claim(claim)


def _replace_path_claims(store: Store, relpath: str, claims: list[Claim]) -> None:
    _put_claims(store, claims)
    store.reconcile_path_claims(relpath, [c for c in claims if c.body.get("edge_kind") not in {"calls", "reads", "writes", "inherits", "overrides", "uses_type", "reads_env", "reads_config_key", "injects", "publishes_to", "subscribes_to"}])
    store.reconcile_edge_claims_for_caller_path(relpath, [c for c in claims if c.body.get("edge_kind") in {"calls", "reads", "writes", "inherits", "overrides", "uses_type", "reads_env", "reads_config_key", "injects", "publishes_to", "subscribes_to"}])


def retrieve_path(repo_root: str | Path, path: str, *, use_model: bool = False) -> RetrieveResult:
    repo = GitRepo(repo_root)
    store = Store(repo.root)
    rel = repo.relpath(path)
    claims = store.claims_for_path(rel)

    # v1 read-through: missing or stale => derive current file + function claims synchronously.
    stale_items = [c for c in claims if (not check_freshness(repo, c).fresh) or _is_unverified_foreign(c)]
    if not claims:
        log_event(repo.root, "miss", node_id=rel)
    elif stale_items:
        for claim in stale_items:
            fr = check_freshness(repo, claim)
            log_event(repo.root, "stale_detected", node_id=claim.id, stale_bindings=fr.stale_bindings)
    else:
        log_event(repo.root, "cache_hit", node_id=rel, cache_bytes_estimate=sum(len(c.to_dict().get("claim", "")) for c in claims))

    if not claims or stale_items:
        import time
        start = time.perf_counter()
        with store.write_lock():
            current_claims = derive_claims_for_path(repo, rel, use_model=use_model)
            _replace_path_claims(store, rel, current_claims)
        log_event(repo.root, "rederive", node_id=rel, duration_ms=round((time.perf_counter() - start) * 1000, 3), used_model=bool(use_model))
        claims = current_claims

    retrieved = [_fresh_item(repo, claim) for claim in claims]
    source = repo.read_file(rel)
    log_event(repo.root, "degrade_to_source", node_id=rel, read_bytes=len(source.encode("utf-8")))
    return RetrieveResult(query=rel, claims=retrieved, source_fallback={rel: source})


def retrieve_text(repo_root: str | Path, query: str, limit: int = 5, *, use_model: bool = False) -> RetrieveResult:
    repo = GitRepo(repo_root)
    store = Store(repo.root)
    terms = {t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", query)}

    def lexical_score(claim: Claim) -> int:
        hay = " ".join([claim.claim, str(claim.body.get("keywords", [])), claim.bindings[0].path if claim.bindings else ""]).lower()
        return sum(1 for term in terms if term in hay)

    scored: list[tuple[int, Claim]] = []
    for claim in store.iter_claims():
        score = lexical_score(claim)
        if score:
            scored.append((score, claim))
    scored.sort(key=lambda item: item[0], reverse=True)

    claims: list[Claim] = []
    seen_ids: set[str] = set()
    for _, claim in scored[:limit]:
        current_claims = [claim]
        freshness = check_freshness(repo, claim)
        if _is_unverified_foreign(claim):
            continue
        if not freshness.fresh and claim.bindings:
            path = claim.bindings[0].path
            if Path(repo.root / path).exists():
                with store.write_lock():
                    current_claims = derive_claims_for_path(repo, path, use_model=use_model)
                    _replace_path_claims(store, path, current_claims)
                # A stale lexical hit is only permission to re-read its source.
                # It must not confer the old claim's match onto unrelated facts
                # derived from the current file. Re-score against current memory.
                current_claims = sorted(
                    (current for current in current_claims if lexical_score(current)),
                    key=lexical_score,
                    reverse=True,
                )
        for current in current_claims:
            if current.id not in seen_ids:
                seen_ids.add(current.id)
                claims.append(current)
                if len(claims) >= limit:
                    break
        if len(claims) >= limit:
            break

    if len(claims) < limit:
        _add_router_seeds(repo, store, query, claims, seen_ids, limit)
    if len(claims) < limit:
        _add_embedding_seed_expansion(repo, store, query, claims, seen_ids, limit)

    retrieved = [_fresh_item(repo, claim) for claim in claims]
    source: dict[str, str] = {}
    for claim in claims:
        for binding in claim.bindings:
            if binding.path not in source and Path(repo.root / binding.path).exists():
                source[binding.path] = repo.read_file(binding.path)
    return RetrieveResult(query=query, claims=retrieved, source_fallback=source)


def _claim_embedding_text(claim: Claim) -> str:
    return " ".join([
        claim.claim,
        str(claim.body.get("summary", "")),
        str(claim.body.get("keywords", [])),
        str(claim.body.get("qualname", "")),
    ])


def _add_router_seeds(repo: GitRepo, store: Store, query: str, claims: list[Claim], seen_ids: set[str], limit: int) -> None:
    candidates = [claim for claim in store.iter_claims() if claim.id not in seen_ids and check_freshness(repo, claim).fresh]
    by_id = {claim.id: claim for claim in candidates}
    for claim_id in route_claim_ids(query, candidates, limit - len(claims)):
        claim = by_id.get(claim_id)
        if claim is None or claim.id in seen_ids:
            continue
        seen_ids.add(claim.id)
        claims.append(claim)
        if len(claims) >= limit:
            return


def _add_embedding_seed_expansion(repo: GitRepo, store: Store, query: str, claims: list[Claim], seen_ids: set[str], limit: int) -> None:
    candidates = [claim for claim in store.iter_claims() if claim.id not in seen_ids and check_freshness(repo, claim).fresh]
    ranked = rank_by_embedding(query, [_claim_embedding_text(claim) for claim in candidates], max(limit * 2, limit))
    for item in ranked:
        seed = candidates[item.index]
        if seed.id not in seen_ids:
            seen_ids.add(seed.id)
            claims.append(seed)
            if len(claims) >= limit:
                return
        for neighbor in _fresh_edge_neighbors(repo, store, seed):
            if neighbor.id in seen_ids:
                continue
            seen_ids.add(neighbor.id)
            claims.append(neighbor)
            if len(claims) >= limit:
                return


def _fresh_edge_neighbors(repo: GitRepo, store: Store, claim: Claim) -> list[Claim]:
    out: list[Claim] = []
    for edge in store.iter_claims():
        if edge.body.get("edge_kind") not in {"calls", "inherits", "overrides"} or not check_freshness(repo, edge).fresh:
            continue
        neighbor_id = None
        if edge.body.get("edge_kind") == "calls":
            if edge.body.get("caller_id") == claim.id:
                neighbor_id = edge.body.get("callee_id")
            elif edge.body.get("callee_id") == claim.id:
                neighbor_id = edge.body.get("caller_id")
        elif edge.body.get("edge_kind") == "inherits":
            if edge.body.get("child_id") == claim.id:
                neighbor_id = edge.body.get("parent_id")
            elif edge.body.get("parent_id") == claim.id:
                neighbor_id = edge.body.get("child_id")
        if isinstance(neighbor_id, str):
            neighbor = store.get_claim(neighbor_id)
            if neighbor is not None and check_freshness(repo, neighbor).fresh:
                out.append(neighbor)
    return out


def reverse_callers(repo_root: str | Path, node_id: str) -> dict[str, Any]:
    repo = GitRepo(repo_root)
    store = Store(repo.root)
    index = load_complete_reverse_index(repo.root)
    if index is not None:
        indexed_callers = index.get("by_callee", {}).get(node_id, [])
        fresh_callers: list[dict[str, str | None]] = []
        for item in indexed_callers:
            if not isinstance(item, dict):
                continue
            edge_id = item.get("edge_id")
            claim = store.get_claim(edge_id) if isinstance(edge_id, str) else None
            if claim is None or not check_freshness(repo, claim).fresh:
                return _reverse_callers_lazy(repo, store, node_id)
            fresh_callers.append({k: item.get(k) for k in ["caller_id", "caller_path", "callee_qualname", "resolution", "evidence", "anchor"]})
        return {"node_id": node_id, "callers": fresh_callers, "stale_skipped": 0, "coverage": "complete", "note": COMPLETE_NOTE}
    return _reverse_callers_lazy(repo, store, node_id)


def _reverse_callers_lazy(repo: GitRepo, store: Store, node_id: str) -> dict[str, Any]:
    callers: list[dict[str, str | None]] = []
    stale_skipped = 0
    note = PARTIAL_NOTE

    def collect(claim: Claim) -> bool:
        freshness = check_freshness(repo, claim)
        if not freshness.fresh:
            return False
        callers.append({
            "caller_id": claim.body.get("caller_id"),
            "caller_path": claim.body.get("caller_path"),
            "callee_qualname": claim.body.get("callee_qualname"),
            "resolution": claim.body.get("resolution"),
            "evidence": claim.evidence,
            "anchor": claim.body.get("caller_anchor"),
        })
        return True

    for claim in list(store.iter_claims()):
        if claim.body.get("edge_kind") != "calls" or claim.body.get("callee_id") != node_id:
            continue
        if collect(claim):
            continue
        caller_path = claim.body.get("caller_path")
        if isinstance(caller_path, str) and Path(repo.root / caller_path).exists():
            # Lazy scan is the semantic baseline: future reverse indexes must return
            # the same fresh-caller set as this read-through path, only faster.
            current_claims = derive_claims_for_path(repo, caller_path)
            _replace_path_claims(store, caller_path, current_claims)
            refreshed = store.get_claim(claim.id)
            if refreshed is not None and collect(refreshed):
                continue
        stale_skipped += 1

    return {"node_id": node_id, "callers": callers, "stale_skipped": stale_skipped, "coverage": "partial", "note": note}


def reverse_readers(repo_root: str | Path, declaration_id: str) -> dict[str, Any]:
    repo = GitRepo(repo_root)
    store = Store(repo.root)
    readers: list[dict[str, str | None]] = []
    stale_skipped = 0

    def collect(claim: Claim) -> bool:
        freshness = check_freshness(repo, claim)
        if not freshness.fresh:
            return False
        readers.append({
            "reader_id": claim.body.get("reader_id"),
            "reader_path": claim.body.get("reader_path"),
            "declaration_qualname": claim.body.get("declaration_qualname"),
            "resolution": claim.body.get("resolution"),
            "evidence": claim.evidence,
            "anchor": claim.body.get("reader_anchor"),
        })
        return True

    for claim in list(store.iter_claims()):
        if claim.body.get("edge_kind") != "reads" or claim.body.get("declaration_id") != declaration_id:
            continue
        if collect(claim):
            continue
        reader_path = claim.body.get("reader_path")
        if isinstance(reader_path, str) and Path(repo.root / reader_path).exists():
            current_claims = derive_claims_for_path(repo, reader_path)
            _replace_path_claims(store, reader_path, current_claims)
            refreshed = store.get_claim(claim.id)
            if refreshed is not None and collect(refreshed):
                continue
        stale_skipped += 1
    return {"node_id": declaration_id, "readers": readers, "stale_skipped": stale_skipped, "coverage": "partial", "note": "Known readers from already-derived files only; not a complete blast radius."}


def reverse_writers(repo_root: str | Path, declaration_id: str) -> dict[str, Any]:
    repo = GitRepo(repo_root)
    store = Store(repo.root)
    writers: list[dict[str, Any]] = []
    stale_skipped = 0

    def collect(claim: Claim) -> bool:
        freshness = check_freshness(repo, claim)
        if not freshness.fresh:
            return False
        writers.append({
            "writer_id": claim.body.get("writer_id"),
            "writer_path": claim.body.get("writer_path"),
            "declaration_qualname": claim.body.get("declaration_qualname"),
            "anchor": claim.body.get("writer_anchor"),
            "resolution": claim.body.get("resolution"),
            "evidence": claim.evidence,
        })
        return True

    for claim in list(store.iter_claims()):
        if claim.body.get("edge_kind") != "writes" or claim.body.get("declaration_id") != declaration_id:
            continue
        if collect(claim):
            continue
        writer_path = claim.body.get("writer_path")
        if isinstance(writer_path, str) and Path(repo.root / writer_path).exists():
            current_claims = derive_claims_for_path(repo, writer_path)
            _replace_path_claims(store, writer_path, current_claims)
            refreshed = store.get_claim(claim.id)
            if refreshed is not None and collect(refreshed):
                continue
        stale_skipped += 1
    return {"node_id": declaration_id, "writers": writers, "stale_skipped": stale_skipped, "coverage": "partial", "note": "Known writers from already-derived files only; not a complete blast radius."}


def reverse_subtypes(repo_root: str | Path, node_id: str) -> dict[str, Any]:
    repo = GitRepo(repo_root)
    store = Store(repo.root)
    subtypes: list[dict[str, Any]] = []
    stale_skipped = 0

    def collect(claim: Claim) -> bool:
        freshness = check_freshness(repo, claim)
        if not freshness.fresh:
            return False
        subtypes.append({
            "child_id": claim.body.get("child_id"),
            "child_path": claim.body.get("child_path"),
            "parent_qualname": claim.body.get("parent_qualname"),
            "relation": claim.body.get("relation"),
            "resolution": claim.body.get("resolution"),
            "evidence": claim.evidence,
            "anchor": claim.body.get("child_anchor"),
        })
        return True

    for claim in list(store.iter_claims()):
        if claim.body.get("edge_kind") != "inherits" or claim.body.get("parent_id") != node_id or claim.body.get("relation") != "extends":
            continue
        if collect(claim):
            continue
        child_path = claim.body.get("child_path")
        if isinstance(child_path, str) and Path(repo.root / child_path).exists():
            current_claims = derive_claims_for_path(repo, child_path)
            _replace_path_claims(store, child_path, current_claims)
            refreshed = store.get_claim(claim.id)
            if refreshed is not None and collect(refreshed):
                continue
        stale_skipped += 1
    return {"node_id": node_id, "subtypes": subtypes, "stale_skipped": stale_skipped, "coverage": "partial", "note": "Known subtypes from already-derived files only; Java inheritance reverse coverage is partial."}


def reverse_implementors(repo_root: str | Path, node_id: str) -> dict[str, Any]:
    repo = GitRepo(repo_root)
    store = Store(repo.root)
    implementors: list[dict[str, Any]] = []
    stale_skipped = 0

    def collect(claim: Claim) -> bool:
        freshness = check_freshness(repo, claim)
        if not freshness.fresh:
            return False
        implementors.append({
            "child_id": claim.body.get("child_id"),
            "child_path": claim.body.get("child_path"),
            "parent_qualname": claim.body.get("parent_qualname"),
            "relation": claim.body.get("relation"),
            "resolution": claim.body.get("resolution"),
            "evidence": claim.evidence,
            "anchor": claim.body.get("child_anchor"),
        })
        return True

    for claim in list(store.iter_claims()):
        if claim.body.get("edge_kind") != "inherits" or claim.body.get("parent_id") != node_id or claim.body.get("relation") != "implements":
            continue
        if collect(claim):
            continue
        child_path = claim.body.get("child_path")
        if isinstance(child_path, str) and Path(repo.root / child_path).exists():
            current_claims = derive_claims_for_path(repo, child_path)
            _replace_path_claims(store, child_path, current_claims)
            refreshed = store.get_claim(claim.id)
            if refreshed is not None and collect(refreshed):
                continue
        stale_skipped += 1
    return {"node_id": node_id, "implementors": implementors, "stale_skipped": stale_skipped, "coverage": "partial", "note": "Known implementors from already-derived files only; Java inheritance reverse coverage is partial."}



def reverse_overridden_by(repo_root: str | Path, node_id: str) -> dict[str, Any]:
    repo = GitRepo(repo_root)
    store = Store(repo.root)
    overridden_by: list[dict[str, Any]] = []
    stale_skipped = 0

    def collect(claim: Claim) -> bool:
        freshness = check_freshness(repo, claim)
        if not freshness.fresh:
            return False
        overridden_by.append({
            "method_id": claim.body.get("method_id"),
            "method_path": claim.body.get("method_path"),
            "overridden_qualname": claim.body.get("overridden_qualname"),
            "resolution": claim.body.get("resolution"),
            "evidence": claim.evidence,
            "anchor": claim.body.get("method_anchor"),
        })
        return True

    for claim in list(store.iter_claims()):
        if claim.body.get("edge_kind") != "overrides" or claim.body.get("overridden_id") != node_id:
            continue
        if collect(claim):
            continue
        method_path = claim.body.get("method_path")
        if isinstance(method_path, str) and Path(repo.root / method_path).exists():
            current_claims = derive_claims_for_path(repo, method_path)
            _replace_path_claims(store, method_path, current_claims)
            refreshed = store.get_claim(claim.id)
            if refreshed is not None and collect(refreshed):
                continue
        stale_skipped += 1
    return {"node_id": node_id, "overridden_by": overridden_by, "stale_skipped": stale_skipped, "coverage": "partial", "note": "Known override candidates from already-derived files only; Java override coverage is partial."}


def reverse_used_by_types(repo_root: str | Path, type_id: str) -> dict[str, Any]:
    repo = GitRepo(repo_root)
    store = Store(repo.root)
    users: list[dict[str, Any]] = []
    stale_skipped = 0

    def collect(claim: Claim) -> bool:
        freshness = check_freshness(repo, claim)
        if not freshness.fresh:
            return False
        users.append({
            "user_id": claim.body.get("user_id"),
            "user_path": claim.body.get("user_path"),
            "type_qualname": claim.body.get("type_qualname"),
            "use_kind": claim.body.get("use_kind"),
            "anchor": claim.body.get("user_anchor"),
            "resolution": claim.body.get("resolution"),
            "evidence": claim.evidence,
        })
        return True

    for claim in list(store.iter_claims()):
        if claim.body.get("edge_kind") != "uses_type" or claim.body.get("type_id") != type_id:
            continue
        if collect(claim):
            continue
        user_path = claim.body.get("user_path")
        if isinstance(user_path, str) and Path(repo.root / user_path).exists():
            current_claims = derive_claims_for_path(repo, user_path)
            _replace_path_claims(store, user_path, current_claims)
            refreshed = store.get_claim(claim.id)
            if refreshed is not None and collect(refreshed):
                continue
        stale_skipped += 1
    return {"node_id": type_id, "used_by_types": users, "stale_skipped": stale_skipped, "coverage": "partial", "note": "Known Java type users from already-derived files only; not a complete blast radius."}


def reverse_env_readers(repo_root: str | Path, env_name: str) -> dict[str, Any]:
    repo = GitRepo(repo_root)
    store = Store(repo.root)
    try:
        from .ids import stable_env_claim_id
        env_id = stable_env_claim_id(env_name) if not env_name.startswith("claim_env_") else env_name
    except Exception:
        env_id = env_name
    readers: list[dict[str, Any]] = []
    stale_skipped = 0

    def collect(claim: Claim) -> bool:
        freshness = check_freshness(repo, claim)
        if not freshness.fresh:
            return False
        readers.append({
            "reader_id": claim.body.get("reader_id"),
            "reader_path": claim.body.get("reader_path"),
            "env_name": claim.body.get("env_name"),
            "resolution": claim.body.get("resolution"),
            "evidence": claim.evidence,
            "anchor": claim.body.get("reader_anchor"),
        })
        return True

    for claim in list(store.iter_claims()):
        if claim.body.get("edge_kind") != "reads_env" or claim.body.get("env_id") != env_id:
            continue
        if collect(claim):
            continue
        reader_path = claim.body.get("reader_path")
        if isinstance(reader_path, str) and Path(repo.root / reader_path).exists():
            current_claims = derive_claims_for_path(repo, reader_path)
            _replace_path_claims(store, reader_path, current_claims)
            refreshed = store.get_claim(claim.id)
            if refreshed is not None and collect(refreshed):
                continue
        stale_skipped += 1
    return {"node_id": env_id, "env_name": env_name if not env_name.startswith("claim_env_") else None, "readers": readers, "stale_skipped": stale_skipped, "coverage": "partial", "note": "Known env readers from already-derived files only; not a complete blast radius."}


def reverse_config_key_readers(repo_root: str | Path, config_id: str) -> dict[str, Any]:
    repo = GitRepo(repo_root)
    store = Store(repo.root)
    readers: list[dict[str, Any]] = []
    stale_skipped = 0

    def collect(claim: Claim) -> bool:
        freshness = check_freshness(repo, claim)
        if not freshness.fresh:
            return False
        readers.append({
            "reader_id": claim.body.get("reader_id"),
            "reader_path": claim.body.get("reader_path"),
            "config_key": claim.body.get("config_key"),
            "config_path": claim.body.get("config_path"),
            "resolution": claim.body.get("resolution"),
            "evidence": claim.evidence,
            "anchor": claim.body.get("reader_anchor"),
        })
        return True

    for claim in list(store.iter_claims()):
        if claim.body.get("edge_kind") != "reads_config_key" or claim.body.get("config_id") != config_id:
            continue
        if collect(claim):
            continue
        reader_path = claim.body.get("reader_path")
        if isinstance(reader_path, str) and Path(repo.root / reader_path).exists():
            current_claims = derive_claims_for_path(repo, reader_path)
            _replace_path_claims(store, reader_path, current_claims)
            refreshed = store.get_claim(claim.id)
            if refreshed is not None and collect(refreshed):
                continue
        stale_skipped += 1
    return {"node_id": config_id, "readers": readers, "stale_skipped": stale_skipped, "coverage": "partial", "note": "Known config-key readers from already-derived files only; not a complete blast radius."}


def reverse_injected_by(repo_root: str | Path, bean_id: str) -> dict[str, Any]:
    repo = GitRepo(repo_root); store = Store(repo.root)
    out: list[dict[str, Any]] = []; stale_skipped = 0
    def collect(claim: Claim) -> bool:
        if not check_freshness(repo, claim).fresh:
            return False
        out.append({"source_id": claim.body.get("injector_id"), "source_path": claim.body.get("injector_path"), "bean_qualname": claim.body.get("bean_qualname"), "inject_kind": claim.body.get("inject_kind"), "resolution": claim.body.get("resolution"), "evidence": claim.evidence, "confidence": claim.confidence, "tier": claim.body.get("tier")})
        return True
    for claim in list(store.iter_claims()):
        if claim.body.get("edge_kind") != "injects" or claim.body.get("bean_id") != bean_id:
            continue
        if collect(claim):
            continue
        stale_skipped += 1
    return {"node_id": bean_id, "injected_by": out, "stale_skipped": stale_skipped, "coverage": "partial", "note": "Known Spring DI attributed edges from already-derived files only."}


def reverse_topic_publishers(repo_root: str | Path, topic_id: str) -> dict[str, Any]:
    repo = GitRepo(repo_root); store = Store(repo.root)
    out: list[dict[str, Any]] = []; stale_skipped = 0
    def collect(claim: Claim) -> bool:
        if not check_freshness(repo, claim).fresh:
            return False
        out.append({"source_id": claim.body.get("source_id"), "source_path": claim.body.get("source_path"), "topic_name": claim.body.get("topic_name"), "resolution": claim.body.get("resolution"), "evidence": claim.evidence, "confidence": claim.confidence, "tier": claim.body.get("tier")})
        return True
    for claim in list(store.iter_claims()):
        if claim.body.get("edge_kind") != "publishes_to" or claim.body.get("topic_id") != topic_id:
            continue
        if collect(claim):
            continue
        stale_skipped += 1
    return {"node_id": topic_id, "publishers": out, "stale_skipped": stale_skipped, "coverage": "partial", "note": "Known Kafka publishers from already-derived files only; no direct consumer coupling inferred."}


def reverse_topic_subscribers(repo_root: str | Path, topic_id: str) -> dict[str, Any]:
    repo = GitRepo(repo_root); store = Store(repo.root)
    out: list[dict[str, Any]] = []; stale_skipped = 0
    def collect(claim: Claim) -> bool:
        if not check_freshness(repo, claim).fresh:
            return False
        out.append({"source_id": claim.body.get("source_id"), "source_path": claim.body.get("source_path"), "topic_name": claim.body.get("topic_name"), "resolution": claim.body.get("resolution"), "evidence": claim.evidence, "confidence": claim.confidence, "tier": claim.body.get("tier")})
        return True
    for claim in list(store.iter_claims()):
        if claim.body.get("edge_kind") != "subscribes_to" or claim.body.get("topic_id") != topic_id:
            continue
        if collect(claim):
            continue
        stale_skipped += 1
    return {"node_id": topic_id, "subscribers": out, "stale_skipped": stale_skipped, "coverage": "partial", "note": "Known Kafka subscribers from already-derived files only; no direct producer coupling inferred."}


def reverse_saga_participants(repo_root: str | Path, saga_id: str) -> dict[str, Any]:
    repo = GitRepo(repo_root); store = Store(repo.root)
    claim = store.get_claim(saga_id)
    if claim is None:
        return {"node_id": saga_id, "participants": [], "stale_skipped": 0, "coverage": "partial", "note": "Saga definition claim not found."}
    if not check_freshness(repo, claim).fresh:
        return {"node_id": saga_id, "participants": [], "stale_skipped": 1, "coverage": "partial", "note": "Saga definition claim is stale; source fallback required."}
    definition = claim.body.get("graph", {}).get("saga_definition")
    if not isinstance(definition, dict):
        return {"node_id": saga_id, "participants": [], "stale_skipped": 0, "coverage": "partial", "note": "No uniquely parsed SagaDefinition; unresolved evidence remains on the source claim."}
    participants = []
    for index, step in enumerate(definition.get("steps", [])):
        if step.get("kind") != "participant":
            continue
        contract = step.get("participant_contract")
        item = {"step_index": index, "method": step.get("method"), "replies": step.get("replies", []), "resolution": "eventuate_simple_saga_literal_dsl"}
        if isinstance(contract, dict):
            item["participant_contract"] = contract
            item["resolution"] = "eventuate_saga_participant_contract_unique"
        participants.append(item)
    return {"node_id": saga_id, "participants": participants, "stale_skipped": 0, "coverage": "partial", "note": "Static Saga DSL and uniquely matched participant contracts only; runtime dispatch is not inferred."}
