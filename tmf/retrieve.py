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
    store.reconcile_path_claims(relpath, [c for c in claims if c.body.get("edge_kind") not in {"calls", "reads", "writes"}])
    store.reconcile_edge_claims_for_caller_path(relpath, [c for c in claims if c.body.get("edge_kind") in {"calls", "reads", "writes"}])


def retrieve_path(repo_root: str | Path, path: str, *, use_model: bool = False) -> RetrieveResult:
    repo = GitRepo(repo_root)
    store = Store(repo.root)
    rel = repo.relpath(path)
    claims = store.claims_for_path(rel)

    # v1 read-through: missing or stale => derive current file + function claims synchronously.
    if not claims or any(not check_freshness(repo, c).fresh for c in claims):
        current_claims = derive_claims_for_path(repo, rel, use_model=use_model)
        _replace_path_claims(store, rel, current_claims)
        claims = current_claims

    retrieved = [_fresh_item(repo, claim) for claim in claims]
    source = repo.read_file(rel)
    return RetrieveResult(query=rel, claims=retrieved, source_fallback={rel: source})


def retrieve_text(repo_root: str | Path, query: str, limit: int = 5, *, use_model: bool = False) -> RetrieveResult:
    repo = GitRepo(repo_root)
    store = Store(repo.root)
    terms = {t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", query)}
    scored: list[tuple[int, Claim]] = []
    for claim in store.iter_claims():
        hay = " ".join([claim.claim, str(claim.body.get("keywords", [])), claim.bindings[0].path if claim.bindings else ""]).lower()
        score = sum(1 for term in terms if term in hay)
        if score:
            scored.append((score, claim))
    scored.sort(key=lambda item: item[0], reverse=True)

    claims: list[Claim] = []
    seen_ids: set[str] = set()
    for _, claim in scored[:limit]:
        current_claims = [claim]
        freshness = check_freshness(repo, claim)
        if not freshness.fresh and claim.bindings:
            path = claim.bindings[0].path
            if Path(repo.root / path).exists():
                current_claims = derive_claims_for_path(repo, path, use_model=use_model)
                _replace_path_claims(store, path, current_claims)
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
        if edge.body.get("edge_kind") != "calls" or not check_freshness(repo, edge).fresh:
            continue
        neighbor_id = None
        if edge.body.get("caller_id") == claim.id:
            neighbor_id = edge.body.get("callee_id")
        elif edge.body.get("callee_id") == claim.id:
            neighbor_id = edge.body.get("caller_id")
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
