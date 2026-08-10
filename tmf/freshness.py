from __future__ import annotations

from dataclasses import dataclass

from .extract import extract_apis, extract_classes, extract_configs, extract_declarations, extract_functions
from .java_extract import extract_java_classes, extract_java_fields, extract_java_methods, extract_java_functional_apis
from .git import GitRepo
from .schema import Claim


@dataclass(frozen=True)
class Freshness:
    fresh: bool
    stale_bindings: list[str]


def _current_fn_hash(repo: GitRepo, path: str, qualname: str | None) -> str | None:
    if not qualname:
        return None
    try:
        source = repo.read_file(path)
    except FileNotFoundError:
        return None
    for fn in extract_functions(path, source):
        if fn.qualname == qualname:
            return fn.fn_hash
    return None


def _current_class_hash(repo: GitRepo, path: str, qualname: str | None) -> str | None:
    if not qualname:
        return None
    try:
        source = repo.read_file(path)
    except FileNotFoundError:
        return None
    for cls in extract_classes(path, source):
        if cls.qualname == qualname:
            return cls.class_hash
    return None


def _current_declaration_hash(repo: GitRepo, path: str, qualname: str | None) -> str | None:
    if not qualname:
        return None
    try:
        source = repo.read_file(path)
    except FileNotFoundError:
        return None
    for decl in extract_declarations(path, source):
        if decl.qualname == qualname:
            return decl.declaration_hash
    return None


def _current_config_hash(repo: GitRepo, path: str, qualname: str | None) -> str | None:
    if not qualname:
        return None
    try:
        source = repo.read_file(path)
    except FileNotFoundError:
        return None
    for config in extract_configs(path, source):
        if config.key == qualname:
            return config.config_hash
    return None


def _current_api_hash(repo: GitRepo, path: str, method: str | None, route_path: str | None, handler_qualname: str | None) -> str | None:
    if not method or not route_path or not handler_qualname:
        return None
    try:
        source = repo.read_file(path)
    except FileNotFoundError:
        return None
    for api in extract_apis(path, source):
        if api.method == method and api.route_path == route_path and api.handler_qualname == handler_qualname:
            return api.api_hash
    return None


def _current_java_node_hash(repo: GitRepo, path: str, qualname: str | None, node_kind: str | None) -> str | None:
    if not qualname or not node_kind:
        return None
    try:
        source = repo.read_file(path)
    except FileNotFoundError:
        return None
    try:
        nodes = [*extract_java_classes(path, source), *extract_java_methods(path, source), *extract_java_fields(path, source)]
    except Exception:
        return None
    for node in nodes:
        kind = getattr(node, "declaration_kind", getattr(node, "node_kind", ""))
        node_hash = getattr(node, "declaration_hash", getattr(node, "class_hash", None))
        if node.qualname == qualname and kind == node_kind:
            return node_hash
    return None


