from __future__ import annotations

import ast
from dataclasses import dataclass

from .extract import DeclarationNode, FunctionNode, extract_declarations, extract_functions
from .git import GitRepo
from .imports import ImportTarget, parse_import_targets
from .ids import stable_declaration_claim_id, stable_function_claim_id


@dataclass(frozen=True)
class CallEdge:
    caller_id: str
    callee_id: str
    callee_qualname: str
    evidence: str = "observed"
    resolution: str = "module_name_or_self_method"
    caller_path: str | None = None
    callee_path: str | None = None
    caller_fn_hash: str | None = None
    callee_fn_hash: str | None = None
    caller_qualname: str | None = None


@dataclass(frozen=True)
class WriteEdge:
    writer_id: str
    declaration_id: str
    declaration_qualname: str
    evidence: str = "observed"
    resolution: str = "global_module_declaration_assignment"
    writer_path: str | None = None
    declaration_path: str | None = None
    writer_fn_hash: str | None = None
    declaration_hash: str | None = None
    writer_qualname: str | None = None


@dataclass(frozen=True)
class UnresolvedWrite:
    writer_id: str
    expr: str
    reason: str


@dataclass(frozen=True)
class ReadEdge:
    reader_id: str
    declaration_id: str
    declaration_qualname: str
    evidence: str = "observed"
    resolution: str = "module_declaration_name"
    reader_path: str | None = None
    declaration_path: str | None = None
    reader_fn_hash: str | None = None
    declaration_hash: str | None = None
    reader_qualname: str | None = None


@dataclass(frozen=True)
class UnresolvedRead:
    reader_id: str
    expr: str
    reason: str


@dataclass(frozen=True)
class UnresolvedCall:
    caller_id: str
    expr: str
    reason: str


def _node_id(path: str, qualname: str) -> str:
    return stable_function_claim_id(path, qualname)


