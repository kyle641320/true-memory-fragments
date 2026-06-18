from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from .edges import resolve_call_edges, resolve_read_edges, resolve_write_edges
from .extract import ApiNode, ClassNode, ConfigNode, DeclarationNode, FunctionNode, extract_apis, extract_classes, extract_configs, extract_declarations, extract_functions
from .backends import SemanticExtractorBackend
from .java_extract import JAVA_DEGRADE_HINT, extract_java_classes, extract_java_fields, extract_java_methods, java_status, resolve_java_inherit_edges
from .llm import DeriverModel
from .model_derive import derive_model_function_claims
from .git import GitRepo
from .ids import now_utc, stable_api_claim_id, stable_call_edge_claim_id, stable_class_claim_id, stable_config_claim_id, stable_declaration_claim_id, stable_file_claim_id, stable_function_claim_id, stable_java_node_claim_id, stable_read_edge_claim_id, stable_write_edge_claim_id, stable_inherit_edge_claim_id
from .schema import Binding, Claim
from .verify import verify_observed_claim

MODEL = "tmf-v1-heuristic"


def _anchor(path: str, line_start: int | None, line_end: int | None, qualname: str | None) -> dict:
    return {"path": path, "line_start": line_start, "line_end": line_end, "qualname": qualname}


@lru_cache(maxsize=8192)
def _function_anchor_cached(root: str, path: str, qualname: str, blob: str | None) -> tuple[int | None, int | None]:
    try:
        source = (Path(root) / path).read_text(encoding="utf-8")
        for fn in extract_functions(path, source):
            if fn.qualname == qualname:
                return fn.line_start, fn.line_end
    except Exception:
        pass
    return None, None


@lru_cache(maxsize=8192)
def _declaration_anchor_cached(root: str, path: str, qualname: str, blob: str | None) -> tuple[int | None, int | None]:
    try:
        source = (Path(root) / path).read_text(encoding="utf-8")
        for decl in extract_declarations(path, source):
            if decl.qualname == qualname:
                return decl.line_start, decl.line_end
    except Exception:
        pass
    return None, None


def _function_anchor_for(repo: GitRepo, path: str | None, qualname: str | None) -> dict:
    if not path or not qualname:
        return _anchor(path, None, None, qualname)
    blob = repo.blob_sha(path)
    line_start, line_end = _function_anchor_cached(str(repo.root), path, qualname, blob)
    return _anchor(path, line_start, line_end, qualname)


def _declaration_anchor_for(repo: GitRepo, path: str | None, qualname: str | None) -> dict:
    if not path or not qualname:
        return _anchor(path, None, None, qualname)
    blob = repo.blob_sha(path)
    line_start, line_end = _declaration_anchor_cached(str(repo.root), path, qualname, blob)
    return _anchor(path, line_start, line_end, qualname)


def _keywords(text: str, limit: int = 16) -> list[str]:
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text)
    stop = {"the", "and", "for", "from", "with", "return", "class", "def", "import", "const", "let", "var"}
    seen: set[str] = set()
    out: list[str] = []
    for word in words:
        key = word.lower()
        if key in stop or key in seen:
            continue
        seen.add(key)
        out.append(word)
        if len(out) >= limit:
            break
    return out


