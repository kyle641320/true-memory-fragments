# Claim 2 Proof — Current-source refresh separation

## Claim

With stale facts withheld and localized current-source refresh, TMF can solve hidden-oracle tasks that source-only or stale-context controls miss.

## Strict proof standard

A clean positive separation requires, in the same task/run tag:

- SOURCE_ONLY fails hidden oracle.
- PREREAD_STALE_SOURCE fails hidden oracle.
- STALE_DOC_CONTROL fails hidden oracle.
- TMF_REFRESHED_MAP passes hidden oracle and task result.

## Evidence: M21 corevalue smoke R1

Input files:

- `results/order_m21_corevalue_smoke_r1.json`
- `results/ORDER_M21_COREVALUE_SMOKE_R1_REPORT.md`

Observed results:

| arm | result |
|---|---|
| SOURCE_ONLY | 0/1 pass, hidden_oracle_fail |
| PREREAD_STALE_SOURCE | 0/1 pass, hidden_oracle_fail |
| STALE_DOC_CONTROL | 0/1 pass, hidden_oracle_fail |
| TMF_REFRESHED_MAP | 1/1 pass |

## Result

Claim 2 is proven for M21 R1 as a strict one-run separation: all three non-TMF arms failed and TMF passed.

## Supporting but weaker evidence

M21 checkerfix R2 replay also supports TMF vs stale controls:

- PREREAD_STALE_SOURCE: 0/2
- STALE_DOC_CONTROL: 0/2
- TMF_REFRESHED_MAP: 2/2

However SOURCE_ONLY was also 2/2 in that replay, so it does not prove TMF > source-only.

M21 clean R4 supports TMF vs stale controls but not TMF > source-only:

- SOURCE_ONLY: 2/4
- PREREAD_STALE_SOURCE: 0/4
- STALE_DOC_CONTROL: 0/4
- TMF_REFRESHED_MAP: 2/4

## Boundary

This proves existence of a clean stale-context/current-refresh separation, not broad statistical dominance.
