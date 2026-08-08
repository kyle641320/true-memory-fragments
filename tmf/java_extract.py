from __future__ import annotations

import hashlib
from functools import lru_cache
from dataclasses import dataclass
from typing import Any

from .extract import ApiNode, ClassNode, DeclarationNode, _identifier_keywords

JAVA_DEGRADE_HINT = (
    "Java extraction requires optional dependencies: tree_sitter and "
    "tree_sitter_java. Install in a venv with `python -m pip install "
    "tree_sitter tree_sitter_java`, then rerun TMF."
)


@dataclass(frozen=True)
class JavaExtractionStatus:
    available: bool
    degrade_hint: str | None = None


@lru_cache(maxsize=1)
def _java_available() -> bool:
    try:
        _language_and_parser()
        return True
    except Exception:
        return False


def java_status() -> JavaExtractionStatus:
    available = _java_available()
    return JavaExtractionStatus(available=available, degrade_hint=None if available else JAVA_DEGRADE_HINT)


def _language_and_parser():
    # Lazy imports keep Python core at zero hard dependency.
    from tree_sitter import Language, Parser  # type: ignore
    import tree_sitter_java  # type: ignore

    language_obj = tree_sitter_java.language()
    try:
        language = Language(language_obj)
    except TypeError:  # older bindings may already return a Language
        language = language_obj
    parser = Parser()
    if hasattr(parser, "set_language"):
        parser.set_language(language)
    else:
        parser.language = language
    return language, parser


_SKIP_LEAF_TYPES = {"line_comment", "block_comment"}


def _is_named_type(node: Any, type_name: str) -> bool:
    return getattr(node, "type", None) == type_name


def _children(node: Any) -> list[Any]:
    return list(getattr(node, "children", []) or [])


def _named_children(node: Any) -> list[Any]:
    return list(getattr(node, "named_children", []) or [])


def _child_by_field(node: Any, field: str) -> Any | None:
    getter = getattr(node, "child_by_field_name", None)
    if getter is None:
        return None
    return getter(field)


def _node_text(source_bytes: bytes, node: Any) -> str:
    return source_bytes[int(node.start_byte): int(node.end_byte)].decode("utf-8", errors="replace")


def _line_start(node: Any) -> int:
    return int(node.start_point[0]) + 1


def _line_end(node: Any) -> int:
    return int(node.end_point[0]) + 1


def _leaf_token_items(source_bytes: bytes, node: Any) -> list[str]:
    items: list[str] = []

    def walk(cur: Any) -> None:
        if cur.type in _SKIP_LEAF_TYPES:
            return
        children = _children(cur)
        if not children:
            text = _node_text(source_bytes, cur)
            if text.strip():
                items.append(f"{cur.type}:{text}")
            return
        for child in children:
            walk(child)

    walk(node)
    return items


def java_hash_for_node(source: str, node: Any) -> str:
    source_bytes = source.encode("utf-8")
    token_stream = "\0".join(_leaf_token_items(source_bytes, node))
    return hashlib.sha256(token_stream.encode("utf-8")).hexdigest()


def _find_descendant(node: Any, type_name: str) -> Any | None:
    if node.type == type_name:
        return node
    for child in _named_children(node):
        found = _find_descendant(child, type_name)
        if found is not None:
            return found
    return None


def _identifier_from_node(source_bytes: bytes, node: Any) -> str | None:
    name = _child_by_field(node, "name")
    if name is not None:
        return _node_text(source_bytes, name)
    for child in _named_children(node):
        if child.type == "identifier":
            return _node_text(source_bytes, child)
    return None


def _constants_from_field_declaration(source_bytes: bytes, field_node: Any) -> list[str]:
    names: list[str] = []

    def walk(cur: Any) -> None:
        if cur.type == "variable_declarator":
            name_node = _child_by_field(cur, "name")
            if name_node is not None:
                name = _node_text(source_bytes, name_node)
                if name.isupper():
                    names.append(name)
            return
        for child in _named_children(cur):
            walk(child)

    walk(field_node)
    return names


def _field_qualnames(source_bytes: bytes, field_node: Any, container_stack: list[str]) -> list[str]:
    names: list[str] = []

    def walk(cur: Any) -> None:
        if cur.type == "variable_declarator":
            name_node = _child_by_field(cur, "name")
            if name_node is not None:
                names.append(".".join([*container_stack, _node_text(source_bytes, name_node)]))
            return
        for child in _named_children(cur):
            walk(child)

    walk(field_node)
    return names


def _method_qualname(source_bytes: bytes, method_node: Any, container_stack: list[str]) -> str | None:
    name = _identifier_from_node(source_bytes, method_node)
    if name is None:
        return None
    return ".".join([*container_stack, name])


_CLASS_TYPES = {"class_declaration", "interface_declaration", "enum_declaration"}
_METHOD_TYPES = {"method_declaration", "constructor_declaration"}




def _java_string_literal_value(source_bytes: bytes, node: Any | None) -> str | None:
    if node is None or node.type != "string_literal":
        return None
    text = _node_text(source_bytes, node).strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return None


def _java_annotation_name(source_bytes: bytes, node: Any) -> str | None:
    for child in _named_children(node):
        if child.type in {"identifier", "scoped_identifier"}:
            return _node_text(source_bytes, child).split(".")[-1]
    return None


def _java_annotation_args(node: Any) -> list[Any]:
    args = _find_descendant(node, "annotation_argument_list")
    if args is None:
        return []
    return _named_children(args)


def _java_annotation_literal_path(source_bytes: bytes, node: Any) -> tuple[str | None, str | None]:
    args = _java_annotation_args(node)
    for arg in args:
        if arg.type == "string_literal":
            return _java_string_literal_value(source_bytes, arg), None
        # element_value_pair value="/x" or path="/x"
        value = _child_by_field(arg, "value")
        if value is not None and value.type == "string_literal":
            return _java_string_literal_value(source_bytes, value), None
    if args:
        return None, "java_route_path_not_literal"
    return "", None


def _join_java_paths(prefix: str, route: str) -> str:
    if not prefix:
        return route or ""
    if not route:
        return prefix
    return "/" + prefix.strip("/") + "/" + route.strip("/")


def _java_route_contract(source_bytes: bytes, annotation: Any) -> tuple[list[str], str | None, str | None] | None:
    name = _java_annotation_name(source_bytes, annotation)
    if name is None:
        return None
    shortcut = {
        "GetMapping": "GET",
        "PostMapping": "POST",
        "PutMapping": "PUT",
        "DeleteMapping": "DELETE",
    }
    if name in shortcut:
        path, reason = _java_annotation_literal_path(source_bytes, annotation)
        return [shortcut[name]], path, reason
    if name == "RequestMapping":
        path, reason = _java_annotation_literal_path(source_bytes, annotation)
        # Conservative MVP: only literal path is parsed; method attribute parsing can be extended later.
        return ["UNSPECIFIED"], path, reason
    return None


def _java_annotations(node: Any) -> list[Any]:
    mods = None
    for child in _named_children(node):
        if child.type == "modifiers":
            mods = child
            break
    if mods is None:
        return []
    return [c for c in _named_children(mods) if c.type in {"annotation", "marker_annotation"}]


def extract_java_apis(path: str, source: str) -> list[ApiNode]:
    if not path.endswith(".java"):
        return []
    _language, parser = _language_and_parser()
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    out: list[ApiNode] = []

    def walk(node: Any, stack: list[str], class_prefix: str) -> None:
        next_stack = stack
        next_prefix = class_prefix
        if node.type in _CLASS_TYPES:
            name = _identifier_from_node(source_bytes, node)
            if name:
                next_stack = [*stack, name]
            for ann in _java_annotations(node):
                contract = _java_route_contract(source_bytes, ann)
                if contract is None:
                    continue
                _methods, prefix, reason = contract
                if reason is None and prefix is not None:
                    next_prefix = prefix
                elif reason is not None:
                    next_prefix = ""
        elif node.type == "method_declaration":
            qualname = _method_qualname(source_bytes, node, stack)
            if qualname:
                for ann in _java_annotations(node):
                    contract = _java_route_contract(source_bytes, ann)
                    if contract is None:
                        continue
                    methods, route, reason = contract
                    if reason is not None or route is None:
                        continue
                    full_path = _join_java_paths(class_prefix, route)
                    line_start = _line_start(ann)
                    line_end = _line_end(node)
                    api_hash = java_hash_for_node(source, node)
                    for method in methods:
                        out.append(ApiNode(
                            path=path,
                            method=method,
                            route_path=full_path,
                            handler_qualname=qualname,
                            line_start=line_start,
                            line_end=line_end,
                            api_hash=api_hash,
                            keywords=_identifier_keywords(f"{full_path}_{qualname}"),
                        ))
        for child in _named_children(node):
            walk(child, next_stack, next_prefix)

    walk(tree.root_node, [], "")
    return out


