# TMF Changes

## Versioned dual-binding API relationships + WebFlux functional routes (2026-08-09)

- Advanced serialization to `tmf.schema.v2`; readers continue to accept v0/v1. Binding roles, anchors, and hash kinds are optional; absent fields retain legacy semantics.
- New `claim_api_rel_*` IDs use route source + verb + URI + resolved handler ID. Existing `claim_api_*` IDs are unchanged and never reinterpreted.
- Dual relationships independently bind/freshen/delete route declarations and handlers.
- Exact-import functional WebFlux supports direct literal routes and flat literal builder chains only; rejected forms produce neither APIs nor runtime calls.

Compatibility: v0/v1 read unchanged; legacy Flask/FastAPI/annotated-Spring IDs and single bindings remain; only new functional relationships use dual bindings/new IDs; no automatic cache rewrite.

## True LLM Agent A/B value-proof measurement (2026-06-10)

### Scope / preregistration
- Measurement-only window after benchmark universe decontamination. No engine behavior, MCP tool semantics, tasks/golden symbols, prompts, metrics, or scoring were tuned after seeing results.
- Arms used the same model, temperature 0, same system prompt template except tool list, same budget, and fresh conversations per task/arm/rep.
- Baseline tools: `list_files`, `grep`, `read_file` over the decontaminated universe only.
- TMF tools: baseline tools plus `tmf_retrieve`, `tmf_explain`, `tmf_callers`, `tmf_readers`, `tmf_writers`, `tmf_subtypes`, `tmf_warm`, `tmf_status` via in-process `McpService`.
- Budget: `max_tool_calls=12`, `max_model_turns=15`, `timeout=120s`, `reps=3`, tasks=18, total episodes=108.
- Golden symbols were never inserted into agent prompts; mechanical scoring only.
- Primary metric: `surfaced recall@budget`, where a golden `(path, qualname)` is counted only if a single tool-returned text contains both path and qualname. Secondary: final-answer `answer_anchored` path+qualname co-occurrence.

### Environment
- Model: `qwen3.5-plus` via `https://api.lingyaai.cn/v1` with API key from environment.
- Universe: `50` files, manifest sha256 `ddb1fb3e25ab327076a744600aac5d44ac025e405a75c4ab7b9b165ebe87d54b`.
- Output: `bench/agent_ab/llm_run_20260610T1355/report_llm.json`, `report_llm.md`.
- Raw traces: `traces/agent_ab_llm_20260610T1355/*.jsonl`.

### Validity threats / disclosure
- Implementer pollution is real: the implementing assistant/model family has prior context on this repository. This can compress differences between arms by helping baseline navigate without graph tools; therefore TMF wins would be conservative, but ties/losses are inconclusive rather than proof TMF has no value.
- Agent-as-athlete risk was handled by preregistering prompt, budget, metrics, and scorer before the completed run; no post-hoc prompt/task/metric tuning was performed.
- Scoring is mechanical string/anchor matching, no LLM judge.

### Operational notes
- Initial run attempts exposed adapter bugs before completion: wrong in-process MCP class/method names (`MCPServer`/`tool_reverse`) and were fixed before successful completion. These were interface-adapter bugs, not prompt/metric/task tuning.
- The long run experienced repeated process/session exits; rows/traces were preserved and resumed by skipping completed `(task, arm, rep)` keys. One episode contains a real provider `502 Bad Gateway`; it is kept as a failure row, not retried.
- All 108 episodes completed in the final accumulated run. Failures are budget/API failures inside completed rows, not missing episodes.

### Raw category results
```text
adversarial:
- baseline: surfaced=0.778±0.299; answer=0.083±0.186; tokens=95538.1±32511.7; tool_calls=11.11±2.00; calls_to_full_surfaced=6.36±2.10; failures=15
- tmf: surfaced=0.833±0.236; answer=0.083±0.186; tokens=103062.2±21620.2; tool_calls=11.61±1.11; calls_to_full_surfaced=6.17±2.54; failures=15
graph-shaped:
- baseline: surfaced=0.833±0.236; answer=0.583±0.382; tokens=53386.9±36123.6; tool_calls=8.00±2.56; calls_to_full_surfaced=4.67±2.49; failures=4
- tmf: surfaced=0.833±0.236; answer=0.639±0.365; tokens=60295.7±41707.7; tool_calls=8.11±2.75; calls_to_full_surfaced=5.00±2.94; failures=3
open:
- baseline: surfaced=0.861±0.224; answer=0.750±0.344; tokens=34226.9±28847.5; tool_calls=5.94±2.95; calls_to_full_surfaced=3.46±1.55; failures=2
- tmf: surfaced=0.833±0.236; answer=0.833±0.236; tokens=18866.9±9056.7; tool_calls=4.83±1.86; calls_to_full_surfaced=2.17±1.46; failures=0
```

Failure count: `39` rows.
Failure types:
```text
- max_tool_calls_exceeded: 38
- LLM HTTP 502: <html>
<head><title>502 Bad Gateway</title></head>
<body>
<center><h1>502 Bad Gateway</h1></center>
<hr><center>openresty</center>
</body>
</html>
: 1
```

### Main finding
- TMF did not dominate uniformly under this true-LLM agent setup.
- surfaced recall: TMF slightly higher on adversarial (`0.833` vs `0.778`), tied on graph-shaped (`0.833` vs `0.833`), lower on open (`0.833` vs `0.861`).
- Cost: TMF used fewer tokens and fewer calls on open tasks, but more tokens/calls on adversarial and slightly more on graph-shaped.
- Given implementer pollution and high budget-truncation rate, this is a mixed/inconclusive value proof, not a clean TMF win. The honest conclusion is: TMF shows some adversarial/open-answer anchoring benefit, but this task set/model/budget does not prove broad retrieval superiority.

### Reproduction commands
```bash
PYTHONPATH=. python3 bench/agent_ab/llm_adapter.py \
  --repo . \
  --tasks bench/agent_ab/tasks.jsonl \
  --out bench/agent_ab/llm_run_20260610T1355 \
  --traces traces/agent_ab_llm_20260610T1355 \
  --reps 3 \
  --max-tool-calls 12 \
  --max-model-turns 15 \
  --timeout 120
```

## Benchmark universe decontamination fix (2026-06-10)

### Scope
- Measurement-side repair only for the `bench/agent_ab` scripted proxy benchmark.
- No engine behavior, task questions, golden symbols, or strategy expansion logic was changed.
- Fixes review finding: the previous baseline enumerated `rglob("*")` over `.py/.java/.md/.toml`, allowing released documentation and reports such as `CHANGES.md` / `reports/` to contain golden names and drift benchmark results.

### Fix
- `bench/agent_ab/runner.py` now builds a fixed universe from `git ls-files` only.
- The universe is restricted to tracked source/config files with suffixes `{.py, .java, .toml}`.
- Explicitly excluded: `bench/`, `reports/`, `vendor/`, `scripts/`, dot-directories such as `.git`, `.tmf`, `.ts-venv`, and all Markdown files.
- Both strategies use the same universe for reads/scoring. TMF seeds and graph expansions are filtered to in-universe claim bindings.
- The benchmark store is prepared with generated/store/venv/report directories ignored so warm/read-through does not index benchmark artifacts.
- Reports now include `universe_manifest_sha`, `universe_file_count`, suffix/prefix policy, and the sorted `(path, blob_sha)` manifest entries.
- Golden validity guard now fails fast if any golden path is outside the universe or the qualname cannot be found in its file.

### Before/after benchmark numbers
Before (`tmf-value-proof-mcp-bench-coverage`, contaminated file enumeration):
```text
Tasks: 18  Budget: 6
adversarial: baseline recall=0.000; tmf recall=0.250
graph-shaped: baseline recall=0.250; tmf recall=0.500
open: baseline recall=0.000; tmf recall=0.417
TMF losses: graph-006
```

After (fixed universe, `universe_manifest_sha=ddb1fb3e25ab327076a744600aac5d44ac025e405a75c4ab7b9b165ebe87d54b`, `universe_file_count=50`):
```text
Tasks: 18  Budget: 6
adversarial: baseline recall=0.417; tmf recall=0.250
graph-shaped: baseline recall=0.833; tmf recall=0.500
open: baseline recall=0.500; tmf recall=0.417
TMF losses: graph-001, graph-002, graph-004, graph-006, open-002, adversarial-001, adversarial-004
```

### Important finding
- The benchmark was previously deterministic but not validly isolated: documentation/report drift could improve baseline recall by exposing golden terms.
- Directionally this made TMF look worse, not better; no cheating was indicated. Still, benchmark validity required fixing.
- After decontamination, baseline remains stronger on several tasks and TMF losses increased. This is reported as a measurement finding, not hidden or tuned away.

### Validation evidence
```text
python3 bench/agent_ab/runner.py --repo . --out bench/agent_ab/universe_fix1
python3 bench/agent_ab/runner.py --repo . --out bench/agent_ab/universe_fix2
cmp bench/agent_ab/universe_fix1/report.json bench/agent_ab/universe_fix2/report.json
# deterministic cmp: OK
```


## Value proof window: MCP service + agent A/B benchmark + graph coverage (2026-06-10)

### Scope
- Strategic turn from adding relationship types to proving end-to-end agent consumption value.
- No new node kinds and no new edge kinds were added in this window.
- No Java step2+, rename persistent identity, store trust-boundary hardening, or real LLM calls were added.
- Measurement-only integrity rule: benchmark and coverage numbers are reported as observed. TMF losses and low coverage are treated as findings, not failures to hide.

### Deliverables
- `tmf/mcp_server.py` — stdlib-only newline-delimited JSON-RPC/MCP stdio server. Handles `initialize`, `notifications/initialized`, `tools/list`, `tools/call`, and `ping`; malformed JSON-RPC requests return errors without crashing; protocol output stays on stdout.
- `tmf/cli.py` — added `tmf mcp --repo <root>` entry point.
- MCP tools: `tmf_retrieve`, `tmf_explain`, `tmf_callers`, `tmf_readers`, `tmf_writers`, `tmf_subtypes`, `tmf_warm`, and `tmf_status`. Tool descriptions explicitly state partial coverage, fresh-is-not-correct, source authority, and stale/degrade behavior.
- `tests/test_mcp_server.py` — subprocess pipe test for initialize → tools/list → tools/call, malformed request resilience, path-boundary rejection, and clean protocol framing.
- `bench/agent_ab/tasks.jsonl` — 18 real-repo tasks across `graph-shaped`, `open`, and `adversarial` categories. Tasks are intentionally not curated to make TMF always win.
- `bench/agent_ab/runner.py` — deterministic scripted proxy comparing lexical baseline versus TMF/MCP-shaped retrieval under the same budget. It reports recall, calls, read bytes, category aggregates, and limitations. It ignores generated benchmark output directories so reports do not index their own prior runs.
- `bench/agent_ab/adapter.py` and `bench/agent_ab/README.md` — `AgentAdapter` interface/stub and instructions for running real Claude Code/API A/B experiments in an environment with model access. Offline tests do not call LLMs.
- `tmf/validation.py` — graph coverage measurement section in held-out and self-dogfood reports, split by Python/Java and by edge kind. This measures resolved/unresolved counts and unresolved reason histograms only; it has no target threshold and does not alter parser behavior.
- `README.md` — added Agent/MCP integration and trust notes.

### Benchmark results (scripted proxy, not LLM task success rate)
```text
python3 bench/agent_ab/runner.py --repo . --out bench/agent_ab/check5
python3 bench/agent_ab/runner.py --repo . --out bench/agent_ab/check6
cmp bench/agent_ab/check5/report.json bench/agent_ab/check6/report.json
# deterministic cmp: OK

Tasks: 18  Budget: 6
adversarial: baseline recall=0.000; tmf recall=0.250
graph-shaped: baseline recall=0.250; tmf recall=0.500
open: baseline recall=0.000; tmf recall=0.417
TMF losses: graph-006
```

Adverse/important findings are intentionally preserved:
- TMF lost `graph-006` under the deterministic proxy strategy.
- The first benchmark implementation was not byte-deterministic because generated report directories could be re-indexed by warm/self-dogfood. Fixed by isolating benchmark outputs and sorting/deduplicating queue expansion; this was a determinism/stability fix, not an outcome-tuning change.
- The benchmark remains a retrieval proxy only and is not an LLM task success rate.

