# design_intent_v1 Smoke Report — Real Guava EventBus

Subject: real Guava EventBus source from `/root/.openclaw/workspace/worktrees/guava/guava/src/com/google/common/eventbus`.
Smoke: N=2 (`B01`, `B02`)
Arms: `SOURCE_ONLY`, `TMF_STALE`, `TMF_FRESH`
Model broker: `gpt-5.6-sol`
Result file: `results/smoke-n2-real-guava.json`

## Verdict

**FAIL — stop after smoke.**

Staleness detection worked, but mandatory reread-efficiency and design-separation gates did not pass.

## Gate summary

| Task | Stale detected | Stale reread <50% SOURCE_ONLY | Zero stale trust errors | Fresh chain > Source chain | Mandatory pass |
|---|---:|---:|---:|---:|---:|
| B01 | yes | no | yes | no | no |
| B02 | yes | no | yes | no | no |

Aggregate:

- Stale detection rate: 100% (2/2)
- Stale trust errors: 0
- Smoke pass: false

## Read telemetry

| Task | Arm | Valid final | Source bytes read | Range reads | Machine design score | Chain completeness |
|---|---|---:|---:|---:|---:|---:|
| B01 | SOURCE_ONLY | yes | 14,821 | 2 | 2 | 1.00 |
| B01 | TMF_STALE | yes | 13,995 | 4 | 2 | 0.80 |
| B01 | TMF_FRESH | yes | 16,937 | 3 | 2 | 1.00 |
| B02 | SOURCE_ONLY | yes | 12,456 | 0 | 2 | 1.00 |
| B02 | TMF_STALE | yes | 10,321 | 4 | 2 | 0.60 |
| B02 | TMF_FRESH | yes | 14,378 | 4 | 2 | 1.00 |

## Interpretation

### What worked

- The experiment now uses real Guava EventBus source, not invented toy code.
- Source-bound freshness checks correctly invalidated stale claims when an anchored real source file changed.
- Stale claim content was withheld in `TMF_STALE`.
- No stale answer trusted outdated memory.
- Adding `read_range` fixed the previous strict-harness validity problem: all six arms produced final answers.

### What failed

- `TMF_STALE` did not reduce reread volume enough:
  - B01 stale/source ratio ≈ 94%.
  - B02 stale/source ratio ≈ 83%.
- `SOURCE_ONLY` scored machine design score 2 on both tasks. Real Guava comments and local source structure make these prose questions easy enough without TMF.
- `TMF_FRESH` did not show chain-completeness advantage over SOURCE_ONLY.

## Failure mode

**SMOKE_FAILED_REAL_SOURCE_TOO_EASY_FOR_SOURCE_ONLY.**

The freshness mechanism appears sound, but the current real-Guava prose questions do not isolate the intended TMF value. SOURCE_ONLY can read the relevant files and infer the same design intent.

## Recommendation before retry

Do not run full experiment yet. Revise B01/B02/B03 so Phase B requires action/diagnosis that depends on cross-chain continuity rather than asking for design explanation only. Good candidates:

1. Patch or test tasks where code changed in `Dispatcher`/`Subscriber`, then the agent must modify `EventBus.post` without breaking downstream semantics.
2. Questions with hidden tunnel-vision traps: local `EventBus.post` looks sufficient, but correct answer requires noticing changed `Dispatcher` or `Subscriber` behavior.
3. Scoring that checks behavioral/patch correctness plus stale-trust, not just prose keywords.
