from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .extract import extract_apis, extract_classes, extract_configs, extract_declarations, extract_functions, extract_module_top_levels
from .git import GitRepo
from .schema import Claim


@dataclass(frozen=True)
class Freshness:
    fresh: bool
    stale_bindings: list[str]


def _extract_scope_map(repo: GitRepo, path: str) -> dict:
    """Parse the file once and return a lookup dict keyed by (scope, qualname/key)."""
    try:
        source = repo.read_file(path)
    except FileNotFoundError:
        return {}
    result: dict = {}
    for fn in extract_functions(path, source):
        result[("function", fn.qualname)] = fn.fn_hash
    for cls in extract_classes(path, source):
        result[("class", cls.qualname)] = cls.class_hash
    for decl in extract_declarations(path, source):
        result[("declaration", decl.qualname)] = decl.declaration_hash
    for cfg in extract_configs(path, source):
        result[("config", cfg.key)] = cfg.config_hash
    for api in extract_apis(path, source):
        result[("api", api.method, api.route_path, api.handler_qualname)] = api.api_hash
    for node in extract_module_top_levels(path, source):
        result[("module_top_level", node.region_id)] = node.top_level_hash
    return result


def check_freshness(repo: GitRepo, claim: Claim) -> Freshness:
    stale: list[str] = []
    body_qualname = claim.body.get("qualname") if isinstance(claim.body, dict) else None

    # Group bindings by path so each file is read/parsed at most once.
    by_path: dict[str, list] = defaultdict(list)
    for binding in claim.bindings:
        by_path[binding.path].append(binding)

    for path, bindings in by_path.items():
        current_blob = repo.blob_sha(path)
        # Pre-compute scope map only if any binding needs fine-grained hash.
        scope_map: dict | None = None

        for binding in bindings:
            if current_blob is None:
                stale.append(f"{path}: missing")
                continue
            if binding.fn_hash is None:
                if binding.file_blob != current_blob:
                    stale.append(f"{path}: blob mismatch")
                continue
            if binding.file_blob == current_blob:
                continue

            # Need fine-grained hash — parse once per path.
            if scope_map is None:
                scope_map = _extract_scope_map(repo, path)

            qualname = binding.qualname or (str(body_qualname) if body_qualname else None)

            if claim.scope == "class":
                current = scope_map.get(("class", qualname))
                if current is None:
                    stale.append(f"{path}:{qualname}: class missing")
                elif binding.fn_hash != current:
                    stale.append(f"{path}:{qualname}: class_hash mismatch")
                continue
            if claim.scope == "declaration":
                current = scope_map.get(("declaration", qualname))
                if current is None:
                    stale.append(f"{path}:{qualname}: declaration missing")
                elif binding.fn_hash != current:
                    stale.append(f"{path}:{qualname}: declaration_hash mismatch")
                continue
            if claim.scope == "config":
                current = scope_map.get(("config", qualname))
                if current is None:
                    stale.append(f"{path}:{qualname}: config missing")
                elif binding.fn_hash != current:
                    stale.append(f"{path}:{qualname}: config_hash mismatch")
                continue
            if claim.scope == "api":
                current = scope_map.get((
                    "api",
                    str(claim.body.get("method") or ""),
                    str(claim.body.get("route_path") or ""),
                    qualname,
                ))
                if current is None:
                    stale.append(f"{path}:{qualname}: api missing")
                elif binding.fn_hash != current:
                    stale.append(f"{path}:{qualname}: api_hash mismatch")
                continue
            if claim.scope == "module_top_level":
                current = scope_map.get(("module_top_level", qualname))
                if current is None:
                    stale.append(f"{path}:{qualname}: module_top_level missing")
                elif binding.fn_hash != current:
                    stale.append(f"{path}:{qualname}: module_top_level_hash mismatch")
                continue
            if (
                claim.body.get("edge_kind") in {"reads", "writes"}
                and path == claim.body.get("declaration_path")
                and qualname == claim.body.get("declaration_qualname")
            ):
                current = scope_map.get(("declaration", qualname))
                if current is None:
                    stale.append(f"{path}:{qualname}: declaration missing")
                elif binding.fn_hash != current:
                    stale.append(f"{path}:{qualname}: declaration_hash mismatch")
                continue
            current = scope_map.get(("function", qualname))
            if current is None:
                stale.append(f"{path}:{qualname}: function missing")
            elif binding.fn_hash != current:
                stale.append(f"{path}:{qualname}: fn_hash mismatch")

    return Freshness(fresh=not stale, stale_bindings=stale)
