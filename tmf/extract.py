from __future__ import annotations

import ast
import hashlib
import io
import json
import tokenize
from dataclasses import dataclass, field
from typing import Literal

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    tomllib = None

NodeKind = Literal["function", "class", "declaration", "config", "api"]
ExtractionTier = Literal["python-ast", "java-treesitter-syntactic", "semantic-resolved"]


@dataclass(frozen=True)
class FunctionNode:
    path: str
    qualname: str
    line_start: int
    line_end: int
    fn_hash: str
    keywords: list[str]
    docstring: str | None = None
    language: str = "python"
    extraction_tier: ExtractionTier = "python-ast"


@dataclass(frozen=True)
class ClassNode:
    path: str
    qualname: str
    line_start: int
    line_end: int
    class_hash: str
    keywords: list[str]
    docstring: str | None = None
    language: str = "python"
    node_kind: str = "class"
    extraction_tier: ExtractionTier = "python-ast"


@dataclass(frozen=True)
class DeclarationNode:
    path: str
    qualname: str
    line_start: int
    line_end: int
    declaration_hash: str
    keywords: list[str]
    declaration_kind: str
    language: str = "python"
    extraction_tier: ExtractionTier = "python-ast"


@dataclass(frozen=True)
class ConfigNode:
    path: str
    key: str
    config_hash: str
    keywords: list[str]
    config_kind: str


@dataclass(frozen=True)
class ApiNode:
    path: str
    method: str
    route_path: str
    handler_qualname: str
    line_start: int
    line_end: int
    api_hash: str
    keywords: list[str]


_SKIP_TOKEN_TYPES = {
    tokenize.ENCODING,
    tokenize.COMMENT,
    tokenize.NL,
    tokenize.ENDMARKER,
}


def _token_items_for_lines(source: str, line_start: int, line_end: int) -> list[str]:
    """Return normalized token stream for a source span.

    This is intentionally token-based, not regex whitespace stripping. String
    literal contents and identifiers are preserved; comments are ignored. Python
    INDENT/DEDENT/NEWLINE events are kept because they affect block semantics,
    but their whitespace strings are discarded so formatting width is trivia.

    Span boundaries may overlap INDENT/DEDENT tokens that belong to an outer
    scope rather than to the function itself. A first method in a class, for
    example, shares its ``def`` line with the class body's INDENT token. Including
    that outer-boundary INDENT makes the method hash change when another class
    member is inserted above it. Keep semantic block tokens inside the function,
    but trim boundary INDENT/DEDENT events that appear before the first real
    content token or after the last real content token.
    """
    items: list[tuple[int, str]] = []
    reader = io.StringIO(source).readline
    for tok in tokenize.generate_tokens(reader):
        if tok.type in _SKIP_TOKEN_TYPES:
            continue
        start_line = tok.start[0]
        end_line = tok.end[0]
        if end_line < line_start or start_line > line_end:
            continue
        if tok.type in {tokenize.INDENT, tokenize.DEDENT, tokenize.NEWLINE}:
            items.append((tok.type, tokenize.tok_name[tok.type]))
        else:
            items.append((tok.type, f"{tokenize.tok_name[tok.type]}:{tok.string}"))

    content_indexes = [
        idx
        for idx, (tok_type, _item) in enumerate(items)
        if tok_type not in {tokenize.INDENT, tokenize.DEDENT, tokenize.NEWLINE}
    ]
    if not content_indexes:
        return []
    first_content = content_indexes[0]
    last_content = content_indexes[-1]
    normalized = items[first_content : last_content + 1]
    return [item for _tok_type, item in normalized]


def fn_hash_for_span(source: str, line_start: int, line_end: int) -> str:
    token_stream = "\0".join(_token_items_for_lines(source, line_start, line_end))
    return hashlib.sha256(token_stream.encode("utf-8")).hexdigest()


def _identifier_keywords(name: str, limit: int = 16) -> list[str]:
    parts = [p for p in name.replace(".", "_").split("_") if p]
    seen: set[str] = set()
    out: list[str] = []
    for part in parts:
        key = part.lower()
        if key not in seen:
            seen.add(key)
            out.append(part)
        if len(out) >= limit:
            break
    return out


class _FunctionVisitor(ast.NodeVisitor):
    def __init__(self, path: str, source: str) -> None:
        self.path = path
        self.source = source
        self.stack: list[str] = []
        self.nodes: list[FunctionNode] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._add_function(node)
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._add_function(node)
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def _add_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        line_start = int(getattr(node, "lineno", 1))
        line_end = int(getattr(node, "end_lineno", line_start))
        qualname = ".".join([*self.stack, node.name])
        self.nodes.append(
            FunctionNode(
                path=self.path,
                qualname=qualname,
                line_start=line_start,
                line_end=line_end,
                fn_hash=fn_hash_for_span(self.source, line_start, line_end),
                keywords=_identifier_keywords(qualname),
                docstring=ast.get_docstring(node, clean=True),
            )
        )


def extract_functions(path: str, source: str) -> list[FunctionNode]:
    if not path.endswith(".py"):
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    visitor = _FunctionVisitor(path, source)
    visitor.visit(tree)
    return visitor.nodes


def _literal_route_path(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _literal_methods(node: ast.AST | None) -> list[str] | None:
    if node is None:
        return ["GET"]
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value.upper()]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        methods: list[str] = []
        for item in node.elts:
            if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
                return None
            methods.append(item.value.upper())
        return methods
    return None