### Coverage measurements (observed, no target threshold)
Held-out validation:
```text
python calls: resolved=2 unresolved=3 resolution_rate=0.400 reasons={'attribute_call_not_resolved': 2, 'from_import_symbol_not_direct_top_level_def': 1}
python reads: resolved=0 unresolved=3 resolution_rate=0.000 reasons={'from_import_symbol_not_tracked_declaration': 3}
python writes: resolved=0 unresolved=0 resolution_rate=1.000 reasons={}
python inherits: resolved=0 unresolved=0 resolution_rate=1.000 reasons={}
java calls/reads/writes/inherits: resolved=0 unresolved=0 resolution_rate=1.000 reasons={}
```

Self-dogfood validation:
```text
python calls: resolved=1176 unresolved=3563 resolution_rate=0.248 reasons={'attribute_call_not_resolved': 2058, 'dynamic_call_not_resolved': 1, 'from_import_symbol_not_direct_top_level_def': 235, 'import_module_not_unique_or_missing': 146, 'name_not_module_local_function': 693, 'self_method_not_found_in_class': 430}
python reads: resolved=92 unresolved=1037 resolution_rate=0.081 reasons={'from_import_symbol_not_tracked_declaration': 558, 'import_module_not_unique_or_missing': 479}
python writes: resolved=0 unresolved=0 resolution_rate=1.000 reasons={}
python inherits: resolved=0 unresolved=0 resolution_rate=1.000 reasons={}
java calls/reads/writes/inherits: resolved=0 unresolved=0 resolution_rate=1.000 reasons={}
```

### Validation / zero-regression proof
```text
python3 -m unittest discover -s tests -q
Ran 106 tests in 13.461s
OK

bash scripts/verify_java_offline.sh
JAVA OFFLINE VERIFY: PASS

python3 -m tmf.cli validate --repo . --out reports/value-proof-validation --heldout --self-validate --sample-limit 20
heldout_status: pass
heldout_precision: 1.0
heldout_recall: 1.0
self_status: pass
self_precision: 1.0
self_recall: 1.0
self_fp: 0
self_fn: 0

python3 scripts/check_python_claim_regression.py
ok: true
normalized byte-identical: true for tests/test_retrieve_thin.py, tests/test_embeddings.py, tests/test_calls_edges.py
```

### Explicitly deferred
- New node/edge kinds, Java step2+, rename persistent identity, store trust-boundary hardening, real LLM calls, and semantic/SCIP/LSP relationship expansion.


## Java step1 conservative inheritance edges (2026-06-09)

### Scope
- Additive Java relationship step only: `body.edge_kind = "inherits"` for Java type -> Java supertype edges.
- Supported relations are `body.relation = "extends"` and `body.relation = "implements"` for:
  - `class A extends B`
  - `class A implements I, J`
  - `interface I extends J, K`
- Resolution is intentionally conservative and syntactic: same-file unique top-level class/interface names and explicit-import top-level targets only.
- External/JDK supertypes, wildcard imports, same-package implicit guesses, missing targets, and ambiguous duplicate names are recorded as unresolved and are never linked.
- Generic supertypes are erased to the bare type name for syntactic resolution. Coverage is marked `partial`; semantic resolution is deferred to a future SCIP/LSP step.

### Files changed
- `tmf/ids.py` — added `stable_inherit_edge_claim_id(subtype_id, supertype_id, relation)`.
- `tmf/java_extract.py` — added `JavaInheritEdge`, `JavaUnresolvedInherit`, and `resolve_java_inherit_edges()` with conservative Java supertype parsing/resolution.
- `tmf/derive.py` — derives Java inherit edge claims, populates forward graph `inherits`, reverse graph `subtypes` / `implementors`, and surfaces unresolved inheritance metadata.
- `tmf/freshness.py` — inherit edges become stale when subtype or supertype endpoint hashes change, and remain fresh on unrelated source edits.
- `tmf/store.py`, `tmf/retrieve.py`, `tmf/warm.py`, `tmf/validation.py` — edge-kind filtering/reconciliation/freshness/retrieval now includes `inherits` alongside `calls`, `reads`, and `writes`.
- `tmf/retrieve.py` — added `reverse_subtypes()` and `reverse_implementors()` helpers.
- `tests/test_java_inherit.py` — focused same-file, explicit-import, unresolved, retarget/reconcile, and endpoint-deletion tests.
- `scripts/verify_java_offline.sh` — offline verifier now includes the Java inherits bench: warm → store → check_freshness → retarget → reconciliation → endpoint deletion.
- `README.md` — documents optional Java nodes plus conservative step1 inheritance edges and remaining exclusions.

### Validation / zero-regression proof
```text
python3 -m unittest discover -s tests -q
Ran 105 tests in 12.891s
OK

bash scripts/verify_java_offline.sh
JAVA OFFLINE VERIFY: PASS

python3 -m tmf validate --repo . --out reports/java-inherit-step1-validation --heldout --self-validate --sample-limit 20
heldout_status: pass
heldout_precision: 1.0
heldout_recall: 1.0
heldout_fp: 0
heldout_fn: 0
self_status: pass
self_precision: 1.0
self_recall: 1.0
self_fp: 0
self_fn: 0
self_tp: 44
self_samples: 20

python3 scripts/check_python_claim_regression.py
normalized byte-identical: OK
```

### Explicitly deferred
- Java override, use-type, constructor/call edges, annotations, DI, pub-sub, SQL/ORM, reflection, codegen, multi-file semantic package resolution, SCIP/LSP integration, and semantic read-through.

## Java step0 offline verifier + validation cleanup (2026-06-09)

### Scope
- Verification/packaging/small-fix pass only; no Java edges and no engine semantic broadening.
- Vendored offline Java dependencies for Linux x86_64 / CPython 3.12 / manylinux2014-compatible review under `vendor/wheels/`.
- Added MIT license texts under `vendor/licenses/`.
- Added `scripts/verify_java_offline.sh`, which creates `.ts-venv`, installs tree-sitter wheels with `--no-index`, runs Java tests without skips, warms a minimal Java fixture, and asserts two-way freshness plus deletion reconcile.
- Kept the online fallback install command in README.

### Small fixes
- Cached Java availability probing with `@lru_cache(maxsize=1)` and made `java_status()` call it once.
- Reserved `ExtractionTier = "semantic-resolved"` in both core and backend type aliases.
- Added a semantic backend stub test proving an available semantic backend queues background refresh and records degrade/queued metadata without synchronously emitting semantic claims.
- Made warm/self-validation ignore local packaging noise (`.ts-venv`, `vendor`, `reports`, `__pycache__`) so vendored review assets do not pollute dogfood.

### Validation
```text
python3 -m unittest discover -s tests -q
Ran 101 tests in 12.219s
OK

bash scripts/verify_java_offline.sh
JAVA OFFLINE VERIFY: PASS

python3 -m tmf.cli validate --repo . --out reports/java-offline-final-validation --heldout --self-validate --sample-limit 20
heldout_status: pass
heldout_precision: 1.0
heldout_recall: 1.0
heldout_fp: 0
heldout_fn: 0
self_status: pass
self_precision: 1.0
self_recall: 1.0
self_fp: 0
self_fn: 0
self_tp: 44
self_samples: 20
```

### Python regression proof
- `scripts/check_python_claim_regression.py` compares representative unchanged Python paths against the previous Java step0 package.
- Non-file Python claims are byte-identical after normalizing `last_verified`, `binding.commit`, and `binding.file_blob`; file-claim text remains the existing Java-node-count summary behavior.

## Multi-language Java step0: optional tree-sitter syntactic nodes (2026-06-09)

### Scope
- Added Java **node extraction only** for `.java` files: class, interface, enum, method, constructor, field, and constant nodes.
- No Java edges were added. Calls/reads/writes remain Python-only; Java relationships, inheritance, override, use-type, semantic SCIP/LSP, and DI are intentionally out of scope.
- Java extraction is optional and lazy-imported through `tree_sitter` + `tree_sitter_java`; Python core/package dependencies remain empty.
- If optional Java dependencies are missing, `.java` read-through degrades to a file/source fallback claim with an explicit install hint, while Python behavior remains unchanged.

### Complete Java arc ordering
1. `tmf retrieve --path X.java` or `tmf warm` sees a `.java` path.
2. `derive_claims_for_path` always emits the normal file claim first.
3. Java backend availability is checked lazily via `tmf.java_extract.java_status()`.
4. If unavailable: no Java node claims are emitted; the file claim body records `java_extraction.degraded=true` and the CLI surfaces `degrade_hint`.
5. If available: tree-sitter parses the file and extracts syntactic declarations in source-tree order.
6. Extracted Java class/interface/enum nodes are represented as class-scope claims with `language="java"`, `node_kind`, and `extraction_tier="java-treesitter-syntactic"`.
7. Extracted Java method/constructor nodes are represented as class-scope node claims with qualified names such as `Outer.method` / `Outer.Outer`.
8. Extracted Java field/constant nodes are represented as declaration-scope node claims with qualified names such as `Outer.FIELD`.
9. Per-node freshness hash is computed from tree-sitter leaf token `type:text`, dropping comments/whitespace and retaining punctuation, keywords, identifiers, literals, modifiers, and annotations.
10. Claim anchors include `{path,line_start,line_end,qualname}`.
11. Read-through stores current claims, then existing path reconciliation deletes stale Java tombstones when Java nodes disappear or are renamed.
12. Freshness checks Java claims by re-extracting the same node kind and qualname and comparing the tree-sitter token hash; comments/whitespace remain fresh, token/literal/body changes stale.
13. Semantic read-through/background is exposed only as a stub interface in `tmf/backends.py`; no semantic backend is implemented.

### Files changed
- `tmf/backends.py` — new pluggable extractor backend skeleton and semantic backend stub/degrade interface.
- `tmf/java_extract.py` — optional tree-sitter Java parser, leaf-token hashing, Java class/interface/enum/method/constructor/field/constant extraction, dependency status/degrade hint.
- `tmf/extract.py` — added default `language`, `node_kind`, and `extraction_tier` metadata to existing node dataclasses without changing Python defaults.
- `tmf/ids.py` — added `stable_java_node_claim_id(path, qualname, node_kind)`.
- `tmf/derive.py` — integrates optional Java extraction, emits Java node claims, records Java degrade hints, and preserves Python derivation flow.
- `tmf/freshness.py` — re-extracts Java nodes for freshness and reports `java_hash mismatch` / `java node missing`.
- `tmf/warm.py` — includes `.java` files in warmable paths.
- `tmf/cli.py`, `tmf/explain.py` — surfaces Java degrade hint and Java metadata in thin/explain views.
- `tests/test_java_nodes.py` — Java extraction, two-way freshness, reconcile/delete, and missing-dependency degrade tests.
- `README.md` — documented optional pinned grammar install and step0 limitations.

### Optional dependency instructions
```bash
python -m pip install "tree_sitter==0.25.2" "tree_sitter_java==0.23.5"
```

### Validation / zero-regression proof
```text
python3 -m unittest discover -s tests -q
Ran 95 tests in 12.699s
OK (skipped=1)

python3 -m tmf.cli validate --repo . --out reports/java-step0-validation --heldout --self-validate --sample-limit 20
heldout_status: pass
heldout_precision: 1.0
heldout_recall: 1.0
self_status: pass
self_precision: 1.0
self_recall: 1.0
self_fp: 0
self_fn: 0
```

### Java freshness two-way proof
- `tests/test_java_nodes.py::test_java_freshness_is_two_way_comments_whitespace_ignored_literals_included` verifies comment/trivia edits keep the Java method claim fresh while literal/body token edits stale both the method node and containing class node.


## Relationship completion step 1: Python `writes` edges + precise anchors (2026-06-09)

### Scope
- Additive relationship only: `body.edge_kind = "writes"` for Python function -> module-level declaration writes.
- Also surfaces precise reference anchors `{path, line_start, line_end, qualname}` for forward and reverse `calls` / `reads` / `writes` references where available.
- This is the first relationship-completion step. No other relationship families were added in this window.