def extract_java_classes(path: str, source: str) -> list[ClassNode]:
    if not path.endswith(".java"):
        return []
    _language, parser = _language_and_parser()
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    root = tree.root_node
    out: list[ClassNode] = []

    def walk(node: Any, stack: list[str]) -> None:
        if node.type in _CLASS_TYPES:
            name = _identifier_from_node(source_bytes, node)
            if name:
                qualname = ".".join([*stack, name])
                kind = node.type.replace("_declaration", "")
                out.append(ClassNode(
                    path=path,
                    qualname=qualname,
                    line_start=_line_start(node),
                    line_end=_line_end(node),
                    class_hash=java_hash_for_node(source, node),
                    keywords=_identifier_keywords(qualname),
                    docstring=None,
                    language="java",
                    node_kind=kind,
                    extraction_tier="java-treesitter-syntactic",
                ))
                stack = [*stack, name]
        for child in _named_children(node):
            walk(child, stack)

    walk(root, [])
    return out


def extract_java_methods(path: str, source: str) -> list[ClassNode]:
    if not path.endswith(".java"):
        return []
    _language, parser = _language_and_parser()
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    root = tree.root_node
    out: list[ClassNode] = []

    def walk(node: Any, stack: list[str]) -> None:
        next_stack = stack
        if node.type in _CLASS_TYPES:
            name = _identifier_from_node(source_bytes, node)
            if name:
                next_stack = [*stack, name]
        elif node.type in _METHOD_TYPES:
            qualname = _method_qualname(source_bytes, node, stack)
            if qualname:
                out.append(ClassNode(
                    path=path,
                    qualname=qualname,
                    line_start=_line_start(node),
                    line_end=_line_end(node),
                    class_hash=java_hash_for_node(source, node),
                    keywords=_identifier_keywords(qualname),
                    docstring=None,
                    language="java",
                    node_kind="method" if node.type == "method_declaration" else "constructor",
                    extraction_tier="java-treesitter-syntactic",
                ))
        for child in _named_children(node):
            walk(child, next_stack)

    walk(root, [])
    return out


def extract_java_fields(path: str, source: str) -> list[DeclarationNode]:
    if not path.endswith(".java"):
        return []
    _language, parser = _language_and_parser()
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    root = tree.root_node
    out: list[DeclarationNode] = []

    def walk(node: Any, stack: list[str]) -> None:
        next_stack = stack
        if node.type in _CLASS_TYPES:
            name = _identifier_from_node(source_bytes, node)
            if name:
                next_stack = [*stack, name]
        elif node.type in {"field_declaration", "constant_declaration"}:
            constants = set(_constants_from_field_declaration(source_bytes, node))
            for qualname in _field_qualnames(source_bytes, node, stack):
                simple = qualname.rsplit(".", 1)[-1]
                kind = "constant" if node.type == "constant_declaration" or simple in constants else "field"
                out.append(DeclarationNode(
                    path=path,
                    qualname=qualname,
                    line_start=_line_start(node),
                    line_end=_line_end(node),
                    declaration_hash=java_hash_for_node(source, node),
                    keywords=_identifier_keywords(qualname),
                    declaration_kind=kind,
                    language="java",
                    extraction_tier="java-treesitter-syntactic",
                ))
        for child in _named_children(node):
            walk(child, next_stack)

    walk(root, [])
    return out


@dataclass(frozen=True)
class JavaCallEdge:
    caller_id: str
    callee_id: str
    callee_qualname: str
    evidence: str = "observed"
    resolution: str = "java_syntax"
    caller_path: str | None = None
    callee_path: str | None = None
    caller_fn_hash: str | None = None
    callee_fn_hash: str | None = None
    caller_qualname: str | None = None
    callee_node_kind: str | None = "method"
    language: str = "java"


@dataclass(frozen=True)
class JavaUnresolvedCall:
    caller_id: str
    expr: str
    reason: str


def _method_signature_parts(source_bytes: bytes, node: Any) -> tuple[str | None, int, tuple[str, ...]]:
    name = _identifier_from_node(source_bytes, node)
    params = _child_by_field(node, "parameters")
    types: list[str] = []
    if params is not None:
        for child in _named_children(params):
            if child.type in {"formal_parameter", "spread_parameter"}:
                typ = _child_by_field(child, "type")
                types.append(_node_text(source_bytes, typ).strip() if typ is not None else "")
    return name, len(types), tuple(types)


def _method_signature_index(path: str, source: str) -> dict[str, tuple[int, tuple[str, ...]]]:
    if not path.endswith(".java"):
        return {}
    _language, parser = _language_and_parser()
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    out: dict[str, tuple[int, tuple[str, ...]]] = {}
    stack: list[str] = []

    def walk(node: Any, stack: list[str]) -> None:
        next_stack = stack
        if node.type in _CLASS_TYPES:
            name = _identifier_from_node(source_bytes, node)
            if name:
                next_stack = [*stack, name]
        elif node.type in _METHOD_TYPES:
            name, argc, types = _method_signature_parts(source_bytes, node)
            if name:
                out[".".join([*stack, name])] = (argc, types)
        for child in _named_children(node):
            walk(child, next_stack)

    walk(tree.root_node, [])
    return out


def _call_expr_name(source_bytes: bytes, node: Any) -> tuple[str, str | None] | None:
    name_node = _child_by_field(node, "name")
    if name_node is None:
        return None
    name = _node_text(source_bytes, name_node)
    obj = _child_by_field(node, "object")
    if obj is None:
        return name, None
    return name, _node_text(source_bytes, obj).strip()


def _call_arg_count(node: Any) -> int:
    args = _child_by_field(node, "arguments")
    if args is None:
        return 0
    return len([c for c in _named_children(args) if c.type not in {",", "(" , ")"}])


