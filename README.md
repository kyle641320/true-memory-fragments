# True Memory Fragments (TMF)

True Memory Fragments is a lazy, source-bound code memory layer for AI coding agents. It records small, verifiable facts about a repository, keeps those facts bound to the current working tree, and degrades back to source whenever memory is missing, stale, or uncertain.

TMF is designed for agents that need useful memory without trusting memory blindly: source remains authoritative, confidence comes from validation, and every claim has provenance and freshness checks.

## Core premises

- **Self-maintaining memory:** TMF stores derived claims in the repository-local `.tmf/` directory and refreshes them on read-through.
- **Fully lazy read-through:** reads detect missing or stale claims and synchronously re-derive; writes and commits do not run hooks or background work.
- **Freshness is working-tree based:** freshness binds to the current working-tree blob plus node-specific hashes, not to `HEAD` or commit identity.
- **Fresh is not correct:** a fresh claim only means its bindings still match the current source. Correctness is established by validation and source support.
- **Confidence comes from validation, not frequency:** usage/read frequency does not raise confidence. Model self-report is clamped by verification.
- **Conservative parsing:** TMF connects only what it can parse and support. Unknown, dynamic, shadowed, or ambiguous facts are omitted or marked unresolved rather than guessed.
- **Source is authoritative:** if memory is missing, stale, unsupported, or partial, TMF falls back to source.
- **Untrusted text is never instructions:** source, comments, docstrings, commit messages, model output, and future PR text are data, not commands for the agent.

## Install

```bash
pip install -e .
```

Runtime dependencies are intentionally empty: `dependencies = []`. Optional model, embedder, and router integrations are command-backed through `TMF_*` environment variables and are not package dependencies.

## Quick start

Run the commands from the repository root after `pip install -e .`:

```bash
# 1. Warm a repository into .tmf/
tmf warm --repo .

# 2. Retrieve a thin view by source path
tmf retrieve --path tmf/cli.py --repo .

# 3. Retrieve a thin lexical view
tmf retrieve cli --repo . --limit 3

# 4. Pick one claim id for examples below
CLAIM_ID=$(python - <<'PY'
from tmf.store import Store
for claim in Store('.').iter_claims():
    if claim.scope == 'function':
        print(claim.id)
        break
PY
)
echo "$CLAIM_ID"

# 5. Expand one thick/full claim
tmf retrieve --full "$CLAIM_ID" --repo .

# 6. Explain provenance/freshness/trust/action hints
tmf explain "$CLAIM_ID" --repo .
tmf explain "$CLAIM_ID" --repo . --json

# 7. Inspect conservative reverse callers for a function claim
tmf callers "$CLAIM_ID" --repo .

# 8. Reproduce validation evidence
tmf validate --repo .
```

## CLI reference

- `tmf warm --repo <repo>` — derive supported claims into `.tmf/` and build indexes.
- `tmf retrieve --path <file> --repo <repo>` — read through a path and return a thin view plus source fallback paths.
- `tmf retrieve <query> --repo <repo> [--limit N]` — lexical retrieval over derived claims, thin view by default.
- `tmf retrieve --full <claim-id> --repo <repo>` — expand one claim into a thick/full view with body and full explain data.
- `tmf explain <claim-id> --repo <repo> [--json]` — explain freshness, trust, provenance refs, anchors, bindings, and action hints.
- `tmf callers <function-claim-id> --repo <repo>` — list conservative reverse caller edges for a function claim.

Python API note: `tmf.retrieve.reverse_readers(repo, declaration_id)` returns partial known readers for declaration-read edges. `tmf.retrieve.reverse_writers(repo, declaration_id)` returns partial known writers for declaration-write edges. Both are intentionally separate from `reverse_callers`. All forward and reverse references surface `{path, line_start, line_end, qualname}` anchors when available.
- `tmf feedback <claim-id> <usage|verified|falsified|hunch> --repo <repo> [--note ...]` — record feedback without turning hunches into facts.
- `tmf validate --repo <repo> [--heldout|--self]` — run held-out fixture validation and/or self-dogfood validation reports.

## Supported node types

TMF 0.1.0 supports a conservative subset:

- **Python functions** — function claims bind to token-stream hashes. Comments and outer-scope boundary indentation are normalized; semantic tokens remain value-sensitive.
- **Python declaration-read edges** — partial support for unambiguous `function -> module-level declaration` reads, using `body.edge_kind="reads"`. Same-file declarations and direct `from module import NAME` declarations are supported only when the name is not locally bound or shadowed. Reverse `read_by` coverage is partial.
- **Python global write edges** — partial support for `function -> module-level declaration` writes, using `body.edge_kind="writes"`. A same-file assignment/annotated assignment/augmented assignment/delete to `X` is linked only when the function declares `global X`; assignment without `global` is local and never linked. Reverse `written_by` coverage is partial.
- **Python classes** — class claims are source-bound and participate in freshness sampling. Nested methods are measured with containment-aware validation.
- **Module-level declarations** — partial support for top-level uppercase constants and simple top-level dict declarations.
- **JSON/TOML config** — partial support for top-level keys only. Config anchors are file-level; nested config structure is not expanded. Malformed config degrades to source without config nodes.
- **API route contracts** — partial AST-only support for literal Flask `@app.route("/x", methods=[...])` and FastAPI-style `@router.get/post/put/delete/patch("/x")`. Dynamic paths, unknown decorators, re-exports, and framework-specific behavior are skipped.

