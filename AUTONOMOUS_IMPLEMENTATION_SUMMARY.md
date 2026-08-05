# TMF v2 Autonomous Implementation Summary

## Status note

This file was rewritten after a stale-summary issue was found, and updated again after the held-out validation bench found then verified a freshness over-invalidation fix. The code, tests, and `CHANGES.md` are the truth source; this document is only a human-readable reconstruction.

Current verified state: T1-T6 are implemented, V1 held-out validation bench is implemented and expanded, the freshness over-invalidation bug found by V1 is fixed, V2 conservative module-level declaration nodes are implemented, V1 embedding/router-off additivity is strengthened against a fixed lexical baseline, V2 JSON/TOML top-level config nodes are implemented, V1 self dogfood validation is implemented, and 66 unittest tests pass. Real TMF dogfood currently reports a suspected class/body insertion freshness over-invalidation defect (precision 0.606, recall 1.000), so API contract nodes were not started.

## Baseline

Starting point for this continuation was `tmf-v2-edge-freshness-reverse-callers`, then T1-T3 were added, followed by T4-T6.

Before T1, TMF already had:
- lazy source-bound claims under `.tmf/`;
- working-tree `file_blob` freshness via `git hash-object`;
- Python function token-stream `fn_hash`;
- conservative Python module-level declaration nodes;
- JSON/TOML top-level config nodes with normalized value hashes;
- multi-binding cross-file calls edge claims;
- per-binding `Binding.qualname` freshness for edge claims;
- lazy `reverse_callers(repo, node_id)` returning fresh callers only and `coverage:"partial"`.

## Red-line invariants preserved

- Freshness remains based on working-tree blob/hash, not commit hash.
- All bindings must be fresh for a claim to be fresh.
- Commit/PR/docstring provenance is attribution only, not a freshness gate.
- Confidence is capped by verification/evidence class, not usage frequency or model self-report.
- Hunches do not become facts.
- Intent without provenance remains low-confidence inferred; provenance can make it attributed but still inferred and capped.
- Edges are created only when conservatively and statically resolved.
- Source/comments/commit/PR/model/router/embedder text are untrusted data, not instructions.
- Thin/default payloads do not include thick body or quoted provenance text.
- Partial/complete coverage is explicit.

## Completed T1 — warm / full-repo derive + reverse caller index

Files:
- `tmf/warm.py`
- `tmf/retrieve.py`
- `tmf/cli.py`
- `tests/test_warm.py`

Summary:
- Added `warm_repo(repo)` and CLI `tmf warm --repo <repo>`.
- Warm traverses repo-local `.py` files using the same `derive_claims_for_path` path as lazy retrieval.
- Warm is incremental: unchanged blob + fresh claims are skipped.
- Added `.tmf/warm_manifest.json` and `.tmf/reverse_callers.json`.
- Reverse index is cache only; callers are still freshness-checked before return.
- `coverage:"complete"` is only returned when the warm manifest matches the current `.py` file set and current working-tree blobs; otherwise reverse callers fall back to lazy `coverage:"partial"`.

Acceptance:
- Warm makes reverse callers complete and equal to lazy fresh callers.
- Removing the index falls back to lazy partial with same fresh callers.
- Second warm is no-op.
- Editing one file derives only that file.
- Stale warm index returns partial, not false complete.

Test at T1:

```text
Ran 43 tests in 4.856s

OK
```

Package:

```text
artifacts/tmf-v2-warm-20260605T014903Z.tar.gz
```

## Completed T2 — thin cross-file graph neighbors

Files:
- `tmf/explain.py`
- `tests/test_retrieve_thin.py`

Summary:
- Thin/explain graph is augmented from fresh stored call-edge claims.
- Stale edge claims are not listed.
- Thin adds `graph_coverage` and `unresolved_call_count`.
- Thin still excludes thick body and untrusted quoted provenance text.

