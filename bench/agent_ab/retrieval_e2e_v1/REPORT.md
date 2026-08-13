# Retrieval E2E v1 audit report

## Immutable prior evidence

The v1/v2 artifacts were retained byte-for-byte and were not rescored. V2's published three-pair audit remains SOURCE_ONLY task/citation 3/3, TMF_MAP 2/3, and TMF adoption 0/3.

## Retrieval baseline → one preregistered general fix

| task | R@3 before→after | R@5 | R@10 | MRR |
|---|---:|---:|---:|---:|
| P01 | 0→.667 | 0→.667 | .667→.667 | .167→.5 |
| P02 | .333→.333 | .667→.667 | 1→1 | 1→1 |
| P03 | .5→.5 | .5→1 | .5→1 | 1→1 |
| macro | .278→.5 | .389→.778 | .722→.889 | .722→.833 |

All golden paths existed in the fresh graph. Baseline defects were retrieval/ranking, not graph absence. The sole change was generic morphology plus event one-hop traversal; no task/path/golden literals were added. P01's listener remains outside Top10, so residual retrieval/relationship packing weakness is explicit.

## Controlled-agent stop gate

The one-pair smoke preserved model/prompt/budgets and broker raw-inference isolation, but produced **0 valid pairs**: both arms exhausted/ended before a schema-valid final answer. Neutral TMF made 0 TMF calls; SOURCE_ONLY used 0 source lines and TMF_AVAILABLE 267. Consequently the preregistered invalid-smoke gate stopped the 3-pair pilot; no task/citation comparison is valid.

The one allowed discoverability description A/B was then run on P01 only. Neutral: 0 calls, 0 adoption. Capability/when-to-use: 1 `tmf_retrieve`, followed by source reads (adoption true), 570 source lines, 29,459 tokens, 30.06s, but no valid final answer. This identifies a tool-description/decision discoverability problem and proves action can be induced without hints; it does **not** establish outcome benefit.

## Decision

Not ready for productization. Retrieval improved materially, and the generic description changed call/adoption from 0 to 1, but there are zero valid paired outcomes and the loop's completion/token economics are unacceptable. Next work requires a separately preregistered protocol (not tuning this frozen run) with a compact observation envelope and an explicit final-answer reservation.

Artifacts: `results/baseline-current.json`, `results/after-general-fix.json`, `results/smoke-1pair.json`, `results/description-ab-p01.json`. No pilot result is claimed because the frozen smoke stop gate fired.
