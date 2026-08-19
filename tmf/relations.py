from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .boundary_detection import is_semantic_boundary
from .derivation_versions import versions_for_path
from .freshness import Freshness, check_freshness
from .git import GitRepo
from .index import EDGE_ENDPOINT_FIELDS
from .schema import Claim
from .store import Store

HARD_MAX_NODES = 64
HARD_MAX_EDGES = 128
HARD_MAX_HOPS = 4

# Async handoff relations: these represent asynchronous message passing,
# not synchronous call flow
ASYNC_RELATIONS = frozenset(["publishes_to", "subscribes_to", "publishes_type", "listens_type"])


@dataclass
class RequestFreshnessCache:
    """Request-scoped cache keyed by the current source/version fingerprint."""

    repo: GitRepo
    _items: dict[tuple[str, tuple[Any, ...]], Freshness] = field(default_factory=dict)

    def _fingerprint(self, claim: Claim) -> tuple[Any, ...]:
        bindings = tuple(
            (
                binding.path,
                self.repo.blob_sha(binding.path),
                binding.file_blob,
                binding.fn_hash,
                binding.qualname,
                binding.role,
            )
            for binding in claim.bindings
        )
        versions = tuple(sorted(
            (pipeline, version)
            for binding in claim.bindings
            for pipeline, version in versions_for_path(binding.path).items()
        ))
        stored_versions = tuple(sorted((claim.body.get("derivation_versions") or {}).items()))
        return bindings, versions, stored_versions

    def check(self, claim: Claim) -> Freshness:
        key = (claim.id, self._fingerprint(claim))
        cached = self._items.get(key)
        if cached is None:
            cached = check_freshness(self.repo, claim)
            self._items[key] = cached
        return cached


def _foreign(claim: Claim) -> bool:
    return claim.body.get("source_provenance", {}).get("trust") == "unverified_foreign"


def _hint(claim: Claim) -> dict[str, Any]:
    anchors = claim.body.get("anchors") or []
    anchor = anchors[0] if anchors else (claim.bindings[0].path if claim.bindings else None)
    return {
        "claim_id": claim.id,
        "qualname": claim.body.get("qualname"),
        "path": claim.bindings[0].path if claim.bindings else None,
        "scope": claim.scope,
        "anchor": anchor,
    }


def _classify_branching(
    edges: list[tuple[str, str, list[str]]],  # (edge_id, relation_kind, endpoint_ids)
) -> dict[str, Any]:
    """
    Classify routing shape into single/branching/unresolved tri-state.
    
    Returns:
        {
            "shape": "single" | "branching" | "unresolved",
            "next_hop_count": int,
            "polymorphic": bool,  # True if contains override edges
            "async_handoff": bool,  # True if contains async message edges
        }
    """
    if not edges:
        return {"shape": "unresolved", "next_hop_count": 0, "polymorphic": False, "async_handoff": False}
    
    next_hops = set()
    has_override = False
    has_async = False
    
    for edge_id, relation_kind, endpoint_ids in edges:
        if relation_kind == "overrides":
            has_override = True
        if relation_kind in ASYNC_RELATIONS:
            has_async = True
        next_hops.update(endpoint_ids)
    
    count = len(next_hops)
    if count == 0:
        shape = "unresolved"
    elif count == 1:
        shape = "single"
    else:
        shape = "branching"
    
    return {
        "shape": shape,
        "next_hop_count": count,
        "polymorphic": has_override,
        "async_handoff": has_async,
    }