def _route_decorator_contract(decorator: ast.AST) -> tuple[list[str], str] | None:
    if not isinstance(decorator, ast.Call):
        return None
    func = decorator.func
    route_path = _literal_route_path(decorator.args[0]) if decorator.args else None
    if route_path is None:
        return None
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        if func.value.id == "app" and func.attr == "route":
            methods_node = None
            for keyword in decorator.keywords:
                if keyword.arg == "methods":
                    methods_node = keyword.value
                    break
            methods = _literal_methods(methods_node)
            return (methods, route_path) if methods else None
        if func.value.id == "router" and func.attr in {"get", "post", "put", "delete", "patch"}:
            return ([func.attr.upper()], route_path)
    return None


class _ApiVisitor(ast.NodeVisitor):
    def __init__(self, path: str, source: str) -> None:
        self.path = path
        self.source = source
        self.stack: list[str] = []
        self.nodes: list[ApiNode] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._add_api_nodes(node)
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._add_api_nodes(node)
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def _add_api_nodes(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        contracts: list[tuple[str, str]] = []
        decorator_lines: list[int] = []
        for decorator in node.decorator_list:
            contract = _route_decorator_contract(decorator)
            if contract is None:
                continue
            methods, route_path = contract
            decorator_lines.append(int(getattr(decorator, "lineno", getattr(node, "lineno", 1))))
            for method in methods:
                contracts.append((method, route_path))
        if not contracts:
            return
        handler_qualname = ".".join([*self.stack, node.name])
        line_start = min(decorator_lines) if decorator_lines else int(getattr(node, "lineno", 1))
        line_end = int(getattr(node, "end_lineno", getattr(node, "lineno", line_start)))
        api_hash = fn_hash_for_span(self.source, line_start, line_end)
        for method, route_path in contracts:
            self.nodes.append(ApiNode(
                path=self.path,
                method=method,
                route_path=route_path,
                handler_qualname=handler_qualname,
                line_start=line_start,
                line_end=line_end,
                api_hash=api_hash,
                keywords=_identifier_keywords(f"{route_path}_{handler_qualname}"),
            ))


def extract_apis(path: str, source: str) -> list[ApiNode]:
    if not path.endswith(".py"):
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    visitor = _ApiVisitor(path, source)
    visitor.visit(tree)
    return visitor.nodes


class _ClassVisitor(ast.NodeVisitor):
    def __init__(self, path: str, source: str) -> None:
        self.path = path
        self.source = source
        self.stack: list[str] = []
        self.nodes: list[ClassNode] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        line_start = int(getattr(node, "lineno", 1))
        line_end = int(getattr(node, "end_lineno", line_start))
        qualname = ".".join([*self.stack, node.name])
        self.nodes.append(
            ClassNode(
                path=self.path,
                qualname=qualname,
                line_start=line_start,
                line_end=line_end,
                class_hash=fn_hash_for_span(self.source, line_start, line_end),
                keywords=_identifier_keywords(qualname),
                docstring=ast.get_docstring(node, clean=True),
            )
        )
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()


def extract_classes(path: str, source: str) -> list[ClassNode]:
    if not path.endswith(".py"):
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    visitor = _ClassVisitor(path, source)
    visitor.visit(tree)
    return visitor.nodes


def _assigned_names(node: ast.Assign | ast.AnnAssign) -> list[str]:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    names: list[str] = []
    for target in targets:
        if isinstance(target, ast.Name):
            names.append(target.id)
    return names


def _declaration_kind(name: str, value: ast.AST | None) -> str | None:
    if name.isupper():
        return "constant"
    if isinstance(value, ast.Dict):
        return "config_dict"
    return None


def extract_declarations(path: str, source: str) -> list[DeclarationNode]:
    if not path.endswith(".py"):
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    nodes: list[DeclarationNode] = []
    for stmt in tree.body:
        if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            continue
        value = stmt.value
        for name in _assigned_names(stmt):
            kind = _declaration_kind(name, value)
            if kind is None:
                continue
            line_start = int(getattr(stmt, "lineno", 1))
            line_end = int(getattr(stmt, "end_lineno", line_start))
            nodes.append(DeclarationNode(
                path=path,
                qualname=name,
                line_start=line_start,
                line_end=line_end,
                declaration_hash=fn_hash_for_span(source, line_start, line_end),
                keywords=_identifier_keywords(name),
                declaration_kind=kind,
            ))
    return nodes


def _canonical_config_value(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def config_hash_for_value(value: object) -> str:
    return hashlib.sha256(_canonical_config_value(value).encode("utf-8")).hexdigest()


def _parse_config(path: str, source: str) -> tuple[str, object] | None:
    try:
        if path.endswith(".json"):
            return "json", json.loads(source)
        if path.endswith(".toml") and tomllib is not None:
            return "toml", tomllib.loads(source)
    except Exception:
        return None
    return None


def extract_configs(path: str, source: str) -> list[ConfigNode]:
    parsed = _parse_config(path, source)
    if parsed is None:
        return []
    kind, data = parsed
    if not isinstance(data, dict):
        return []
    nodes: list[ConfigNode] = []
    for key in sorted(data):
        if not isinstance(key, str):
            continue
        nodes.append(ConfigNode(
            path=path,
            key=key,
            config_hash=config_hash_for_value(data[key]),
            keywords=_identifier_keywords(key),
            config_kind=kind,
        ))
    return nodes
