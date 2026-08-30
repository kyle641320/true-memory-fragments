# Claim 1 Proof — Stale-memory containment

## Claim

When a stored TMF claim is stale after source mutation, TMF can detect/withhold it instead of injecting obsolete facts into the agent context.

## Evidence source

This proof uses already-generated M21 result JSON files. No LLM rerun and no TMF body modification.

Input files:

- `results/order_m21_corevalue_smoke_r1.json`
- `results/order_m21_stale_api_trap_classfix_checkerfix_r4.json`
- `results/order_m21_stale_api_trap_classfix_r2_checkerfix_replay.json`

## Observed TMF rows

| file | rep | stale claim withheld | primary result | raw pass |
|---|---:|---:|---|---:|
| order_m21_corevalue_smoke_r1.json | 1 | true | pass | true |
| order_m21_stale_api_trap_classfix_checkerfix_r4.json | 1 | true | hidden_oracle_fail | false |
| order_m21_stale_api_trap_classfix_checkerfix_r4.json | 2 | true | pass | true |
| order_m21_stale_api_trap_classfix_checkerfix_r4.json | 3 | true | hidden_oracle_fail | false |
| order_m21_stale_api_trap_classfix_checkerfix_r4.json | 4 | true | pass | true |
| order_m21_stale_api_trap_classfix_r2_checkerfix_replay.json | 1 | true | pass | true |
| order_m21_stale_api_trap_classfix_r2_checkerfix_replay.json | 2 | true | pass | true |

## Result

TMF withheld the stale claim in 7/7 observed M21 TMF rows.

This proves Claim 1 for the current M21 stale API trap fixture: stale freshness detection and containment are working independently of whether the final edit passes hidden oracle.

## Important boundary

This proof does not claim every downstream edit succeeds. In M21 clean R4, two TMF rows still failed hidden oracle even though stale claim containment worked. Those are downstream semantic/read-selection failures, not stale injection failures.