def resolve_java_call_edges(path: str, source: str, java_methods: list[ClassNode], repo: Any | None = None) -> tuple[list[JavaCallEdge], dict[str, list[JavaUnresolvedCall]]]:
    if not path.endswith(".java"):
        return [], {}
    _language, parser = _language_and_parser()
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    root = tree.root_node
    explicit_imports, _wildcards = _java_imports(source_bytes, root)
    by_qual = {m.qualname: m for m in java_methods if m.node_kind == "method"}
    by_class: dict[str, list[ClassNode]] = {}
    for m in java_methods:
        if m.node_kind == "method" and "." in m.qualname:
            cls = m.qualname.rsplit(".", 1)[0]
            by_class.setdefault(cls, []).append(m)
    classes_by_qual = {cls.qualname: cls for cls in extract_java_classes(path, source)}
    sigs_current = _method_signature_index(path, source)
    edges: list[JavaCallEdge] = []
    unresolved: dict[str, list[JavaUnresolvedCall]] = {}

    def add_unresolved(caller: ClassNode, expr: str, reason: str) -> None:
        caller_id = __import__("tmf.ids", fromlist=["stable_java_node_claim_id"]).stable_java_node_claim_id(caller.path, caller.qualname, caller.node_kind)
        unresolved.setdefault(caller_id, []).append(JavaUnresolvedCall(caller_id=caller_id, expr=expr, reason=reason))

    def add_edge(caller: ClassNode, callee: ClassNode, resolution: str) -> None:
        ids = __import__("tmf.ids", fromlist=["stable_java_node_claim_id"])
        edges.append(JavaCallEdge(
            caller_id=ids.stable_java_node_claim_id(caller.path, caller.qualname, caller.node_kind),
            callee_id=ids.stable_java_node_claim_id(callee.path, callee.qualname, callee.node_kind),
            callee_qualname=callee.qualname,
            resolution=resolution,
            caller_path=caller.path,
            callee_path=callee.path,
            caller_fn_hash=caller.class_hash,
            callee_fn_hash=callee.class_hash,
            caller_qualname=caller.qualname,
            callee_node_kind=callee.node_kind,
        ))

    def unique_method(methods: list[ClassNode], name: str, argc: int) -> tuple[ClassNode | None, str | None]:
        cands = [m for m in methods if m.qualname.rsplit(".", 1)[-1] == name]
        if not cands:
            return None, "java_method_not_found"
        argc_matches = []
        for m in cands:
            sig = sigs_current.get(m.qualname)
            if sig is None or sig[0] == argc:
                argc_matches.append(m)
        if len(argc_matches) == 1:
            return argc_matches[0], None
        return None, "java_overloaded_or_ambiguous_method"

    def imported_methods(type_name: str) -> tuple[list[ClassNode], str | None]:
        if repo is None or type_name not in explicit_imports:
            return [], "java_variable_or_unknown_receiver"
        target_path = explicit_imports[type_name]
        try:
            target_source = repo.read_file(target_path)
        except Exception:
            return [], "java_external_or_jdk_receiver"
        methods = extract_java_methods(target_path, target_source)
        methods = [m for m in methods if m.qualname.startswith(type_name + ".")]
        return methods, None

    def visit(node: Any, stack: list[str]) -> None:
        next_stack = stack
        current_method: ClassNode | None = None
        if node.type in _CLASS_TYPES:
            name = _identifier_from_node(source_bytes, node)
            if name:
                next_stack = [*stack, name]
        elif node.type in _METHOD_TYPES:
            q = _method_qualname(source_bytes, node, stack)
            current_method = by_qual.get(q or "")
        if current_method is not None:
            class_qual = current_method.qualname.rsplit(".", 1)[0]
            local_methods = by_class.get(class_qual, [])
            local_names = {m.qualname.rsplit(".", 1)[-1] for m in local_methods}
            parent_names: set[str] = set()
            superclass = classes_by_qual.get(class_qual)
            def walk_calls(cur: Any) -> None:
                if cur.type == "method_invocation":
                    parsed = _call_expr_name(source_bytes, cur)
                    if parsed is not None:
                        name, receiver = parsed
                        argc = _call_arg_count(cur)
                        if receiver is None:
                            callee, reason = unique_method(local_methods, name, argc)
                            if callee is not None:
                                add_edge(current_method, callee, "java_same_class_method")
                            elif name not in local_names:
                                add_unresolved(current_method, name, "java_parent_method_deferred_to_override_window")
                            else:
                                add_unresolved(current_method, name, reason or "java_overloaded_or_ambiguous_method")
                        elif receiver == "this":
                            callee, reason = unique_method(local_methods, name, argc)
                            if callee is not None:
                                add_edge(current_method, callee, "java_this_method")
                            else:
                                add_unresolved(current_method, f"this.{name}", reason or "java_method_not_found")
                        elif receiver in explicit_imports:
                            methods, reason = imported_methods(receiver)
                            callee, why = unique_method(methods, name, argc)
                            if callee is not None:
                                add_edge(current_method, callee, "java_explicit_import_static_method")
                            else:
                                add_unresolved(current_method, f"{receiver}.{name}", why or reason or "java_method_not_found")
                        else:
                            add_unresolved(current_method, f"{receiver}.{name}", "java_variable_or_unknown_receiver")
                for child in _named_children(cur):
                    walk_calls(child)
            walk_calls(node)
            return
        for child in _named_children(node):
            visit(child, next_stack)

    visit(root, [])
    return edges, unresolved


@dataclass(frozen=True)
class JavaFieldEdge:
    accessor_id: str
    field_id: str
    field_qualname: str
    edge_kind: str
    evidence: str = "observed"
    resolution: str = "java_field_syntax"
    accessor_path: str | None = None
    field_path: str | None = None
    accessor_hash: str | None = None
    field_hash: str | None = None
    accessor_qualname: str | None = None
    language: str = "java"


@dataclass(frozen=True)
class JavaUnresolvedFieldAccess:
    accessor_id: str
    expr: str
    reason: str
    edge_kind: str


def _method_params_and_locals(source_bytes: bytes, method_node: Any) -> set[str]:
    names: set[str] = set()
    params = _child_by_field(method_node, "parameters")
    if params is not None:
        for child in _named_children(params):
            if child.type in {"formal_parameter", "spread_parameter"}:
                name = _child_by_field(child, "name")
                if name is not None:
                    names.add(_node_text(source_bytes, name))
    def walk(cur: Any) -> None:
        if cur.type == "variable_declarator":
            name = _child_by_field(cur, "name")
            if name is not None:
                names.add(_node_text(source_bytes, name))
        for child in _named_children(cur):
            walk(child)
    body = _child_by_field(method_node, "body")
    if body is not None:
        walk(body)
    return names


def _field_index_by_class(java_fields: list[DeclarationNode]) -> dict[str, dict[str, DeclarationNode]]:
    out: dict[str, dict[str, DeclarationNode]] = {}
    for f in java_fields:
        if "." not in f.qualname:
            continue
        cls, name = f.qualname.rsplit(".", 1)
        out.setdefault(cls, {})[name] = f
    return out


def resolve_java_field_edges(path: str, source: str, java_methods: list[ClassNode], java_fields: list[DeclarationNode], repo: Any | None = None) -> tuple[list[JavaFieldEdge], dict[str, list[JavaUnresolvedFieldAccess]]]:
    if not path.endswith(".java"):
        return [], {}
    _language, parser = _language_and_parser()
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    root = tree.root_node
    explicit_imports, _wildcards = _java_imports(source_bytes, root)
    methods_by_qual = {m.qualname: m for m in java_methods if m.node_kind == "method"}
    fields_by_class = _field_index_by_class(java_fields)
    edges: list[JavaFieldEdge] = []
    unresolved: dict[str, list[JavaUnresolvedFieldAccess]] = {}

    ids = __import__("tmf.ids", fromlist=["stable_java_node_claim_id"])

    def accessor_id(m: ClassNode) -> str:
        return ids.stable_java_node_claim_id(m.path, m.qualname, m.node_kind)

    def field_id(f: DeclarationNode) -> str:
        return ids.stable_java_node_claim_id(f.path, f.qualname, f.declaration_kind)

    def add_edge(m: ClassNode, f: DeclarationNode, kind: str, resolution: str) -> None:
        edges.append(JavaFieldEdge(
            accessor_id=accessor_id(m),
            field_id=field_id(f),
            field_qualname=f.qualname,
            edge_kind=kind,
            resolution=resolution,
            accessor_path=m.path,
            field_path=f.path,
            accessor_hash=m.class_hash,
            field_hash=f.declaration_hash,
            accessor_qualname=m.qualname,
        ))

    def add_unresolved(m: ClassNode, expr: str, reason: str, kind: str) -> None:
        unresolved.setdefault(accessor_id(m), []).append(JavaUnresolvedFieldAccess(accessor_id=accessor_id(m), expr=expr, reason=reason, edge_kind=kind))

    def imported_field(type_name: str, field_name: str) -> tuple[DeclarationNode | None, str]:
        if repo is None or type_name not in explicit_imports:
            return None, "java_variable_or_unknown_receiver"
        target_path = explicit_imports[type_name]
        try:
            target_source = repo.read_file(target_path)
        except Exception:
            return None, "java_external_or_jdk_receiver"
        candidates = [f for f in extract_java_fields(target_path, target_source) if f.qualname == f"{type_name}.{field_name}"]
        if len(candidates) == 1:
            return candidates[0], "java_explicit_import_static_field"
        if len(candidates) > 1:
            return None, "java_ambiguous_field"
        return None, "java_field_not_found"

    def assignment_lefts(method_node: Any) -> set[int]:
        lefts: set[int] = set()
        def walk(cur: Any) -> None:
            if cur.type == "assignment_expression":
                left = _child_by_field(cur, "left")
                if left is not None:
                    lefts.add(int(left.start_byte))
            elif cur.type == "update_expression":
                for c in _named_children(cur):
                    lefts.add(int(c.start_byte))
            for child in _named_children(cur):
                walk(child)
        walk(method_node)
        return lefts

    def field_expr(cur: Any) -> tuple[str, str | None] | None:
        if cur.type == "field_access":
            field = _child_by_field(cur, "field")
            obj = _child_by_field(cur, "object")
            if field is not None and obj is not None:
                return _node_text(source_bytes, field), _node_text(source_bytes, obj).strip()
        if cur.type == "identifier":
            return _node_text(source_bytes, cur), None
        return None

    def visit(node: Any, stack: list[str]) -> None:
        next_stack = stack
        current_method: ClassNode | None = None
        if node.type in _CLASS_TYPES:
            name = _identifier_from_node(source_bytes, node)
            if name:
                next_stack = [*stack, name]
        elif node.type in _METHOD_TYPES:
            q = _method_qualname(source_bytes, node, stack)
            current_method = methods_by_qual.get(q or "")
        if current_method is not None:
            class_qual = current_method.qualname.rsplit(".", 1)[0]
            locals_ = _method_params_and_locals(source_bytes, node)
            class_fields = fields_by_class.get(class_qual, {})
            lefts = assignment_lefts(node)
            seen: set[tuple[str, str]] = set()
            def walk_access(cur: Any) -> None:
                # avoid counting method invocation names as fields
                if cur.type == "method_invocation":
                    return
                parsed = field_expr(cur)
                if parsed is not None:
                    name, receiver = parsed
                    kind = "writes" if int(cur.start_byte) in lefts else "reads"
                    key = (kind, f"{receiver+'.' if receiver else ''}{name}")
                    if key not in seen:
                        seen.add(key)
                        if receiver == "this":
                            f = class_fields.get(name)
                            if f is not None:
                                add_edge(current_method, f, kind, "java_this_field")
                            else:
                                add_unresolved(current_method, f"this.{name}", "java_field_not_found", kind)
                        elif receiver is None:
                            if name in locals_:
                                add_unresolved(current_method, name, "java_local_or_parameter_shadow", kind)
                            elif name in class_fields:
                                add_edge(current_method, class_fields[name], kind, "java_same_class_static_or_field")
                        elif receiver in explicit_imports:
                            f, reason = imported_field(receiver, name)
                            if f is not None:
                                add_edge(current_method, f, kind, reason)
                            else:
                                add_unresolved(current_method, f"{receiver}.{name}", reason, kind)
                        else:
                            add_unresolved(current_method, f"{receiver}.{name}", "java_variable_receiver_field_not_resolved", kind)
                    if receiver is not None:
                        return
                for child in _named_children(cur):
                    walk_access(child)
            body = _child_by_field(node, "body") or node
            walk_access(body)
            return
        for child in _named_children(node):
            visit(child, next_stack)

    visit(root, [])
    return edges, unresolved




