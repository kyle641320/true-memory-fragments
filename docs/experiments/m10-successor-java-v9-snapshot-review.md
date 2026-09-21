# M10 successor structural snapshot review: Java derivation v9

Date: 2026-09-21. No model experiment has been executed for this migration.

The direct Java receiver correction increments `JAVA_DERIVATION_VERSION` from
v8 to v9. Consequently the successor's old T0 claim correctly fails freshness
and full-production-claim equality. Keeping that old claim fresh, dropping the
version check, or accepting an extra T1 stale cause would violate the preflight.

## Reviewed migration

The old specification is retained byte-for-byte as
`bench/agent_ab/same_version_chain_v1/m10_successor_fixture_spec_java_v8.json`.
Its SHA-256 is `b01b2e9314e4294d943f003644e4dbd9cbbe20fc60a01d7537e1688b99f04a14`.

The active specification remains `m10_successor_fixture_spec.json`. Both full
structural claims were freshly produced by `derive_t0_claim` after the existing
`prepare_fixture(..., "t0")` and `_init_git` routines. No field was rewritten
inside either derived claim; only the existing deterministic acquisition clock
was injected by the production fixture helper, as before.

The complete reviewed delta is:

- Target and control `body.derivation_versions.java`: v8 → v9.
- Target unresolved call reasons at indices 3, 4, 6, 7, 8, 12, 13, and control
  indices 1, 3: generic `java_method_not_found` → the actual source-type lookup
  failure. No invocation expression, edge or binding changes.

Everything else is identical: the eleven T0/T1 source files, sole mutation and
its diff, semantic memory payload, independent AST fact proof, compiler pins,
target/control bindings and fixed acquisition identity. Prompts, arms, tools,
budgets, scoring and interpretation rules are unchanged. This is an explicit
pre-execution structural snapshot review, not post-result benchmark tuning.

## Gates retained

`test_java_v9_snapshot_preserves_experiment_inputs_and_rejects_v8_claim` checks
the historical bytes, whole-spec invariance outside the complete claims, the
precise claim delta, and rejection of the old v8 claim at T0.

The production preflight still requires full claim equality, FRESH(T0), the
single intended Java hash mismatch at T1, a fresh unchanged control, and
independent compilation. It does not regenerate its own golden specification.
Existing seals include the active specification and implementation hashes, so
old seals cannot be reused as v9 admission. A new offline preflight/seal is
required; neither the migration nor that seal authorizes live-model execution.