### Files changed
- `tmf/ids.py` — added `stable_write_edge_claim_id(writer_id, declaration_id)`.
- `tmf/edges.py` — added conservative `resolve_write_edges`; updated read-side scope handling so explicit `global X` does not make `X` look local, and `X += ...` with `global X` is both read and write.
- `tmf/derive.py` — derives `writes` edge claims; surfaces function `writes` / `writes_unresolved`; surfaces declaration `written_by`; adds exact anchors for forward/reverse calls/reads/writes.
- `tmf/freshness.py` — writes edges stale when writer function hash or written declaration hash changes.
- `tmf/store.py`, `tmf/retrieve.py`, `tmf/warm.py` — reconciles `writes` edges independently; adds `reverse_writers`; keeps callers/readers/writers distinct; warm reverse caller index preserves anchors.
- `tmf/validation.py` — added `_write_edge_checks`; expected-stale oracle includes `writes` endpoints symmetrically with `calls`/`reads`.
- `tests/test_write_edges.py` — new focused behavior/freshness/reconcile tests.
- `tests/test_validation.py`, `tests/test_warm.py` — validation/property and anchor expectations updated.
- `README.md`, `CHANGELOG.md` — documented the Python-only `global`-aware writes MVP and explicit backlog.

### Conservative behavior
- Resolved only when a function body explicitly declares `global X` and then assigns / annotated-assigns / augmented-assigns / deletes `X`, and `X` is a same-file tracked module-level declaration.
- Assignment to same-name `X` without `global X` is local and never linked.
- `nonlocal` is not a module declaration write and remains unresolved.
- Nested def/class bodies are not attributed to the enclosing function.
- No full-repo name matching. No cross-file `mod.X = ...` extension in this package; left deferred rather than risk a wrong edge.

### Backlog explicitly not done in this window
- use-type / implements / inheritance / override / construct relations.
- DI assembly.
- pub-sub / Kafka topics.
- SQL / ORM.
- codegen, macros, reflection.
- multi-language extractors.

### Validation / zero-regression proof
```text
python3 -m unittest discover -s tests -q
Ran 91 tests in 11.280s
OK

python3 -m tmf.cli validate --repo . --heldout --out reports/writes-validation-2/heldout
heldout_status: pass
heldout_precision: 1.0
heldout_recall: 1.0

python3 -m tmf.cli validate --repo . --self --out reports/writes-validation-2/self
self_status: pass
self_precision: 1.0
self_recall: 1.0
self_fp: 0
self_fn: 0
```

### Note on verification friction
- First self-dogfood run became unusually slow after naive anchor lookup because edge-claim anchor generation repeatedly re-parsed files.
- Fixed by adding blob-keyed anchor caches in `derive.py`; validation then completed and passed.


## Config-usage declaration read edges: Python MVP (2026-06-09)

### Scope
- Added one additive edge type only: Python function -> module-level declaration reads.
- Edge claims use `body.edge_kind = "reads"`; call edges remain `body.edge_kind = "calls"` and are not mixed with readers.
- This is a config-usage relationship MVP over existing Python declaration nodes, not config-file-key tracking.

### Files changed
- `tmf/ids.py` — added `stable_read_edge_claim_id(reader_id, declaration_id)`.
- `tmf/edges.py` — added conservative, scope-aware `resolve_read_edges` for Python `Name` loads.
- `tmf/derive.py` — derives read edge claims; surfaces function `reads` / `reads_unresolved`; surfaces declaration `read_by` with partial coverage.
- `tmf/freshness.py` — read edge freshness checks both reader function hash and declaration hash, including same-file endpoints.
- `tmf/store.py`, `tmf/retrieve.py`, `tmf/warm.py` — reconciles `reads` edges independently of path-local nodes; adds separate `reverse_readers`; keeps `reverse_callers` calls-only.
- `tmf/explain.py` — thin/full/explain surface `reads`, `reads_unresolved`, and declaration `read_by`.
- `tmf/validation.py` — adds `_read_edge_checks`; extends self-dogfood expected-stale oracle to include `reads` edge endpoints tightly and symmetrically with calls.
- `tests/test_read_edges.py` — new focused behavior/freshness/reconcile tests.
- `tests/test_validation.py` — held-out property list includes `read_edges`.
- `README.md`, `CHANGELOG.md` — document the Python-only partial MVP and exclusions.

### Conservative behavior
- Resolved only when a function body `Name` load unambiguously targets:
  - a same-file top-level declaration node; or
  - a direct `from module import NAME` whose target module has that top-level declaration node.
- No full-repo name matching.
- Parameters, local assignments, and comprehension targets shadow names and prevent resolved edges.
- Unknown/dynamic/unsupported names are recorded as `reads_unresolved` where relevant, not guessed.
- Nested functions/classes are not attributed to the enclosing function.

### Explicitly deferred
- Config file key reads and getter/string-to-key mapping.
- Environment variable reads and virtual source nodes.
- Framework getters, dependency injection, annotations, and dynamic sources.
- Non-Python extractors, YAML, and SQL.

### Validation / zero-regression proof
```text
python3 -m unittest discover -s tests -q
Ran 87 tests in 10.589s
OK

python3 -m tmf.cli validate --repo . --heldout --out reports/read-edges-validation/heldout
heldout_status: pass
heldout_precision: 1.0
heldout_recall: 1.0

python3 -m tmf.cli validate --repo . --self --out reports/read-edges-validation/self
self_status: pass
self_precision: 1.0
self_recall: 1.0
self_fp: 0
self_fn: 0
```


## Release wrapup / open-source preparation (2026-06-09)

### Added files / release metadata
- `pyproject.toml` — updated distribution metadata to `true-memory-fragments` 0.1.0, import package `tmf`, console script `tmf = tmf.cli:main`, and `dependencies = []`.
- `README.md` — replaced prototype notes with release-facing documentation, quick start, CLI reference, supported partial node subsets, honest limitations, and reproducible validation evidence.
- `DESIGN.md` — added the correctness invariant contract.
- `CONTRIBUTING.md` — added invariant-preserving contribution and validation rules.
- `CHANGELOG.md` — added clean 0.1.0 release history.
- `.github/workflows/ci.yml` — added stdlib-only CI workflow file for unit tests plus validation.
- `tmf/py.typed` — marks the typed package.
- `.gitignore` — includes `.tmf/`, `__pycache__/`, `build/`, `dist/`, `*.egg-info/`, `.pytest_cache/`.

### CLI interface wrapup
- `tmf/cli.py` only: added `validate` wrapper subcommand and clearer help text.
- `validate` delegates to existing `run_heldout_validation` and `run_self_validation`; validation semantics were not changed.

### Confirmation needed before public publication
- MIT license choice and copyright holder/year must be confirmed by Kyle.
- Distribution name `true-memory-fragments` must be confirmed by Kyle.

### Validation / zero-regression proof
```text
python3 -m venv /tmp/tmf-release-venv
. /tmp/tmf-release-venv/bin/activate
python -m pip install -e .
# Successfully installed true-memory-fragments-0.1.0

tmf --help
tmf warm --help
tmf retrieve --help
tmf explain --help
tmf callers --help
tmf validate --help
tmf feedback --help
# all help commands returned successfully

python -m unittest discover -s tests -q
Ran 82 tests in 9.330s
OK

tmf validate --repo . --heldout --out reports/release-wrapup/validate-heldout
heldout_status: pass
heldout_precision: 1.0
heldout_recall: 1.0

tmf validate --repo . --self --out reports/release-wrapup/validate-self
self_status: pass
self_precision: 1.0
self_recall: 1.0
self_fp: 0
self_fn: 0
```

### Environment note
- Direct system `python3 -m pip install -e .` was blocked by the host PEP 668 externally-managed Python policy. Editable install was therefore validated in a clean external virtualenv at `/tmp/tmf-release-venv`, which is the recommended local path for this host.


## V1 containment-aware dogfood + V2 API contract nodes (2026-06-09)

### Files changed
- `tmf/validation.py` — made self-validation freshness sampling containment-aware for nested perturbations, keeping the expected-stale set tight by using the insertion gap and source-span containment; added API node validation checks.
- `tmf/extract.py` — added conservative AST-only API route extraction for known Flask/FastAPI-style decorators, with decorator-to-handler spans hashed by the existing token-stream hash.
- `tmf/derive.py` — derives `scope="api"` claims through the normal claim/binding/reconcile path.
- `tmf/freshness.py` — adds per-binding API hash freshness checks, keyed by method/path/handler.
- `tmf/ids.py` — adds `stable_api_claim_id(path, method, route_path, handler_qualname)`.
- `tmf/schema.py` — adds `scope="api"`.
- `tests/test_self_validation.py` — regression coverage for nested containment expectations and tight anti-overbroad expected sets.
- `tests/test_api_nodes.py` — API node derivation/freshness/reconcile coverage.
- `tests/test_validation.py` — asserts the held-out validation report includes the API node bench section.
- `CHANGES.md` — records validation results.

### V1 dogfood containment behavior
- Previous boundary-INDENT baseline still had measurement-side false positives when perturbing nested nodes: enclosing spans that truly changed were not in the expected-stale set.
- Self-validation now derives expected stale IDs from the insertion gap plus source-span containment, and then includes edges whose endpoints are in those affected nodes.
- The expected set remains tight: same-file claims whose spans do not contain the insertion gap stay outside the expected set, so real over-invalidation still appears as FP.
- This is measurement-only; engine freshness semantics were not changed for V1.

### V2 API contract node behavior
- Recognized decorators only:
  - `@app.route("/x", methods=[...])`
  - `@router.get/post/put/delete/patch("/x")`
- Path must be a string literal; dynamic paths and unknown decorators are skipped.
- API span includes route decorators through handler end and uses the same `fn_hash_for_span` token rules.
- Route method/path changes stale the API node; handler body changes stale the API node; comments/formatting stay fresh; unrelated same-file functions do not stale the API node.
- Deleting the route reconciles the API claim tombstone.

### Acceptance / validation
```text
python3 -m unittest discover -s tests -v
Ran 82 tests in 9.265s
OK
```

Real TMF self-dogfood after V1+V2:
```text
Status: pass
Freshness sample count: 10
Freshness sample precision: 1.000
Freshness sample recall: 1.000
Freshness sample fp/fn: 0 / 0
```

Held-out validation after V1+V2:
```text
Status: pass
Repos: 2
Freshness precision: 1.000
Freshness recall: 1.000
Freshness fp/fn: 0 / 0
Invariant violations: 0
Observed/source support violations: 0
Degrade-to-source failures: 0
Property failures: 0
```

### Red-line self-check
- No validation expectation was weakened; V1 corrected the measurement oracle to model true nested source containment while preserving FP detection for non-containing spans.
- API nodes are conservative and additive; dynamic/unknown routes degrade to source instead of being guessed.
- Worktree freshness, multi-binding edge rules, confidence/provenance/thin behavior, and resolver semantics were not relaxed.


## Boundary INDENT normalization fixes class→method over-invalidation (2026-06-09)

### Files changed
- `tmf/extract.py` — normalized `fn_hash_for_span` token items by trimming only span-boundary outer-scope `INDENT`/`DEDENT` events before the first real content token and after the last real content token. Function-internal `INDENT`/`DEDENT`/`NEWLINE` tokens are still preserved, so body/block structure remains hash-sensitive.
- `tests/test_freshness_over_invalidation.py` — added regression and guardrail coverage for the first class-method boundary-INDENT bug, nested first inner functions, body changes, internal block changes, comment/reformat immunity, and structure-distinction hashes.
- `CHANGES.md` — recorded the dogfood failure-to-pass result for this surgical fix.

### Behavior
- Fixes the false stale result reported by the previous `tmf-v2-self-dogfood-found-defect` package, where real TMF dogfood found freshness precision `0.606` and class perturbations over-invalidated nested method function claims.
- The precise cause was token-span selection including the parent scope's boundary `INDENT` when a method/function was the first member of its parent block. Inserting a sibling above moved that outer `INDENT` out of the method span, changing `fn_hash` despite an unchanged method body.
- The fix is extraction-only. Freshness decision logic, confidence, feedback, resolver behavior, verification, provenance, thin retrieval, and validation expectations were not changed.
- Boundary normalization is intentionally narrow: it removes leading structural trivia before the first content token and trailing structural trivia after the last content token, while preserving internal block tokens that distinguish real semantic/body changes.

### Acceptance / validation
```text
python3 -m unittest tests.test_freshness_over_invalidation -v
Ran 11 tests in 0.263s
OK
```

```text
python3 -m unittest discover -s tests -v
Ran 72 tests in 8.628s
OK
```

Real TMF self-dogfood after the fix:
```text
Status: pass
Claims scanned: 831
Freshness sample count: 10
Freshness sample precision: 1.000
Freshness sample recall: 1.000
Freshness sample fp/fn: 0 / 0
```