@dataclass(frozen=True)
class JavaTypeUseEdge:
    user_id: str
    type_id: str
    type_qualname: str
    use_kind: str
    evidence: str = "observed"
    resolution: str = "java_type_syntax"
    user_path: str | None = None
    type_path: str | None = None
    user_hash: str | None = None
    type_hash: str | None = None
    user_qualname: str | None = None
    user_node_kind: str | None = None
    type_node_kind: str | None = "class"
    language: str = "java"


@dataclass(frozen=True)
class JavaUnresolvedTypeUse:
    user_id: str
    type_expr: str
    reason: str
    use_kind: str


_JAVA_KNOWN_EXTERNAL_TYPES = {"String", "List", "Map", "Set", "Collection", "Optional", "Integer", "Long", "Boolean", "Double", "Float", "Object", "Void"}


def _java_type_tokens(type_text: str) -> list[str]:
    import re
    cleaned = type_text.replace("[]", " ").replace("?", " ")
    out: list[str] = []
    for tok in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", cleaned):
        if tok in {"extends", "super"}:
            continue
        out.append(tok.split(".")[-1])
    return out


def resolve_java_type_use_edges(path: str, source: str, java_classes: list[ClassNode], java_methods: list[ClassNode], java_fields: list[DeclarationNode], repo: Any | None = None) -> tuple[list[JavaTypeUseEdge], dict[str, list[JavaUnresolvedTypeUse]]]:
    if not path.endswith(".java"):
        return [], {}
    _language, parser = _language_and_parser()
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    root = tree.root_node
    explicit_imports, wildcard_imports = _java_imports(source_bytes, root)
    ids = __import__("tmf.ids", fromlist=["stable_java_node_claim_id"])
    class_by_qual = {c.qualname: c for c in java_classes if c.node_kind in {"class", "interface", "enum"}}
    same_by_simple: dict[str, list[ClassNode]] = {}
    for c in class_by_qual.values():
        same_by_simple.setdefault(c.qualname.rsplit(".", 1)[-1], []).append(c)
    methods_by_qual = {m.qualname: m for m in java_methods if m.node_kind in {"method", "constructor"}}
    fields_by_qual = {f.qualname: f for f in java_fields}
    edges: list[JavaTypeUseEdge] = []
    unresolved: dict[str, list[JavaUnresolvedTypeUse]] = {}

    def user_id_for(kind: str, q: str) -> str:
        if kind in {"method", "constructor", "class", "interface", "enum"}:
            node_kind = kind
            return ids.stable_java_node_claim_id(path, q, node_kind)
        decl = fields_by_qual[q]
        return ids.stable_java_node_claim_id(path, q, decl.declaration_kind)

    def user_hash_for(kind: str, q: str) -> str | None:
        if kind in {"method", "constructor"} and q in methods_by_qual:
            return methods_by_qual[q].class_hash
        if kind in {"class", "interface", "enum"} and q in class_by_qual:
            return class_by_qual[q].class_hash
        if q in fields_by_qual:
            return fields_by_qual[q].declaration_hash
        return None

    def add_unresolved(uid: str, type_expr: str, reason: str, use_kind: str) -> None:
        unresolved.setdefault(uid, []).append(JavaUnresolvedTypeUse(user_id=uid, type_expr=type_expr, reason=reason, use_kind=use_kind))

    def resolve_one(simple: str) -> tuple[ClassNode | None, str]:
        same = same_by_simple.get(simple, [])
        if len(same) == 1:
            return same[0], "java_same_file_type"
        if len(same) > 1:
            return None, "java_ambiguous_type"
        if simple in explicit_imports:
            if repo is None:
                return None, "java_type_not_resolved"
            target_path = explicit_imports[simple]
            try:
                target_source = repo.read_file(target_path)
            except Exception:
                return None, "java_external_or_jdk_type_not_resolved"
            candidates = [c for c in extract_java_classes(target_path, target_source) if c.qualname.rsplit(".", 1)[-1] == simple]
            top = [c for c in candidates if "." not in c.qualname]
            if len(top) == 1:
                return top[0], "java_explicit_import_type"
            if len(candidates) == 1:
                return candidates[0], "java_explicit_import_type"
            if candidates:
                return None, "java_ambiguous_type"
            return None, "java_external_or_jdk_type_not_resolved"
        if simple in _JAVA_KNOWN_EXTERNAL_TYPES or wildcard_imports:
            return None, "java_external_or_jdk_type_not_resolved"
        return None, "java_type_not_resolved"

    def add_type_uses(user_kind: str, user_q: str, type_text: str, use_kind: str) -> None:
        uid = user_id_for(user_kind, user_q)
        for simple in _java_type_tokens(type_text):
            target, reason = resolve_one(simple)
            if target is None:
                add_unresolved(uid, simple, reason, use_kind)
                continue
            tid = ids.stable_java_node_claim_id(target.path, target.qualname, target.node_kind)
            edges.append(JavaTypeUseEdge(
                user_id=uid, type_id=tid, type_qualname=target.qualname, use_kind=use_kind,
                resolution=reason, user_path=path, type_path=target.path,
                user_hash=user_hash_for(user_kind, user_q), type_hash=target.class_hash,
                user_qualname=user_q, user_node_kind=user_kind, type_node_kind=target.node_kind,
            ))

    def walk(node: Any, stack: list[str]) -> None:
        next_stack = stack
        if node.type in _CLASS_TYPES:
            name = _identifier_from_node(source_bytes, node)
            if name:
                q = ".".join([*stack, name])
                next_stack = [*stack, name]
                # superclass/interfaces are handled by inherits; field/method signatures below.
        elif node.type in {"field_declaration", "constant_declaration"}:
            typ = _child_by_field(node, "type")
            if typ is not None:
                for fq in _field_qualnames(source_bytes, node, stack):
                    add_type_uses("field", fq, _node_text(source_bytes, typ).strip(), "field_type")
        elif node.type in _METHOD_TYPES:
            q = _method_qualname(source_bytes, node, stack)
            if q:
                user_kind = "constructor" if node.type == "constructor_declaration" else "method"
                ret = _child_by_field(node, "type")
                if ret is not None:
                    add_type_uses(user_kind, q, _node_text(source_bytes, ret).strip(), "return_type")
                params = _child_by_field(node, "parameters")
                if params is not None:
                    for child in _named_children(params):
                        if child.type in {"formal_parameter", "spread_parameter"}:
                            typ = _child_by_field(child, "type")
                            if typ is not None:
                                add_type_uses(user_kind, q, _node_text(source_bytes, typ).strip(), "param_type")
        for child in _named_children(node):
            walk(child, next_stack)

    walk(root, [])
    return edges, unresolved


@dataclass(frozen=True)
class JavaOverrideEdge:
    method_id: str
    overridden_id: str
    overridden_qualname: str
    evidence: str = "inferred"
    resolution: str = "java_same_file_override_candidate"
    method_path: str | None = None
    overridden_path: str | None = None
    method_hash: str | None = None
    overridden_hash: str | None = None
    method_qualname: str | None = None
    language: str = "java"