def derive_file_claim(repo: GitRepo, path: str) -> Claim:
    text = repo.read_file(path)
    blob = repo.blob_sha(path)
    head = repo.head()
    keywords = _keywords(text)
    line_count = len(text.splitlines())
    functions = extract_functions(path, text)
    try:
        java_count = len(extract_java_classes(path, text)) + len(extract_java_methods(path, text)) + len(extract_java_fields(path, text))
    except Exception:
        java_count = 0
    claim_text = f"File {path} exposes observable identifiers: {', '.join(keywords[:8]) or 'no extracted identifiers'}."
    claim = Claim(
        id=stable_file_claim_id(path),
        claim=claim_text,
        kind="structure",
        scope="file",
        bindings=[Binding(path=path, file_blob=blob, fn_hash=None, commit=head)],
        provenance="git",
        evidence="observed",
        confidence=0.35,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        body={
            "summary": f"v1 observed {line_count} lines, {len(keywords)} unique code-like identifiers, {len(functions)} Python functions, and {java_count} Java syntactic nodes; exact behavior lives in source anchors.",
            "keywords": keywords,
            "function_nodes": [fn.qualname for fn in functions],
            "java_nodes": java_count,
            "anchors": [{"path": path, "line_start": 1, "line_end": max(1, min(line_count, 40))}],
            "notes": ["File-level heuristic; use source as ground truth for precise behavior."],
        },
    )
    return verify_observed_claim(claim, text)


def derive_function_claim(repo: GitRepo, fn: FunctionNode, graph: dict | None = None) -> Claim:
    text = repo.read_file(fn.path)
    blob = repo.blob_sha(fn.path)
    head = repo.head()
    graph = graph or {}
    claim_text = f"Function {fn.qualname} in {fn.path} is a Python function node bound by worktree file_blob and token-stream fn_hash."
    claim = Claim(
        id=stable_function_claim_id(fn.path, fn.qualname),
        claim=claim_text,
        kind="structure",
        scope="function",
        bindings=[Binding(path=fn.path, file_blob=blob, fn_hash=fn.fn_hash, commit=head, qualname=fn.qualname)],
        provenance="git",
        evidence="observed",
        confidence=0.4,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        body={
            "summary": f"v1 observed Python function {fn.qualname}; exact behavior lives in source anchors.",
            "keywords": fn.keywords,
            "qualname": fn.qualname,
            "anchors": [{"path": fn.path, "line_start": fn.line_start, "line_end": fn.line_end}],
            "graph": graph,
            "notes": ["fn_hash is computed from Python tokenize token stream over the current working-tree function span; comments/trivia ignored, literals/identifiers preserved."],
        },
    )
    return verify_observed_claim(claim, text)


def derive_class_claim(repo: GitRepo, cls: ClassNode) -> Claim:
    text = repo.read_file(cls.path)
    blob = repo.blob_sha(cls.path)
    head = repo.head()
    claim = Claim(
        id=stable_class_claim_id(cls.path, cls.qualname),
        claim=f"Class {cls.qualname} in {cls.path} is a Python class node bound by worktree file_blob and token-stream class_hash.",
        kind="structure",
        scope="class",
        bindings=[Binding(path=cls.path, file_blob=blob, fn_hash=cls.class_hash, commit=head, qualname=cls.qualname)],
        provenance="git",
        evidence="observed",
        confidence=0.4,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        body={
            "summary": f"v2 observed Python class {cls.qualname}; class span includes method bodies, so method edits intentionally stale the class node.",
            "keywords": cls.keywords,
            "qualname": cls.qualname,
            "anchors": [{"path": cls.path, "line_start": cls.line_start, "line_end": cls.line_end}],
            "notes": ["class_hash uses the same token-stream span hash rules as functions; comments/trivia ignored, literals/identifiers preserved.", "Class span includes methods by design, causing safe over-invalidation when method bodies change."],
        },
    )
    return verify_observed_claim(claim, text)


def derive_declaration_claim(repo: GitRepo, decl: DeclarationNode) -> Claim:
    text = repo.read_file(decl.path)
    blob = repo.blob_sha(decl.path)
    head = repo.head()
    claim = Claim(
        id=stable_declaration_claim_id(decl.path, decl.qualname),
        claim=f"Declaration {decl.qualname} in {decl.path} is a module-level Python {decl.declaration_kind} bound by worktree file_blob and token-stream declaration_hash.",
        kind="structure",
        scope="declaration",
        bindings=[Binding(path=decl.path, file_blob=blob, fn_hash=decl.declaration_hash, commit=head, qualname=decl.qualname)],
        provenance="git",
        evidence="observed",
        confidence=0.35,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        body={
            "summary": f"v2 observed module-level declaration {decl.qualname} ({decl.declaration_kind}); exact value lives in source anchors.",
            "keywords": decl.keywords,
            "qualname": decl.qualname,
            "declaration_kind": decl.declaration_kind,
            "anchors": [{"path": decl.path, "line_start": decl.line_start, "line_end": decl.line_end}],
            "notes": ["declaration_hash uses the same token-stream span hash rules as functions/classes; only conservative top-level Assign/AnnAssign declarations are extracted."],
        },
    )
    return verify_observed_claim(claim, text)

