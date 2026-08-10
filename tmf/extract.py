from __future__ import annotations

import ast
import hashlib
import io
import json
import re
import tokenize
from dataclasses import dataclass, field
from functools import lru_cache
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
    identity_key: str | None = None


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
    line_start: int = 1
    line_end: int = 1


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
    handler_node_id: str | None = None
    route_path_source: str | None = None
    route_qualname: str | None = None
    route_line_start: int | None = None
    route_line_end: int | None = None
    route_hash: str | None = None
    handler_path: str | None = None
    handler_hash: str | None = None
    service_name: str | None = None
    service_url: str | None = None
    adapter: str | None = None
    service_name: str | None = None
    service_url: str | None = None
    adapter: str | None = None


_SKIP_TOKEN_TYPES = {
    tokenize.ENCODING,
    tokenize.COMMENT,
    tokenize.NL,
    tokenize.ENDMARKER,
}


@lru_cache(maxsize=64)
def _token_items_for_source(source: str) -> tuple[tuple[int, int, int, str], ...]:
    """Tokenize a Python source file once for all span hashes.

    Large files can contain hundreds of functions.  The old implementation
    regenerated the full token stream for every function/class/declaration span,
    making extraction roughly O(spans * file_tokens).  This cache preserves the
    exact normalized token items while reducing same-file span hashing to a
    filter over one cached token stream.
    """
    items: list[tuple[int, int, int, str]] = []
    reader = io.StringIO(source).readline
    for tok in tokenize.generate_tokens(reader):
        if tok.type in _SKIP_TOKEN_TYPES:
            continue
        start_line = tok.start[0]
        end_line = tok.end[0]
        if tok.type in {tokenize.INDENT, tokenize.DEDENT, tokenize.NEWLINE}:
            item = tokenize.tok_name[tok.type]
        else:
            item = f"{tokenize.tok_name[tok.type]}:{tok.string}"
        items.append((tok.type, start_line, end_line, item))
    return tuple(items)


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
    items: list[tuple[int, str]] = [
        (tok_type, item)
        for tok_type, start_line, end_line, item in _token_items_for_source(source)
        if end_line >= line_start and start_line <= line_end
    ]

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

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

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



_SQL_CREATE_RE = re.compile(r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(TABLE|VIEW)\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_$.]*|\"[^\"]+\"|`[^`]+`|\[[^\]]+\])", re.IGNORECASE)


def _clean_sql_name(name: str) -> str:
    raw = name.strip()
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith('`') and raw.endswith('`')) or (raw.startswith('[') and raw.endswith(']')):
        raw = raw[1:-1]
    return raw


def extract_sql_declarations(path: str, source: str) -> list[DeclarationNode]:
    """Conservative SQL declaration extractor.

    Only standalone .sql files are parsed. Dynamic SQL strings embedded in code
    are intentionally ignored by this MVP rather than guessed.
    """
    if not path.endswith('.sql'):
        return []
    nodes: list[DeclarationNode] = []
    for match in _SQL_CREATE_RE.finditer(source):
        kind = match.group(1).lower()
        name = _clean_sql_name(match.group(2))
        line_start = source.count('\n', 0, match.start()) + 1
        line_end = line_start
        nodes.append(DeclarationNode(
            path=path,
            qualname=name,
            line_start=line_start,
            line_end=line_end,
            declaration_hash=hashlib.sha256(match.group(0).encode('utf-8')).hexdigest(),
            keywords=_identifier_keywords(name),
            declaration_kind=f'sql_{kind}',
            language='sql',
            extraction_tier='python-ast',
        ))
    return nodes

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



def _parse_scalar_yaml(value: str) -> object:
    text = value.strip()
    if text in {"", "null", "Null", "NULL", "~"}:
        return None
    if text in {"true", "True", "TRUE"}:
        return True
    if text in {"false", "False", "FALSE"}:
        return False
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        return text[1:-1]
    try:
        if re.fullmatch(r"[-+]?\d+", text):
            return int(text)
        if re.fullmatch(r"[-+]?\d+\.\d+", text):
            return float(text)
    except Exception:
        pass
    return text


