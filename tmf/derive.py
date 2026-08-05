from __future__ import annotations

import re

from .edges import resolve_call_edges, resolve_read_edges, resolve_write_edges
from .extract import ApiNode, ClassNode, ConfigNode, DeclarationNode, FunctionNode, ModuleTopLevelNode, _TokenCache, extract_apis, extract_classes, extract_configs, extract_declarations, extract_functions, extract_module_top_levels
from .llm import DeriverModel
from .model_derive import derive_model_function_claims
from .git import GitRepo
from .ids import now_utc, stable_api_claim_id, stable_call_edge_claim_id, stable_class_claim_id, stable_config_claim_id, stable_declaration_claim_id, stable_file_claim_id, stable_function_claim_id, stable_module_top_level_claim_id, stable_read_edge_claim_id, stable_write_edge_claim_id
from .schema import Binding, Claim, ModuleTopLevelContract, SourceAnchor
from .verify import verify_observed_claim

MODEL = "tmf-v1-heuristic"


def _anchor(path: str, line_start: int | None, line_end: int | None, qualname: str | None) -> dict:
    return {"path": path, "line_start": line_start, "line_end": line_end, "qualname": qualname}


def _function_anchor_for(repo: GitRepo, path: str | None, qualname: str | None,
                         fn_map: dict[str, tuple[int, int]] | None = None,
                         fn_maps_by_path: dict[str, dict[str, tuple[int, int]]] | None = None) -> dict:
    if not path or not qualname:
        return _anchor(path, None, None, qualname)
    if fn_map and qualname in fn_map:
        ls, le = fn_map[qualname]
        return _anchor(path, ls, le, qualname)
    if fn_maps_by_path is not None:
        path_map = fn_maps_by_path.get(path)
        if path_map is None:
            try:
                source = repo.read_file(path)
                cache = _TokenCache(source) if path.endswith(".py") else None
                path_map = {fn.qualname: (fn.line_start, fn.line_end) for fn in extract_functions(path, source, cache=cache)}
            except Exception:
                path_map = {}
            fn_maps_by_path[path] = path_map
        if qualname in path_map:
            ls, le = path_map[qualname]
            return _anchor(path, ls, le, qualname)
    try:
        source = repo.read_file(path)
        for fn in extract_functions(path, source):
            if fn.qualname == qualname:
                return _anchor(path, fn.line_start, fn.line_end, qualname)
    except Exception:
        pass
    return _anchor(path, None, None, qualname)


def _declaration_anchor_for(repo: GitRepo, path: str | None, qualname: str | None,
                            decl_map: dict[str, tuple[int, int]] | None = None) -> dict:
    if not path or not qualname:
        return _anchor(path, None, None, qualname)
    if decl_map and qualname in decl_map:
        ls, le = decl_map[qualname]
        return _anchor(path, ls, le, qualname)
    try:
        source = repo.read_file(path)
        for decl in extract_declarations(path, source):
            if decl.qualname == qualname:
                return _anchor(path, decl.line_start, decl.line_end, qualname)
    except Exception:
        pass
    return _anchor(path, None, None, qualname)


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


def derive_file_claim(repo: GitRepo, path: str, *, text: str | None = None, blob: str | None = None, head: str | None = None, functions: list[FunctionNode] | None = None, cache: _TokenCache | None = None) -> Claim:
    text = text if text is not None else repo.read_file(path)
    blob = blob if blob is not None else repo.blob_sha(path)
    head = head if head is not None else repo.head()
    keywords = _keywords(text)
    line_count = len(text.splitlines())
    if functions is None:
        functions = extract_functions(path, text, cache=cache)
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
            "summary": f"v1 observed {line_count} lines, {len(keywords)} unique code-like identifiers, and {len(functions)} Python functions; exact behavior lives in source anchors.",
            "keywords": keywords,
            "function_nodes": [fn.qualname for fn in functions],
            "anchors": [{"path": path, "line_start": 1, "line_end": max(1, min(line_count, 40))}],
            "notes": ["File-level heuristic; use source as ground truth for precise behavior."],
        },
    )
    return verify_observed_claim(claim, text)