def derive_java_node_claim(repo: GitRepo, node: ClassNode | DeclarationNode) -> Claim:
    text = repo.read_file(node.path)
    blob = repo.blob_sha(node.path)
    head = repo.head()
    is_decl = isinstance(node, DeclarationNode)
    node_kind = node.declaration_kind if is_decl else node.node_kind
    node_hash = node.declaration_hash if is_decl else node.class_hash
    scope = "declaration" if is_decl else "class"
    claim = Claim(
        id=stable_java_node_claim_id(node.path, node.qualname, node_kind),
        claim=f"Java {node_kind} {node.qualname} in {node.path} is a tree-sitter syntactic node bound by worktree file_blob and token-stream hash.",
        kind="structure",
        scope=scope,
        bindings=[Binding(path=node.path, file_blob=blob, fn_hash=node_hash, commit=head, qualname=node.qualname)],
        provenance="git",
        evidence="observed",
        confidence=0.35,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        body={
            "summary": f"Observed Java {node_kind} {node.qualname} syntactically; Java inheritance edges may be derived conservatively when extends/implements targets resolve without ambiguity.",
            "keywords": node.keywords,
            "qualname": node.qualname,
            "language": "java",
            "node_kind": node_kind,
            "extraction_tier": "java-treesitter-syntactic",
            "semantic_backend": {"available": False, "mode": "stub", "degrade": "semantic read-through/background interface reserved; SCIP/LSP not implemented in step0"},
            "anchors": [{"path": node.path, "line_start": node.line_start, "line_end": node.line_end, "qualname": node.qualname}],
            "notes": ["Java hash is computed from tree-sitter leaf token type+text; comments/whitespace dropped, punctuation/keywords/identifiers/literals/modifiers/annotations included.", "Java inheritance edges are syntactic-only and conservative: unresolved external/JDK, wildcard, or ambiguous supertypes are reported without linking."],
        },
    )
    return verify_observed_claim(claim, text)



def derive_config_claim(repo: GitRepo, node: ConfigNode) -> Claim:
    text = repo.read_file(node.path)
    blob = repo.blob_sha(node.path)
    head = repo.head()
    claim = Claim(
        id=stable_config_claim_id(node.path, node.key),
        claim=f"Config key {node.key} in {node.path} is a top-level {node.config_kind} key bound by normalized value hash.",
        kind="structure",
        scope="config",
        bindings=[Binding(path=node.path, file_blob=blob, fn_hash=node.config_hash, commit=head, qualname=node.key)],
        provenance="git",
        evidence="observed",
        confidence=0.35,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        body={
            "summary": f"v2 observed top-level {node.config_kind} config key {node.key}; exact value lives in source fallback.",
            "keywords": node.keywords,
            "qualname": node.key,
            "config_kind": node.config_kind,
            "anchors": [{"path": node.path, "line_start": 1, "line_end": 1}],
            "notes": ["config_hash is computed from canonical parsed top-level key value; whitespace and object key order are ignored, value changes stale the node."],
        },
    )
    return verify_observed_claim(claim, text)