class _CallVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.calls: list[ast.Call] = []

    def visit_Call(self, node: ast.Call) -> None:
        self.calls.append(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Nested function calls are not attributed to the enclosing function.
        # Record as unresolved so coverage gaps are visible in debug output.
        self.nested_fn_calls_skipped: int = getattr(self, "nested_fn_calls_skipped", 0) + 1
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return


def _expr_name(expr: ast.AST) -> str:
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        base = _expr_name(expr.value)
        return f"{base}.{expr.attr}" if base else expr.attr
    if isinstance(expr, ast.Call):
        return _expr_name(expr.func) + "(...)"
    return expr.__class__.__name__


def _function_ast_nodes(source: str) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    out: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    stack: list[str] = []

    class Visitor(ast.NodeVisitor):
        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            qualname = ".".join([*stack, node.name])
            out[qualname] = node
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            qualname = ".".join([*stack, node.name])
            out[qualname] = node
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()

    Visitor().visit(tree)
    return out


def resolve_call_edges(path: str, source: str, functions: list[FunctionNode], repo: GitRepo | None = None) -> tuple[list[CallEdge], dict[str, list[UnresolvedCall]]]:
    """Conservative Python call resolver.

    v2 first cut resolves only:
    - module-local Name() calls to a unique top-level function in the same file;
    - self.method() calls to methods on the same class.

    Unknown attributes, dynamic calls, stdlib/external names, cross-file imports,
    and ambiguous names become unresolved calls, not guessed edges.
    """
    fn_by_qual = {fn.qualname: fn for fn in functions}
    fn_by_id = {_node_id(fn.path, fn.qualname): fn for fn in functions}
    top_level_by_name = {fn.qualname: fn for fn in functions if "." not in fn.qualname}
    import_table: dict[str, ImportTarget] = {}
    import_unresolved: dict[str, str] = {}
    external_functions_cache: dict[str, dict[str, FunctionNode]] = {}
    if repo is not None:
        import_table, import_unresolved = parse_import_targets(repo, path, source)
    ast_by_qual = _function_ast_nodes(source)
    edges: list[CallEdge] = []
    unresolved: dict[str, list[UnresolvedCall]] = {}

    for fn in functions:
        caller_id = _node_id(path, fn.qualname)
        node = ast_by_qual.get(fn.qualname)
        if node is None:
            continue
        visitor = _CallVisitor()
        for stmt in node.body:
            visitor.visit(stmt)
        for call in visitor.calls:
            callee_qual: str | None = None
            reason: str | None = None
            if isinstance(call.func, ast.Name):
                target = top_level_by_name.get(call.func.id)
                if target is not None:
                    callee_qual = target.qualname
                elif repo is not None and call.func.id in import_table and import_table[call.func.id].kind == "from_import":
                    target_import = import_table[call.func.id]
                    target_map = external_functions_cache.get(target_import.module_path)
                    if target_map is None:
                        target_source = repo.read_file(target_import.module_path)
                        target_map = {f.qualname: f for f in extract_functions(target_import.module_path, target_source) if "." not in f.qualname}
                        external_functions_cache[target_import.module_path] = target_map
                    target_fn = target_map.get(str(target_import.symbol))
                    if target_fn is not None:
                        edges.append(CallEdge(
                            caller_id=caller_id,
                            callee_id=_node_id(target_fn.path, target_fn.qualname),
                            callee_qualname=target_fn.qualname,
                            resolution="from_import_direct_top_level",
                            caller_path=fn.path,
                            callee_path=target_fn.path,
                            caller_fn_hash=fn.fn_hash,
                            callee_fn_hash=target_fn.fn_hash,
                            caller_qualname=fn.qualname,
                        ))
                        continue
                    reason = "from_import_symbol_not_direct_top_level_def"
                else:
                    reason = import_unresolved.get(call.func.id, "name_not_module_local_function")
            elif isinstance(call.func, ast.Attribute):
                if isinstance(call.func.value, ast.Name) and repo is not None and call.func.value.id in import_table and import_table[call.func.value.id].kind == "import_module":
                    target_import = import_table[call.func.value.id]
                    target_map = external_functions_cache.get(target_import.module_path)
                    if target_map is None:
                        target_source = repo.read_file(target_import.module_path)
                        target_map = {f.qualname: f for f in extract_functions(target_import.module_path, target_source) if "." not in f.qualname}
                        external_functions_cache[target_import.module_path] = target_map
                    target_fn = target_map.get(call.func.attr)
                    if target_fn is not None:
                        edges.append(CallEdge(
                            caller_id=caller_id,
                            callee_id=_node_id(target_fn.path, target_fn.qualname),
                            callee_qualname=target_fn.qualname,
                            resolution="import_module_direct_top_level",
                            caller_path=fn.path,
                            callee_path=target_fn.path,
                            caller_fn_hash=fn.fn_hash,
                            callee_fn_hash=target_fn.fn_hash,
                            caller_qualname=fn.qualname,
                        ))
                        continue
                    reason = "import_module_attr_not_direct_top_level_def"
                elif isinstance(call.func.value, ast.Name) and call.func.value.id == "self" and "." in fn.qualname:
                    class_name = fn.qualname.rsplit(".", 1)[0]
                    candidate = f"{class_name}.{call.func.attr}"
                    if candidate in fn_by_qual:
                        callee_qual = candidate
                    else:
                        reason = "self_method_not_found_in_class"
                else:
                    reason = "attribute_call_not_resolved"
            else:
                reason = "dynamic_call_not_resolved"

            if callee_qual is not None:
                callee_fn = fn_by_qual.get(callee_qual)
                edges.append(CallEdge(
                    caller_id=caller_id,
                    callee_id=_node_id(path, callee_qual),
                    callee_qualname=callee_qual,
                    caller_path=fn.path,
                    callee_path=callee_fn.path if callee_fn else path,
                    caller_fn_hash=fn.fn_hash,
                    callee_fn_hash=callee_fn.fn_hash if callee_fn else None,
                    caller_qualname=fn.qualname,
                ))
            else:
                unresolved.setdefault(caller_id, []).append(UnresolvedCall(caller_id=caller_id, expr=_expr_name(call.func), reason=reason or "unresolved"))
        nested_skipped = getattr(visitor, "nested_fn_calls_skipped", 0)
        if nested_skipped:
            unresolved.setdefault(caller_id, []).append(
                UnresolvedCall(caller_id=caller_id, expr="<nested_function_defs>", reason=f"nested_function_calls_not_tracked:{nested_skipped}")
            )
    return edges, unresolved


class _ReadVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.loads: list[ast.Name] = []
        self.local_bindings: set[str] = set()
        self.global_names: set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self.loads.append(node)
        elif isinstance(node.ctx, (ast.Store, ast.Del)):
            if node.id not in self.global_names:
                self.local_bindings.add(node.id)

    def visit_Global(self, node: ast.Global) -> None:
        self.global_names.update(node.names)

    def visit_arg(self, node: ast.arg) -> None:
        self.local_bindings.add(node.arg)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        # ``X += y`` reads X and writes X. Only keep target read when global
        # makes it a module declaration candidate; otherwise Store still shadows.
        if isinstance(node.target, ast.Name) and node.target.id in self.global_names:
            self.loads.append(node.target)
        else:
            self.visit(node.target)
        self.visit(node.value)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Do not attribute nested function reads to the enclosing function.
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self.visit(node.target)
        for item in node.ifs:
            self.visit(item)
        # Deliberately skip iter after collecting target: comprehension target
        # binding makes same-name loads ambiguous for this conservative MVP.


def _looks_like_declaration_name(name: str) -> bool:
    return name.isupper()


def _declaration_id(path: str, qualname: str) -> str:
    return stable_declaration_claim_id(path, qualname)


def resolve_read_edges(path: str, source: str, functions: list[FunctionNode], declarations: list[DeclarationNode], repo: GitRepo | None = None) -> tuple[list[ReadEdge], dict[str, list[UnresolvedRead]]]:
    """Conservative Python declaration-read resolver.

    Resolves only function-body ``Name`` loads that unambiguously refer to a
    module-level declaration node in the same file or to a direct ``from`` import
    whose target module has a unique top-level declaration of that symbol.
    Local bindings/parameters shadow module declarations and are not linked.
    """
    same_file_decls = {decl.qualname: decl for decl in declarations}
    import_table: dict[str, ImportTarget] = {}
    import_unresolved: dict[str, str] = {}
    external_declarations_cache: dict[str, dict[str, DeclarationNode]] = {}
    if repo is not None:
        import_table, import_unresolved = parse_import_targets(repo, path, source)
    ast_by_qual = _function_ast_nodes(source)
    edges: list[ReadEdge] = []
    unresolved: dict[str, list[UnresolvedRead]] = {}
    seen_edges: set[tuple[str, str]] = set()
    seen_unresolved: set[tuple[str, str, str]] = set()

    for fn in functions:
        reader_id = _node_id(path, fn.qualname)
        node = ast_by_qual.get(fn.qualname)
        if node is None:
            continue
        visitor = _ReadVisitor()
        for arg in list(node.args.posonlyargs) + list(node.args.args) + list(node.args.kwonlyargs):
            visitor.visit_arg(arg)
        if node.args.vararg:
            visitor.visit_arg(node.args.vararg)
        if node.args.kwarg:
            visitor.visit_arg(node.args.kwarg)
        for stmt in node.body:
            visitor.visit(stmt)
        for name_node in visitor.loads:
            name = name_node.id
            if name in visitor.local_bindings:
                if _looks_like_declaration_name(name):
                    key = (reader_id, name, "local_binding_shadows_declaration")
                    if key not in seen_unresolved:
                        unresolved.setdefault(reader_id, []).append(UnresolvedRead(reader_id, name, "local_binding_shadows_declaration"))
                        seen_unresolved.add(key)
                continue
            target_decl: DeclarationNode | None = None
            resolution = "module_declaration_name"
            reason: str | None = None
            if name in same_file_decls:
                target_decl = same_file_decls[name]
            elif repo is not None and name in import_table and import_table[name].kind == "from_import":
                target_import = import_table[name]
                decls = external_declarations_cache.get(target_import.module_path)
                if decls is None:
                    target_source = repo.read_file(target_import.module_path)
                    decls = {decl.qualname: decl for decl in extract_declarations(target_import.module_path, target_source)}
                    external_declarations_cache[target_import.module_path] = decls
                target_decl = decls.get(str(target_import.symbol))
                resolution = "from_import_direct_top_level_declaration"
                if target_decl is None:
                    reason = "from_import_symbol_not_tracked_declaration"
            elif name in import_unresolved:
                reason = import_unresolved[name]
            elif _looks_like_declaration_name(name):
                reason = "name_not_tracked_declaration"
            else:
                continue

            if target_decl is not None:
                declaration_id = _declaration_id(target_decl.path, target_decl.qualname)
                key = (reader_id, declaration_id)
                if key in seen_edges:
                    continue
                seen_edges.add(key)
                edges.append(ReadEdge(
                    reader_id=reader_id,
                    declaration_id=declaration_id,
                    declaration_qualname=target_decl.qualname,
                    resolution=resolution,
                    reader_path=fn.path,
                    declaration_path=target_decl.path,
                    reader_fn_hash=fn.fn_hash,
                    declaration_hash=target_decl.declaration_hash,
                    reader_qualname=fn.qualname,
                ))
            elif reason is not None:
                key = (reader_id, name, reason)
                if key not in seen_unresolved:
                    unresolved.setdefault(reader_id, []).append(UnresolvedRead(reader_id, name, reason))
                    seen_unresolved.add(key)
    return edges, unresolved


class _WriteVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.global_names: set[str] = set()
        self.writes: list[tuple[str, str]] = []
        self.unresolved: list[tuple[str, str]] = []

    def visit_Global(self, node: ast.Global) -> None:
        self.global_names.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        for name in node.names:
            self.unresolved.append((name, "nonlocal_not_module_declaration"))

    def _target_names(self, node: ast.AST) -> list[str]:
        if isinstance(node, ast.Name):
            return [node.id]
        if isinstance(node, (ast.Tuple, ast.List)):
            out: list[str] = []
            for item in node.elts:
                out.extend(self._target_names(item))
            return out
        return []

    def _record_target(self, name: str, op: str) -> None:
        if name in self.global_names:
            self.writes.append((name, op))
        elif _looks_like_declaration_name(name):
            self.unresolved.append((name, "assignment_without_global_is_local"))

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit(node.value)
        for target in node.targets:
            for name in self._target_names(target):
                self._record_target(name, "assign")

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self.visit(node.value)
        for name in self._target_names(node.target):
            self._record_target(name, "annassign")

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.visit(node.value)
        for name in self._target_names(node.target):
            self._record_target(name, "augassign")

    def visit_Delete(self, node: ast.Delete) -> None:
        for target in node.targets:
            for name in self._target_names(target):
                self._record_target(name, "delete")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return


def resolve_write_edges(path: str, source: str, functions: list[FunctionNode], declarations: list[DeclarationNode], repo: GitRepo | None = None) -> tuple[list[WriteEdge], dict[str, list[UnresolvedWrite]]]:
    same_file_decls = {decl.qualname: decl for decl in declarations}
    ast_by_qual = _function_ast_nodes(source)
    edges: list[WriteEdge] = []
    unresolved: dict[str, list[UnresolvedWrite]] = {}
    seen_edges: set[tuple[str, str]] = set()
    seen_unresolved: set[tuple[str, str, str]] = set()
    for fn in functions:
        writer_id = _node_id(path, fn.qualname)
        node = ast_by_qual.get(fn.qualname)
        if node is None:
            continue
        visitor = _WriteVisitor()
        for stmt in node.body:
            visitor.visit(stmt)
        for name, reason in visitor.unresolved:
            key = (writer_id, name, reason)
            if key not in seen_unresolved:
                unresolved.setdefault(writer_id, []).append(UnresolvedWrite(writer_id, name, reason))
                seen_unresolved.add(key)
        for name, op in visitor.writes:
            decl = same_file_decls.get(name)
            if decl is None:
                reason = "global_name_not_tracked_declaration"
                key = (writer_id, name, reason)
                if key not in seen_unresolved:
                    unresolved.setdefault(writer_id, []).append(UnresolvedWrite(writer_id, name, reason))
                    seen_unresolved.add(key)
                continue
            declaration_id = _declaration_id(decl.path, decl.qualname)
            key = (writer_id, declaration_id)
            if key in seen_edges:
                continue
            seen_edges.add(key)
            edges.append(WriteEdge(
                writer_id=writer_id,
                declaration_id=declaration_id,
                declaration_qualname=decl.qualname,
                resolution=f"global_module_declaration_{op}",
                writer_path=fn.path,
                declaration_path=decl.path,
                writer_fn_hash=fn.fn_hash,
                declaration_hash=decl.declaration_hash,
                writer_qualname=fn.qualname,
            ))
    return edges, unresolved
