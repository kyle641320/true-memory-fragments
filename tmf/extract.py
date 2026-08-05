from __future__ import annotations

import ast
import hashlib
import io
import json
import tokenize
from dataclasses import dataclass
from typing import Literal

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    tomllib = None

NodeKind = Literal["function", "class", "declaration", "config", "api", "module_top_level"]


@dataclass(frozen=True)
class FunctionNode:
    path: str
    qualname: str
    line_start: int
    line_end: int
    fn_hash: str
    keywords: list[str]
    docstring: str | None = None


@dataclass(frozen=True)
class ClassNode:
    path: str
    qualname: str
    line_start: int
    line_end: int
    class_hash: str
    keywords: list[str]
    docstring: str | None = None


@dataclass(frozen=True)
class DeclarationNode:
    path: str
    qualname: str
    line_start: int
    line_end: int
    declaration_hash: str
    keywords: list[str]
    declaration_kind: str


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


@dataclass(frozen=True)
class ModuleTopLevelNode:
    path: str
    region_id: str
    line_start: int
    line_end: int
    top_level_hash: str
    keywords: list[str]


_SKIP_TOKEN_TYPES = {
    tokenize.ENCODING,
    tokenize.COMMENT,
    tokenize.NL,
    tokenize.ENDMARKER,
}

# ---------------------------------------------------------------------------
# Single-pass tokenization for O(file_tokens + total_span_filter) hashing.
# Every *_for_span helper accepts an optional _TokenCache to avoid N×full
# tokenize on large files with many functions / nodes.
# ---------------------------------------------------------------------------

class _TokenCache:
    """Pre-tokenized & pre-bucketed token stream for a single source blob."""

    __slots__ = ("_source", "_tokens", "_line_buckets", "_padding", "_len")

    def __init__(self, source: str) -> None:
        self._source = source
        _items: list[tuple[int, str]] = []
        reader = io.StringIO(source).readline
        for tok in tokenize.generate_tokens(reader):
            if tok.type in _SKIP_TOKEN_TYPES:
                continue
            start_line = tok.start[0]
            if tok.type in {tokenize.INDENT, tokenize.DEDENT, tokenize.NEWLINE}:
                _items.append((start_line, (tok.type, tokenize.tok_name[tok.type])))
            else:
                _items.append((start_line, (tok.type, f"{tokenize.tok_name[tok.type]}:{tok.string}")))
        self._tokens = _items
        self._len = len(_items)

        # Build an index: first token index for every line that has tokens.
        self._line_buckets: list[int] = []
        self._padding: list[int] = []   # _line_buckets[line - 1]  -> first index
        cur_line = 1
        for idx, (line_no, _) in enumerate(_items):
            while cur_line < line_no:
                self._padding.insert(cur_line - 1, idx)
                cur_line += 1
            if cur_line == line_no:
                self._padding.insert(cur_line - 1, idx)
                self._line_buckets.append(idx)
                cur_line += 1

    def span_tokens(self, line_start: int, line_end: int) -> list[str]:
        """Extract tokens that belong to [line_start .. line_end]."""
        if not self._tokens:
            return []
        # Find first token whose line >= line_start.
        lo = self._padding[line_start - 1] if line_start - 1 < len(self._padding) else self._len
        # Find first token whose line >  line_end.
        hi = self._padding[line_end] if line_end < len(self._padding) else self._len

        items: list[tuple[int, str]] = []
        for idx in range(lo, hi):
            tok_type, item = self._tokens[idx][1]
            tok_line = self._tokens[idx][0]
            if tok_line < line_start or tok_line > line_end:
                continue
            items.append((tok_type, item))

        # Trim leading / trailing INDENT/DEDENT/NEWLINE that are boundary noise
        # (same logic as before but O(span size) instead of O(file size)).
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


# ---------------------------------------------------------------------------
# Public hash helpers (backward-compatible – cache is optional).
# ---------------------------------------------------------------------------

def _token_items_for_lines(source: str, line_start: int, line_end: int) -> list[str]:
    """Original one-shot path kept for standalone / test compatibility."""
    return _TokenCache(source).span_tokens(line_start, line_end)


def fn_hash_for_span(source: str, line_start: int, line_end: int,
                     *, cache: _TokenCache | None = None) -> str:
    """Compute a stable span hash.

    When *cache* is provided the full file token stream is reused across
    every call, turning N×O(file) into O(file + N×span).
    """
    if cache is not None:
        tokens = cache.span_tokens(line_start, line_end)
    else:
        tokens = _token_items_for_lines(source, line_start, line_end)
    token_stream = "\0".join(tokens)
    return hashlib.sha256(token_stream.encode("utf-8")).hexdigest()


def module_top_level_hash_for_span(source: str, line_start: int, line_end: int,
                                   *, cache: _TokenCache | None = None) -> str:
    return fn_hash_for_span(source, line_start, line_end, cache=cache)

# ---------------------------------------------------------------------------
# Internal helpers that accept an optional cache to avoid re-tokenizing.
# ---------------------------------------------------------------------------

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
    def __init__(self, path: str, source: str, *,
                 cache: _TokenCache | None = None) -> None:
        self.path = path
        self.source = source
        self.cache = cache
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
                fn_hash=fn_hash_for_span(self.source, line_start, line_end, cache=self.cache),
                keywords=_identifier_keywords(qualname),
                docstring=ast.get_docstring(node, clean=True),
            )
        )