@dataclass(frozen=True)
class JavaUnresolvedOverride:
    method_id: str
    expr: str
    reason: str


def resolve_java_override_edges(path: str, source: str, java_classes: list[ClassNode], java_methods: list[ClassNode], inherit_edges: list[JavaInheritEdge], unresolved_inherits: dict[str, list[JavaUnresolvedInherit]]) -> tuple[list[JavaOverrideEdge], dict[str, list[JavaUnresolvedOverride]]]:
    ids = __import__("tmf.ids", fromlist=["stable_java_node_claim_id"])
    method_by_qual = {m.qualname: m for m in java_methods if m.node_kind == "method"}
    methods_by_class: dict[str, list[ClassNode]] = {}
    sigs = _method_signature_index(path, source)
    for m in java_methods:
        if m.node_kind == "method" and "." in m.qualname:
            cls = m.qualname.rsplit(".", 1)[0]
            methods_by_class.setdefault(cls, []).append(m)
    class_id_to_qual = {ids.stable_java_node_claim_id(c.path, c.qualname, c.node_kind): c.qualname for c in java_classes}
    same_file_parent_by_child: dict[str, list[str]] = {}
    cross_file_child_ids: set[str] = set()
    for e in inherit_edges:
        if e.child_path == path and e.parent_path == path:
            pq = class_id_to_qual.get(e.parent_id)
            cq = class_id_to_qual.get(e.child_id)
            if pq and cq:
                same_file_parent_by_child.setdefault(cq, []).append(pq)
        elif e.child_path == path:
            cross_file_child_ids.add(e.child_id)
    unresolved_parent_child_ids = set(unresolved_inherits.keys())
    edges: list[JavaOverrideEdge] = []
    unresolved: dict[str, list[JavaUnresolvedOverride]] = {}

    def mid(m: ClassNode) -> str:
        return ids.stable_java_node_claim_id(m.path, m.qualname, m.node_kind)

    def add_unresolved(m: ClassNode, reason: str) -> None:
        name = m.qualname.rsplit(".", 1)[-1]
        unresolved.setdefault(mid(m), []).append(JavaUnresolvedOverride(method_id=mid(m), expr=name, reason=reason))

    for m in java_methods:
        if m.node_kind != "method" or "." not in m.qualname:
            continue
        cls = m.qualname.rsplit(".", 1)[0]
        cls_id = ids.stable_java_node_claim_id(path, cls, "class")
        if cls_id not in class_id_to_qual:
            cls_id = ids.stable_java_node_claim_id(path, cls, "interface")
        parents = same_file_parent_by_child.get(cls, [])
        name = m.qualname.rsplit(".", 1)[-1]
        if not parents:
            if cls_id in cross_file_child_ids:
                add_unresolved(m, "java_cross_file_override_deferred")
            elif cls_id in unresolved_parent_child_ids:
                add_unresolved(m, "java_parent_type_unresolved")
            continue
        msig = sigs.get(m.qualname)
        candidates: list[ClassNode] = []
        ambiguous = False
        for parent in parents:
            pcands = [pm for pm in methods_by_class.get(parent, []) if pm.qualname.rsplit(".", 1)[-1] == name]
            if not pcands:
                continue
            if len(pcands) > 1:
                ambiguous = True
                continue
            pm = pcands[0]
            psig = sigs.get(pm.qualname)
            if msig is not None and psig is not None and msig != psig:
                continue
            candidates.append(pm)
        if len(candidates) == 1 and not ambiguous:
            target = candidates[0]
            edges.append(JavaOverrideEdge(
                method_id=mid(m), overridden_id=mid(target), overridden_qualname=target.qualname,
                method_path=m.path, overridden_path=target.path, method_hash=m.class_hash,
                overridden_hash=target.class_hash, method_qualname=m.qualname,
            ))
        elif ambiguous or len(candidates) > 1:
            add_unresolved(m, "java_overloaded_or_ambiguous_override")
    return edges, unresolved


@dataclass(frozen=True)
class JavaInheritEdge:
    child_id: str
    parent_id: str
    relation: str
    parent_qualname: str
    evidence: str = "observed"
    resolution: str = "same_file_or_explicit_import_top_level"
    child_path: str | None = None
    parent_path: str | None = None
    child_hash: str | None = None
    parent_hash: str | None = None
    child_qualname: str | None = None
    parent_node_kind: str | None = None
    child_node_kind: str | None = None


@dataclass(frozen=True)
class JavaUnresolvedInherit:
    child_id: str
    expr: str
    reason: str
    relation: str


_EXTERNAL_OR_JDK_SIMPLE_TYPES = {
    "Object", "String", "Exception", "RuntimeException", "Throwable", "Error",
    "List", "ArrayList", "LinkedList", "Map", "HashMap", "Set", "HashSet",
    "Comparable", "Comparator", "Iterable", "Collection", "Optional", "Number",
    "Integer", "Long", "Boolean", "Double", "Float", "Short", "Byte", "Character",
}


def _simple_name(name: str) -> str:
    return name.rsplit(".", 1)[-1]


def _bare_type_name(source_bytes: bytes, node: Any) -> str | None:
    """Return the syntactic bare supertype name, erasing generic arguments."""
    if node.type == "generic_type":
        for child in _named_children(node):
            if child.type in {"type_identifier", "scoped_type_identifier"}:
                return _node_text(source_bytes, child)
        return None
    if node.type in {"type_identifier", "scoped_type_identifier", "identifier", "scoped_identifier"}:
        return _node_text(source_bytes, node)
    for child in _named_children(node):
        found = _bare_type_name(source_bytes, child)
        if found:
            return found
    return None


def _type_list_names(source_bytes: bytes, node: Any | None) -> list[str]:
    if node is None:
        return []
    out: list[str] = []
    # For a superclass node, take its direct type child only.
    if node.type == "superclass":
        for child in _named_children(node):
            if child.type in {"type_identifier", "scoped_type_identifier", "generic_type"}:
                name = _bare_type_name(source_bytes, child)
                if name:
                    return [name]
        return []
    # For interface lists, collect direct entries under type_list.
    type_list = node
    if node.type in {"super_interfaces", "extends_interfaces"}:
        for child in _named_children(node):
            if child.type == "type_list":
                type_list = child
                break
    if type_list.type == "type_list":
        for child in _named_children(type_list):
            if child.type in {"type_identifier", "scoped_type_identifier", "generic_type"}:
                name = _bare_type_name(source_bytes, child)
                if name:
                    out.append(name)
    else:
        name = _bare_type_name(source_bytes, type_list)
        if name:
            out.append(name)
    return out


def _java_imports(source_bytes: bytes, root: Any) -> tuple[dict[str, str], set[str]]:
    explicit: dict[str, str] = {}
    wildcard_packages: set[str] = set()
    for child in _named_children(root):
        if child.type != "import_declaration":
            continue
        text = _node_text(source_bytes, child).strip()
        body = text[len("import"):].strip().rstrip(";").strip()
        if body.startswith("static "):
            body = body[len("static "):].strip()
        if body.endswith(".*"):
            wildcard_packages.add(body[:-2])
            continue
        if body:
            explicit[_simple_name(body)] = body.replace(".", "/") + ".java"
    return explicit, wildcard_packages


def _top_level_java_types(path: str, source: str) -> dict[str, list[ClassNode]]:
    return { }


def _current_java_type_nodes(path: str, source: str) -> list[ClassNode]:
    return [node for node in extract_java_classes(path, source) if node.node_kind in {"class", "interface"}]


def _resolve_java_supertype(repo: Any, current_path: str, source: str, type_expr: str, same_file_types: dict[str, list[ClassNode]], explicit_imports: dict[str, str], wildcard_imports: set[str]) -> tuple[ClassNode | None, str]:
    simple = _simple_name(type_expr)
    same = same_file_types.get(simple, [])
    if len(same) == 1:
        return same[0], "same_file_unique"
    if len(same) > 1:
        return None, "ambiguous_type"
    if simple in explicit_imports:
        target_path = explicit_imports[simple]
        try:
            target_source = repo.read_file(target_path)
        except Exception:
            return None, "external_or_jdk_type"
        candidates = [node for node in _current_java_type_nodes(target_path, target_source) if node.qualname.split(".")[-1] == simple]
        top_level = [node for node in candidates if "." not in node.qualname]
        if len(top_level) == 1:
            return top_level[0], "explicit_import_top_level"
        if len(top_level) > 1 or len(candidates) > 1:
            return None, "ambiguous_type"
        return None, "external_or_jdk_type"
    if wildcard_imports:
        return None, "wildcard_import"
    if type_expr.startswith("java.") or simple in _EXTERNAL_OR_JDK_SIMPLE_TYPES:
        return None, "external_or_jdk_type"
    return None, "external_or_jdk_type"


