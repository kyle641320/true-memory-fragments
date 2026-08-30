# TMF Core Value Proof Ledger — 2026-08-30

This ledger decomposes the broad question “is TMF core value proven?” into separately testable claims.

Current rule from user: do **not** modify TMF body code unless explicitly re-authorized.

## Claim 1 — Stale-memory containment works

**Statement:** When a stored TMF claim is stale after source mutation, TMF can detect/withhold it instead of injecting obsolete facts into the agent context.

**Proof standard:**

- Stale binding detected after mutation.
- TMF arm records `stale_claim_withheld=1`.
- Agent does not receive the stale claim text as authoritative context.

**Current evidence:**

- M21 clean R4: `TMF_REFRESHED_MAP` withheld stale claim in 4/4 runs.
  - `results/order_m21_stale_api_trap_classfix_checkerfix_r4.json`
- M21 corevalue smoke R1: `TMF_REFRESHED_MAP` withheld stale claim in 1/1 run.
  - `results/order_m21_corevalue_smoke_r1.json`
- Earlier M16 R8 also showed TMF withheld stale claims in 8/8 runs, per recorded summary.

**Status:** PROVEN for current synthetic stale-context fixtures.

**Limits:** This proves containment in the benchmark harness; not yet broad-language/repo coverage.

## Claim 2 — Current-source refresh can recover hidden invariants that stale/source-only contexts miss

**Statement:** With stale facts withheld and localized current-source reread/semantic refresh, TMF can solve hidden-oracle tasks that source-only or stale controls fail.

**Proof standard:**

- Same task / same model / same protocol.
- SOURCE_ONLY and stale controls fail hidden oracle.
- TMF_REFRESHED_MAP passes hidden oracle and task result.

**Current evidence:**

- M21 corevalue smoke R1:
  - SOURCE_ONLY: 0/1, `hidden_oracle_fail`
  - PREREAD_STALE_SOURCE: 0/1, `hidden_oracle_fail`
  - STALE_DOC_CONTROL: 0/1, `hidden_oracle_fail`
  - TMF_REFRESHED_MAP: 1/1 pass
  - Files: `results/order_m21_corevalue_smoke_r1.json`, `results/ORDER_M21_COREVALUE_SMOKE_R1_REPORT.md`
- M21 checkerfix R2 replay:
  - SOURCE_ONLY: 2/2 pass
  - PREREAD_STALE_SOURCE: 0/2
  - STALE_DOC_CONTROL: 0/2
  - TMF_REFRESHED_MAP: 2/2 pass
  - Files: `results/order_m21_stale_api_trap_classfix_r2_checkerfix_replay.json`, report.
- M16 earlier R8 evidence supports TMF recovering hidden invariant in 6/8, while SOURCE_ONLY and PREREAD failed 0/8; however STALE_DOC_CONTROL also passed 8/8 there, so M16 does not prove superiority over stale-doc.

**Status:** PROVEN as scoped positive separation in M21 R1; SUPPORTED but not universally stable in larger R4 because SOURCE_ONLY and TMF were both 2/4 while stale controls were 0/4.

**Limits:** Needs more multi-fixture replication before broad claim.

## Claim 3 — TMF is better than simply pre-reading stale source or stale docs

**Statement:** TMF’s stale handling + refresh is superior to naive stale preread/doc controls.

**Proof standard:**

- PREREAD_STALE_SOURCE and STALE_DOC_CONTROL fail under the same task.
- TMF passes at materially higher rate.

**Current evidence:**

- M21 corevalue smoke R1: both stale controls 0/1, TMF 1/1.
- M21 clean R4: PREREAD 0/4, STALE_DOC 0/4, TMF 2/4.

**Status:** PROVEN for M21 stale API trap; not yet generally proven.

**Limits:** M16 showed STALE_DOC_CONTROL can be very strong (8/8 in earlier R8), so the claim must remain scenario-specific.

## Claim 4 — TMF is better than source-only baseline

**Statement:** TMF improves correctness over a no-memory/source-only agent.

**Proof standard:**

- SOURCE_ONLY fails materially more often than TMF on matched tasks.

**Current evidence:**

- M21 corevalue smoke R1: SOURCE_ONLY 0/1 vs TMF 1/1.
- M21 clean R4: SOURCE_ONLY 2/4 vs TMF 2/4, so no advantage in that run.
- M16 earlier R8: SOURCE_ONLY 0/8 vs TMF 6/8, but M16 has other control caveats.

**Status:** PARTIALLY PROVEN / NOT YET STABLE.

**Limits:** Needs larger clean replications and more fixtures.

## Claim 5 — TMF failures are semantic-boundary/harness-attributable, not stale-gating failure

**Statement:** When TMF fails in these runs, the cause is usually missing semantic inference, read ranking, ordering, or harness noise, not stale claim injection.

**Proof standard:**

- Failure analysis shows `stale_claim_withheld=1` despite hidden oracle failure.
- Diff/raw inspection identifies downstream semantic or protocol cause.

**Current evidence:**

- M21 clean R4 TMF failures: stale claims withheld; failures concentrated around not reading/using `FulfillmentPolicy` gate or ordering when using current gate.
- B12/B13 earlier review similarly separated semantic failures from edit/protocol failures.

**Status:** SUPPORTED.

**Limits:** Requires per-failure attribution discipline; cannot infer from raw pass alone.

## Claim 6 — TMF has positive product ROI

**Statement:** TMF improves real-world development outcomes enough to justify token/tool/read overhead.

**Proof standard:**

- Multi-task, multi-repo benchmark with cost accounting.
- Correctness uplift remains after harness noise removal.
- Added reads/tokens/tools are acceptable relative to avoided failures.

**Current evidence:**

- M16 cost notes show TMF can be more expensive in tool/read count.
- Correctness uplift exists in some fixtures but is not yet broad/stable enough.

**Status:** NOT PROVEN.

**Next evidence needed:** standardized cost-adjusted score across fixtures.

## Claim 7 — TMF should be modified now based on M21

**Statement:** M21 evidence requires changing TMF body code now.

**Proof standard:**

- Stable, repeated TMF failure after benchmark checker/classification cleanup.
- Failure points to a generalizable TMF defect rather than fixture/budget/ordering ambiguity.

**Current evidence:**

- M21 showed potential read-ranking/ordering issues.
- But user explicitly decided not to modify TMF, and the evidence supports caution.

**Status:** NOT PROVEN. Do not modify TMF body now.

## Current overall conclusion

TMF core value is **scoped-positive proven** for stale-memory containment and M21-style stale-context/current-refresh separation.

It is **not fully proven** for broad source-only superiority, universal stale-doc superiority, or product ROI.
