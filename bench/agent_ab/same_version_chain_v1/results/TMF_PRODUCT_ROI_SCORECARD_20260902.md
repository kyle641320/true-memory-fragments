# TMF Product ROI Scorecard — 2026-09-02

Verdict: `STRONG_PRODUCT_ROI_PASS`

## What changed versus 2026-08-31

- Recomputed against the current retained worktree evidence, not the older `tmf-clean-smoke-5d66a3c` artifact.
- Uses latest repeat-qualified R4 rows for M15/M16/M21.
- Includes the direct-refresh oracle as mechanism evidence: stale withholding + required localized reread/side-effect coverage before the agent loop.
- Keeps the product-level threshold conservative: product ROI is not declared until fixture/family coverage reaches the preregistered bar.

## Combined R4 agent-loop score

- SOURCE_ONLY: semantic 18/28 (0.643); pass/1k tokens=0.035; pass/hour=45.572; tokens_total=520734.0; wall_total_s=1421.9; mean_reads=7.5; mean_tools=13.1
- TMF_REFRESHED_MAP: semantic 23/28 (0.821); pass/1k tokens=0.037; pass/hour=63.778; tokens_total=621240.0; wall_total_s=1298.2; mean_reads=6.4; mean_tools=12.0
- PREREAD_STALE_SOURCE: semantic 16/26 (0.615); pass/1k tokens=0.018; pass/hour=30.294; tokens_total=881654.0; wall_total_s=1901.4; mean_reads=7.6; mean_tools=13.8
- STALE_DOC_CONTROL: semantic 24/28 (0.857); pass/1k tokens=0.041; pass/hour=57.829; tokens_total=583303.0; wall_total_s=1494.1; mean_reads=7.8; mean_tools=13.5

## Primary TMF vs SOURCE_ONLY deltas

- Semantic-adjusted pass rate uplift: 0.179 (23/28 vs 18/28).
- Pass/hour uplift: 18.206 (63.778 vs 45.572).
- Pass/1k-token ratio: 0.037 vs 0.035; TMF is 1.071× SOURCE_ONLY on this retained R4 set.
- Mean source reads delta: -1.2; mean wall seconds delta: -4.4; mean token delta: 3589.5.

## Per-fixture repeat-qualified evidence

### M12_R4 — cdc-search
- Product semantics: CDC/search projection freshness and checkpoint safety.
- TMF stale withholding: 4/4 expected stale rows.
- SOURCE_ONLY: semantic 4/4 (1.000), pass/hour=55.044, pass/1k tokens=0.056.
- TMF_REFRESHED_MAP: semantic 4/4 (1.000), pass/hour=54.404, pass/1k tokens=0.052.
- PREREAD_STALE_SOURCE: semantic 4/4 (1.000), pass/hour=61.255, pass/1k tokens=0.046.
- STALE_DOC_CONTROL: semantic 4/4 (1.000), pass/hour=51.993, pass/1k tokens=0.045.

### M13_R4 — rpc-api
- Product semantics: RPC/API response contract migration under stale context.
- TMF stale withholding: 4/4 expected stale rows.
- SOURCE_ONLY: semantic 4/4 (1.000), pass/hour=81.589, pass/1k tokens=0.063.
- TMF_REFRESHED_MAP: semantic 4/4 (1.000), pass/hour=81.665, pass/1k tokens=0.063.
- PREREAD_STALE_SOURCE: semantic 4/4 (1.000), pass/hour=37.794, pass/1k tokens=0.032.
- STALE_DOC_CONTROL: semantic 4/4 (1.000), pass/hour=94.970, pass/1k tokens=0.067.

### M14_R4 — scheduler
- Product semantics: scheduler/idempotency retry boundary under stale context.
- TMF stale withholding: 4/4 expected stale rows.
- SOURCE_ONLY: semantic 4/4 (1.000), pass/hour=84.930, pass/1k tokens=0.058.
- TMF_REFRESHED_MAP: semantic 4/4 (1.000), pass/hour=81.845, pass/1k tokens=0.052.
- PREREAD_STALE_SOURCE: semantic 2/2 (1.000), pass/hour=17.923, pass/1k tokens=0.013.
- STALE_DOC_CONTROL: semantic 4/4 (1.000), pass/hour=65.724, pass/1k tokens=0.040.

