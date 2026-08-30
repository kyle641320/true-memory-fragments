# Claim 4 Status — TMF vs source-only

## Claim

TMF refreshed-map behavior outperforms source-only baseline.

## Proof standard

A stable claim requires repeated matched runs where SOURCE_ONLY fails materially more often than TMF, after excluding harness/protocol failures.

## Evidence supporting the claim

### M21 corevalue smoke R1

File:

- `results/order_m21_corevalue_smoke_r1.json`

Result:

| arm | pass rate |
|---|---:|
| SOURCE_ONLY | 0/1 |
| TMF_REFRESHED_MAP | 1/1 |

This is a clean one-run positive separation.

### Earlier M16 R8 summary

Recorded prior result:

- SOURCE_ONLY: 0/8
- TMF_REFRESHED_MAP: 6/8

This supports TMF > SOURCE_ONLY in the M16 complex payment-review fixture, though M16 had a separate stale-doc caveat.

## Evidence limiting the claim

### M21 clean R4

File:

- `results/order_m21_stale_api_trap_classfix_checkerfix_r4.json`

Result:

| arm | pass rate |
|---|---:|
| SOURCE_ONLY | 2/4 |
| TMF_REFRESHED_MAP | 2/4 |

This does not show superiority over source-only.

### M21 checkerfix R2 replay

File:

- `results/order_m21_stale_api_trap_classfix_r2_checkerfix_replay.json`

Result:

| arm | pass rate |
|---|---:|
| SOURCE_ONLY | 2/2 |
| TMF_REFRESHED_MAP | 2/2 |

This also does not show superiority over source-only.

## Result

Claim 4 is **not fully proven**.

What is proven:

- Existence of cases where TMF beats SOURCE_ONLY, e.g. M21 corevalue smoke R1 and earlier M16 R8.

What is not proven:

- Stable statistical superiority over SOURCE_ONLY across repeated M21 runs and across multiple fixture families.

## Next evidence needed

Run more clean, high-signal fixtures where source-only plausibly misses stale/current boundaries and compare pass rates with cost reporting.

## Additional evidence: M16 retry R1 on 2026-08-30

Command:

```bash
python3 bench/agent_ab/same_version_chain_v1/order_m16_complex_two_phase_runner.py \
  --repeats 1 \
  --tag order_m16_corevalue_retry_r1 \
  --final-gate hard \
  --phase-a-turns 8 \
  --phase-b-turns 24
```

Result file:

- `results/order_m16_corevalue_retry_r1.json`

Observed summary:

| arm | hidden oracle | runner primary |
|---|---|---|
| SOURCE_ONLY | fail | hidden_oracle_fail |
| PREREAD_STALE_SOURCE | fail | hidden_oracle_fail |
| STALE_DOC_CONTROL | pass | pass |
| TMF_REFRESHED_MAP | pass | compile_action_fail |

Interpretation:

At the hidden-oracle level, this retry supports the existence of TMF > SOURCE_ONLY separation on M16: SOURCE_ONLY failed while TMF passed hidden tests.

However, the runner still labels TMF raw/task result as failed because of execution/classifier noise:

- There was an early compile failure, later recovered by a successful compile.
- Hidden JUnit passed.
- The deterministic placement checker reported no direct payment-status branch because the patch used a different derived condition shape.

Therefore this run should be counted as **supporting hidden-oracle separation**, but not as a clean raw-pass proof until the M16 classifier/checker is cleaned like M21 was.

Updated Claim 4 result:

- Existence of TMF > SOURCE_ONLY separation is now better supported by M21 R1 and M16 retry R1 hidden-oracle evidence.
- Stable superiority remains not fully proven because repeated M21 R4/R2 still show source-only sometimes matches TMF.

## M16 retry R1 after classfix/checkerfix replay

After cleaning the M16 benchmark classification/checker in the same style as M21, the existing M16 retry work dirs were replayed without LLM rerun.

Files:

- `results/order_m16_corevalue_retry_r1_classfix_checkerfix_replay.json`
- `results/ORDER_M16_COREVALUE_RETRY_R1_CLASSFIX_CHECKERFIX_REPLAY_REPORT.md`

Corrected summary:

| arm | corrected pass rate |
|---|---:|
| SOURCE_ONLY | 0/1 |
| PREREAD_STALE_SOURCE | 0/1 |
| STALE_DOC_CONTROL | 1/1 |
| TMF_REFRESHED_MAP | 1/1 |

Result:

This upgrades the M16 retry evidence from “hidden-oracle support with runner noise” to a clean corrected replay: TMF beats SOURCE_ONLY on M16 retry R1.

Updated Claim 4 status:

- Proven as existence: there are clean corrected fixtures where TMF beats SOURCE_ONLY.
- Still not proven as stable universal superiority: M21 R4 and R2 replay still show SOURCE_ONLY can match TMF in some runs.
