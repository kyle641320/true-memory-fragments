# Java Real Stale A/B v4 Protocol

Frozen design on 2026-09-02. This extends the v3 single Petclinic event smoke into three independent real-repo stale-contract fixtures before running costly agent repeats.

## Goal

Validate whether repo-local TMF freshness helps agents notice stale source-derived notes in real Java/Spring code after controlled mutations. The first gate is deterministic fixture validity; agent A/B runs come only after the fixture itself proves stale/fresh behavior.

## Arms

- `SOURCE_ONLY`: receives the old note and current repo path, but must not use TMF. It may inspect source within the frozen budget.
- `TMF_MAP`: receives the same old note and current repo path. It must first check repo-local TMF claims related to the old symbol/string, treat stale output only as a locator, then reread current source minimally.

## Fixtures

1. `RV4F01` API route contract drift: `OwnerController.showOwner` old GET `/owners/{ownerId}` becomes GET `/owners/{ownerId}/profile`.
2. `RV4F02` cache contract drift: `VetRepository` old cache name `vets` becomes `activeVets`.
3. `RV4F03` transaction contract drift: `VetRepository.findAll` old `@Transactional(readOnly = true)` becomes `@Transactional(readOnly = false)`.

## Deterministic validity gate

Each fixture must show:

- old `.tmf` claims exist for the old route/cache/transaction contract,
- those old relevant claims become stale after mutation,
- current source contains the new contract,
- current source no longer contains the old contract at the target site,
- no agent answer is scored until this gate passes.

## Claim discipline

Fresh is not correctness. TMF output is a locator/guard only. Current source citations remain authoritative. Transport/runtime failures are reported separately and never counted as semantic failures.