def resolve_java_inherit_edges(path: str, source: str, java_classes: list[ClassNode], repo: Any | None = None) -> tuple[list[JavaInheritEdge], dict[str, list[JavaUnresolvedInherit]]]:
    if not path.endswith(".java") or repo is None:
        return [], {}
    _language, parser = _language_and_parser()
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    root = tree.root_node
    explicit_imports, wildcard_imports = _java_imports(source_bytes, root)
    type_nodes = [node for node in java_classes if node.node_kind in {"class", "interface"}]
    by_qual = {node.qualname: node for node in type_nodes}
    same_file_by_simple: dict[str, list[ClassNode]] = {}
    for node in type_nodes:
        same_file_by_simple.setdefault(node.qualname.split(".")[-1], []).append(node)
    edges: list[JavaInheritEdge] = []
    unresolved: dict[str, list[JavaUnresolvedInherit]] = {}

    def visit(node: Any, stack: list[str]) -> None:
        next_stack = stack
        if node.type in {"class_declaration", "interface_declaration"}:
            name = _identifier_from_node(source_bytes, node)
            if name:
                qualname = ".".join([*stack, name])
                next_stack = [*stack, name]
                child = by_qual.get(qualname)
                if child is not None and child.node_kind in {"class", "interface"}:
                    child_id = __import__("tmf.ids", fromlist=["stable_java_node_claim_id"]).stable_java_node_claim_id(child.path, child.qualname, child.node_kind)
                    specs: list[tuple[str, str]] = []
                    if node.type == "class_declaration":
                        for expr in _type_list_names(source_bytes, _child_by_field(node, "superclass")):
                            specs.append(("extends", expr))
                        super_ifaces = next((c for c in _named_children(node) if c.type == "super_interfaces"), None)
                        for expr in _type_list_names(source_bytes, super_ifaces):
                            specs.append(("implements", expr))
                    elif node.type == "interface_declaration":
                        ext_ifaces = next((c for c in _named_children(node) if c.type == "extends_interfaces"), None)
                        for expr in _type_list_names(source_bytes, ext_ifaces):
                            specs.append(("extends", expr))
                    for relation, expr in specs:
                        parent, reason = _resolve_java_supertype(repo, path, source, expr, same_file_by_simple, explicit_imports, wildcard_imports)
                        if parent is None:
                            unresolved.setdefault(child_id, []).append(JavaUnresolvedInherit(child_id=child_id, expr=_simple_name(expr), reason=reason, relation=relation))
                            continue
                        parent_id = __import__("tmf.ids", fromlist=["stable_java_node_claim_id"]).stable_java_node_claim_id(parent.path, parent.qualname, parent.node_kind)
                        edges.append(JavaInheritEdge(
                            child_id=child_id,
                            parent_id=parent_id,
                            relation=relation,
                            parent_qualname=parent.qualname,
                            resolution=reason,
                            child_path=child.path,
                            parent_path=parent.path,
                            child_hash=child.class_hash,
                            parent_hash=parent.class_hash,
                            child_qualname=child.qualname,
                            child_node_kind=child.node_kind,
                            parent_node_kind=parent.node_kind,
                        ))
        for child_node in _named_children(node):
            visit(child_node, next_stack)

    visit(root, [])
    return edges, unresolved


def _first_descendant_text(source_bytes: bytes, node: Any, types: set[str]) -> str | None:
    if node.type in types:
        return _node_text(source_bytes, node)
    for child in _named_children(node):
        found = _first_descendant_text(source_bytes, child, types)
        if found is not None:
            return found
    return None


def _java_method_node_for(source: str, method: ClassNode) -> Any | None:
    _language, parser = _language_and_parser()
    source_bytes = source.encode("utf-8")
    root = parser.parse(source_bytes).root_node
    stack: list[str] = []
    found = None
    def walk(node: Any, st: list[str]) -> None:
        nonlocal found
        if found is not None:
            return
        next_stack = st
        if node.type in _CLASS_TYPES:
            name = _identifier_from_node(source_bytes, node)
            if name:
                next_stack = [*st, name]
        elif node.type in _METHOD_TYPES:
            q = _method_qualname(source_bytes, node, st)
            if q == method.qualname and _line_start(node) == method.line_start:
                found = node
                return
        for child in _named_children(node):
            walk(child, next_stack)
    walk(root, stack)
    return found


def _java_method_interface_from_node(source_bytes: bytes, node: Any) -> dict[str, Any]:
    params: list[dict[str, str | None]] = []
    throws: list[str] = []
    annotations: list[str] = []
    modifiers: list[str] = []
    return_type: str | None = None
    for child in _children(node):
        if child.type == "modifiers":
            for m in _children(child):
                if m.type == "marker_annotation":
                    txt = _node_text(source_bytes, m).strip().lstrip("@")
                    annotations.append(txt.split("(", 1)[0])
                elif m.type in {"public", "private", "protected", "static", "final", "abstract", "synchronized", "native"}:
                    modifiers.append(m.type)
        elif child.type in {"void_type", "integral_type", "floating_point_type", "boolean_type", "type_identifier", "generic_type", "scoped_type_identifier"} and return_type is None:
            return_type = _node_text(source_bytes, child)
        elif child.type == "formal_parameters":
            for pnode in _named_children(child):
                if pnode.type not in {"formal_parameter", "spread_parameter"}:
                    continue
                name_node = _child_by_field(pnode, "name")
                type_node = _child_by_field(pnode, "type")
                params.append({"name": _node_text(source_bytes, name_node) if name_node is not None else None, "type": _node_text(source_bytes, type_node) if type_node is not None else None})
        elif child.type == "throws":
            for t in _named_children(child):
                txt = _bare_type_name(source_bytes, t)
                if txt:
                    throws.append(_simple_name(txt))
    # Literal raises inside the body also count as observed raise names.
    def walk_throws(cur: Any) -> None:
        if cur.type == "throw_statement":
            txt = _first_descendant_text(source_bytes, cur, {"type_identifier", "identifier"})
            if txt and txt not in throws:
                throws.append(_simple_name(txt))
        for ch in _named_children(cur):
            walk_throws(ch)
    walk_throws(node)
    return {"language": "java", "signature": _node_text(source_bytes, node).split("{",1)[0].strip(), "params": params, "return_type": return_type, "throws": sorted(set(throws)), "modifiers": sorted(set(modifiers)), "annotations": sorted(set(annotations))}


@lru_cache(maxsize=512)
def _java_method_interface_index(source: str) -> dict[tuple[str, int], dict[str, Any]]:
    _language, parser = _language_and_parser()
    source_bytes = source.encode("utf-8")
    root = parser.parse(source_bytes).root_node
    out: dict[tuple[str, int], dict[str, Any]] = {}

    def walk(node: Any, stack: list[str]) -> None:
        next_stack = stack
        if node.type in _CLASS_TYPES:
            name = _identifier_from_node(source_bytes, node)
            if name:
                next_stack = [*stack, name]
        elif node.type in _METHOD_TYPES:
            q = _method_qualname(source_bytes, node, stack)
            if q:
                out[(q, _line_start(node))] = _java_method_interface_from_node(source_bytes, node)
        for child in _named_children(node):
            walk(child, next_stack)

    walk(root, [])
    return out


def java_method_interface(source: str, method: ClassNode) -> dict[str, Any]:
    return dict(_java_method_interface_index(source).get((method.qualname, method.line_start), {}))



@dataclass(frozen=True)
class JavaInjectEdge:
    injector_id: str
    bean_id: str
    bean_qualname: str
    inject_kind: str
    evidence: str = "attributed"
    confidence: float = 0.55
    resolution: str = "spring_autowired_field_type"
    injector_path: str | None = None
    bean_path: str | None = None
    injector_hash: str | None = None
    bean_hash: str | None = None
    injector_qualname: str | None = None
    bean_node_kind: str | None = "class"


@dataclass(frozen=True)
class JavaUnresolvedInject:
    injector_id: str
    type_expr: str
    reason: str
    inject_kind: str
    candidates: list[str] | None = None


@dataclass(frozen=True)
class JavaTopicEdge:
    source_id: str
    topic_name: str
    edge_kind: str
    evidence: str = "attributed"
    confidence: float = 0.5
    resolution: str = "spring_kafka_literal_topic"
    source_path: str | None = None
    source_hash: str | None = None
    source_qualname: str | None = None
    dependency_path: str | None = None
    dependency_qualname: str | None = None


