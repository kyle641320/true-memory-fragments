# TMF Changes

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
