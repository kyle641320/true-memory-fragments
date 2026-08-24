# R20 Scenario 1 Execution Plan

## Inputs frozen

- Scenario: refresh completion hook placement
- Chain: CacheBuilder -> LocalCache -> LoadingValueReference -> CacheLoader -> LoadingCache
- Mutation: asynchronous refresh completion timing
- Oracle: hook must fire after completion/publication

## Arms

### SOURCE_ONLY
- Uses only A-side view
- No stale detection
- No forced reread

### TMF_PROTECT
- Uses TMF stale fragment for the refresh boundary
- Forces reread of the completion boundary if stale
- Then edits A

## Execution steps

1. Instantiate a real Guava fixture or a close benchmark harness.
2. Freeze a t0 understanding for both arms.
3. Apply the asynchronous refresh mutation.
4. Run SOURCE_ONLY and TMF_PROTECT edits.
5. Check patches with the mechanical oracle.
6. Compare bug rate.

## Primary outcome

Lower bug rate for TMF_PROTECT.