def derive_api_claim(repo: GitRepo, api: ApiNode) -> Claim:
    text = repo.read_file(api.path)
    blob = repo.blob_sha(api.path)
    head = repo.head()
    claim = Claim(
        id=stable_api_claim_id(api.path, api.method, api.route_path, api.handler_qualname),
        claim=f"API route {api.method} {api.route_path} in {api.path} is handled by {api.handler_qualname}.",
        kind="structure",
        scope="api",
        bindings=[Binding(path=api.path, file_blob=blob, fn_hash=api.api_hash, commit=head, qualname=api.handler_qualname)],
        provenance="git",
        evidence="observed",
        confidence=0.45,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        body={
            "summary": f"v2 observed API route {api.method} {api.route_path} handled by {api.handler_qualname}.",
            "keywords": api.keywords,
            "method": api.method,
            "route_path": api.route_path,
            "handler_qualname": api.handler_qualname,
            "qualname": api.handler_qualname,
            "anchors": [{"path": api.path, "line_start": api.line_start, "line_end": api.line_end}],
            "notes": ["api_hash includes recognized route decorators plus handler body using the same token-stream span hash rules as functions."],
        },
    )
    return verify_observed_claim(claim, text)

def derive_call_edge_claim(repo: GitRepo, edge) -> Claim | None:
    if not edge.caller_path or not edge.callee_path or not edge.caller_fn_hash or not edge.callee_fn_hash:
        return None
    caller_blob = repo.blob_sha(edge.caller_path)
    callee_blob = repo.blob_sha(edge.callee_path)
    head = repo.head()
    return Claim(
        id=stable_call_edge_claim_id(edge.caller_id, edge.callee_id),
        claim=f"{edge.caller_id} calls {edge.callee_qualname}.",
        kind="structure",
        scope="cross-repo",
        bindings=[
            Binding(path=edge.caller_path, file_blob=caller_blob, fn_hash=edge.caller_fn_hash, commit=head, qualname=edge.caller_qualname),
            Binding(path=edge.callee_path, file_blob=callee_blob, fn_hash=edge.callee_fn_hash, commit=head, qualname=edge.callee_qualname),
        ],
        provenance="git",
        evidence="observed",
        confidence=0.55,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        body={
            "edge_kind": "calls",
            "caller_id": edge.caller_id,
            "callee_id": edge.callee_id,
            "caller_path": edge.caller_path,
            "callee_path": edge.callee_path,
            "callee_qualname": edge.callee_qualname,
            "resolution": edge.resolution,
            "caller_anchor": _function_anchor_for(repo, edge.caller_path, edge.caller_qualname),
            "callee_anchor": _function_anchor_for(repo, edge.callee_path, edge.callee_qualname),
            "anchors": [],
            "notes": ["Call edge is observed only when statically resolved without ambiguity; source remains authority."],
        },
    )


def derive_read_edge_claim(repo: GitRepo, edge) -> Claim | None:
    if not edge.reader_path or not edge.declaration_path or not edge.reader_fn_hash or not edge.declaration_hash:
        return None
    reader_blob = repo.blob_sha(edge.reader_path)
    declaration_blob = repo.blob_sha(edge.declaration_path)
    head = repo.head()
    return Claim(
        id=stable_read_edge_claim_id(edge.reader_id, edge.declaration_id),
        claim=f"{edge.reader_id} reads declaration {edge.declaration_qualname}.",
        kind="structure",
        scope="cross-repo",
        bindings=[
            Binding(path=edge.reader_path, file_blob=reader_blob, fn_hash=edge.reader_fn_hash, commit=head, qualname=edge.reader_qualname),
            Binding(path=edge.declaration_path, file_blob=declaration_blob, fn_hash=edge.declaration_hash, commit=head, qualname=edge.declaration_qualname),
        ],
        provenance="git",
        evidence="observed",
        confidence=0.55,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        body={
            "edge_kind": "reads",
            "reader_id": edge.reader_id,
            "declaration_id": edge.declaration_id,
            "reader_path": edge.reader_path,
            "declaration_path": edge.declaration_path,
            "declaration_qualname": edge.declaration_qualname,
            "resolution": edge.resolution,
            "coverage": "partial",
            "reader_anchor": _function_anchor_for(repo, edge.reader_path, edge.reader_qualname),
            "declaration_anchor": _declaration_anchor_for(repo, edge.declaration_path, edge.declaration_qualname),
            "anchors": [],
            "notes": ["Read edge is observed only for unambiguous Python Name loads of tracked module-level declarations; source remains authority.", "Coverage is partial: only already-derived files and conservative static reads are included."],
        },
    )



