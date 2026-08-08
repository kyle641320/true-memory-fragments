from __future__ import annotations

import ast
from dataclasses import dataclass

from .extract import ClassNode, DeclarationNode, FunctionNode, extract_classes, extract_declarations, extract_functions
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
class EnvReadEdge:
    reader_id: str
    env_name: str
    evidence: str = "observed"
    resolution: str = "python_literal_env_key"
    reader_path: str | None = None
    reader_fn_hash: str | None = None
    reader_qualname: str | None = None


@dataclass(frozen=True)
class UnresolvedEnvRead:
    reader_id: str
    expr: str
    reason: str


@dataclass(frozen=True)
class ConfigKeyReadEdge:
    reader_id: str
    config_id: str
    config_key: str
    evidence: str = "observed"
    resolution: str = "python_literal_config_key_unique_file"
    reader_path: str | None = None
    config_path: str | None = None
    reader_fn_hash: str | None = None
    config_hash: str | None = None
    reader_qualname: str | None = None


@dataclass(frozen=True)
class UnresolvedConfigKeyRead:
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
        # Do not attribute nested function calls to the enclosing function.
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




def _class_ast_nodes(source: str) -> dict[str, ast.ClassDef]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    out: dict[str, ast.ClassDef] = {}
    stack: list[str] = []

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            qualname = ".".join([*stack, node.name])
            out[qualname] = node
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()

    Visitor().visit(tree)
    return out


def _base_name(expr: ast.AST) -> str | None:
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        return expr.attr
    return None


def _unique_inherited_method(class_qual: str, method: str, classes: list[ClassNode], class_ast: dict[str, ast.ClassDef], fn_by_qual: dict[str, FunctionNode]) -> str | None:
    by_short: dict[str, list[str]] = {}
    for cls in classes:
        by_short.setdefault(cls.qualname.rsplit('.', 1)[-1], []).append(cls.qualname)
    seen: set[str] = set()

    def walk(cls_qual: str) -> list[str] | None:
        if cls_qual in seen:
            return []
        seen.add(cls_qual)
        node = class_ast.get(cls_qual)
        if node is None:
            return None
        hits: list[str] = []
        for base in node.bases:
            name = _base_name(base)
            if not name:
                return None
            candidates = by_short.get(name, [])
            if len(candidates) != 1:
                return None
            parent = candidates[0]
            direct = f"{parent}.{method}"
            if direct in fn_by_qual:
                hits.append(direct)
            nested = walk(parent)
            if nested is None:
                return None
            hits.extend(nested)
        return hits

    found = walk(class_qual)
    if found is None:
        return None
    unique = sorted(set(found))
    return unique[0] if len(unique) == 1 else None

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
    classes = extract_classes(path, source)
    class_ast = _class_ast_nodes(source)
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
                        inherited = _unique_inherited_method(class_name, call.func.attr, classes, class_ast, fn_by_qual)
                        if inherited is not None:
                            callee_qual = inherited
                        else:
                            reason = "self_method_not_found_in_class_or_unique_resolved_base"
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