def bounded_fragment(
    repo: GitRepo,
    store: Store,
    *,
    entry: str,
    relations: Iterable[str],
    hop_limit: int,
    boundary_types: Iterable[str],
    max_nodes: int = HARD_MAX_NODES,
    max_edges: int = HARD_MAX_EDGES,
    semantic_boundaries: bool = True,
) -> dict[str, Any]:
    """Return a bounded evidence fragment. This is a query result, not a graph.
    
    Args:
        semantic_boundaries: If True, use semantic boundary detection (writes/publishes)
                           instead of scope-based boundary_types for Java/enterprise code.
                           Semantic detection identifies persistence and message queue boundaries
                           by checking indexed writes/publishes_to edges.
                           Declaration annotations (@Transactional, @Async) are not currently
                           indexed as reverse edges and cannot be used for boundary detection.
                           Legacy scope-based detection remains as fallback when disabled.
    """
    relation_set = {str(kind) for kind in relations}
    boundaries_set = {str(scope) for scope in boundary_types}
    if not entry or not relation_set or hop_limit < 0:
        raise ValueError("entry, relations, and hop_limit are required and non-empty")
    unknown_relations = relation_set.difference(EDGE_ENDPOINT_FIELDS)
    if unknown_relations:
        raise ValueError(f"unsupported relations: {sorted(unknown_relations)}")
    if hop_limit > HARD_MAX_HOPS:
        raise ValueError(f"hop_limit exceeds hard limit {HARD_MAX_HOPS}")
    if not 1 <= max_nodes <= HARD_MAX_NODES or not 1 <= max_edges <= HARD_MAX_EDGES:
        raise ValueError(
            f"bounds must satisfy max_nodes<= {HARD_MAX_NODES}, max_edges<= {HARD_MAX_EDGES}"
        )

    cache = RequestFreshnessCache(repo)
    entry_claim = store.get_claim(entry)
    nodes: dict[str, Claim] = {}
    edges: list[dict[str, Any]] = []
    boundaries: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    stale_or_unknown: list[dict[str, Any]] = []
    stop_reason = "frontier_exhausted"
    if entry_claim is None:
        return {
            "entry": entry,
            "verified_hops": [],
            "boundaries": [],
            "gaps": [{"at": entry, "reason": "entry_claim_missing"}],
            "stale_or_unknown": [],
            "stop_reason": "entry_missing",
            "coverage": "partial",
        }
    if not cache.check(entry_claim).fresh or _foreign(entry_claim):
        return {
            "entry": _hint(entry_claim),
            "verified_hops": [],
            "boundaries": [],
            "gaps": [],
            "stale_or_unknown": [{"claim_id": entry, "reason": "entry_stale_or_unverified"}],
            "stop_reason": "entry_stale_or_unknown",
            "coverage": "partial",
        }
    nodes[entry] = entry_claim
    frontier = [entry]
    seen_edges: set[str] = set()
    
    # Track routing shape per hop
    routing_by_hop: dict[int, dict[str, Any]] = {}
    
    for hop in range(1, hop_limit + 1):
        next_frontier: list[str] = []
        hop_edges: list[tuple[str, str, list[str]]] = []  # (edge_id, relation_kind, endpoint_ids)
        
        for endpoint in frontier:
            remaining = max_edges - len(edges)
            if remaining <= 0:
                stop_reason = "max_edges"
                break
            edge_ids = store.index.edge_ids(endpoint, relation_kinds=relation_set, limit=remaining + 1)
            if edge_ids is None:
                gaps.append({"at": endpoint, "reason": "endpoint_edge_index_missing"})
                stop_reason = "index_missing"
                continue
            if len(edge_ids) > remaining:
                edge_ids = edge_ids[:remaining]
                stop_reason = "max_edges"
            for edge_id in edge_ids:
                if edge_id in seen_edges:
                    continue
                seen_edges.add(edge_id)
                edge = store.get_claim(edge_id)
                if edge is None:
                    stale_or_unknown.append({"edge_id": edge_id, "reason": "edge_claim_missing"})
                    continue
                freshness = cache.check(edge)
                if not freshness.fresh or _foreign(edge):
                    stale_or_unknown.append({"edge_id": edge_id, "reason": "edge_stale_or_unverified"})
                    continue
                kind = str(edge.body.get("edge_kind"))
                fields = EDGE_ENDPOINT_FIELDS[kind]
                endpoint_ids = {field: edge.body.get(field) for field in fields}
                endpoint_claims: dict[str, Claim] = {}
                bad = False
                for value in endpoint_ids.values():
                    claim = store.get_claim(value) if isinstance(value, str) else None
                    if claim is None or not cache.check(claim).fresh or _foreign(claim):
                        stale_or_unknown.append({"edge_id": edge_id, "endpoint": value, "reason": "endpoint_stale_or_unknown"})
                        bad = True
                        break
                    endpoint_claims[claim.id] = claim
                if bad:
                    continue
                new_ids = [claim_id for claim_id in endpoint_claims if claim_id not in nodes]
                if len(nodes) + len(new_ids) > max_nodes:
                    stop_reason = "max_nodes"
                    break
                nodes.update(endpoint_claims)
                
                # Classify edge for routing shape analysis
                is_async = kind in ASYNC_RELATIONS
                
                edges.append({
                    "hop": hop,
                    "edge_id": edge_id,
                    "relation_kind": kind,
                    "endpoints": endpoint_ids,
                    "endpoint_hints": {field: _hint(endpoint_claims[value]) for field, value in endpoint_ids.items()},
                    "async_handoff": is_async,
                })
                
                # Collect for routing shape analysis
                hop_edges.append((edge_id, kind, list(endpoint_ids.values())))
                
                for claim_id in new_ids:
                    claim = endpoint_claims[claim_id]
                    
                    # Determine if this is a boundary
                    is_boundary = False
                    if semantic_boundaries:
                        # Semantic detection: check for @Transactional, @Async, writes, publishes_to
                        is_boundary = is_semantic_boundary(store, claim_id)
                    else:
                        # Legacy scope-based detection
                        is_boundary = claim.scope in boundaries_set
                    
                    if is_boundary:
                        boundaries.append({**_hint(claim), "reached_at_hop": hop})
                    else:
                        # Async handoff edges don't contribute to synchronous frontier
                        if not is_async:
                            next_frontier.append(claim_id)
            if stop_reason in {"max_nodes", "max_edges"}:
                break
        
        # Analyze routing shape for this hop
        routing_by_hop[hop] = _classify_branching(hop_edges)
        
        frontier = sorted(set(next_frontier))
        if stop_reason in {"max_nodes", "max_edges"} or not frontier:
            break
    else:
        if frontier:
            stop_reason = "hop_limit"
    if hop_limit == 0:
        stop_reason = "hop_limit"
    coverage = "partial" if gaps or stale_or_unknown or stop_reason in {"index_missing", "max_nodes", "max_edges", "hop_limit"} else "complete_for_indexed_bounded_query"
    return {
        "entry": _hint(entry_claim),
        "verified_hops": edges,
        "boundaries": boundaries,
        "gaps": gaps,
        "stale_or_unknown": stale_or_unknown,
        "stop_reason": stop_reason,
        "coverage": coverage,
        "routing_shape": routing_by_hop,
    }
