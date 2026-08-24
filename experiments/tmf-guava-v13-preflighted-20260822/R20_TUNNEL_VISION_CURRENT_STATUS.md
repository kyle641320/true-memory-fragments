# R20 Tunnel-Vision Prevention Current Status

## Latest result

Scenario 3 produced the first positive bug-prevention signal.

Result file:

- `R20_SCENARIO_3_RESULT.md`

Correction note:

- `R20_SCENARIO_3_ORACLE_CORRECTION.md`

## Scenario outcomes so far

| Scenario | SOURCE_ONLY | TMF_PROTECT | Separation? | Notes |
| --- | --- | --- | --- | --- |
| Scenario 1 | PASS | PASS | No | Task exposed completion listener too clearly. |
| Scenario 2 | PASS | PASS | No | Stronger local trap, but still too discoverable. |
| Scenario 3 | FAIL | PASS | Yes | SOURCE_ONLY used stale local return path; TMF_PROTECT used fresh listener/completion fragment. |

## Current interpretation

R20 now has one concrete positive tunnel-vision-prevention result:

- SOURCE_ONLY placed a refresh-completion hook on the wrong side of the async refresh boundary.
- TMF_PROTECT placed it on the correct completion/publication side.

This supports the core-value claim that TMF can prevent tunnel-vision bugs when stale/local context is misleading and the fresh boundary fragment changes the edit decision.

## Caveat

This is still single-scenario evidence. The next step should be replication on additional chains/tasks with the same SOURCE_ONLY vs TMF_PROTECT protocol and direct patch-placement oracle.