def derive_function_claim(repo: GitRepo, fn: FunctionNode, graph: dict | None = None, *, text: str | None = None, blob: str | None = None, head: str | None = None) -> Claim:
    text = text if text is not None else repo.read_file(fn.path)
    blob = blob if blob is not None else repo.blob_sha(fn.path)
    head = head if head is not None else repo.head()
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


def derive_class_claim(repo: GitRepo, cls: ClassNode, *, text: str | None = None, blob: str | None = None, head: str | None = None) -> Claim:
    text = text if text is not None else repo.read_file(cls.path)
    blob = blob if blob is not None else repo.blob_sha(cls.path)
    head = head if head is not None else repo.head()
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


def derive_declaration_claim(repo: GitRepo, decl: DeclarationNode, *, text: str | None = None, blob: str | None = None, head: str | None = None) -> Claim:
    text = text if text is not None else repo.read_file(decl.path)
    blob = blob if blob is not None else repo.blob_sha(decl.path)
    head = head if head is not None else repo.head()
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



def derive_config_claim(repo: GitRepo, node: ConfigNode, *, text: str | None = None, blob: str | None = None, head: str | None = None) -> Claim:
    text = text if text is not None else repo.read_file(node.path)
    blob = blob if blob is not None else repo.blob_sha(node.path)
    head = head if head is not None else repo.head()
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



def derive_api_claim(repo: GitRepo, api: ApiNode, *, text: str | None = None, blob: str | None = None, head: str | None = None) -> Claim:
    text = text if text is not None else repo.read_file(api.path)
    blob = blob if blob is not None else repo.blob_sha(api.path)
    head = head if head is not None else repo.head()
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


def derive_module_top_level_claim(repo: GitRepo, node: ModuleTopLevelNode, *, text: str | None = None, blob: str | None = None, head: str | None = None) -> Claim:
    text = text if text is not None else repo.read_file(node.path)
    blob = blob if blob is not None else repo.blob_sha(node.path)
    head = head if head is not None else repo.head()
    claim = Claim(
        id=stable_module_top_level_claim_id(node.path, node.region_id),
        claim=f"Module top-level executable region {node.region_id} in {node.path} is bound by token-stream top_level_hash.",
        kind="structure",
        scope="module_top_level",
        bindings=[Binding(path=node.path, file_blob=blob, fn_hash=node.top_level_hash, commit=head, qualname=node.region_id)],
        provenance="git",
        evidence="observed",
        confidence=0.35,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        module_top_level_contract=ModuleTopLevelContract(
            region_id=node.region_id,
            anchor=SourceAnchor(start=node.line_start, end=node.line_end),
        ),
        body={
            "summary": f"v2 observed module top-level executable region {node.region_id}; exact behavior lives in source anchors.",
            "keywords": node.keywords,
            "region_id": node.region_id,
            "anchors": [{"path": node.path, "line_start": node.line_start, "line_end": node.line_end}],
            "notes": ["Top-level executable regions exclude def/class bodies and module docstring-only trivia; comments/blank lines are ignored by token hashing, while import changes are behavior-bearing and intentionally stale the region."],
        },
    )
    return verify_observed_claim(claim, text)

def derive_call_edge_claim(repo: GitRepo, edge, fn_map: dict[str, tuple[int, int]] | None = None,
                           fn_maps_by_path: dict[str, dict[str, tuple[int, int]]] | None = None) -> Claim | None:
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
            "caller_anchor": _function_anchor_for(repo, edge.caller_path, edge.caller_qualname, fn_map, fn_maps_by_path),
            "callee_anchor": _function_anchor_for(repo, edge.callee_path, edge.callee_qualname, None, fn_maps_by_path),
            "anchors": [],
            "notes": ["Call edge is observed only when statically resolved without ambiguity; source remains authority."],
        },
    )


