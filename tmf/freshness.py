from __future__ import annotations

from dataclasses import dataclass

from .extract import extract_apis, extract_classes, extract_configs, extract_declarations, extract_functions
from .java_extract import extract_java_classes, extract_java_fields, extract_java_methods, extract_java_functional_apis
from .git import GitRepo
from .schema import Claim
from .derivation_versions import versions_for_path


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
    matches: list[str] = []
    for node in nodes:
        kind = getattr(node, "declaration_kind", getattr(node, "node_kind", ""))
        node_hash = getattr(node, "declaration_hash", getattr(node, "class_hash", None))
        if node.qualname == qualname and kind == node_kind:
            if node_hash:
                matches.append(node_hash)
    # Java permits overloads with the same display qualname.  A binding is
    # fresh when its exact stored declaration token hash is still present;
    # callers compare this result to the stored binding hash below.
    return matches[0] if len(matches) == 1 else None


def _current_java_node_hashes(repo: GitRepo, path: str, qualname: str | None, node_kind: str | None) -> set[str]:
    if not qualname or not node_kind:
        return set()
    try:
        source = repo.read_file(path)
        nodes = [*extract_java_classes(path, source), *extract_java_methods(path, source), *extract_java_fields(path, source)]
    except Exception:
        return set()
    return {
        node_hash for node in nodes
        if node.qualname == qualname
        and getattr(node, "declaration_kind", getattr(node, "node_kind", "")) == node_kind
        and (node_hash := getattr(node, "declaration_hash", getattr(node, "class_hash", None)))
    }


def check_freshness(repo: GitRepo, claim: Claim) -> Freshness:
    stale: list[str] = []
    expected_versions: dict[str, str] = {}
    for binding in claim.bindings:
        expected_versions.update(versions_for_path(binding.path))
    stored_versions = claim.body.get("derivation_versions", {}) if isinstance(claim.body, dict) else {}
    for pipeline, expected in sorted(expected_versions.items()):
        actual = stored_versions.get(pipeline) if isinstance(stored_versions, dict) else None
        if actual != expected:
            stale.append(f"derivation version mismatch: {pipeline} stored={actual!r} current={expected!r}")
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
            # Relationship claims have two independently bound Java endpoints.
            # Do not fall back to an empty node kind: that made *every* edge to
            # an edited Java file stale, including unrelated declarations.
            edge_kind = claim.body.get("edge_kind")
            if binding.role == "repository_domain_entity":
                dependencies = [x.get("domain_entity_dependency") for x in claim.body.get("graph", {}).get("repository_declaration", {}).get("inherited_repository_types", [])]
                dependency = next((x for x in dependencies if x and x.get("path") == binding.path and x.get("qualname") == qualname), None)
                if dependency is None:
                    stale.append(f"{binding.path}:{qualname}: repository entity dependency metadata missing")
                    continue
                node_kind = dependency.get("node_kind")
                current_java_hashes = _current_java_node_hashes(repo, binding.path, qualname, str(node_kind or ""))
                if binding.fn_hash not in current_java_hashes:
                    stale.append(f"{binding.path}:{qualname}: java_hash mismatch or node missing")
                continue
            endpoint_fields = {
                "calls": {"caller": "caller_node_kind", "callee": "callee_node_kind"},
                "reads": {"reader": "reader_node_kind", "declaration": "declaration_node_kind"},
                "writes": {"writer": "writer_node_kind", "declaration": "declaration_node_kind"},
                "uses_type": {"user": "user_node_kind", "type": "type_node_kind"},
                "inherits": {"child": "child_node_kind", "parent": "parent_node_kind"},
                "overrides": {"method": "method_node_kind", "overridden": "overridden_node_kind"},
                "injects": {"injector": "injector_node_kind", "bean": "bean_node_kind"},
            }
            if edge_kind in endpoint_fields:
                field = endpoint_fields[edge_kind].get(binding.role or "")
                if field is None:
                    stale.append(f"{binding.path}:{qualname}: unknown java binding role {binding.role!r} for {edge_kind}")
                    continue
                node_kind = claim.body.get(field)
            else:
                node_kind = claim.body.get("node_kind")
            current_java_hashes = _current_java_node_hashes(repo, binding.path, qualname, str(node_kind or ""))
            if not current_java_hashes:
                stale.append(f"{binding.path}:{qualname}: java node missing")
            elif binding.fn_hash not in current_java_hashes:
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