@dataclass(frozen=True)
class JavaUnresolvedTopic:
    source_id: str
    expr: str
    reason: str
    edge_kind: str


def _java_class_annotations_regex(source: str) -> dict[str, set[str]]:
    import re
    anns: dict[str, set[str]] = {}
    pat = re.compile(r"((?:@\w+(?:\([^)]*\))?\s*)*)(?:public\s+)?(?:class|interface)\s+(\w+)")
    for m in pat.finditer(source):
        names = set(re.findall(r"@(\w+)", m.group(1) or ""))
        anns[m.group(2)] = names
    return anns


def _java_implements_regex(source: str) -> dict[str, list[str]]:
    import re
    out: dict[str, list[str]] = {}
    for m in re.finditer(r"(?:class)\s+(\w+)\s+implements\s+([^\{]+)\{", source):
        out[m.group(1)] = [x.strip().split()[-1] for x in m.group(2).split(',') if x.strip()]
    return out


def resolve_java_inject_edges(path: str, source: str, java_classes: list[ClassNode], java_fields: list[DeclarationNode], inherit_edges: list[JavaInheritEdge] | None = None, repo: Any | None = None) -> tuple[list[JavaInjectEdge], dict[str, list[JavaUnresolvedInject]]]:
    if not path.endswith('.java'):
        return [], {}
    ids = __import__('tmf.ids', fromlist=['stable_java_node_claim_id'])
    lines = source.splitlines()
    anns = _java_class_annotations_regex(source)
    bean_ann = {'Component','Service','Repository','Controller','RestController'}
    class_by_simple = {c.qualname.rsplit('.',1)[-1]: c for c in java_classes if c.node_kind in {'class','interface'}}
    beans = {simple: c for simple, c in class_by_simple.items() if anns.get(simple, set()) & bean_ann}
    implements = _java_implements_regex(source)
    impls_by_iface: dict[str, list[ClassNode]] = {}
    for impl_simple, ifaces in implements.items():
        if impl_simple in beans:
            for iface in ifaces:
                impls_by_iface.setdefault(iface, []).append(beans[impl_simple])
    fields_by_owner: dict[str, list[DeclarationNode]] = {}
    for field in java_fields:
        owner = field.qualname.rsplit('.', 1)[0] if '.' in field.qualname else ''
        fields_by_owner.setdefault(owner, []).append(field)
    edges: list[JavaInjectEdge] = []
    unresolved: dict[str, list[JavaUnresolvedInject]] = {}
    seen: set[tuple[str,str,str]] = set()
    import re
    for owner, fields in fields_by_owner.items():
        cls = class_by_simple.get(owner)
        if cls is None:
            continue
        injector_id = ids.stable_java_node_claim_id(path, cls.qualname, cls.node_kind)
        for field in fields:
            line = lines[field.line_start-1] if 0 < field.line_start <= len(lines) else ''
            if '@Autowired' not in line:
                continue
            fm = re.search(r"@Autowired\s+(?:private\s+|public\s+|protected\s+)?([A-Za-z_][A-Za-z0-9_]*)\s+([A-Za-z_][A-Za-z0-9_]*)\s*;", line)
            if not fm:
                continue
            typ = fm.group(1)
            target = beans.get(typ)
            reason = 'spring_autowired_field_type'
            candidates: list[str] = []
            if target is None and typ in class_by_simple and class_by_simple[typ].node_kind == 'interface':
                impls = impls_by_iface.get(typ, [])
                candidates = [x.qualname for x in impls]
                if len(impls) == 1:
                    target = impls[0]
                    reason = 'spring_autowired_interface_unique_bean'
                elif len(impls) > 1:
                    unresolved.setdefault(injector_id, []).append(JavaUnresolvedInject(injector_id, typ, 'spring_interface_multiple_beans', 'field', candidates))
                    continue
            if target is None:
                unresolved.setdefault(injector_id, []).append(JavaUnresolvedInject(injector_id, typ, 'spring_injection_type_not_resolved', 'field', candidates))
                continue
            bean_id = ids.stable_java_node_claim_id(target.path, target.qualname, target.node_kind)
            key=(injector_id, bean_id, 'field')
            if key in seen:
                continue
            seen.add(key)
            edges.append(JavaInjectEdge(injector_id, bean_id, target.qualname, 'field', resolution=reason, injector_path=cls.path, bean_path=target.path, injector_hash=cls.class_hash, bean_hash=target.class_hash, injector_qualname=cls.qualname, bean_node_kind=target.node_kind))
    return edges, unresolved

def _java_package(source: str) -> str | None:
    import re
    match = re.search(r"(?m)^\s*package\s+([A-Za-z_][\w.]*)\s*;", source)
    return match.group(1) if match else None


def _java_explicit_imports(source: str) -> dict[str, str]:
    import re
    return {name.rsplit('.', 1)[-1]: name for name in re.findall(r"(?m)^\s*import\s+([A-Za-z_][\w.]*)\s*;", source)}


def _java_source_type_fqn(source: str, type_name: str) -> str | None:
    simple = type_name.strip()
    if '.' in simple:
        return simple
    imported = _java_explicit_imports(source).get(simple)
    if imported:
        return imported
    package = _java_package(source)
    return f"{package}.{simple}" if package else simple


def _eventuate_wrapper_channels(repo: Any, source: str) -> tuple[dict[str, tuple[str, str, str]], set[str]]:
    import re
    receiver_types = {
        receiver: type_name
        for type_name, receiver in re.findall(
            r"\b([A-Za-z_][\w.]*(?:EventPublisher|DomainEventPublisher))\s+([a-zA-Z_][\w]*)\s*(?:[;,)])",
            source,
        )
    }
    channels: dict[str, tuple[str, str, str]] = {}
    ambiguous: set[str] = set()
    if repo is None:
        return channels, set(receiver_types)
    for receiver, type_name in receiver_types.items():
        simple = type_name.rsplit('.', 1)[-1]
        if simple == "DomainEventPublisher":
            continue
        candidates: list[tuple[str, str, str]] = []
        for candidate_path in repo.root.rglob("*.java"):
            if ".git" in candidate_path.parts or ".tmf" in candidate_path.parts:
                continue
            candidate_source = candidate_path.read_text(encoding="utf-8", errors="ignore")
            match = re.search(
                rf"\binterface\s+{re.escape(simple)}\s+extends\s+DomainEventPublisherForAggregate\s*<\s*([A-Za-z_][\w.]*)\s*,",
                candidate_source,
            )
            if match:
                aggregate = _java_source_type_fqn(candidate_source, match.group(1))
                if aggregate:
                    relpath = candidate_path.relative_to(repo.root).as_posix()
                    candidates.append((aggregate, relpath, simple))
        unique = sorted(set(candidates))
        if len(unique) == 1:
            channels[receiver] = unique[0]
        else:
            ambiguous.add(receiver)
    return channels, ambiguous