Held-out validation after the fix:
```text
Status: pass
Repos: 2
Freshness precision: 1.000
Freshness recall: 1.000
Freshness fp/fn: 0 / 0
Invariant violations: 0
Observed/source support violations: 0
Degrade-to-source failures: 0
Property failures: 0
```

### Red-line self-check
- No under-invalidation introduced in regression coverage: method body changes and internal block-structure changes still stale.
- Existing intended immunities still hold: comments, formatting/indent-width changes, and module-level comment insertion stay fresh.
- Structurally different functions still hash differently.
- The validation harness was not weakened; dogfood went from the recorded `0.606` precision failure to `1.000` via the `fn_hash` boundary-token fix.

## V1 self dogfood validation found freshness over-invalidation (2026-06-05)

### Files changed
- `tmf/validation.py` — added `run_self_validation(repo_root, out_dir, sample_limit=10)` for real-repo dogfood; it warms a temporary copy, scans real claims, emits JSON/Markdown, and samples freshness perturbations without modifying the engine.
- `tests/test_self_validation.py` — added acceptance coverage for the self-validation report entry point on a small realistic repo.
- `reports/self-validation-tmf/self-validation.json` and `.md` — real TMF dogfood evidence report.
- `reports/heldout-validation-self-dogfood/report/heldout-validation.json` and `.md` — regenerated held-out report after the measurement addition.
- `.learnings/ERRORS.md` — recorded the initial SIGKILL resource issue during the first dogfood attempt.

### Behavior
- Self-validation is measurement-only. It copies the target repo to a temp directory, runs `warm_repo`, and checks real derived claims.
- Generic scans include invariant trust/cap checks, observed/source support checks, thin/full redaction/restore checks, verification boundary scan, low-confidence degrade anchor scan, and embed/router-off determinism.
- Freshness dogfood samples real function/class/config claims in temp copies and reports precision/recall plus concrete mismatches.
- Resource guard: held-out validation still owns the expensive reverse-coverage drift microtest; self-validation skips that duplicate fixture-scale probe to complete on real repos.

### Dogfood result on real TMF repo
Self-validation on `/root/.openclaw/workspace/tmf` derived 807 real claims and found a freshness over-invalidation defect:

```text
Status: fail
Freshness sample count: 10
Freshness sample precision: 0.606
Freshness sample recall: 1.000
Freshness sample fp/fn: 13 / 0
```

Other real-repo scans were clean:

```text
Invariant violations: 0
Observed/source support violations: 0
Thin/full failures: 0
Verification boundary failures: 0
Degrade failures: 0
Router/embed off failures: 0
```

Concrete mismatch pattern:
- perturbing some `ClassNode` claims made nested method function claims stale as false positives;
- examples from the report include `claim_class_f6e5c2bedc955799` causing `claim_fn_6469031a38a69422` to stale unexpectedly, and similar class→method false positives.

Likely cause for reviewer investigation:
- class hash semantics intentionally include method bodies, but inserting a class-level member shifts method line spans; current `fn_hash` recomputation uses stored qualname and current extracted span, so method token streams may change under class-body insertions even when method semantic body is unchanged.
- This was not visible in small fixtures because class freshness tests allowed conservative class over-invalidation but did not dogfood class-body insertions against sibling/nested method nodes.

### Acceptance outcome
- New dogfood entry point works and emits JSON + Markdown.
- It honestly reports the real-repo fail instead of tuning the engine.
- Per protocol, V2 API contract nodes were **not** started in this window.
- Held-out validation remains pass after adding the dogfood tool.
- Full suite is green.

### Test result
```text
Ran 66 tests in 67.446s

OK
```

### Held-out report after V1 dogfood addition
```text
Status: pass
Freshness precision: 1.000
Freshness recall: 1.000
Invariant violations: 0
Observed/source support violations: 0
Degrade-to-source failures: 0
Property failures: 0
```

### Red-line self-check
- No engine behavior was changed to make dogfood pass.
- No validation expectation was weakened; one initial measurement false positive and one resource issue were fixed in the measurement harness only.
- Real dogfood failure is recorded as a suspected engine freshness over-invalidation defect and left for review/fix decision.

### Open questions / risks
- Reviewer should decide whether method-level `fn_hash` should be immune to class-body insertions that only shift method spans, and whether extraction should hash AST-normalized function nodes rather than line slices in such cases.
- If this is accepted as a bug, add a targeted regression before changing freshness/extraction.

## V1 embedding/router baseline check + V2 JSON/TOML config nodes (2026-06-05)

### Files changed
- `tmf/validation.py` — strengthened embed/router-off additivity from deterministic self-equality to a fixed lexical baseline check; added `config_nodes` bench section covering value change, reformat/key-order immunity, unrelated-key immunity, delete reconciliation, and parse-error degradation.
- `tmf/extract.py` — added conservative stdlib JSON/TOML top-level config extraction and normalized value hashing.
- `tmf/ids.py` — added `stable_config_claim_id(path, key)`.
- `tmf/schema.py` — added `scope="config"`.
- `tmf/derive.py` — derives config claims through the normal claim/binding/reconcile path.
- `tmf/freshness.py` — added per-binding config hash freshness branch.
- `tmf/warm.py` — warms Python plus JSON/TOML files while keeping reverse caller coverage honest.
- `tests/test_config_nodes.py` — added JSON and TOML config node acceptance coverage.
- `tests/test_validation.py` — asserts the new `config_nodes` validation section exists.
- `README.md` — documented v2 config nodes and normalized-hash freshness semantics.
- `reports/heldout-validation-config-nodes/report/heldout-validation.json` and `.md` — regenerated evidence report.

### V1 validation strengthening
- `_embedding_router_checks` no longer only compares two router/embed-off runs to each other.
- It now compares the off-state `retrieve_text(repo, "helper", limit=5)` result against the fixed lexical fixture baseline:
  - call edge `main -> helper`,
  - `b.py` file claim,
  - `a.py` file claim,
  - `b.py::helper` function claim.
- This can distinguish deterministic drift in off-state retrieval from true additivity.
- No engine behavior was changed for V1; an initial expected-order mistake in the check was corrected after inspecting the actual lexical baseline.

### V2 config node behavior
- Config nodes are derived for `*.json` and, where `tomllib` exists, `*.toml`.
- Nodes are only top-level keys; nested/ambiguous structures are not expanded or guessed.
- IDs use `stable_config_claim_id(path, key)` and claims use `scope="config"`.
- Bindings store the normalized parsed-value hash in `fn_hash` for compatibility with the existing binding contract.
- Hash input is canonical JSON serialization of the parsed value: `json.dumps(value, sort_keys=True, separators=(",", ":"))`.
- Whitespace, pretty-printing, and object key order changes remain fresh.
- Value changes stale the specific key.
- Unrelated top-level key changes do not stale the key.
- Deleted keys reconcile tombstones on read-through.
- Malformed config files produce zero config nodes and no crash; source fallback/file claim remains available.

### Acceptance
- JSON top-level keys are derived and fresh.
- JSON value changes stale; formatting/key-order changes stay fresh; unrelated-key changes stay fresh; key delete reconciles.
- Invalid JSON produces no config nodes and does not crash.
- TOML top-level key acceptance passes on this Python runtime (`tomllib` available).
- New `_config_node_checks` bench section passes.
- Held-out validation after V2 remains pass.
- Full test suite is green.

### Test result
```text
Ran 65 tests in 8.449s

OK
```

### Held-out report after V1/V2
```text
Status: pass
Freshness precision: 1.000
Freshness recall: 1.000
Invariant violations: 0
Observed/source support violations: 0
Degrade-to-source failures: 0
Property failures: 0
```

### Red-line self-check
- Validation remains measurement-only and reports failures rather than tuning around them.
- Config freshness uses working-tree file content and per-key normalized value hash; commit remains anchor only.
- Config parse failure degrades to no config nodes rather than guessing.
- Existing Python function/class/declaration behavior was not weakened.
- Confidence, feedback, resolver, model verification, provenance semantics, thin source hiding, and coverage honesty were not weakened.

### Open questions / risks
- Config anchors are currently file-level conservative anchors (`line_start=1`, `line_end=1`) because stdlib JSON/TOML parsers do not preserve key line spans.
- Nested config keys remain intentionally out of scope until a separate conservative design is approved.
- YAML/SQL/API contract nodes remain out of scope because they require dependencies or framework-specific parsing.

## V1 expanded validation bench + V2 module declarations (2026-06-05)

### Files changed
- `tmf/validation.py` — expanded the offline validation bench with property checks for edge lifecycle, multi-binding reconciliation guard, thin/full consistency, verification caps, provenance freshness, embed/router additivity, warm idempotence/incrementality, reverse coverage honesty, and degrade completeness.
- `tests/test_validation.py` — asserts all expanded validation sections exist and report zero failures.
- `tmf/extract.py` — added conservative module-level declaration extraction for top-level `Assign`/`AnnAssign` constants and simple config dicts.
- `tmf/ids.py` — added `stable_declaration_claim_id`.
- `tmf/freshness.py` — added declaration hash freshness branch.
- `tmf/derive.py` — derives declaration claims.
- `tests/test_declaration_nodes.py` — added declaration node acceptance coverage.
- `reports/heldout-validation-current-fixtures/report/heldout-validation.json` and `.md` — regenerated evidence report.

### V1 validation additions
The validation bench now reports the requested property sections:
1. `cross_file_edge_lifecycle` — callee delete/rename removes edge and reverse callers; multi-binding edge survives path-local node reconciliation.
2. `thin_full_consistency` — thin is a faithful subset, omits body/provenance quoted text/full hashes, and full can restore the claim record.
3. `verification_boundaries` — supported source claims are observed <=0.6; unsupported/intents respect caps; attributed intent remains inferred <=0.6.
4. `provenance_freshness` — provenance is not a freshness gate; bound code changes still stale attributed claims.
5. `embedding_router_additivity` — embed/router off path remains equivalent and does not affect retrieval.
6. `warm_idempotent_incremental` — second warm is no-op and single-file drift derives only that file.
7. `reverse_callers_coverage` — complete only after full warm with no drift; drift forces partial.
8. `degrade_all` — stale/low-confidence claims must have anchors and source/rederive action hints.

All checks are measurement-only and run offline/deterministically.

### V2 declaration behavior
- Conservative Python-only declaration nodes are created for top-level `Assign`/`AnnAssign` names when:
  - name is uppercase (`constant`), or
  - value is a literal AST dict (`config_dict`).
- Ambiguous/non-top-level declarations are skipped; no guessing and no new parser.
- Declaration claims use `scope="declaration"`, token-stream `declaration_hash`, per-binding freshness, and normal path reconciliation.
- Comments/trivia are ignored by the same span hash rules; value/body changes stale the declaration; deleting the declaration reconciles tombstones.

### Acceptance
- V1 expanded bench covers the requested invariant areas and reports zero property failures on current samples.
- V2 module constant declaration is derived/fresh, stales on value change, and is removed on delete/retrieve.
- Held-out validation after V2 remains pass.
- Full test suite is green.

### Test result
```text
Ran 61 tests in 8.178s

OK
```

### Held-out report after V1/V2
```text
Status: pass
Freshness precision: 1.000
Freshness recall: 1.000
Invariant violations: 0
Observed/source support violations: 0
Degrade-to-source failures: 0
Property failures: 0
```

### Red-line self-check
- Validation remains measurement-only and reports failures rather than tuning around them.
- Declaration extraction is conservative and AST-only.
- Freshness still uses working-tree blob/hash; node-level bindings still use endpoint hash after blob drift.
- Confidence, feedback, resolver, model verification, provenance semantics, thin source hiding, and coverage honesty were not weakened.

### Open questions / risks
- Declaration extraction is intentionally narrow. Module-level dataclass/TypedDict/Enum are still represented primarily by class nodes; richer declaration typing can be added later as separate conservative steps.
- `thin_full_consistency` currently compares stable common fields and payload redaction properties; if thin grows new fields, the validator should add corresponding full-source checks.

## V1 freshness over-invalidation fix (2026-06-05)

### Files changed
- `tmf/freshness.py` — fixed per-binding freshness logic for function/class bindings with `fn_hash`.
- `tests/test_freshness_over_invalidation.py` — added targeted regression coverage for same-file sibling edits, comment/indent immunity, file-claim behavior, and cross-file edge endpoint freshness.
- `tests/test_validation.py` — restored held-out validation expectation to `status: pass`, precision/recall 1.0.
- `reports/heldout-validation-current-fixtures/report/heldout-validation.json` and `.md` — regenerated evidence report after the fix.

