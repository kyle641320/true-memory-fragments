from __future__ import annotations

import hashlib
from functools import lru_cache
from dataclasses import dataclass
from typing import Any

from .extract import ClassNode, DeclarationNode, _identifier_keywords

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
