# Claim 3 Proof — TMF vs stale controls

## Claim

TMF refreshed-map behavior outperforms naive stale-context controls on stale-trap tasks.

## Proof standard

A claim is proven for a fixture when stale controls fail materially more often than TMF under the same task, model, and protocol.

Controls considered:

- PREREAD_STALE_SOURCE
- STALE_DOC_CONTROL

## M21 evidence

### M21 corevalue smoke R1

File:

- `results/order_m21_corevalue_smoke_r1.json`

Results:

| arm | pass rate |
|---|---:|
| PREREAD_STALE_SOURCE | 0/1 |
| STALE_DOC_CONTROL | 0/1 |
| TMF_REFRESHED_MAP | 1/1 |

### M21 clean R4

File:

- `results/order_m21_stale_api_trap_classfix_checkerfix_r4.json`

Results:

| arm | pass rate |
|---|---:|
| PREREAD_STALE_SOURCE | 0/4 |
| STALE_DOC_CONTROL | 0/4 |
| TMF_REFRESHED_MAP | 2/4 |

### M21 checkerfix R2 replay

File:

- `results/order_m21_stale_api_trap_classfix_r2_checkerfix_replay.json`

Results:

| arm | pass rate |
|---|---:|
| PREREAD_STALE_SOURCE | 0/2 |
| STALE_DOC_CONTROL | 0/2 |
| TMF_REFRESHED_MAP | 2/2 |

## Result

Claim 3 is proven for the M21 stale API trap fixture: TMF consistently beats both stale controls across the available M21 runs/replays.

Combined M21 rows above:

| arm | combined pass rate |
|---|---:|
| PREREAD_STALE_SOURCE | 0/7 |
| STALE_DOC_CONTROL | 0/7 |
| TMF_REFRESHED_MAP | 5/7 |

## Boundary / caveat

This does not prove TMF always beats stale docs generally. Earlier M16 evidence showed STALE_DOC_CONTROL can be strong/pass in that fixture. Therefore the proven statement is scenario-bounded:

> TMF beats stale controls in M21-style stale API trap tasks, where stale docs/prereads preserve an obsolete but still compilable API contract.