### Bug fixed
Previous package `tmf-v2-heldout-validation-bench` honestly reported freshness over-invalidation:
- editing `helper` made same-file sibling `spare` stale;
- comment-only edits made a function claim stale even though token-stream `fn_hash` was unchanged.

Root cause: `check_freshness` appended `blob mismatch` for every binding before considering node-level `fn_hash`, so function/class bindings were stale on any file byte change.

### New behavior
For each binding:
- If `fn_hash is None` (file-level binding), blob mismatch still means stale.
- If `fn_hash is not None` (function/class/edge endpoint binding):
  - equal current blob is a safe fresh short-circuit;
  - unequal blob triggers recomputation of the endpoint hash using `binding.qualname` with `body.qualname` fallback;
  - only endpoint hash mismatch or missing endpoint makes the binding stale;
  - blob mismatch alone no longer stales node-level bindings.

AND-of-all-bindings is unchanged: a claim is fresh only if every binding is fresh.

### Acceptance 1-8
1. Same file: changing `f1` stales `f1` and leaves untouched `f2` fresh — passed.
2. Comment-only / indent-width changes leave function claim fresh — passed.
3. Real function body change stales that function — passed.
4. File-level claim still stales on any file blob change — passed.
5. Cross-file edge stales only when endpoint hash changes; unrelated callee-file function change does not stale the edge — passed.
6. Rename/delete reconciliation tests still pass — passed.
7. Held-out validation now reports `status: pass`, freshness precision 1.0, recall 1.0, invariant violations 0 — passed.
8. Full suite is green — passed.

### Test result
```text
Ran 59 tests in 7.573s

OK
```

### Held-out report after fix
```text
Status: pass
Freshness precision: 1.000
Freshness recall: 1.000
Invariant violations: 0
Observed/source support violations: 0
Degrade-to-source failures: 0
```

### Red-line self-check
- Freshness still uses working-tree blob/hash; commit remains anchor only.
- For changed files, endpoint hash is recomputed before deciding fresh, avoiding stale-as-fresh under-invalidation.
- File-level claims still use blob mismatch.
- Confidence, feedback, resolver, model verification, provenance, thin output, and validation expectations were not weakened.

### Open questions / risks
- `Binding.file_blob` remains useful as a fast equality short-circuit and provenance/debug anchor for node-level bindings, but no longer acts as an independent stale gate when `fn_hash` exists.

## V1 held-out validation bench (2026-06-05)

### Files changed
- `tmf/validation.py` — added offline deterministic held-out validation bench.
- `tests/test_validation.py` — added validation bench acceptance coverage.
- `reports/heldout-validation-current-fixtures/report/heldout-validation.json` — generated evidence report.
- `reports/heldout-validation-current-fixtures/report/heldout-validation.md` — human-readable evidence summary.

### Behavior
- Validation bench is measurement-only. It does not change engine retrieval, derivation, freshness, confidence, parser, provenance, or thin behavior.
- It warms fixture repositories, applies known perturbations, computes stale detection precision/recall, audits observed/source support, audits invariant violations, checks reverse caller coverage drift, and checks degrade-to-source action hints/anchors.
- Reports are emitted as JSON and Markdown.

### Result
The bench found a real freshness over-invalidation defect and therefore reports `status: fail`.

```text
Freshness precision: 0.500
Freshness recall: 1.000
Invariant violations: 0
Observed/source support violations: 0
Degrade-to-source failures: 0
```

Concrete failing cases:
- `function_body_change`: `spare` in `b.py` was expected fresh when only `helper` changed, but was stale.
- `comment_only_change`: `helper` was expected fresh when only a comment was added, but was stale.

Likely cause, not fixed in this task: current `check_freshness` marks a binding stale on any file-level blob mismatch before considering whether the node-level token hash is unchanged. That makes same-file unrelated node edits and comment-only changes false positives for function/class claims.

### Acceptance outcome
- The validation bench itself is deterministic and reproducible.
- It writes JSON + Markdown reports.
- Invariant audit counts are all zero on current samples.
- It produces stale precision/recall numbers.
- Because it found a real engine defect, V1 intentionally stops here per protocol. No engine fix was made to improve the metrics.

### Test result
```text
Ran 54 tests in 7.109s

OK
```

### Red-line self-check
- Measurement-only: no engine behavior was changed.
- The failing metric was not hidden or tuned away.
- V2 was not started because V1 found a defect requiring review/fix decision.

### Open questions / risks
- The reviewer should decide whether function/class freshness should treat file blob mismatch as stale even when node hash is unchanged, or whether node-level bindings should rely on fn_hash/class_hash for semantic freshness while still carrying file_blob as an anchor. Current held-out expectation favors the latter.

## T6 PR provenance evidence (2026-06-05)

### Files changed
- `tmf/provenance.py` — added `source_type="pr"` support through injectable `pr_evidence(...)`; no GitHub/API client added.
- `tmf/explain.py` — provenance ref can use PR URL while still keeping quoted text out of thin refs.
- `tests/test_model_derive.py` — added PR provenance attribution/no-leak acceptance coverage.

### Behavior
- PR evidence is explicit provenance data, not a freshness gate and not a source of observed facts.
- PR text is stored as `text_untrusted_data` through the same provenance evidence path.
- Intent claims supported by PR provenance can become attributed (`evidence="inferred"`, verification `attributed_external_provenance`) with confidence capped at 0.6.
- Thin output exposes the PR URL ref, not the PR quoted text.

### Acceptance tests added
- Injected PR provenance supports an intent claim and caps model raw confidence 0.99 down to <=0.6.
- Claim remains `inferred`; it does not become `observed` or `verified`.
- PR-only private marker text does not leak into thin output, while the PR URL ref is visible.

### Test result
```text
Ran 53 tests in 6.799s

OK
```

### Red-line self-check
- PR provenance is attribution only, not freshness and not behavioral proof.
- PR text remains untrusted data.
- Thin omits PR quoted text.
- No external API client, network call, or package dependency added.

### Open questions / risks
- This is intentionally only an injectable data helper. Any future PR platform collector must be separate and must preserve the same `text_untrusted_data` / capped-attributed semantics.

## T5 LLM-router seed selection (2026-06-05)

### Files changed
- `tmf/router.py` — added optional local command router using only Python stdlib.
- `tmf/retrieve.py` — `retrieve_text` optionally adds router-selected fresh seeds when lexical results leave room.
- `tests/test_router.py` — added T5 acceptance coverage.

### Behavior
- Default/off behavior is unchanged: without `TMF_ROUTER_COMMAND`, router is a no-op.
- Router is pluggable via `TMF_ROUTER_COMMAND`; no network client, external service SDK, or dependency is added.
- Router input uses `query_untrusted_data` and `claims_untrusted_data`.
- Router only selects seed claim ids. It does not change trust, confidence, evidence, provenance, freshness, or claim text.
- Only fresh claims are eligible as router seeds.
- Results still flow through existing thin rendering.

### Acceptance tests added
- Router off: repeated default CLI retrieval without router/embedder env is equivalent.
- Fake router: lexical-miss query selects `target`; result remains thin, fresh, and trust stays `observed`.

### Test result
```text
Ran 52 tests in 7.227s

OK
```

### Red-line self-check
- Router is seed selection only, not a truth source.
- No confidence/evidence/trust/provenance/feedback code changed.
- No external packages or network clients introduced.
- Stale claims are excluded before the router can return them.

### Open questions / risks
- Router failures silently degrade to existing retrieval. A future diagnostics command could expose router health without changing safe default behavior.

## T4 embeddings + seed-expand (2026-06-05)

### Files changed
- `tmf/embeddings.py` — added optional local command embedder and in-memory cosine ranking, using only Python stdlib.
- `tmf/retrieve.py` — `retrieve_text` keeps lexical behavior first, then optionally adds embedding-selected fresh seeds plus fresh call-edge neighbors when `TMF_EMBED_COMMAND` is configured.
- `tests/test_embeddings.py` — added T4 acceptance coverage.

### Behavior
- Default/off behavior is unchanged: without `TMF_EMBED_COMMAND`, embedding code is a no-op and retrieval remains lexical.
- Embedder is pluggable via `TMF_EMBED_COMMAND`; there is no network service, vector database, or new dependency.
- External embedder input is sent as JSON field `texts_untrusted_data`.
- Embeddings only choose candidate seeds. They do not alter claim text, evidence, trust, confidence, provenance, freshness, or parser behavior.
- Only fresh claims can become embedding seeds.
- Seed expansion follows only fresh stored call-edge claims, and neighbor claims must also be fresh.
- Results still flow through existing thin rendering.

### Acceptance tests added
- Embeddings off: repeated default CLI retrieval without `TMF_EMBED_COMMAND` returns equivalent JSON payloads.
- Configured fake local embedder: lexical-miss query `payments` selects semantic seed `charge` and expands along fresh edge to `main`; result remains thin and contains no untrusted quoted text.
- Stale node exclusion: after editing the semantic target file without re-deriving, the stale claim is not returned as an embedding seed.

### Test result
```text
Ran 50 tests in 6.150s

OK
```

### Red-line self-check
- Embeddings are a derived seed-selection aid only, not a second truth source.
- No confidence/evidence/trust/provenance/feedback code changed.
- No external packages, network clients, or vector DB introduced.
- Stale claims are excluded before ranking/return; stale edge neighbors are also excluded.
- Thin/default payload still omits thick body and untrusted quoted provenance text.

### Open questions / risks
- Current embedding ranking is ephemeral/in-memory. This avoids stale persistent vector risk, but does not provide warm-time vector caching. If a future persistent embedding index is added, it must bind to the same freshness keys and prove stale vectors cannot surface stale seeds.
- `TMF_EMBED_COMMAND` timeout is fixed at 10 seconds and silently falls back to lexical behavior on failure. This preserves safety/default behavior but may hide embedder misconfiguration from users unless a diagnostics command is later added.

## T3 class nodes (2026-06-05)

### Files changed
- `tmf/extract.py` — added `ClassNode` and `extract_classes` using the same token-stream span hash rules as function hashing.
- `tmf/ids.py` — added `stable_class_claim_id(path, qualname)`.
- `tmf/schema.py` — added `"class"` to `ClaimScope`.
- `tmf/freshness.py` — class-scoped claims recompute class span hash by `binding.qualname` / `body.qualname` fallback.
- `tmf/derive.py` — derives class claims alongside file and function claims.
- `tests/test_class_nodes.py` — added class-node acceptance coverage.

### Behavior
- Python `ClassDef` nodes are stored as `scope="class"` structure claims with one binding using `fn_hash` storage for the class span token hash.
- Class span intentionally includes method bodies. This is safe over-invalidation: editing a method body stales both the method function node and containing class node.
- Class claim freshness still uses working-tree blob plus token-stream span hash; commit remains only an anchor.

### Acceptance tests added
- Class claim is derived, visible in thin retrieval, and fresh.
- Editing a class/method body stales the class node with `class_hash mismatch`.
- Deleting a class and retrieving the path reconciles/removes the tombstone claim.

### Test result
```text
Ran 47 tests in 5.683s

OK
```

### Red-line self-check
- Function hashing behavior is unchanged; class hashing reuses the existing token stream rules.
- Class over-invalidation is explicit and conservative.
- Intent/provenance/model/feedback/confidence behavior was not changed.
- No parser edge behavior was changed.

### Open questions / risks
- Class claims currently use the existing `Binding.fn_hash` field to store class span hash to keep schema diff small. Freshness distinguishes class claims by `claim.scope == "class"`. A future schema could rename this to a generic `node_hash`, but that would be a broader migration and was intentionally avoided.

## T2 thin cross-file graph neighbors (2026-06-05)

### Files changed
- `tmf/explain.py` — thin/explain graph now augments function graph neighbors from fresh stored call-edge claims.
- `tests/test_retrieve_thin.py` — added cross-file caller thin-view acceptance coverage.

### Behavior
- Thin view can show cross-file callers/callees from fresh `body.edge_kind == "calls"` edge claims, even when the function claim's original `body.graph` was derived before that opposite file was read.
- Stale edge claims are not listed as neighbors.
- Thin view adds `unresolved_call_count` and `graph_coverage`; coverage is `"complete"` only if the warm manifest is complete, otherwise `"partial"`.
- No source/provenance quoted text or thick body is exposed in thin.