def derive_read_edge_claim(repo: GitRepo, edge, fn_map: dict[str, tuple[int, int]] | None = None, decl_map: dict[str, tuple[int, int]] | None = None) -> Claim | None:
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
            "reader_anchor": _function_anchor_for(repo, edge.reader_path, edge.reader_qualname, fn_map),
            "declaration_anchor": _declaration_anchor_for(repo, edge.declaration_path, edge.declaration_qualname, decl_map),
            "anchors": [],
            "notes": ["Read edge is observed only for unambiguous Python Name loads of tracked module-level declarations; source remains authority.", "Coverage is partial: only already-derived files and conservative static reads are included."],
        },
    )



def derive_write_edge_claim(repo: GitRepo, edge, fn_map: dict[str, tuple[int, int]] | None = None, decl_map: dict[str, tuple[int, int]] | None = None) -> Claim | None:
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
            "writer_anchor": _function_anchor_for(repo, edge.writer_path, edge.writer_qualname, fn_map),
            "declaration_anchor": _declaration_anchor_for(repo, edge.declaration_path, edge.declaration_qualname, decl_map),
            "anchors": [],
            "notes": ["Write edge is observed only for Python global declarations or other unambiguous writes to tracked module-level declarations; source remains authority.", "Coverage is partial: only already-derived files and conservative static writes are included."],
        },
    )

def derive_claims_for_path(repo: GitRepo, path: str, *, use_model: bool = False, model: DeriverModel | None = None) -> list[Claim]:
    text = repo.read_file(path)
    blob = repo.blob_sha(path)
    head = repo.head()
    cache = _TokenCache(text) if path.endswith(".py") else None
    functions = extract_functions(path, text, cache=cache)
    classes = extract_classes(path, text, cache=cache)
    declarations = extract_declarations(path, text, cache=cache)
    configs = extract_configs(path, text)
    apis = extract_apis(path, text, cache=cache)
    module_top_levels = extract_module_top_levels(path, text, cache=cache)
    # Build anchor lookup maps from already-extracted data to avoid re-parsing.
    fn_map: dict[str, tuple[int, int]] = {fn.qualname: (fn.line_start, fn.line_end) for fn in functions}
    decl_map: dict[str, tuple[int, int]] = {d.qualname: (d.line_start, d.line_end) for d in declarations}
    claims = [derive_file_claim(repo, path, text=text, blob=blob, head=head, functions=functions, cache=cache)]
    claims.extend(derive_class_claim(repo, cls, text=text, blob=blob, head=head) for cls in classes)
    claims.extend(derive_declaration_claim(repo, decl, text=text, blob=blob, head=head) for decl in declarations)
    claims.extend(derive_config_claim(repo, config, text=text, blob=blob, head=head) for config in configs)
    claims.extend(derive_api_claim(repo, api, text=text, blob=blob, head=head) for api in apis)
    claims.extend(derive_module_top_level_claim(repo, node, text=text, blob=blob, head=head) for node in module_top_levels)
    edges, unresolved = resolve_call_edges(path, text, functions, repo=repo)
    read_edges, unresolved_reads = resolve_read_edges(path, text, functions, declarations, repo=repo)
    write_edges, unresolved_writes = resolve_write_edges(path, text, functions, declarations, repo=repo)
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
    for claim in claims:
        if claim.scope == "declaration":
            graph = claim.body.setdefault("graph", {})
            graph["read_by"] = readers_by_decl.get(claim.id, [])
            graph["read_by_coverage"] = "partial"
            graph["written_by"] = writers_by_decl.get(claim.id, [])
            graph["written_by_coverage"] = "partial"

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
    fn_maps_by_path = {path: fn_map}
    edge_claims = [claim for edge in edges if (claim := derive_call_edge_claim(repo, edge, fn_map, fn_maps_by_path)) is not None]
    read_edge_claims = [claim for edge in read_edges if (claim := derive_read_edge_claim(repo, edge, fn_map, decl_map)) is not None]
    write_edge_claims = [claim for edge in write_edges if (claim := derive_write_edge_claim(repo, edge, fn_map, decl_map)) is not None]
    claims.extend(edge_claims)
    claims.extend(read_edge_claims)
    claims.extend(write_edge_claims)
    return claims