Acceptance:
- Derive `b.py`, then `a.py` with `a.main -> b.helper`; retrieving thin `b.py` shows `helper` has caller `main` from the cross-file edge claim.
- Editing `b.helper` makes that edge stale and removes the caller from thin.

Test at T2:

```text
Ran 44 tests in 5.743s

OK
```

Package:

```text
artifacts/tmf-v2-thin-cross-file-neighbors-20260605T015137Z.tar.gz
```

## Completed T3 — class nodes

Files:
- `tmf/extract.py`
- `tmf/ids.py`
- `tmf/schema.py`
- `tmf/freshness.py`
- `tmf/derive.py`
- `tests/test_class_nodes.py`

Summary:
- Added `ClassNode`, `extract_classes`, and `stable_class_claim_id(path, qualname)`.
- Added `ClaimScope` value `"class"`.
- `derive_claims_for_path` now derives class claims.
- Class span uses the same token-stream span hash rules as functions.
- Class span intentionally includes method bodies. This is conservative over-invalidation: method edits stale the containing class claim.

Acceptance:
- Class claim is derived, visible in thin retrieve, and fresh.
- Editing class/method body stales class claim with `class_hash mismatch`.
- Deleting class removes tombstone claim after path retrieve.

Test at T3:

```text
Ran 47 tests in 5.683s

OK
```

Package:

```text
artifacts/tmf-v2-class-nodes-20260605T015425Z.tar.gz
```

## Completed T4 — embeddings + seed-expand

Files:
- `tmf/embeddings.py`
- `tmf/retrieve.py`
- `tests/test_embeddings.py`

Summary:
- Added optional local command embedder via `TMF_EMBED_COMMAND`.
- Default/off behavior is unchanged and lexical retrieval remains the fallback.
- No network, vector database, or new dependency was added.
- Embedder input is JSON field `texts_untrusted_data`.
- Embeddings only choose candidate seeds; they do not change claims, trust, confidence, evidence, provenance, freshness, or parser behavior.
- Only fresh claims can be embedding seeds.
- Seed expansion follows only fresh call-edge claims, and neighbor claims must also be fresh.
- Results still flow through thin rendering.

Acceptance:
- Embeddings off: default retrieval remains equivalent.
- Fake local embedder: lexical-miss query `payments` selects semantic seed `charge` and expands along a fresh edge to `main`.
- Stale semantic target is not returned as a seed.

Test at T4:

```text
Ran 50 tests in 6.150s

OK
```

Package:

```text
artifacts/tmf-v2-embeddings-seed-expand-20260605T062216Z.tar.gz
```

## Completed T5 — LLM-router seed selection

Files:
- `tmf/router.py`
- `tmf/retrieve.py`
- `tests/test_router.py`

Summary:
- Added optional local command router via `TMF_ROUTER_COMMAND`.
- Default/off behavior is unchanged.
- Router input uses `query_untrusted_data` and `claims_untrusted_data`.
- Router only returns seed claim ids.
- Router does not change trust, confidence, evidence, provenance, freshness, or claim text.
- Only fresh claims are eligible as router seeds.

Acceptance:
- Router off: default retrieval remains equivalent.
- Fake router: lexical-miss query selects `target`; result remains thin, fresh, and trust stays `observed`.

Test at T5:

```text
Ran 52 tests in 7.227s

OK
```

Package:

```text
artifacts/tmf-v2-llm-router-seeds-20260605T062510Z.tar.gz
```

## Completed T6 — PR provenance evidence

Files:
- `tmf/provenance.py`
- `tmf/explain.py`
- `tests/test_model_derive.py`

Summary:
- Added injectable `pr_evidence(...)` with `source_type="pr"`.
- No GitHub/API client was added.
- PR text is stored as `text_untrusted_data`.
- PR evidence is attribution only, not freshness and not behavioral proof.
- Intent claims supported by PR provenance can become attributed (`evidence="inferred"`, verification `attributed_external_provenance`) with confidence capped at 0.6.
- Thin output exposes PR URL ref, not PR quoted text.