### Acceptance tests added
- Derive `b.py`, then `a.py` where `a.main -> b.helper`; retrieving thin `b.py` shows `helper.callers[0].source_qualname == "main"` from the stored cross-file edge.
- After editing `b.helper`, the stale edge is no longer listed.
- The thin view reports `graph_coverage == "partial"` and an unresolved-call count.

### Test result
```text
Ran 44 tests in 5.743s

OK
```

### Red-line self-check
- Only fresh edge claims are exposed as graph neighbors.
- Partial graph coverage remains explicit unless warm is complete.
- Conservative parser behavior is unchanged; this only renders already-derived resolved edges.
- Thin payload still omits thick body and untrusted quoted provenance text.

### Open questions / risks
- `source_qualname` for edge-derived callers currently comes from the caller binding qualname. This is correct for current call-edge shape; if future edge claims bind more than caller/callee, source endpoint metadata may need to move explicitly into `body`.

## T1 warm / full-repo derive + reverse caller index (2026-06-05)

### Files changed
- `tmf/warm.py` — added `warm_repo`, warm manifest, complete reverse caller index, and helpers.
- `tmf/retrieve.py` — `reverse_callers` now uses a complete warm index when valid, otherwise falls back to the existing lazy partial scan.
- `tmf/cli.py` — added `tmf warm --repo <repo>` JSON command.
- `tests/test_warm.py` — added T1 acceptance coverage.

### Behavior
- `warm_repo(repo)` eagerly derives all repo-local `.py` files using the same `derive_claims_for_path` path as lazy reads.
- Warm is incremental: if a file's working-tree blob is unchanged and its claims are fresh, it is skipped.
- Reverse caller index is a cache only. `reverse_callers` still re-checks edge claim freshness before returning indexed callers.
- `coverage` is upgraded to `"complete"` only when the warm manifest exactly matches the current repo-local `.py` file set and working-tree blobs; otherwise the existing lazy path returns `"partial"`.
- If the complete index file is missing, invalid, or stale, `reverse_callers` degrades to lazy partial scan.

### Acceptance tests added
- Warm makes `reverse_callers` complete and indexed callers match the lazy fresh-caller set.
- Removing the index falls back to lazy partial behavior with the same fresh callers.
- Running warm twice makes the second run a no-op (`derived=0`, all files skipped).
- After editing one file, incremental warm derives only that file.
- Stale warm index causes `reverse_callers` to return partial rather than pretending complete.
- CLI `tmf warm --repo` emits JSON and writes `.tmf/warm_manifest.json` plus `.tmf/reverse_callers.json`.

### Test result
```text
Ran 43 tests in 4.856s

OK
```

### Red-line self-check
- Freshness remains working-tree `blob_sha` / `fn_hash`; warm stores blobs only to decide cache completeness and does not use commit as freshness.
- Edge index is not a second truth source; indexed edge claims are rechecked with `check_freshness` before return.
- Confidence, feedback, hunch, provenance, model verification, and conservative call parsing were not changed.
- Complete coverage is only reported when the current `.py` file set exactly matches the warm manifest; otherwise coverage remains partial/lower-bound.

### Open questions / risks
- `.py` discovery currently uses `Path.rglob("*.py")` and skips `.git/` / `.tmf/`; it may include virtualenv or generated Python files if they live inside the target repo. Future work may need a conservative ignore mechanism, but this was not added to avoid changing project policy.
- Complete means complete for repo-local Python files visible to this scanner and current conservative parser, not semantically complete for dynamic/runtime calls.

## 2026-06-10 — MCP ergonomics Phase A for adoption measurement

Scope: delivery/retrieval presentation only. No engine semantics, node/edge extraction, freshness, task golden, or benchmark policy changes.

Changes:
- Added `tmf_context(question, max_chars?)` MCP tool as the suggested first investigation entrypoint. It builds a deterministic thin bundle from lexical retrieval plus bounded fresh reverse graph expansion (`callers`, `readers`, `writers`, `subtypes`) with anchors, partial coverage labels, max-char truncation, and no claim bodies/source text.
- Added name addressing for `tmf_callers`, `tmf_readers`, `tmf_writers`, and `tmf_subtypes`: callers can pass `qualname` plus optional `path` instead of a `claim_id`; `claim_id` remains compatible. Ambiguous names return candidate IDs/anchors and never guess.
- Moved the repeated honesty framework out of per-call payloads and into MCP tool descriptions. Payloads retain only semantic labels such as `coverage`, `stale`/freshness data, and explicit `action_hint` stop guidance.
- Reverse/no-edge and ambiguous-addressing responses now include stop-oriented hints: pick a concrete candidate, read the source anchor, or accept static uncertainty rather than continuing blind search.

Offline protocol coverage:
- `tests/test_mcp_ergonomics.py` covers: unique name lookup, ambiguous-name candidate returns, claim_id compatibility, `tmf_context` determinism, thin discipline, `max_chars` truncation, and payload slimming.
- Existing MCP protocol/security tests updated to include `tmf_context`.

Payload byte comparison on the same fixture/query (`helper caller`, limit=3):
- Previous payload with repeated `framework`: 3133 bytes.
- New slim payload: 2841 bytes.
- Saved: 292 bytes per `tmf_retrieve` response on this fixture.

Phase boundary:
- This package is Phase A only. Do not run Phase B three-arm LLM A/B until external review/approval releases it.

## Final adjudication Phase A — delivery economics, mechanical interface, contracts (2026-06-11)

Scope: Phase A only. This package does **not** enter Phase B and does not tune any measurement results.

### A1 Delivery economics
- `tmf_context` now defaults to `max_chars=3000` instead of large context envelopes.
- Retrieval candidate count is budgeted before expensive explain/reverse-edge work:
  - `<=3000` chars: 8 candidates
  - `<=6000` chars: 12 candidates
  - larger explicit budgets: 16 candidates
- Truncation is deterministic and linear: keep early relevant claims as full payloads where possible, then retain addressable `tmf_explain` stubs, and stop before exceeding budget.
- Regression fixture (`reports/final裁决-a/context-byte-compare.log`): old 12000-byte envelope 11829 bytes; new default 3000-byte envelope 2993 bytes; saved 8836 bytes.

### A2 Mechanical interface layer
- Added Python `function_interface(source, function_node)` with mechanical facts only: signature, params, return annotation/shape, decorators, async/generator flags, observed raises, and coarse side effects.
- Added Java `java_method_interface(source, method_node)` for tree-sitter Java method/constructor interface facts: signature, params/types, return type, throws, modifiers, annotations.
- Function/method node bodies now expose interface facts for downstream consumers.

### A3 Contract layer
- Added claim scope `contract` and stable contract ids via `stable_contract_claim_id(path, qualname)`.
- Added Python contract derivation for non-trivial functions from mechanical interface facts; bindings use function body hash so body edits stale the contract.
- Added Java method/constructor contract derivation from mechanical Java interface facts; no semantic purpose is invented.
- Contract payload includes `_contract_checks`, slot confidence, observed evidence, anchors, and explicit notes about offline mechanical limits.

### A4 External-battlefield preparation
- Deferred to the Phase A handoff package: no Phase B run was started in this window.

### A5 Guardrails and regression
- Added `tests/test_final_contracts.py` for interface facts, contract checks, stale-on-body-change, default context budget/stubs, retrieval budget limits, and Java interface facts when tree-sitter Java is available.
- Final verification:
  - `python3 -m unittest discover -s tests -q` → `Ran 115 tests in 47.159s OK`
  - `bash scripts/verify_java_offline.sh` → `JAVA OFFLINE VERIFY: PASS`

## Final adjudication A4+ and S supplement (2026-06-11)

### A4+
- Added semantic contract sanitizer (`tmf/contracts.py`) and validation stage `_contract_checks`.
- Semantic contract model candidates are treated as untrusted data; accepted slots remain attributed/inferred and confidence-capped at <=0.6.
- Sanitizer cross-examines parameters, raises/throws, return-value claims, and no-side-effect claims against mechanical interface facts and resolved write edges.
- External battlefield prepared on `pypa/pip` @ `486db076e2f4f0bf6780c24cd487f09dc2a14015` with 30 mechanically validated tasks.
- DS4 Pro true-model sample set produced 20 semantic contract claims; all remained inferred and sanitizer-capped.
- One self-validation class freshness FP was disclosed as a measurement/expected-stale attribution issue, not suppressed.

### S supplement
- Added resumable true-model contract warming: `tmf warm --contracts --contract-command <cmd>`.
- Contract warming writes one record per function under `.tmf/contract_warm/records`, is safe to resume, records elapsed time/call outcomes, and writes offline-review samples with embedded source spans under `.tmf/contract_warm/samples`.
- External coverage now reports contract counts split by `contract_version` (`contract.v1.mechanical` vs `contract.v2.semantic_sanitized`).
- `function_interface` side-effect limits: the function interface itself exposes signature/return/raise/decorator facts; side-effect contradiction checks depend on separately resolved conservative `writes` edges supplied to the sanitizer. If static write resolution does not see a write, sanitizer cannot reject a model's no-side-effect claim on that basis alone.
- Packaging hygiene: offline Java wheels in `vendor/wheels` are intentionally included for reviewer-side `scripts/verify_java_offline.sh`.

## 阶段 B 终局（2026-06-12）

- Phase B v3 final three-arm LLM agent A/B completed measurement-only on external pip battlefield.
- Battlefield: `vendor/external_battlefield/pip`, commit `486db076e2f4f0bf6780c24cd487f09dc2a14015`, tracked `.py` files 635, manifest sha `bd9975b25f92daf45f0f7c94a41678fd26cc9987d71a5e42b5dcd61800f730b7`.
- Prewarmed contract store counts: `contract.v2.semantic_sanitized=5141`, `contract.v1.mechanical=253`; warm status `partial` (`succeeded=5177`, `failed=254`). `TMF_MODEL_COMMAND` was unset; no in-run model warming.
- Protocol: 30 tasks, 3 arms (`baseline`, `tmf-offered`, `tmf-first`), reps=1, `qwen3.5-plus`, temperature 0, max_tool_calls=15, max_model_turns=18, timeout=150s.
- Completion: 90/90 rows, traces 90/90. Failures retained as measured: `max_tool_calls_exceeded=5`, `timeout=3`.
- Category means (answer / surfaced / total tokens):
  - graph-shaped baseline `1.000 / 1.000 / 3921.6`; tmf-offered `1.000 / 1.000 / 5958.7`; tmf-first `1.000 / 1.000 / 7792.9`.
  - adversarial baseline `0.800 / 1.000 / 38221.3`; tmf-offered `0.700 / 1.000 / 87928.6`; tmf-first `0.700 / 1.000 / 41253.4`.
  - open baseline `1.000 / 1.000 / 5520.7`; tmf-offered `1.000 / 1.000 / 10271.9`; tmf-first `1.000 / 1.000 / 15675.3`.
- Primary execution clause result: E1 answer(tmf-first - baseline) mean diff `-0.03333333333333333`, nonzero pairs 3, wins 1, losses 2, nonzero winrate `0.3333333333333333`; E2 total tokens mean diff `+5686.0` vs baseline mean `15887.866666666667` (not cheaper / worse).
- Execution conclusion: `agent 运行时记忆假设在本协议下未获支持`.
- Outputs: `bench/agent_ab/llm_run_v3_20260612T124957/report_llm_v3.json`, `report_llm_v3.md`, traces at `traces/agent_ab_llm_v3_20260612T124957/`, golden claims at `golden_contract_claims.json`.


## Window 1/4 — D1/D4/D3/D2 maintenance (2026-06-12)

Scope: window 1 only. This change does not add Java step2+, SCIP/LSP semantics, multi-language expansion, new node/edge families, or Phase B/v3 review work.

### D1 defect fixes
- Python nested class extraction now treats classes declared inside functions as function-scoped qualnames such as `outer.Inner`, matching existing function qualname scope rules.
- Mechanical contract facts remain interface-derived and are confidence-capped at `<=0.6`; they are not promoted to semantic proof.
- `self.method()` resolution stays conservative: direct same-class methods win; inherited methods link only when the base chain resolves uniquely inside the current v1 resolver scope (same-file bases in window 1). Cross-file inherited method resolution via unique imports is backlog, not claimed here.
- `imported_module.func()` direct top-level calls are covered by regression tests and only resolve when the imported module target is unique and local.