def check_freshness(repo: GitRepo, claim: Claim) -> Freshness:
    stale: list[str] = []
    body_qualname = claim.body.get("qualname") if isinstance(claim.body, dict) else None
    for binding in claim.bindings:
        current_blob = repo.blob_sha(binding.path)
        if current_blob is None:
            stale.append(f"{binding.path}: missing")
            continue
        if binding.fn_hash is None:
            if binding.file_blob != current_blob:
                stale.append(f"{binding.path}: blob mismatch")
            continue
        if binding.file_blob == current_blob:
            continue
        qualname = binding.qualname or (str(body_qualname) if body_qualname else None)
        if claim.scope == "api" and claim.body.get("api_binding_model") == "dual-v2":
            if binding.role == "route_declaration":
                matches = [api for api in extract_java_functional_apis(repo, binding.path, repo.read_file(binding.path))
                           if api.method == claim.body.get("method") and api.route_path == claim.body.get("route_path")
                           and api.handler_node_id == claim.body.get("handler_node_id")]
                if len(matches) != 1:
                    stale.append(f"{binding.path}:{qualname}: route declaration missing")
                elif binding.fn_hash != matches[0].route_hash:
                    stale.append(f"{binding.path}:{qualname}: route_hash mismatch")
                continue
            if binding.role == "handler":
                current_java_hash = _current_java_node_hash(repo, binding.path, qualname, "method")
                if current_java_hash is None:
                    stale.append(f"{binding.path}:{qualname}: handler missing")
                elif binding.fn_hash != current_java_hash:
                    stale.append(f"{binding.path}:{qualname}: handler_hash mismatch")
                continue
        if claim.scope == "api":
            current_api_hash = _current_api_hash(
                repo,
                binding.path,
                str(claim.body.get("method") or ""),
                str(claim.body.get("route_path") or ""),
                qualname,
            )
            if current_api_hash is None:
                stale.append(f"{binding.path}:{qualname}: api missing")
            elif binding.fn_hash != current_api_hash:
                stale.append(f"{binding.path}:{qualname}: api_hash mismatch")
            continue
        if claim.body.get("language") == "java":
            current_java_hash = _current_java_node_hash(repo, binding.path, qualname, str(claim.body.get("node_kind") or ""))
            if current_java_hash is None:
                stale.append(f"{binding.path}:{qualname}: java node missing")
            elif binding.fn_hash != current_java_hash:
                stale.append(f"{binding.path}:{qualname}: java_hash mismatch")
            continue
        if claim.scope == "class":
            current_class_hash = _current_class_hash(repo, binding.path, qualname)
            if current_class_hash is None:
                stale.append(f"{binding.path}:{qualname}: class missing")
            elif binding.fn_hash != current_class_hash:
                stale.append(f"{binding.path}:{qualname}: class_hash mismatch")
            continue
        if claim.scope == "declaration":
            current_declaration_hash = _current_declaration_hash(repo, binding.path, qualname)
            if current_declaration_hash is None:
                stale.append(f"{binding.path}:{qualname}: declaration missing")
            elif binding.fn_hash != current_declaration_hash:
                stale.append(f"{binding.path}:{qualname}: declaration_hash mismatch")
            continue
        if claim.scope == "config":
            current_config_hash = _current_config_hash(repo, binding.path, qualname)
            if current_config_hash is None:
                stale.append(f"{binding.path}:{qualname}: config missing")
            elif binding.fn_hash != current_config_hash:
                stale.append(f"{binding.path}:{qualname}: config_hash mismatch")
            continue
        if claim.body.get("edge_kind") in {"reads", "writes"} and binding.path == claim.body.get("declaration_path") and qualname == claim.body.get("declaration_qualname"):
            current_declaration_hash = _current_declaration_hash(repo, binding.path, qualname)
            if current_declaration_hash is None:
                stale.append(f"{binding.path}:{qualname}: declaration missing")
            elif binding.fn_hash != current_declaration_hash:
                stale.append(f"{binding.path}:{qualname}: declaration_hash mismatch")
            continue
        if claim.body.get("edge_kind") == "inherits":
            if binding.path == claim.body.get("child_path") and qualname == claim.body.get("child_qualname"):
                node_kind = str(claim.body.get("child_node_kind") or "")
            elif binding.path == claim.body.get("parent_path") and qualname == claim.body.get("parent_qualname"):
                node_kind = str(claim.body.get("parent_node_kind") or "")
            else:
                node_kind = ""
            current_java_hash = _current_java_node_hash(repo, binding.path, qualname, node_kind)
            if current_java_hash is None:
                stale.append(f"{binding.path}:{qualname}: java node missing")
            elif binding.fn_hash != current_java_hash:
                stale.append(f"{binding.path}:{qualname}: java_hash mismatch")
            continue
        current_fn_hash = _current_fn_hash(repo, binding.path, qualname)
        if current_fn_hash is None:
            stale.append(f"{binding.path}:{qualname}: function missing")
        elif binding.fn_hash != current_fn_hash:
            stale.append(f"{binding.path}:{qualname}: fn_hash mismatch")
    return Freshness(fresh=not stale, stale_bindings=stale)