Acceptance:
- Injected PR provenance supports an intent claim and caps model raw confidence 0.99 down to <=0.6.
- Claim remains inferred; it does not become observed or verified.
- PR-only private marker text does not leak into thin output, while the PR URL ref is visible.

Test at T6:

```text
Ran 53 tests in 6.799s

OK
```

Package:

```text
artifacts/tmf-v2-pr-provenance-20260605T062910Z.tar.gz
```

## Final verified state

Final full suite:

```text
Ran 53 tests in 6.725s

OK
```

Final T4-T6 handoff package:

```text
artifacts/tmf-v2-t4-t6-handoff-20260605T062910Z.tar.gz
```

## Completed V1 — held-out validation bench and freshness fix

Files:
- `tmf/validation.py`
- `tmf/freshness.py`
- `tests/test_validation.py`
- `tests/test_freshness_over_invalidation.py`
- `reports/heldout-validation-current-fixtures/report/heldout-validation.json`
- `reports/heldout-validation-current-fixtures/report/heldout-validation.md`

Summary:
- Added an offline deterministic held-out validation bench that warms fixture repos, applies known perturbations, reports freshness precision/recall, audits source/provenance support, audits invariants, checks reverse-caller drift, and checks degrade-to-source hints/anchors.
- Initial bench run found a real over-invalidation bug: file-level blob mismatch made same-file unrelated functions and comment-only changes stale despite unchanged endpoint token hashes.
- The bug was then fixed surgically in `check_freshness`: file-level bindings still stale on blob mismatch; node-level bindings with `fn_hash` use blob equality only as a fast fresh short-circuit, and otherwise recompute endpoint hash before deciding stale.

Acceptance:
- Same-file changed function stales only that function, not untouched sibling.
- Comment-only and indent-width changes leave function claims fresh.
- Real function body changes still stale the function.
- File-level claims still stale on any file byte change.
- Cross-file edge stales only when caller/callee endpoint hash changes, not when unrelated functions in endpoint files change.
- Rename/delete reconciliation still passes.
- Held-out validation now passes with freshness precision 1.0, recall 1.0, invariant violations 0.

Final full suite:

```text
Ran 59 tests in 7.573s

OK
```

## Completed V2 — module-level Python declaration nodes

Files:
- `tmf/extract.py`
- `tmf/ids.py`
- `tmf/freshness.py`
- `tmf/derive.py`
- `tests/test_declaration_nodes.py`

Summary:
- Added conservative module-level declaration extraction for top-level `Assign`/`AnnAssign`.
- Extracts only uppercase constants and simple config dict declarations.
- Added `stable_declaration_claim_id` and `scope="declaration"` claims.
- Declaration freshness uses the same token-stream span hash rules and per-binding freshness model as function/class nodes.
- Ambiguous/non-top-level declarations are skipped; no new parser and no guessing.

Acceptance:
- Module constant declaration is derived and fresh.
- Changing declaration value stales the declaration.
- Deleting declaration and retrieving path removes the tombstone.
- Expanded held-out validation remains pass.

## Expanded V1 validation bench

The held-out validation bench now also audits:
- cross-file edge lifecycle and multi-binding guard behavior;
- thin/full consistency and thin redaction;
- verification/evidence confidence boundaries;
- provenance not acting as freshness gate;
- embedding/router off additivity;
- warm idempotence/incrementality;
- reverse caller coverage honesty;
- degrade-to-source completeness for stale/low-confidence claims.

Final full suite:

```text
Ran 61 tests in 8.178s

OK
```

## Known hooks / real integrations still pending

- Embeddings are currently a pluggable local command hook and fake-test verified; no real local embedding model has been integrated or benchmarked.
- Router is a pluggable local command hook and fake-test verified; no real router model has been integrated.
- PR provenance is a data structure/factory only; automatic GitHub/PR collection is intentionally not implemented.
- Non-function nodes currently include class only. Config / SQL / API declarations are not implemented.
- Held-out validation is still needed before treating confidence numbers as empirically predictive; fresh+observed should be tested against real correctness, not assumed.

