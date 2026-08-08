from __future__ import annotations

from dataclasses import replace
from typing import Any

from .ids import stable_api_claim_id, stable_call_edge_claim_id, stable_class_claim_id, stable_config_claim_id, stable_contract_claim_id, stable_declaration_claim_id, stable_file_claim_id, stable_function_claim_id, stable_inherit_edge_claim_id, stable_java_node_claim_id, stable_read_edge_claim_id, stable_write_edge_claim_id
from .schema import Claim


def _node_new_id(claim: Claim, old_path: str, new_path: str) -> str:
    body = claim.body if isinstance(claim.body, dict) else {}
    q = claim.bindings[0].qualname if claim.bindings else None
    q = q or str(body.get('qualname') or body.get('handler_qualname') or '')
    if claim.scope == 'file':
        return stable_file_claim_id(new_path)
    if claim.scope == 'function':
        return stable_function_claim_id(new_path, q)
    if claim.scope == 'class':
        if body.get('language') == 'java':
            return stable_java_node_claim_id(new_path, q, str(body.get('node_kind') or 'class'))
        return stable_class_claim_id(new_path, q)
    if claim.scope == 'declaration':
        if body.get('language') == 'java':
            return stable_java_node_claim_id(new_path, q, str(body.get('node_kind') or body.get('declaration_kind') or 'field'))
        return stable_declaration_claim_id(new_path, q)
    if claim.scope == 'config':
        return stable_config_claim_id(new_path, q)
    if claim.scope == 'api':
        return stable_api_claim_id(new_path, str(body.get('method') or ''), str(body.get('route_path') or ''), str(body.get('handler_qualname') or q))
    if claim.scope == 'contract':
        return stable_contract_claim_id(new_path, q)
    return claim.id


def _edge_new_id(claim: Claim, id_map: dict[str, str]) -> str:
    kind = claim.body.get('edge_kind') if isinstance(claim.body, dict) else None
    if kind == 'calls':
        return stable_call_edge_claim_id(str(id_map.get(claim.body.get('caller_id'), claim.body.get('caller_id'))), str(id_map.get(claim.body.get('callee_id'), claim.body.get('callee_id'))))
    if kind == 'reads':
        return stable_read_edge_claim_id(str(id_map.get(claim.body.get('reader_id'), claim.body.get('reader_id'))), str(id_map.get(claim.body.get('declaration_id'), claim.body.get('declaration_id'))))
    if kind == 'writes':
        return stable_write_edge_claim_id(str(id_map.get(claim.body.get('writer_id'), claim.body.get('writer_id'))), str(id_map.get(claim.body.get('declaration_id'), claim.body.get('declaration_id'))))
    if kind == 'inherits':
        return stable_inherit_edge_claim_id(str(id_map.get(claim.body.get('child_id'), claim.body.get('child_id'))), str(id_map.get(claim.body.get('parent_id'), claim.body.get('parent_id'))), str(claim.body.get('relation') or 'extends'))
    return claim.id


def build_rename_id_map(claims: list[Claim], old_path: str, new_path: str) -> dict[str, str]:
    id_map: dict[str, str] = {}
    for claim in claims:
        if claim.body.get('edge_kind') in {'calls', 'reads', 'writes', 'inherits'}:
            continue
        if any(b.path == old_path for b in claim.bindings):
            id_map[claim.id] = _node_new_id(claim, old_path, new_path)
    for claim in claims:
        if claim.body.get('edge_kind') in {'calls', 'reads', 'writes', 'inherits'} and any(b.path == old_path for b in claim.bindings):
            id_map[claim.id] = _edge_new_id(claim, id_map)
    return id_map


def _replace_path_obj(obj: Any, old_path: str, new_path: str) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k.endswith('path') and v == old_path:
                out[k] = new_path
            else:
                out[k] = _replace_path_obj(v, old_path, new_path)
        return out
    if isinstance(obj, list):
        return [_replace_path_obj(v, old_path, new_path) for v in obj]
    return obj


def _replace_ids(obj: Any, id_map: dict[str, str]) -> Any:
    if isinstance(obj, dict):
        return {k: _replace_ids(v, id_map) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_replace_ids(v, id_map) for v in obj]
    if isinstance(obj, str):
        return id_map.get(obj, obj)
    return obj


def rebind_claim_path(claim: Claim, old_path: str, new_path: str, id_map: dict[str, str]) -> Claim:
    bindings = [replace(b, path=new_path) if b.path == old_path else b for b in claim.bindings]
    body = _replace_ids(_replace_path_obj(dict(claim.body), old_path, new_path), id_map)
    return Claim(
        id=id_map.get(claim.id, claim.id),
        claim=claim.claim.replace(old_path, new_path),
        kind=claim.kind,
        scope=claim.scope,
        bindings=bindings,
        provenance=claim.provenance,
        evidence=claim.evidence,
        confidence=claim.confidence,
        endorsed_by=claim.endorsed_by,
        last_verified=claim.last_verified,
        model=claim.model,
        body=body,
        schema_version=claim.schema_version,
    )