def _literal_str(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_os_environ(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "environ" and isinstance(node.value, ast.Name) and node.value.id == "os"


def _env_key_from_call(node: ast.Call) -> tuple[str | None, str | None]:
    f = node.func
    if isinstance(f, ast.Attribute):
        if f.attr == "getenv" and isinstance(f.value, ast.Name) and f.value.id == "os":
            if not node.args:
                return None, "env_key_missing"
            key = _literal_str(node.args[0])
            return key, None if key is not None else "env_key_not_literal"
        if f.attr == "get" and _is_os_environ(f.value):
            if not node.args:
                return None, "env_key_missing"
            key = _literal_str(node.args[0])
            return key, None if key is not None else "env_key_not_literal"
    return None, None


def resolve_env_read_edges(path: str, source: str, functions: list[FunctionNode]) -> tuple[list[EnvReadEdge], dict[str, list[UnresolvedEnvRead]]]:
    if not path.endswith(".py"):
        return [], {}
    fn_nodes = _function_ast_nodes(source)
    edges: list[EnvReadEdge] = []
    unresolved: dict[str, list[UnresolvedEnvRead]] = {}
    for fn in functions:
        node = fn_nodes.get(fn.qualname)
        if node is None:
            continue
        rid = stable_function_claim_id(fn.path, fn.qualname)
        class V(ast.NodeVisitor):
            def visit_FunctionDef(self, n: ast.FunctionDef) -> None:
                if n is node:
                    self.generic_visit(n)
            def visit_AsyncFunctionDef(self, n: ast.AsyncFunctionDef) -> None:
                if n is node:
                    self.generic_visit(n)
            def visit_Subscript(self, n: ast.Subscript) -> None:
                if _is_os_environ(n.value):
                    key = _literal_str(n.slice)
                    if key is not None:
                        edges.append(EnvReadEdge(rid, key, reader_path=fn.path, reader_fn_hash=fn.fn_hash, reader_qualname=fn.qualname))
                    else:
                        unresolved.setdefault(rid, []).append(UnresolvedEnvRead(rid, _expr_name(n), "env_key_not_literal"))
                self.generic_visit(n)
            def visit_Call(self, n: ast.Call) -> None:
                key, reason = _env_key_from_call(n)
                if key is not None:
                    edges.append(EnvReadEdge(rid, key, reader_path=fn.path, reader_fn_hash=fn.fn_hash, reader_qualname=fn.qualname))
                elif reason is not None:
                    unresolved.setdefault(rid, []).append(UnresolvedEnvRead(rid, _expr_name(n), reason))
                self.generic_visit(n)
        V().visit(node)
    return edges, unresolved


def _config_load_assignments(fn_node: ast.AST) -> dict[str, str]:
    out: dict[str, str] = {}
    for n in ast.walk(fn_node):
        if not isinstance(n, ast.Assign) or not isinstance(n.value, ast.Call):
            continue
        if len(n.targets) != 1 or not isinstance(n.targets[0], ast.Name):
            continue
        call = n.value
        f = call.func
        if not (isinstance(f, ast.Attribute) and f.attr == "load" and isinstance(f.value, ast.Name) and f.value.id in {"json", "toml"}):
            continue
        if not call.args:
            continue
        arg = call.args[0]
        config_path = None
        if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) and arg.func.id == "open" and arg.args:
            config_path = _literal_str(arg.args[0])
        if config_path:
            out[n.targets[0].id] = config_path
    return out


def _subscript_literal_chain(n: ast.Subscript) -> tuple[str | None, list[str], str | None]:
    parts: list[str] = []
    cur: ast.AST = n
    while isinstance(cur, ast.Subscript):
        key = _literal_str(cur.slice)
        if key is None:
            if isinstance(cur.value, ast.Name):
                return cur.value.id, list(reversed(parts)), "config_key_not_literal"
            return None, list(reversed(parts)), "config_key_not_literal"
        parts.append(key)
        cur = cur.value
    if isinstance(cur, ast.Name):
        return cur.id, list(reversed(parts)), None
    return None, list(reversed(parts)), "config_base_not_name"


def resolve_config_key_read_edges(path: str, source: str, functions: list[FunctionNode], repo: GitRepo | None = None) -> tuple[list[ConfigKeyReadEdge], dict[str, list[UnresolvedConfigKeyRead]]]:
    if not path.endswith(".py") or repo is None:
        return [], {}
    from .extract import extract_configs
    from .ids import stable_config_claim_id
    fn_nodes = _function_ast_nodes(source)
    edges: list[ConfigKeyReadEdge] = []
    unresolved: dict[str, list[UnresolvedConfigKeyRead]] = {}
    seen_edges: set[tuple[str, str]] = set()
    seen_unresolved: set[tuple[str, str, str]] = set()
    for fn in functions:
        node = fn_nodes.get(fn.qualname)
        if node is None:
            continue
        rid = stable_function_claim_id(fn.path, fn.qualname)
        assigns = _config_load_assignments(node)
        if not assigns:
            continue
        class V(ast.NodeVisitor):
            def visit_Subscript(self, n: ast.Subscript) -> None:
                base, keys, reason = _subscript_literal_chain(n)
                if base in assigns and (keys or reason is not None):
                    if reason is not None:
                        keyu = (rid, _expr_name(n), reason)
                        if keyu not in seen_unresolved:
                            unresolved.setdefault(rid, []).append(UnresolvedConfigKeyRead(rid, _expr_name(n), reason))
                            seen_unresolved.add(keyu)
                    else:
                        cfg_path = assigns[base]
                        key_path = ".".join(keys)
                        try:
                            cfg_text = repo.read_file(cfg_path)
                            configs = {c.key: c for c in extract_configs(cfg_path, cfg_text)}
                        except Exception:
                            configs = {}
                        cfg = configs.get(key_path)
                        if cfg is None:
                            keyu = (rid, _expr_name(n), "config_key_not_found")
                            if keyu not in seen_unresolved:
                                unresolved.setdefault(rid, []).append(UnresolvedConfigKeyRead(rid, _expr_name(n), "config_key_not_found"))
                                seen_unresolved.add(keyu)
                        else:
                            edge_key = (rid, stable_config_claim_id(cfg_path, key_path))
                            if edge_key not in seen_edges:
                                edges.append(ConfigKeyReadEdge(rid, stable_config_claim_id(cfg_path, key_path), key_path, reader_path=fn.path, config_path=cfg_path, reader_fn_hash=fn.fn_hash, config_hash=cfg.config_hash, reader_qualname=fn.qualname))
                                seen_edges.add(edge_key)
                self.generic_visit(n)
        V().visit(node)
    return edges, unresolved