def _parse_simple_yaml(source: str) -> tuple[dict[str, object], dict[str, int]] | None:
    """Parse a conservative YAML mapping subset without external deps.

    Supports indentation-based mappings and scalar values only. Lists, anchors,
    tags, multiline scalars, duplicate keys, and malformed indentation degrade to
    no YAML nodes rather than approximate semantics.
    """
    root: dict[str, object] = {}
    line_by_key: dict[str, int] = {}
    stack: list[tuple[int, dict[str, object], str]] = [(-1, root, "")]
    seen: set[str] = set()
    for lineno, raw in enumerate(source.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith('#'):
            continue
        if '\t' in raw:
            return None
        stripped = raw.strip()
        if stripped.startswith(('-', '&', '*', '!', '|', '>')) or ' #' in stripped:
            # Avoid lists, anchors/tags, multiline scalars, and inline comment ambiguity.
            return None
        if ':' not in stripped:
            return None
        key, value = stripped.split(':', 1)
        key = key.strip()
        if not key or any(ch in key for ch in '[]{}'):
            return None
        indent = len(raw) - len(raw.lstrip(' '))
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            return None
        parent_indent, parent, parent_path = stack[-1]
        full_key = f"{parent_path}.{key}" if parent_path else key
        if full_key in seen:
            return None
        seen.add(full_key)
        line_by_key[full_key] = lineno
        if value.strip() == "":
            child: dict[str, object] = {}
            parent[key] = child
            stack.append((indent, child, full_key))
        else:
            parent[key] = _parse_scalar_yaml(value)
    return root, line_by_key

def _parse_config(path: str, source: str) -> tuple[str, object, dict[str, int]] | None:
    try:
        if path.endswith(".json"):
            return "json", json.loads(source), {}
        if path.endswith(".toml") and tomllib is not None:
            return "toml", tomllib.loads(source), {}
        if path.endswith((".yaml", ".yml")):
            parsed = _parse_simple_yaml(source)
            if parsed is None:
                return None
            data, line_by_key = parsed
            return "yaml", data, line_by_key
    except Exception:
        return None
    return None


def _flatten_config_items(value: object, prefix: str = "") -> list[tuple[str, object]]:
    items: list[tuple[str, object]] = []
    if isinstance(value, dict):
        for key in sorted(value):
            if not isinstance(key, str):
                continue
            path = f"{prefix}.{key}" if prefix else key
            items.append((path, value[key]))
            items.extend(_flatten_config_items(value[key], path))
    return items


def extract_configs(path: str, source: str) -> list[ConfigNode]:
    parsed = _parse_config(path, source)
    if parsed is None:
        return []
    kind, data, line_by_key = parsed
    if not isinstance(data, dict):
        return []
    nodes: list[ConfigNode] = []
    seen: set[str] = set()
    for key, value in _flatten_config_items(data):
        if key in seen:
            continue
        seen.add(key)
        nodes.append(ConfigNode(
            path=path,
            key=key,
            config_hash=config_hash_for_value(value),
            keywords=_identifier_keywords(key),
            config_kind=kind,
            line_start=line_by_key.get(key, 1),
            line_end=line_by_key.get(key, 1),
        ))
    return nodes


def _unparse(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return None

def _annotation_text(node: ast.AST | None) -> str | None:
    return _unparse(node)

def _default_text(node: ast.AST | None) -> str | None:
    return _unparse(node)

def _decorator_name(node: ast.AST) -> str:
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        parts = [target.attr]
        cur = target.value
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    return _unparse(target) or "<decorator>"

def _raise_names(node: ast.AST) -> list[str]:
    out: set[str] = set()
    class V(ast.NodeVisitor):
        def visit_Raise(self, n: ast.Raise) -> None:
            exc = n.exc
            if isinstance(exc, ast.Call):
                exc = exc.func
            if isinstance(exc, ast.Name):
                out.add(exc.id)
            elif isinstance(exc, ast.Attribute):
                out.add(exc.attr)
            self.generic_visit(n)
    V().visit(node)
    return sorted(out)

def _return_shape(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, object]:
    has_bare = False
    has_value = False
    class V(ast.NodeVisitor):
        def visit_Return(self, n: ast.Return) -> None:
            nonlocal has_bare, has_value
            if n.value is None:
                has_bare = True
            else:
                has_value = True
        def visit_FunctionDef(self, n: ast.FunctionDef) -> None:  # skip nested
            if n is not node:
                return
            self.generic_visit(n)
        def visit_AsyncFunctionDef(self, n: ast.AsyncFunctionDef) -> None:
            if n is not node:
                return
            self.generic_visit(n)
    V().visit(node)
    annotation = _annotation_text(node.returns)
    if has_value:
        shape = "value"
    elif has_bare:
        shape = "bare"
    elif annotation:
        shape = "annotation_only"
    else:
        shape = "none"
    return {"shape": shape, "annotation": annotation, "has_value": has_value, "has_bare": has_bare}

def _is_generator(node: ast.AST) -> bool:
    found = False
    class V(ast.NodeVisitor):
        def visit_Yield(self, n: ast.Yield) -> None:
            nonlocal found; found = True
        def visit_YieldFrom(self, n: ast.YieldFrom) -> None:
            nonlocal found; found = True
        def visit_FunctionDef(self, n: ast.FunctionDef) -> None:
            if n is not node:
                return
            self.generic_visit(n)
        def visit_AsyncFunctionDef(self, n: ast.AsyncFunctionDef) -> None:
            if n is not node:
                return
            self.generic_visit(n)
    V().visit(node)
    return found

def _param_items(args: ast.arguments) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    pos = [*args.posonlyargs, *args.args]
    defaults = [None] * (len(pos) - len(args.defaults)) + list(args.defaults)
    for arg, default in zip(pos, defaults):
        out.append({"name": arg.arg, "kind": "positional", "annotation": _annotation_text(arg.annotation), "default": _default_text(default)})
    if args.vararg:
        out.append({"name": args.vararg.arg, "kind": "vararg", "annotation": _annotation_text(args.vararg.annotation), "default": None})
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        out.append({"name": arg.arg, "kind": "kwonly", "annotation": _annotation_text(arg.annotation), "default": _default_text(default)})
    if args.kwarg:
        out.append({"name": args.kwarg.arg, "kind": "kwarg", "annotation": _annotation_text(args.kwarg.annotation), "default": None})
    return out

def _signature_text(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    parts: list[str] = []
    pos = [*node.args.posonlyargs, *node.args.args]
    defaults = [None] * (len(pos) - len(node.args.defaults)) + list(node.args.defaults)
    for arg, default in zip(pos, defaults):
        text = arg.arg
        ann = _annotation_text(arg.annotation)
        if ann:
            text += f": {ann}"
        d = _default_text(default)
        if d is not None:
            text += f"={d}"
        parts.append(text)
    if node.args.vararg:
        text = "*" + node.args.vararg.arg
        ann = _annotation_text(node.args.vararg.annotation)
        if ann: text += f": {ann}"
        parts.append(text)
    elif node.args.kwonlyargs:
        parts.append("*")
    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
        text = arg.arg
        ann = _annotation_text(arg.annotation)
        if ann: text += f": {ann}"
        d = _default_text(default)
        if d is not None: text += f"={d}"
        parts.append(text)
    if node.args.kwarg:
        text = "**" + node.args.kwarg.arg
        ann = _annotation_text(node.args.kwarg.annotation)
        if ann: text += f": {ann}"
        parts.append(text)
    ret = _annotation_text(node.returns)
    return f"{prefix} {node.name}(" + ", ".join(parts) + ")" + (f" -> {ret}" if ret else "")

def function_interface(source: str, fn: FunctionNode) -> dict[str, object]:
    tree = ast.parse(source)
    target: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    stack: list[str] = []
    class V(ast.NodeVisitor):
        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            stack.append(node.name); self.generic_visit(node); stack.pop()
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            nonlocal target
            q = ".".join([*stack, node.name])
            if q == fn.qualname and int(getattr(node, "lineno", 0)) == fn.line_start:
                target = node
            stack.append(node.name); self.generic_visit(node); stack.pop()
        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            nonlocal target
            q = ".".join([*stack, node.name])
            if q == fn.qualname and int(getattr(node, "lineno", 0)) == fn.line_start:
                target = node
            stack.append(node.name); self.generic_visit(node); stack.pop()
    V().visit(tree)
    if target is None:
        return {}
    return {
        "language": "python",
        "signature": _signature_text(target),
        "params": _param_items(target.args),
        "is_async": isinstance(target, ast.AsyncFunctionDef),
        "is_generator": _is_generator(target),
        "return": _return_shape(target),
        "raises": _raise_names(target),
        "decorators": [_decorator_name(d) for d in target.decorator_list],
    }