## Process lesson

The stale previous version of this file proves that unattended self-reports can lag behind code. For TMF review, code + tests + generated packages are the authority; prose summaries are useful only when verified against them.

## Completed V1 additivity strengthening + V2 config nodes

Files:
- `tmf/validation.py`
- `tmf/extract.py`
- `tmf/ids.py`
- `tmf/schema.py`
- `tmf/derive.py`
- `tmf/freshness.py`
- `tmf/warm.py`
- `tests/test_config_nodes.py`
- `tests/test_validation.py`
- `README.md`
- `CHANGES.md`

Summary:
- Strengthened embed/router-off validation from self-equality to a fixed lexical baseline for the held-out fixture.
- Added JSON/TOML top-level config nodes with `scope="config"` and `stable_config_claim_id(path, key)`.
- Config hashes are computed from canonical parsed values, not raw text slices.
- Reformatting, whitespace, and object key order changes stay fresh.
- Value changes stale only the affected top-level key.
- Unrelated top-level key changes do not stale a config key.
- Deleted keys reconcile on read-through.
- Invalid JSON/TOML parses produce zero config nodes and no crash.
- Warm now includes JSON/TOML files through the same derive/reconcile path while reverse-caller completeness remains tied to the warm manifest.

Acceptance:
- New `_config_node_checks` bench section passes.
- JSON and TOML tests pass on the current Python runtime.
- Held-out validation remains pass / precision 1.0 / recall 1.0 / property failures 0.
- Full suite passes.

Test result:

```text
Ran 65 tests in 8.449s

OK
```

Held-out report:

```text
Status: pass
Freshness precision: 1.000
Freshness recall: 1.000
Invariant violations: 0
Observed/source support violations: 0
Degrade-to-source failures: 0
Property failures: 0
```

Package:

```text
artifacts/tmf-v2-config-nodes-20260605T131330Z.tar.gz
```

## Completed V1 self dogfood validation — found defect, stopped before API nodes

Files:
- `tmf/validation.py`
- `tests/test_self_validation.py`
- `reports/self-validation-tmf/self-validation.json`
- `reports/self-validation-tmf/self-validation.md`
- `reports/heldout-validation-self-dogfood/report/heldout-validation.json`
- `reports/heldout-validation-self-dogfood/report/heldout-validation.md`
- `CHANGES.md`

Summary:
- Added `run_self_validation(repo_root, out_dir, sample_limit=10)`.
- It copies the target repo to a temporary directory, warms the copy, scans real claims, runs generic invariant/support/thin/degrade/router-off checks, and performs freshness sampling on real function/class/config nodes.
- It emits JSON and Markdown evidence reports.
- On the real TMF repo, dogfood derived 807 claims and reported `status: fail`.
- The fail is from freshness sampling false positives when perturbing class nodes; method/function claims become stale unexpectedly after class-body insertion.
- Other scans were clean: invariant/support/thin/verification/degrade/router-off all had zero failures.
- Per protocol, API contract nodes were not started.

Dogfood result:

```text
Status: fail
Freshness sample count: 10
Freshness sample precision: 0.606
Freshness sample recall: 1.000
Freshness sample fp/fn: 13 / 0
```

Held-out validation after adding dogfood still passes:

```text
Status: pass
Freshness precision: 1.000
Freshness recall: 1.000
Invariant violations: 0
Observed/source support violations: 0
Degrade-to-source failures: 0
Property failures: 0
```

Test result:

```text
Ran 66 tests in 67.446s

OK
```

Next recommended step:
- Treat the dogfood failure as a suspected engine freshness over-invalidation bug.
- Add a targeted regression for class-body insertion shifting nested method spans.
- Only after review/fix should API contract nodes resume.