### D4 rename identity
- Pure rename migration is allowed only for exact blob identity with one old missing path and one current path.
- Rename+edit and ambiguous same-blob copies do not migrate identity; old-path claims are deleted as tombstones and current files are rederived.
- Migrated claims remap node/contract ids, update `Binding.path`, and rebind edge claim bodies and ids through the endpoint id map.

### D3 metrics/stats/FIELD_TEST harness
- Metrics/stat tests cover rename migration and mass-invalidation counters.
- Added `scripts/field_test_harness.py`, an offline plan-only harness for later field testing. It writes command templates and capture fields; it does not clone, fetch, run external reconnaissance, or warm models.

### D2 documentation honesty
- README/DESIGN/CHANGELOG/CHANGES disclose the conservative limits: fresh means all current bindings match the worktree, mechanical contracts are capped observations, rename identity is exact-blob-only, and FIELD_TEST is not started in this window.

## Window 2/4 — J1 Java calls (2026-06-12)

- Added conservative Java `calls` edges for syntactic method invocations.
- Resolved cases only:
  - same-class `m()` when exactly one same-class method candidate matches;
  - `this.m()` under the same uniqueness rule;
  - explicit-import type static call `Util.f()` when `Util` is a unique explicit import and `f` resolves to one imported top-level type method.
- Unresolved by design:
  - variable/unknown receivers such as `u.f()`;
  - overloaded or ambiguous same-name methods;
  - parent/superclass method calls, deferred to the override/semantic window.
- Java call edges reuse the existing `calls` edge kind and reverse callers API, with `body.language="java"`, observed evidence, partial coverage, and precise Java method anchors.
- Validation checkpoint: `python3 -m unittest tests.test_java_calls tests.test_java_inherit tests.test_java_nodes -q` → 14 tests OK; full suite `python3 -m unittest discover -s tests -q` → 139 tests OK.

## Window 2/4 — J2 Java reads/writes (2026-06-12)

- Added conservative Java field `reads`/`writes` edges, adapted onto the existing read/write edge claim and reverse reader/writer APIs.
- Resolved cases only:
  - `this.field` reads/writes to same-class fields;
  - bare same-class fields when not shadowed by a local variable or parameter;
  - explicit-import type field access such as `Config.LIMIT` when `Config` is a unique explicit import.
- Unresolved by design:
  - local/parameter shadowing;
  - variable or unknown receivers such as `other.value`;
  - external/JDK/wildcard import or ambiguous field references.
- Java field edges carry `body.language="java"`, observed evidence, partial coverage, and Java method/field anchors.
- Updated Java node tests so Java node assertions filter syntactic node claims rather than assuming no Java edge claims exist.
- Validation checkpoint: Java calls/fields/inherit/nodes suite → 17 tests OK; full suite `python3 -m unittest discover -s tests -q` → 142 tests OK; `scripts/verify_java_offline.sh` → PASS.

## Window 2 continuation: F0 J2 guard + J4/J5/J6 Java completion

- F0 J2 field guard: explicit Java variable receiver field accesses (`x.field`) are now unresolved with `java_variable_receiver_field_not_resolved`; same-class binding is limited to `this.field` and unshadowed bare fields. Added regression fixture for `other.count` not cross-binding to `A.count`.
- J4 Java Spring route API nodes: added conservative tree-sitter extraction for literal `@GetMapping`, `@PostMapping`, `@PutMapping`, `@DeleteMapping`, and `@RequestMapping`. Literal class-level prefix plus method-level path is concatenated; non-literal/dynamic paths do not fabricate API nodes. Java API claim bodies include `language`, `http_methods`, `route_path`, and handler qualname.
- J5 Java `uses_type` edges: added `uses_type` edge IDs, derivation, graph backfills, and lazy reverse `reverse_used_by_types`. Resolution is limited to same-file types and explicit-import unique types. JDK/external/wildcard/unknown/ambiguous types remain unresolved with reasons.
- J6 Java contracts: fixed semantic Java contract branch so sanitized model output is stored as inferred `contract.v2.semantic_sanitized` instead of being mislabeled observed/mechanical. Java contract sanitizer now receives method graph writes, allowing false no-side-effect claims to be rejected. Added adversarial Java tests for fabricated throws, fake no-side-effect with writes, void return lies, confidence cap, stale body hash, and trivial-method skip.

Validation so far:
- `python3 -m unittest tests.test_java_fields_edges tests.test_java_api_nodes tests.test_java_uses_type tests.test_java_contracts_window2 tests.test_java_calls tests.test_java_inherit tests.test_java_nodes tests.test_java_override tests.test_contract_sanitizer tests.test_final_contracts -q` -> 40 tests OK.

## Window 4/4 robustness closeout (2026-06-15)

### F-backfill from Window 3
- Documented Window 3 R1/R2/R3/S semantics as final project behavior: env/config read edges, Spring DI `injects`, Kafka topic-mediated pub/sub, and the optional semantic-resolved tier.
- R2/R3 remain `attributed` with confidence capped at `<=0.6`; framework convention and annotation inference are never promoted to `observed`.
- SCIP/semantic-resolved remains a separate tier: external indexer resolution is neither syntactic direct evidence nor framework inference. The interface skeleton and degraded/default-off behavior are implemented; true `scip-python` end-to-end consumption still requires Kyle to verify in an environment with that indexer installed.

### W1 foreign `.tmf` trust boundary
- Added repository-local `.tmf/local_identity.json` plus machine-hash identity checks. A pre-existing `.tmf/claims` directory without this local identity is marked foreign via `.tmf/foreign_store.json`.
- Foreign claims are surfaced as `source_provenance.trust = unverified_foreign`, trust label `unverified_foreign`, and effective confidence `0.0` in explain/thin views.
- Retrieval treats unverified foreign claims as stale and performs read-through re-derive from source. Re-derived claims are stamped `locally_derived` and replace foreign cache content. The foreign cache never gets to preserve its self-asserted confidence or verification status.
- Added `_trust_boundary_checks`: a malicious fresh-looking foreign claim asserting a mutating function is verified pure is marked unverified, then corrected by local re-derivation. Locally generated stores remain locally derived.

### W2 scale benchmark measurement
- Added deterministic scale benchmark `bench/scale/gen.py` and report outputs under `reports/window4/scale/`.
- Measured two CI-friendly synthetic sizes in this environment:
  - 200 functions / 4 files / 207 claims: warm 1.6544s, incremental warm 0.6236s, retrieve 0.0325s, reverse 0.0324s, store 490356 bytes, maxrss 26572 KB.
  - 1000 functions / 20 files / 1039 claims: warm 8.6149s, incremental warm 2.6938s, retrieve 0.0890s, reverse 0.1342s, store 2467012 bytes, maxrss 41516 KB.
- This is measurement, not optimization. Observed limitation remains: reverse/query paths can still scan claims when complete indexes are absent/inapplicable; 50k-node enterprise behavior is not claimed.

### W3 concurrent writer safety
- Added a repository-local interprocess `.tmf/.lock` using `fcntl.flock` around warm/read-through writes.
- Claim/metadata writes use temp-file plus atomic replace so readers should see old complete files or new complete files, not half-written JSON.
- This is a corruption guard, not full snapshot isolation. The documented guarantee is conservative: concurrent warm writers do not corrupt claim files; full multi-writer database semantics are out of scope.
- Added `tests/test_concurrency.py`: two concurrent warm processes complete without deadlock and leave parseable claim files.

### W4 retrieval relevance measurement
- Added `bench/retrieval/queries.jsonl` with 20 natural-language diagnostic queries and `bench/retrieval/eval.py` for deterministic recall@k/MRR measurement.
- Report output: `reports/window4/retrieval/`.
- Observed result at k=10: recall@10 = 0.50, MRR = 0.34541666666666665.
- Weak classes are explicitly preserved: pure semantic/descriptive queries and ignored-path documentation/script queries under `.tmfignore` miss often. This is diagnostic evidence for future retrieval work, not a hidden failure.

### W5 YAML / SQL nodes
- Added stdlib-only conservative YAML config support for a simple mapping/scalar subset in `.yaml`/`.yml`. Lists, anchors/tags, multiline scalars, duplicate keys, tabs, and ambiguous inline comments degrade to no YAML config nodes.
- YAML config nodes reuse config semantics: canonical value hash, source-bound freshness, key-path qualnames, and line anchors.
- Added conservative SQL declaration nodes for standalone `.sql` `CREATE TABLE` / `CREATE VIEW` clauses. Dynamic SQL strings embedded in code are intentionally not parsed.
- Added `tests/test_yaml_sql_nodes.py` covering YAML value staleness, complex YAML degradation, SQL table/view nodes, and dynamic SQL skip behavior.

### Validation evidence
- Targeted Window 4 + Window 3 regression: 15 tests OK.
- Full unit suite: `Ran 168 tests in 20.636s OK` (ResourceWarnings only).
- Java offline verifier: `JAVA OFFLINE VERIFY: PASS`.
- Held-out validation: PASS, precision/recall 1.0/1.0.
- Self validation initially hit process SIGKILL/SIGTERM when copying/scanning oversized generated directories. Harness was fixed to respect `.tmfignore`/skip generated heavy directories; sample-limit 3 self validation then PASS: 3012 claims, precision/recall 1.0/1.0, fp/fn 0/0.

### Known limits after Window 4
- True SCIP/scip-python semantic indexer consumption is still not end-to-end verified in this environment.
- Scale measurement covered 200 and 1000 synthetic functions here, not 20k/50k due runtime/resource constraints.
- Self validation final pass used `sample-limit=3` after larger samples were killed by runtime limits.
- Retrieval relevance is weak for some natural-language queries; current retrieval remains lexical/graph-seeded rather than a full semantic search engine.

## Final hardening tail package (2026-06-16)

### W1 depth-defense: redact unverified foreign assertion text in thin/default views
- `unverified_foreign` claims now replace their default `claim` text with `[unverified foreign claim — re-derive before trusting]` in `explain_claim()` and therefore in `thin_view()`.
- The original foreign assertion text is not emitted by thin view. Full explain keeps it only under `raw_foreign_claim_untrusted_data` for explicit audit use.
- Locally derived claims are unchanged and continue to display their normal claim text.
- Added trust-boundary assertions proving the malicious fixture text `verified pure` does not appear in default explain/thin claim fields while the trust label and placeholder do appear.

### Final hardening validation
- Trust boundary test: 2 tests OK.
- Targeted regression: 15 tests OK.
- Full unittest: 168 tests OK.
- Java offline verifier: `JAVA OFFLINE VERIFY: PASS`.
- Heldout validation: PASS, precision/recall 1.0/1.0.
- Self validation: sample-limit 3 PASS, precision/recall 1.0/1.0, fp/fn 0/0.
## Versioned dual-binding API relationships + WebFlux functional routes (2026-08-09)

- Advanced serialization to `tmf.schema.v2`; readers continue to accept v0/v1. Added optional binding role, exact line anchor, and hash-kind fields. Missing fields retain legacy semantics and are never inferred.
- Added a new `claim_api_rel_*` identity namespace derived from route source + verb + literal URI + resolved handler node ID. Existing `claim_api_*` IDs are unchanged and are not silently reinterpreted or rewritten.
- Dual API relationships carry independent `route_declaration` and `handler` bindings with separate hashes/freshness/deletion. Route-source reconciliation owns tombstones; handler changes/deletion force route re-derivation.
- Added exact-import Spring WebFlux functional extraction for direct literal routes and flat literal builder chains. Unsupported/ambiguous forms emit no API relationship and no runtime call.

Compatibility matrix: v0/v1 claims read unchanged; new ordinary/annotated Python and Java claims serialize as v2 but keep legacy ID and single-binding behavior; only new resolved functional relationships use dual bindings and the new ID namespace. No automatic persisted-cache migration is performed.

### Java external semantic facts v1
- Added a default-off provider-neutral compiler/JDT/SCIP ingestion contract with strict provenance, content/build/classpath fingerprints, deterministic overlay IDs, fail-closed reconciliation, and explicit degraded reasons.
- Semantic evidence remains attributed and separate from syntax. True JDT end-to-end is unavailable locally; offline executable fixture verification is provided.