def derive_write_edge_claim(repo: GitRepo, edge) -> Claim | None:
    if not edge.writer_path or not edge.declaration_path or not edge.writer_fn_hash or not edge.declaration_hash:
        return None
    writer_blob = repo.blob_sha(edge.writer_path)
    declaration_blob = repo.blob_sha(edge.declaration_path)
    head = repo.head()
    return Claim(
        id=stable_write_edge_claim_id(edge.writer_id, edge.declaration_id),
        claim=f"{edge.writer_id} writes declaration {edge.declaration_qualname}.",
        kind="structure",
        scope="cross-repo",
        bindings=[
            Binding(path=edge.writer_path, file_blob=writer_blob, fn_hash=edge.writer_fn_hash, commit=head, qualname=edge.writer_qualname),
            Binding(path=edge.declaration_path, file_blob=declaration_blob, fn_hash=edge.declaration_hash, commit=head, qualname=edge.declaration_qualname),
        ],
        provenance="git",
        evidence="observed",
        confidence=0.55,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        body={
            "edge_kind": "writes",
            "writer_id": edge.writer_id,
            "declaration_id": edge.declaration_id,
            "writer_path": edge.writer_path,
            "declaration_path": edge.declaration_path,
            "declaration_qualname": edge.declaration_qualname,
            "resolution": edge.resolution,
            "coverage": "partial",
            "writer_anchor": _function_anchor_for(repo, edge.writer_path, edge.writer_qualname),
            "declaration_anchor": _declaration_anchor_for(repo, edge.declaration_path, edge.declaration_qualname),
            "anchors": [],
            "notes": ["Write edge is observed only for Python global declarations or other unambiguous writes to tracked module-level declarations; source remains authority.", "Coverage is partial: only already-derived files and conservative static writes are included."],
        },
    )


def _java_node_anchor_for(repo: GitRepo, path: str | None, qualname: str | None, node_kind: str | None) -> dict:
    if not path or not qualname or not node_kind:
        return _anchor(path, None, None, qualname)
    try:
        source = repo.read_file(path)
        for node in extract_java_classes(path, source):
            if node.qualname == qualname and node.node_kind == node_kind:
                return _anchor(path, node.line_start, node.line_end, qualname)
    except Exception:
        pass
    return _anchor(path, None, None, qualname)


def derive_inherit_edge_claim(repo: GitRepo, edge) -> Claim | None:
    if not edge.child_path or not edge.parent_path or not edge.child_hash or not edge.parent_hash:
        return None
    child_blob = repo.blob_sha(edge.child_path)
    parent_blob = repo.blob_sha(edge.parent_path)
    head = repo.head()
    return Claim(
        id=stable_inherit_edge_claim_id(edge.child_id, edge.parent_id, edge.relation),
        claim=f"{edge.child_id} {edge.relation} {edge.parent_qualname}.",
        kind="structure",
        scope="cross-repo",
        bindings=[
            Binding(path=edge.child_path, file_blob=child_blob, fn_hash=edge.child_hash, commit=head, qualname=edge.child_qualname),
            Binding(path=edge.parent_path, file_blob=parent_blob, fn_hash=edge.parent_hash, commit=head, qualname=edge.parent_qualname),
        ],
        provenance="git",
        evidence="observed",
        confidence=0.55,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        body={
            "edge_kind": "inherits",
            "relation": edge.relation,
            "child_id": edge.child_id,
            "parent_id": edge.parent_id,
            "child_path": edge.child_path,
            "parent_path": edge.parent_path,
            "child_qualname": edge.child_qualname,
            "parent_qualname": edge.parent_qualname,
            "child_node_kind": edge.child_node_kind,
            "parent_node_kind": edge.parent_node_kind,
            "resolution": edge.resolution,
            "coverage": "partial",
            "child_anchor": _java_node_anchor_for(repo, edge.child_path, edge.child_qualname, edge.child_node_kind),
            "parent_anchor": _java_node_anchor_for(repo, edge.parent_path, edge.parent_qualname, edge.parent_node_kind),
            "anchors": [],
            "notes": ["Java inheritance edge is observed only for syntactic extends/implements targets resolved by same-file uniqueness or explicit import; unresolved supertypes are not linked.", "Coverage is partial and syntactic; semantic resolution is deferred to SCIP/LSP step."],
        },
    )