def resolve_java_topic_edges(path: str, source: str, java_methods: list[ClassNode], repo: Any | None = None) -> tuple[list[JavaTopicEdge], dict[str, list[JavaUnresolvedTopic]]]:
    if not path.endswith('.java'):
        return [], {}
    # Avoid an O(files²) repository scan for ordinary Java files.  The only
    # cross-file topic lookup currently supported is an Eventuate publisher
    # wrapper, so unrelated sources must return before building that index.
    if not any(marker in source for marker in ("KafkaTemplate", "@KafkaListener", "DomainEventPublisher", "EventPublisher", "@EventuateDomainEventHandler")):
        return [], {}
    ids = __import__('tmf.ids', fromlist=['stable_java_node_claim_id'])
    source_bytes = source.encode('utf-8')
    edges: list[JavaTopicEdge] = []
    unresolved: dict[str, list[JavaUnresolvedTopic]] = {}
    import re
    wrapper_channels, ambiguous_wrappers = _eventuate_wrapper_channels(repo, source)
    receiver_types = {
        receiver: type_name.rsplit('.', 1)[-1]
        for type_name, receiver in re.findall(
            r"\b([A-Za-z_][\w.]*(?:EventPublisher|DomainEventPublisher))\s+([a-zA-Z_][\w]*)\s*(?:[;,)])",
            source,
        )
    }
    for m in java_methods:
        if m.node_kind != 'method':
            continue
        sid=ids.stable_java_node_claim_id(path, m.qualname, m.node_kind)
        node = _java_method_node_for(source, m)
        span = _node_text(source_bytes, node) if node is not None else ''
        lm = re.search(r"@KafkaListener\s*\(\s*topics\s*=\s*\"([^\"]+)\"", span)
        if lm:
            edges.append(JavaTopicEdge(sid, lm.group(1), 'subscribes_to', source_path=m.path, source_hash=m.class_hash, source_qualname=m.qualname))
        em = re.search(r"@EventuateDomainEventHandler\s*\([^)]*\bchannel\s*=\s*\"([^\"]+)\"", span, re.DOTALL)
        if em:
            edges.append(JavaTopicEdge(sid, em.group(1), 'subscribes_to', source_path=m.path, source_hash=m.class_hash, source_qualname=m.qualname, resolution='eventuate_literal_channel'))
        for sm in re.finditer(r"\.send\s*\(\s*([^,\)]+)", span):
            expr=sm.group(1).strip()
            if len(expr) >= 2 and expr[0] == '"' and expr[-1] == '"':
                edges.append(JavaTopicEdge(sid, expr[1:-1], 'publishes_to', source_path=m.path, source_hash=m.class_hash, source_qualname=m.qualname))
            else:
                unresolved.setdefault(sid, []).append(JavaUnresolvedTopic(sid, expr, 'kafka_topic_not_literal', 'publishes_to'))
        for pm in re.finditer(r"\b([a-zA-Z_][\w]*)\.(publish|publishById)\s*\(\s*([^,\)]+)", span):
            receiver, _operation, first_arg = pm.groups()
            if receiver not in receiver_types:
                continue
            wrapper = wrapper_channels.get(receiver)
            topic_name = wrapper[0] if wrapper else None
            dependency_path = wrapper[1] if wrapper else None
            dependency_qualname = wrapper[2] if wrapper else None
            resolution = "eventuate_aggregate_wrapper_unique"
            if receiver_types[receiver] == "DomainEventPublisher":
                class_match = re.fullmatch(r"([A-Za-z_][\w.]*)\.class", first_arg.strip())
                string_match = re.fullmatch(r'"([^\"]+)"', first_arg.strip())
                if class_match:
                    topic_name = _java_source_type_fqn(source, class_match.group(1))
                    resolution = "eventuate_direct_class_literal"
                elif string_match and '.' in string_match.group(1):
                    topic_name = string_match.group(1)
                    resolution = "eventuate_direct_fqn_literal"
                else:
                    unresolved.setdefault(sid, []).append(JavaUnresolvedTopic(sid, first_arg.strip(), 'eventuate_aggregate_not_literal', 'publishes_to'))
                    continue
            elif receiver in ambiguous_wrappers or topic_name is None:
                unresolved.setdefault(sid, []).append(JavaUnresolvedTopic(sid, receiver, 'eventuate_publisher_wrapper_not_unique', 'publishes_to'))
                continue
            edges.append(JavaTopicEdge(sid, topic_name, 'publishes_to', source_path=m.path, source_hash=m.class_hash, source_qualname=m.qualname, resolution=resolution, dependency_path=dependency_path, dependency_qualname=dependency_qualname))
    return edges, unresolved


def resolve_java_saga_definitions(path: str, source: str, java_classes: list[ClassNode], repo: Any | None = None) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """Extract only literal Eventuate SimpleSaga DSL structure.

    This deliberately records the definition on the saga class rather than
    inventing call edges for method references or runtime command delivery.
    """
    if not path.endswith(".java"):
        return {}, {}
    import re
    ids = __import__("tmf.ids", fromlist=["stable_java_node_claim_id"])
    classes = {c.qualname: c for c in java_classes if c.node_kind == "class"}
    if not re.search(r"implements\s+[^\{]*\bSimpleSaga\s*<", source):
        return {}, {}
    result: dict[str, dict[str, Any]] = {}
    unresolved: dict[str, list[dict[str, Any]]] = {}
    proxy_operations: dict[tuple[str, str], list[dict[str, Any]]] = {}
    handlers: dict[tuple[str, str], list[dict[str, Any]]] = {}
    if repo is not None:
        for candidate_path in repo.root.rglob("*.java"):
            if ".git" in candidate_path.parts or ".tmf" in candidate_path.parts:
                continue
            candidate = candidate_path.read_text(encoding="utf-8", errors="ignore")
            proxy = re.search(r"@SagaParticipantProxy\s*\(\s*channel\s*=\s*([A-Za-z_][\w.]*)\s*\)\s*public\s+class\s+(\w+)", candidate)
            if proxy:
                channel_expr, proxy_name = proxy.groups()
                channel_match = re.search(rf"\b{re.escape(proxy_name)}\s*\.\s*CHANNEL\b", candidate)
                constant_match = re.search(r"\bCHANNEL\s*=\s*\"([^\"]+)\"", candidate)
                channel = constant_match.group(1) if channel_match and constant_match else None
                if channel is None:
                    channel = channel_expr.strip('"') if channel_expr.startswith('"') else None
                if channel:
                    for op in re.finditer(r"@SagaParticipantOperation\s*\(\s*commandClass\s*=\s*([\w.]+)\.class\s*,\s*replyClasses\s*=\s*([\w.]+)\.class\s*\)\s*public\s+[^\s]+\s+(\w+)\s*\(", candidate):
                        command, reply, method = op.groups()
                        proxy_operations.setdefault((channel, method), []).append({"path": candidate_path.relative_to(repo.root).as_posix(), "proxy": proxy_name, "command": command, "reply": reply, "channel": channel})
            handler = re.search(r"@EventuateCommandHandler\s*\([^)]*\bchannel\s*=\s*\"([^\"]+)\"[^)]*\)\s*public\s+[^\s]+\s+(\w+)\s*\(\s*CommandMessage\s*<\s*([\w.]+)\s*>", candidate, re.DOTALL)
            if handler:
                channel, method, command = handler.groups()
                handlers.setdefault((channel, command.rsplit('.', 1)[-1]), []).append({"path": candidate_path.relative_to(repo.root).as_posix(), "method": method, "channel": channel, "command": command.rsplit('.', 1)[-1]})
    for cls in java_classes:
        if cls.node_kind != "class":
            continue
        class_match = re.search(rf"\bclass\s+{re.escape(cls.qualname.rsplit('.', 1)[-1])}\b[^\{{]*\bimplements\s+[^\{{]*\bSimpleSaga\s*<", source)
        if not class_match:
            continue
        cid = ids.stable_java_node_claim_id(path, cls.qualname, cls.node_kind)
        definition = re.search(r"SagaDefinition\s*<[^>]+>\s+\w+\s*=\s*(.*?\.build\s*\(\s*\))\s*;", source, re.DOTALL)
        if not definition:
            unresolved[cid] = [{"expr": "SagaDefinition", "reason": "eventuate_saga_definition_not_literal"}]
            continue
        text = definition.group(1)
        steps: list[dict[str, Any]] = []
        for step_text in re.split(r"(?=(?:^|\.)step\s*\(\s*\))", text):
            if not re.search(r"(?:^|\.)step\s*\(\s*\)", step_text):
                continue
            local = re.search(r"\.invokeLocal\s*\(\s*this::(\w+)\s*\)", step_text)
            participant = re.search(r"\.invokeParticipant\s*\(\s*this::(\w+)\s*\)", step_text)
            compensation = re.search(r"\.withCompensation\s*\(\s*this::(\w+)\s*\)", step_text)
            replies = re.findall(r"\.onReply\s*\(\s*([A-Za-z_][\w.]*)\s*,\s*this::(\w+)\s*\)", step_text)
            if local:
                steps.append({"kind": "local", "method": local.group(1), "compensation": compensation.group(1) if compensation else None})
            elif participant:
                step = {"kind": "participant", "method": participant.group(1), "replies": [{"reply": r, "handler": h} for r, h in replies]}
                matches = []
                for (channel, method), operations in proxy_operations.items():
                    if method == participant.group(1):
                        for operation in operations:
                            operation = dict(operation)
                            operation["handlers"] = handlers.get((channel, operation["command"].rsplit('.', 1)[-1]), [])
                            matches.append(operation)
                if len(matches) == 1:
                    step["participant_contract"] = matches[0]
                else:
                    unresolved.setdefault(cid, []).append({"expr": participant.group(1), "reason": "eventuate_saga_participant_operation_not_unique", "candidates": matches})
                steps.append(step)
            else:
                unresolved.setdefault(cid, []).append({"expr": step_text.strip(), "reason": "eventuate_saga_step_not_unique"})
        result[cid] = {"saga_definition": True, "resolution": "eventuate_simple_saga_literal_dsl", "steps": steps, "coverage": "partial"}
    return result, unresolved