## Unreleased — complete-Spring declaration foundation
- Added bounded declaration-only metadata for exact explicitly imported profile, condition, scope, lazy, depends-on, primary, and transactional annotations.
- Added literal `readOnly`, `Propagation`, and `Isolation` transaction attributes without runtime/proxy claims.
- Exact-type source bean resolution may select `@Primary` only when exactly one candidate is primary; qualifiers retain precedence and all remaining ambiguity is unresolved.
- Added explicit deferred reasons for decoys, classpath/meta/composed semantics, SpEL/dynamic values, and unsupported transaction attributes.

- Added conservative Spring Data repository declaration metadata (exact repository inheritance/generic bindings, method declarations, and literal `@Query` opacity/native flag), with unresolved ambiguity and decoy handling.
- Added bounded MyBatis declaration metadata for exact-import `@Mapper` interfaces and literal exact-import `@Select`/`@Insert`/`@Update`/`@Delete` methods. SQL remains opaque; dynamic/constant/concatenated values, providers, scripts, foreach, decoys, and composed annotations fail closed. No execution/database/mapping/transaction/call semantics are inferred, and XML linkage is explicitly deferred pending honest independent dual bindings and exact anchors.

## Unreleased — persistence-adapter production qualification

- Added independent held-out Maven and Gradle fixture repositories under `fixtures/java-persistence-heldout/`; fixture source is not copied from unit tests and includes exact imports, adversarial decoys, providers, and dynamic values.
- Added `tools/verify_java_persistence_qualification.py`, an offline deterministic two-run verifier for JPA/Jakarta, Spring Data, and MyBatis annotation metadata. It gates expected resolution/unresolved reasons, precision, freshness, mutation, deletion, stable IDs/anchors, and absence of fabricated SQL/table/read/write/runtime semantics.
- Added checked evidence under `reports/java-persistence-qualification/` and updated the persistence compatibility matrix and enterprise roadmap. Java relationship coverage remains partial; MyBatis XML and broad production qualification remain deferred.
- Migration: none. Metadata is additive on existing Java node claims and keeps existing IDs/bindings.
- Rollback: remove the held-out fixture/verifier/report/docs package. No cache migration or runtime setting requires reversal; existing declaration metadata behavior is unchanged.
## Java Kafka bounded source-evidence phase

- Added exact-import, source-only Spring Kafka topic edges for literal `@KafkaListener` topics/group IDs and exact two-argument `KafkaTemplate.send` literal topics. Retains payload type only when mechanically unambiguous, preserves existing IDs, and adds method anchors/hash freshness.
- Added decoy, dynamic, overload, cross-file, mutation, and deletion coverage plus an explicit compatibility declaration. Runtime delivery, serializers, partitions/keys/headers, broker topology, classpath semantics, composed annotations, and dynamic expressions remain deferred.

- Added a conservative Spring Cloud OpenFeign declaration adapter: exact explicit imports and literal service/url/path plus literal Spring HTTP method/path metadata only, represented with stable dual-binding API relationships and independent freshness/deletion. Dynamic, composed, inherited, ambiguous and unsupported forms fail closed; runtime RPC semantics remain out of scope.

## Java Spring Cache bounded declaration phase

- Added exact-import, literal-only `@Cacheable`, `@CachePut`, and `@CacheEvict` method metadata with stable IDs, precise annotation anchors/token hashes, opaque literal SpEL fields, overload-safe source identity, freshness/deletion reconciliation, explicit unresolved reasons, held-out Maven/Gradle fixture, offline qualification, and fail-closed negative tests.
- No runtime call edge or CacheManager invocation is emitted; runtime cache effects remain explicitly out of scope.

## Conservative Spring scheduling declaration metadata

- Added exact-explicit-import, source-method-only `@Scheduled` metadata for literal `fixedRate`, `fixedDelay`, `initialDelay`, `cron`, `zone`, and `timeUnit` values.
- Added overload-safe stable IDs, exact annotation anchors/token hashes, normal freshness/deletion reconciliation, and explicit fail-closed reasons for dynamic, conflicting, unsupported, ambiguous, and same-simple-name cases.
- Added focused adversarial tests and an independent held-out Maven/Gradle fixture/offline verifier. No schedule calculation, invocation/runtime execution, timezone semantics, concurrency, proxying, `EnableScheduling`, inheritance/composition, placeholders, or SpEL is inferred.

## 2026-08-09 — Conservative Spring transaction declaration metadata
- Added exact-import, direct class/method `@Transactional` source metadata for mechanically parseable literal enum/boolean/int/string/class-literal attributes.
- Added overload-safe stable IDs, exact annotation anchors/token hashes, unresolved fail-closed diagnostics, adversarial tests, independent Maven/Gradle fixture, offline verifier/report, and compatibility documentation.
- Explicitly does not infer transaction boundaries, database/rollback effects, proxy/runtime propagation, manager resolution, or calls.

## Spring Async declaration adapter (2026-08-09)
- Added exact explicit-import, direct class/method `@Async` declaration claims with stable overload-safe owner IDs, annotation anchors/token hashes, and optional opaque literal executor qualifier metadata.
- Added fail-closed handling for dynamic/constants/placeholders, wildcard/static/conflicting imports, aliases, decoys, malformed values, ambiguous owners, inheritance/composition and external symbols; no runtime async behavior is modeled.
- Added focused adversarial tests and independent Maven/Gradle held-out fixture plus offline qualification verifier/report.

## Spring Retry declaration adapter (2026-08-09)
- Added exact-import direct source `@Retryable`/`@Recover` declaration claims with stable overload-safe IDs, exact anchors/token hashes, and opaque mechanically parseable literal/class-literal metadata.
- Added fail-closed adversarial tests and independent Maven/Gradle fixture/offline qualification. No retry occurrence, runtime attempt/backoff evaluation, exception matching, recovery dispatch, proxy/AOP, call, inherited/composed, or external semantics are inferred.

## Resilience4j CircuitBreaker declaration adapter (2026-08-09)
- Added exact-import direct source `@CircuitBreaker` declaration claims with required literal `name`, optional opaque literal `fallbackMethod`, stable overload-safe IDs, and exact annotation anchors/token hashes.
- Added fail-closed adversarial tests plus an independent Maven/Gradle held-out fixture and offline qualification report. No circuit state, failure/threshold evaluation, fallback resolution/dispatch, configuration activation, proxy/AOP, call, inherited/composed, expression/placeholder, or external semantics are inferred.

## Resilience4j RateLimiter declaration adapter (2026-08-09)
- Added exact-import direct-source `@RateLimiter` declaration claims with required literal `name`, optional opaque literal `fallbackMethod`, stable overload-safe IDs, exact annotation anchors/token hashes, fail-closed unresolved evidence, and independent Maven/Gradle held-out qualification.


## Resilience4j Bulkhead declaration adapter (2026-08-09)
- Added exact-import direct-source `@Bulkhead` declaration claims with required literal `name`, optional opaque literal `fallbackMethod`, stable overload-safe IDs, exact annotation anchors/token hashes, and fail-closed unresolved evidence.
- Added adversarial mutation/deletion tests plus independent Maven/Gradle held-out fixtures and an offline qualification verifier/report. Runtime concurrency, queueing, isolation, fallback dispatch, configuration, proxy/AOP, calls, inheritance/composition, and external symbols remain deliberately unsupported.

## Resilience4j TimeLimiter declaration adapter (2026-08-10)
- Added exact-import direct-source class/method `@TimeLimiter` claims with required literal `name`, optional opaque literal `fallbackMethod`, stable overload-safe IDs, and exact annotation anchors/token hashes.
- Added fail-closed adversarial coverage and an independent Maven/Gradle held-out fixture/offline qualification report. Timeout/cancellation, future/reactive, configuration, fallback dispatch, proxy/AOP, calls, inheritance/composition, and runtime semantics remain deliberately unsupported.


## Resilience4j Retry declaration adapter (2026-08-10)
- Added exact-import direct-source class/method `io.github.resilience4j.retry.annotation.Retry` claims with required literal `name`, optional opaque literal `fallbackMethod`, stable overload-safe IDs, exact annotation anchors/token hashes, freshness/reconciliation, adversarial tests, and Maven/Gradle held-out qualification.
- Kept this namespace and deterministic declaration kind distinct from Spring Retry `Retryable`; no runtime retries/backoff, exception matching/configuration, fallback dispatch, proxy/AOP, calls, inheritance/composition, or external symbols are inferred.

- Add a bounded Spring Security `@PreAuthorize` declaration adapter. Exact-import direct class/method annotations retain literal expression text opaquely; adversarial or dynamic forms fail closed and no authorization/runtime semantics are inferred.

- Add a bounded Spring Security `@PostAuthorize` declaration adapter. Exact-import direct class/method annotations retain only literal expression text opaquely; dynamic or ambiguous forms fail closed and no authorization/runtime semantics are inferred.

- Add a bounded Spring Security `@PreFilter` method declaration adapter. Exact-import direct methods retain literal `value` and optional literal `filterTarget` opaquely; invalid or ambiguous forms fail closed and no SpEL, filtering, authorization, or runtime semantics are inferred.

- Add a bounded Spring Security `@PostFilter` method declaration adapter with exact-import/literal-only fail-closed handling, stable overload-safe identity, exact token anchors, held-out Maven/Gradle fixtures, and executable qualification evidence.

## Spring Security Secured declaration adapter (2026-08-10)

- Add a bounded `@Secured` declaration adapter with exact-import, literal-role-only fail-closed handling, overload-safe stable identity, exact token anchors, Maven/Gradle held-out fixtures, deletion reconciliation, and executable qualification evidence.

## Jakarta/Javax RolesAllowed declaration adapter (2026-08-10)

- Added bounded, namespace-auditable `@RolesAllowed` declaration metadata for direct exact imports from `jakarta.annotation.security` or `javax.annotation.security`, retaining only literal role strings with overload-safe IDs and exact annotation token anchors/hashes.
- Added adversarial tests and Maven/Gradle held-out qualification. No authorization decision, role hierarchy, proxy/AOP, calls, inheritance/composition, or runtime enforcement is inferred.

## 2026-08-10 — Java extractor structural consolidation

- Removed 95 shadowed top-level definitions from `tmf/java_extract.py` (3,112 source lines). These were an accidentally duplicated earlier extractor block; Python executed only the later definitions, so removal preserves the effective implementation, claim schema, IDs, anchors, metadata, freshness, and reconciliation behavior.
- Added an AST structural regression test that rejects duplicate top-level class/function names before another shadowed block can accumulate.
- Qualification baseline after consolidation: 20/20 existing `tools/verify_java_*_qualification.py` programs passed; Java-targeted tests passed 204/204; full unittest passed 367/367 (the prior documented baseline was 366 before the new structural test); compileall and `git diff --check` passed.
- Limitation: `tmf/java_extract.py` remains a large single-module registry/dispatch surface (4,649 lines after consolidation), and several annotation adapters still contain similar but not byte-identical parsing flows. They were not generalized in this pass because behavioral equivalence across their distinct fail-closed reason strings and accepted attributes was not proven. No new adapter or release was produced.

## Unreleased cumulative Java qualification baseline

- Added a manifest-governed aggregate gate covering **41/41 qualifiers and 589/589 checks**; every verifier owns independent Maven/Gradle source evidence unless an auditable manifest exception is declared.
- Newly accumulated declaration qualifiers are explicitly traceable by manifest key: `bean`, `component`, `configuration`, `configuration_properties`, `controller`, `cross_origin`, `init_binder`, `lazy`, `model_attribute`, `post_construct`, `pre_destroy`, `primary`, `repository_stereotype`, `response_body`, `response_status`, `rest_controller_advice`, `rest_controller`, `scope`, `service`, and `session_attributes`. Their shared fail-closed compatibility boundary is documented in `docs/JAVA_SPRING_DECLARATION_COMPAT.md`; the two composed web stereotypes also retain focused compatibility documents.
- Current full unittest baseline is **455/455 tests**. Compileall, `git diff --check`, and the index-free `python3 tools/verify_java_source_only_smoke.py` export gate pass. Aggregate verifier output is one strict JSON object; default output excludes nondeterministic durations and `--timings` is diagnostic-only.
- README, release evidence, and this change record now identify the state as unreleased and make no commit, tag, package, publication, runtime, or enterprise-wide certification claim.
- `tests/test_run_java_qualifications.py` binds the documentation baseline to `tools/java_qualification_manifest.json`, so qualifier/check/test counts and unreleased status cannot drift silently.