def derive_claims_for_path(repo: GitRepo, path: str, *, use_model: bool = False, model: DeriverModel | None = None, semantic_backend: SemanticExtractorBackend | None = None) -> list[Claim]:
    text = repo.read_file(path)
    functions = extract_functions(path, text)
    classes = extract_classes(path, text)
    declarations = extract_declarations(path, text)
    configs = extract_configs(path, text)
    apis = extract_apis(path, text)
    java_classes: list[ClassNode] = []
    java_methods: list[ClassNode] = []
    java_fields: list[DeclarationNode] = []
    java_degrade_hint: str | None = None
    if path.endswith(".java"):
        status = java_status()
        if status.available:
            java_classes = extract_java_classes(path, text)
            java_methods = extract_java_methods(path, text)
            java_fields = extract_java_fields(path, text)
        else:
            java_degrade_hint = status.degrade_hint or JAVA_DEGRADE_HINT
    claims = [derive_file_claim(repo, path)]
    if semantic_backend is not None:
        if semantic_backend.available():
            semantic_backend.enqueue_background_refresh(str(repo.root), path)
            claims[0].body["semantic_extraction"] = {"available": True, "degraded": True, "queued_background_refresh": True, "extraction_tier": "semantic-resolved"}
        else:
            claims[0].body["semantic_extraction"] = {"available": False, "degraded": True, "queued_background_refresh": False, "extraction_tier": "semantic-resolved"}
    if java_degrade_hint:
        claims[0].body["java_extraction"] = {"available": False, "degraded": True, "degrade_hint": java_degrade_hint}
    claims.extend(derive_class_claim(repo, cls) for cls in classes)
    claims.extend(derive_declaration_claim(repo, decl) for decl in declarations)
    claims.extend(derive_config_claim(repo, config) for config in configs)
    claims.extend(derive_api_claim(repo, api) for api in apis)
    claims.extend(derive_java_node_claim(repo, node) for node in [*java_classes, *java_methods, *java_fields])
    edges, unresolved = resolve_call_edges(path, text, functions, repo=repo)
    read_edges, unresolved_reads = resolve_read_edges(path, text, functions, declarations, repo=repo)
    write_edges, unresolved_writes = resolve_write_edges(path, text, functions, declarations, repo=repo)
    inherit_edges, unresolved_inherits = resolve_java_inherit_edges(path, text, java_classes, repo=repo) if java_classes else ([], {})
    callees_by_caller: dict[str, list[dict]] = {}
    callers_by_callee: dict[str, list[dict]] = {}
    fn_anchor_by_id = {stable_function_claim_id(fn.path, fn.qualname): _anchor(fn.path, fn.line_start, fn.line_end, fn.qualname) for fn in functions}
    decl_anchor_by_id = {stable_declaration_claim_id(decl.path, decl.qualname): _anchor(decl.path, decl.line_start, decl.line_end, decl.qualname) for decl in declarations}
    for edge in edges:
        edge_dict = {"target_id": edge.callee_id, "target_qualname": edge.callee_qualname, "target_path": edge.callee_path, "anchor": fn_anchor_by_id.get(edge.callee_id, _anchor(edge.callee_path, None, None, edge.callee_qualname)), "evidence": edge.evidence, "resolution": edge.resolution}
        callees_by_caller.setdefault(edge.caller_id, []).append(edge_dict)
        callers_by_callee.setdefault(edge.callee_id, []).append({"source_id": edge.caller_id, "source_path": edge.caller_path, "anchor": fn_anchor_by_id.get(edge.caller_id, _anchor(edge.caller_path, None, None, edge.caller_qualname)), "evidence": edge.evidence, "resolution": edge.resolution})
    unresolved_by_caller = {caller: [{"expr": item.expr, "reason": item.reason} for item in items] for caller, items in unresolved.items()}
    reads_by_reader: dict[str, list[dict]] = {}
    readers_by_decl: dict[str, list[dict]] = {}
    writes_by_writer: dict[str, list[dict]] = {}
    writers_by_decl: dict[str, list[dict]] = {}
    for edge in read_edges:
        reads_by_reader.setdefault(edge.reader_id, []).append({"target_id": edge.declaration_id, "target_qualname": edge.declaration_qualname, "target_path": edge.declaration_path, "anchor": decl_anchor_by_id.get(edge.declaration_id, _anchor(edge.declaration_path, None, None, edge.declaration_qualname)), "evidence": edge.evidence, "resolution": edge.resolution})
        readers_by_decl.setdefault(edge.declaration_id, []).append({"source_id": edge.reader_id, "source_path": edge.reader_path, "anchor": fn_anchor_by_id.get(edge.reader_id, _anchor(edge.reader_path, None, None, edge.reader_qualname)), "evidence": edge.evidence, "resolution": edge.resolution})
    unresolved_reads_by_reader = {reader: [{"expr": item.expr, "reason": item.reason} for item in items] for reader, items in unresolved_reads.items()}
    for edge in write_edges:
        anchor = decl_anchor_by_id.get(edge.declaration_id, _anchor(edge.declaration_path, None, None, edge.declaration_qualname))
        writes_by_writer.setdefault(edge.writer_id, []).append({"target_id": edge.declaration_id, "target_qualname": edge.declaration_qualname, "target_path": edge.declaration_path, "anchor": anchor, "evidence": edge.evidence, "resolution": edge.resolution})
        writers_by_decl.setdefault(edge.declaration_id, []).append({"source_id": edge.writer_id, "source_path": edge.writer_path, "anchor": fn_anchor_by_id.get(edge.writer_id, _anchor(edge.writer_path, None, None, edge.writer_qualname)), "evidence": edge.evidence, "resolution": edge.resolution})
    unresolved_writes_by_writer = {writer: [{"expr": item.expr, "reason": item.reason} for item in items] for writer, items in unresolved_writes.items()}
    java_anchor_by_id = {stable_java_node_claim_id(node.path, node.qualname, node.node_kind): _anchor(node.path, node.line_start, node.line_end, node.qualname) for node in java_classes if node.node_kind in {"class", "interface"}}
    inherits_by_child: dict[str, list[dict]] = {}
    subtypes_by_parent: dict[str, list[dict]] = {}
    implementors_by_parent: dict[str, list[dict]] = {}
    for edge in inherit_edges:
        target_item = {"target_id": edge.parent_id, "target_qualname": edge.parent_qualname, "target_path": edge.parent_path, "relation": edge.relation, "anchor": java_anchor_by_id.get(edge.parent_id, _anchor(edge.parent_path, None, None, edge.parent_qualname)), "evidence": edge.evidence, "resolution": edge.resolution}
        inherits_by_child.setdefault(edge.child_id, []).append(target_item)
        reverse_item = {"source_id": edge.child_id, "source_path": edge.child_path, "relation": edge.relation, "anchor": java_anchor_by_id.get(edge.child_id, _anchor(edge.child_path, None, None, edge.child_qualname)), "evidence": edge.evidence, "resolution": edge.resolution}
        if edge.relation == "implements":
            implementors_by_parent.setdefault(edge.parent_id, []).append(reverse_item)
        else:
            subtypes_by_parent.setdefault(edge.parent_id, []).append(reverse_item)
    unresolved_inherits_by_child = {child: [{"expr": item.expr, "reason": item.reason, "relation": item.relation} for item in items] for child, items in unresolved_inherits.items()}
    for claim in claims:
        if claim.scope == "declaration":
            graph = claim.body.setdefault("graph", {})
            graph["read_by"] = readers_by_decl.get(claim.id, [])
            graph["read_by_coverage"] = "partial"
            graph["written_by"] = writers_by_decl.get(claim.id, [])
            graph["written_by_coverage"] = "partial"
        if claim.body.get("language") == "java" and claim.body.get("node_kind") in {"class", "interface"}:
            graph = claim.body.setdefault("graph", {})
            graph["inherits"] = inherits_by_child.get(claim.id, [])
            graph["inherits_unresolved"] = unresolved_inherits_by_child.get(claim.id, [])
            graph["inherits_coverage"] = "partial"
            graph["subtypes"] = subtypes_by_parent.get(claim.id, [])
            graph["subtypes_coverage"] = "partial"
            graph["implementors"] = implementors_by_parent.get(claim.id, [])
            graph["implementors_coverage"] = "partial"

    if use_model:
        model_claims = derive_model_function_claims(repo, functions, model=model)
        model_ids = {claim.id for claim in model_claims}
        for claim in model_claims:
            graph = claim.body.setdefault("graph", {})
            graph["callees"] = callees_by_caller.get(claim.id, [])
            graph["callers"] = callers_by_callee.get(claim.id, [])
            graph["unresolved_calls"] = unresolved_by_caller.get(claim.id, [])
            graph["reads"] = reads_by_reader.get(claim.id, [])
            graph["reads_unresolved"] = unresolved_reads_by_reader.get(claim.id, [])
            graph["writes"] = writes_by_writer.get(claim.id, [])
            graph["writes_unresolved"] = unresolved_writes_by_writer.get(claim.id, [])
            claims.append(claim)
        # Fallback to heuristic for functions the model did not cover.
        for fn in functions:
            graph = {
                "callees": callees_by_caller.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "callers": callers_by_callee.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "unresolved_calls": unresolved_by_caller.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "reads": reads_by_reader.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "reads_unresolved": unresolved_reads_by_reader.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "writes": writes_by_writer.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "writes_unresolved": unresolved_writes_by_writer.get(stable_function_claim_id(fn.path, fn.qualname), []),
            }
            claim = derive_function_claim(repo, fn, graph=graph)
            if claim.id not in model_ids:
                claims.append(claim)
    else:
        for fn in functions:
            graph = {
                "callees": callees_by_caller.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "callers": callers_by_callee.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "unresolved_calls": unresolved_by_caller.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "reads": reads_by_reader.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "reads_unresolved": unresolved_reads_by_reader.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "writes": writes_by_writer.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "writes_unresolved": unresolved_writes_by_writer.get(stable_function_claim_id(fn.path, fn.qualname), []),
            }
            claims.append(derive_function_claim(repo, fn, graph=graph))
    edge_claims = [claim for edge in edges if (claim := derive_call_edge_claim(repo, edge)) is not None]
    read_edge_claims = [claim for edge in read_edges if (claim := derive_read_edge_claim(repo, edge)) is not None]
    write_edge_claims = [claim for edge in write_edges if (claim := derive_write_edge_claim(repo, edge)) is not None]
    inherit_edge_claims = [claim for edge in inherit_edges if (claim := derive_inherit_edge_claim(repo, edge)) is not None]
    claims.extend(edge_claims)
    claims.extend(read_edge_claims)
    claims.extend(write_edge_claims)
    claims.extend(inherit_edge_claims)
    return claims