def extract_functions(path: str, source: str, *,
                      cache: _TokenCache | None = None) -> list[FunctionNode]:
    if not path.endswith(".py"):
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    visitor = _FunctionVisitor(path, source, cache=cache if cache is not None else _TokenCache(source))
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
    def __init__(self, path: str, source: str, *,
                 cache: _TokenCache | None = None) -> None:
        self.path = path
        self.source = source
        self.cache = cache
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
        api_hash = fn_hash_for_span(self.source, line_start, line_end, cache=self.cache)
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


def extract_apis(path: str, source: str, *,
                 cache: _TokenCache | None = None) -> list[ApiNode]:
    if not path.endswith(".py"):
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    visitor = _ApiVisitor(path, source, cache=cache if cache is not None else _TokenCache(source))
    visitor.visit(tree)
    return visitor.nodes


def _module_top_level_stmt_lines(stmt: ast.stmt) -> tuple[int, int] | None:
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return None
    if isinstance(stmt, ast.Expr) and isinstance(getattr(stmt, "value", None), ast.Constant) and isinstance(stmt.value.value, str):
        return None
    line_start = int(getattr(stmt, "lineno", 0) or 0)
    line_end = int(getattr(stmt, "end_lineno", line_start) or line_start)
    if line_start <= 0 or line_end <= 0:
        return None
    return line_start, line_end


def extract_module_top_levels(path: str, source: str, *,
                              cache: _TokenCache | None = None) -> list[ModuleTopLevelNode]:
    if not path.endswith(".py"):
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    span_cache = cache if cache is not None else _TokenCache(source)
    regions: list[list[tuple[int, int, ast.stmt]]] = []
    current: list[tuple[int, int, ast.stmt]] = []
    previous_end: int | None = None
    for stmt in tree.body:
        lines = _module_top_level_stmt_lines(stmt)
        if lines is None:
            if current:
                regions.append(current)
                current = []
            previous_end = None
            continue
        line_start, line_end = lines
        if current and previous_end is not None and line_start > previous_end + 1:
            regions.append(current)
            current = []
        current.append((line_start, line_end, stmt))
        previous_end = line_end
    if current:
        regions.append(current)

    nodes: list[ModuleTopLevelNode] = []
    for idx, region in enumerate(regions, start=1):
        line_start = region[0][0]
        line_end = region[-1][1]
        region_id = f"top_level_{idx:04d}"
        names: list[str] = []
        for _start, _end, stmt in region:
            if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                names.append("import")
            elif isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        names.append(target.id)
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                names.append(stmt.target.id)
            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                func = stmt.value.func
                if isinstance(func, ast.Name):
                    names.append(func.id)
                elif isinstance(func, ast.Attribute):
                    names.append(func.attr)
        keywords = []
        for name in names:
            for keyword in _identifier_keywords(name):
                if keyword not in keywords:
                    keywords.append(keyword)
            if len(keywords) >= 16:
                break
        nodes.append(ModuleTopLevelNode(
            path=path,
            region_id=region_id,
            line_start=line_start,
            line_end=line_end,
            top_level_hash=module_top_level_hash_for_span(source, line_start, line_end, cache=span_cache),
            keywords=keywords,
        ))
    return nodes


class _ClassVisitor(ast.NodeVisitor):
    def __init__(self, path: str, source: str, *,
                 cache: _TokenCache | None = None) -> None:
        self.path = path
        self.source = source
        self.cache = cache
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
                class_hash=fn_hash_for_span(self.source, line_start, line_end, cache=self.cache),
                keywords=_identifier_keywords(qualname),
                docstring=ast.get_docstring(node, clean=True),
            )
        )
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()


def extract_classes(path: str, source: str, *,
                    cache: _TokenCache | None = None) -> list[ClassNode]:
    if not path.endswith(".py"):
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    visitor = _ClassVisitor(path, source, cache=cache if cache is not None else _TokenCache(source))
    visitor.visit(tree)
    return visitor.nodes


def _assigned_names(node: ast.Assign | ast.AnnAssign) -> list[str]:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    names: list[str] = []
    for target in targets:
        if isinstance(target, ast.Name):
            names.append(target.id)
    return names


def _declaration_kind(name: str, value: ast.AST | None, annotated: bool = False) -> str | None:
    if name.isupper():
        return "constant"
    if isinstance(value, ast.Dict):
        return "config_dict"
    return None


def _ann_declaration_kind(name: str) -> str | None:
    """AnnAssign path: TYPED_CONST: list[str] = [...] should be tracked."""
    if name.isupper():
        return "constant"
    return None


def extract_declarations(path: str, source: str, *,
                         cache: _TokenCache | None = None) -> list[DeclarationNode]:
    if not path.endswith(".py"):
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    nodes: list[DeclarationNode] = []; cache = cache if cache is not None else _TokenCache(source)
    for stmt in tree.body:
        if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            continue
        value = stmt.value
        is_ann = isinstance(stmt, ast.AnnAssign)
        for name in _assigned_names(stmt):
            kind = _ann_declaration_kind(name) if is_ann else _declaration_kind(name, value)
            if kind is None:
                continue
            line_start = int(getattr(stmt, "lineno", 1))
            line_end = int(getattr(stmt, "end_lineno", line_start))
            nodes.append(DeclarationNode(
                path=path,
                qualname=name,
                line_start=line_start,
                line_end=line_end,
                declaration_hash=fn_hash_for_span(source, line_start, line_end, cache=cache),
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