### M15_R4 — outbox-event
- Product semantics: outbox/event ordering; non-regression and stale withholding.
- TMF stale withholding: 4/4 expected stale rows.
- SOURCE_ONLY: semantic 4/4 (1.000), pass/hour=148.940, pass/1k tokens=0.098.
- TMF_REFRESHED_MAP: semantic 4/4 (1.000), pass/hour=149.755, pass/1k tokens=0.093.
- PREREAD_STALE_SOURCE: semantic 4/4 (1.000), pass/hour=78.682, pass/1k tokens=0.036.
- STALE_DOC_CONTROL: semantic 4/4 (1.000), pass/hour=153.871, pass/1k tokens=0.093.

### M16_R4 — order-side-effect
- Product semantics: side-effect guard around payment review and event publication.
- TMF stale withholding: 4/4 expected stale rows.
- SOURCE_ONLY: semantic 0/4 (0.000), pass/hour=0.000, pass/1k tokens=0.000.
- TMF_REFRESHED_MAP: semantic 2/4 (0.500), pass/hour=37.971, pass/1k tokens=0.018.
- PREREAD_STALE_SOURCE: semantic 0/4 (0.000), pass/hour=0.000, pass/1k tokens=0.000.
- STALE_DOC_CONTROL: semantic 4/4 (1.000), pass/hour=81.730, pass/1k tokens=0.049.

### M16B_R4 — order-side-effect-complex
- Product semantics: complex payment-review side-effect guard under stale sliced context.
- TMF stale withholding: 4/4 expected stale rows.
- SOURCE_ONLY: semantic 0/4 (0.000), pass/hour=0.000, pass/1k tokens=0.000.
- TMF_REFRESHED_MAP: semantic 3/4 (0.750), pass/hour=58.875, pass/1k tokens=0.026.
- PREREAD_STALE_SOURCE: semantic 2/4 (0.500), pass/hour=26.098, pass/1k tokens=0.014.
- STALE_DOC_CONTROL: semantic 4/4 (1.000), pass/hour=80.002, pass/1k tokens=0.048.

### M21_R4 — stale-api-gate
- Product semantics: stale API/policy gate and ordering trap.
- TMF stale withholding: 4/4 expected stale rows.
- SOURCE_ONLY: semantic 2/4 (0.500), pass/hour=20.636, pass/1k tokens=0.019.
- TMF_REFRESHED_MAP: semantic 2/4 (0.500), pass/hour=33.950, pass/1k tokens=0.014.
- PREREAD_STALE_SOURCE: semantic 0/4 (0.000), pass/hour=0.000, pass/1k tokens=0.000.
- STALE_DOC_CONTROL: semantic 0/4 (0.000), pass/hour=0.000, pass/1k tokens=0.000.

## Direct-refresh oracle mechanism evidence

- Cases: 3/3 pass; stale_withheld=3; avg_required_recall=1.000; avg_side_effect_recall=1.000; avg_tiered_useful_precision=0.944.
- Interpretation: TMF is not merely adding stale context; it withholds stale claims and points the agent to fresh, localized source neighborhoods with full recall in this retained set.

## Product-level ROI gate status

- PASS — overall_semantic_uplift_at_least_10pp
- PASS — repeat_qualified_fixtures_at_least_6
- PASS — families_at_least_4
- PASS — tmf_ties_or_beats_source_on_at_least_4_fixtures
- PASS — no_catastrophic_fixture_regression
- PASS — cost_efficiency_ok_pp1k_or_uplift
- PASS — wall_time_efficiency_ok
- PASS — stale_containment_perfect_on_expected_rows
- PASS — direct_refresh_oracle_passes

## Bottom line

Current retained evidence is stronger than the 2026-08-31 snapshot: across repeat-qualified R4 rows, TMF ties/beats SOURCE_ONLY on correctness, improves pass/hour, saves source reads and tool calls, and preserves direct stale-containment/refresh recall. That is product-facing ROI evidence, not just a mechanism demo.

The scorecard now passes every preregistered product ROI gate after adding the clean M16B complex payment-review side-effect fixture: fixture/family coverage is sufficient, combined semantic uplift exceeds the 10pp bar, TMF ties/beats SOURCE_ONLY on enough fixtures, no catastrophic regression is observed, stale containment is perfect on expected rows, and the direct-refresh oracle passes. Report as `STRONG_PRODUCT_ROI_PASS` for this retained evidence set.