Edges are also conservative: TMF records observed calls for module-local `Name()`, same-class `self.method()`, and direct repo-local imports such as `from x import f` or `import x as y; y.f()`. Unknown, dynamic, external, star-import, or re-export calls are unresolved, not guessed.

## Optional inference boundary (`tmf_assist`)

The read-only MCP server exposes `tmf_assist` as an **explicit opt-in** tool. It builds a bounded deterministic `tmf_context` bundle and asks a configured provider for structured hypotheses. `tmf_context` itself never invokes a model.

Assist output is always wrapped by the server as `non_authoritative=true`, `trust.level=inferred`, and `trust.status=provisional` (or `expired` when supporting claims are stale). Provider output cannot set or upgrade trust. The existing numeric `confidence` field is reused; medium-confidence judgments remain usable provisional results, while `unresolved` is reserved for cases where the model cannot form a useful judgment. Nothing is persisted or promoted into TMF claims.

The provider is disabled by default. Configure exactly one shell-free argv command with `TMF_ASSIST_COMMAND_JSON`, for example:

```sh
export TMF_ASSIST_COMMAND_JSON='["python3","/path/to/provider.py"]'
```

The command reads one JSON request from stdin and writes one JSON object to stdout. `TMF_ASSIST_TIMEOUT_SECONDS` sets the timeout (0.1–120 seconds). The former free-form `TMF_ASSIST_COMMAND` setting is intentionally unsupported; migrate it to a JSON string array. No API key, vendor SDK, or hosted provider is built in.

For OpenClaw-managed credentials, use the bundled adapter as the command:

```bash
export TMF_ASSIST_COMMAND_JSON='["python3","-m","tmf.assist_openclaw"]'
export TMF_ASSIST_OPENCLAW_MODEL='aisz/gpt-5.5'
```

The adapter calls `openclaw infer model run --json` with a shell-free argv list,
so OpenClaw keeps provider credentials and TMF only translates the request and
validates the provider JSON.

Input requires a 1–2000 character `question` and may select evidence with `claim_id`, repository-contained `path`, or `qualname`. Caller-supplied context bundles are not accepted, so only TMF-derived claims establish allowed anchors, trust, and freshness. `max_context_chars` (500–12000) hard-limits the complete serialized provider request, including policy, question, addressing, selected claim, and evidence. Requests that cannot fit are rejected deterministically.

Provider response fields are exactly `answer`, `inferences`, finite `confidence`, `evidence`, `assumptions`, `unresolved`, and `suggested_source_reads`. Evidence and suggested reads must use valid line ranges fully contained in supplied TMF anchors. Invalid JSON/constants, schema violations, trust-field injection, citations outside anchors, timeouts, provider exits, and absent configuration return distinct degraded errors; none masquerade as `unresolved`. Source changes expire the inference through supporting claims' existing freshness bindings.

The fixed policy treats the question, source, comments, docstrings, and evidence as untrusted data. Provider prose remains an explicitly unverified inference payload; source is authoritative.

## Honest limitations

- Only Python source is parsed for code nodes and call edges.
- Config support is JSON/TOML only and top-level-key only.
- Declaration-read/write edges are Python-only and declaration-node-only. Write edges currently require explicit Python `global X` for same-file declaration assignment/delete. They do not read config file keys, environment variables, framework getters, dependency injection, annotations, YAML, SQL, or non-Python sources.
- Config anchors are file-level, not exact nested-value spans.
- API route extraction is a partial, literal-decorator subset; dynamic routing is unsupported.
- Intent/why claims are attributed when provenance exists, but **never verified** as facts.
- There is no built-in embedder, LLM, PR fetcher, or hosted service. Optional integrations are external commands via `TMF_*` environment variables.
- Conservative parsing means recall is intentionally incomplete: TMF would rather miss an edge than connect a wrong edge.
- YAML and SQL are not supported in 0.1.0.
- `.tmf/` is local JSON storage, not a database server or synchronization protocol.

## Validation and evidence

TMF’s trust claim is reproducible validation, not assertion.

Two validation layers are included:

1. **Held-out validation bench** — temporary fixture repositories test invariants, freshness precision/recall, source support, degrade-to-source behavior, thin/full consistency, router/embedder additivity, config nodes, API nodes, and reverse callers.
2. **Self-dogfood validation** — TMF warms a copy of this real package and samples freshness behavior on its own claims. This is how prior over-invalidation defects were exposed and fixed.

In this project, **precision** means: when TMF marks a claim stale, it should truly be affected by the source perturbation. **Recall** means: claims expected to become stale should be marked stale. Both are scoped to the validation scenarios, not to every possible Python program.

Current 0.1.0 release-wrapup evidence:

```text
python3 -m unittest discover -s tests -q
# Ran 82 tests ... OK

tmf validate --repo . --heldout
# heldout_status: pass
# heldout_precision: 1.0
# heldout_recall: 1.0

tmf validate --repo . --self
# self_status: pass
# self_precision: 1.0
# self_recall: 1.0
# self_fp: 0
# self_fn: 0
```

Reproduce locally with:

```bash
python3 -m unittest discover -s tests -q
tmf validate --repo . --heldout
tmf validate --repo . --self
```

## Store and ignore files

- Store directory: `.tmf/`
- Ignore file: `.tmfignore`

Both names are part of the 0.1.0 public surface.
