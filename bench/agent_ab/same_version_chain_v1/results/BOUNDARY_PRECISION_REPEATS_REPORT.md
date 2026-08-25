# Boundary Precision Repeated Three-Arm Report

Scope: B07-B13, 3 repeats per task/arm, arms SOURCE_ONLY / TMF_CLAIMS / DOC_CONTROL. Pass means valid answer + compile OK + task-specific trap pass after current audit normalization.

## Arm-level rates

| arm | pass | n | pass_rate | valid_rate | compile_rate | trap_rate |
|---|---:|---:|---:|---:|---:|---:|
| DOC_CONTROL | 17 | 21 | 0.810 | 0.857 | 0.905 | 0.905 |
| SOURCE_ONLY | 14 | 21 | 0.667 | 0.762 | 0.905 | 0.714 |
| TMF_CLAIMS | 15 | 21 | 0.714 | 0.810 | 0.905 | 0.714 |

## Per-task pass rates

| task | SOURCE_ONLY | TMF_CLAIMS | DOC_CONTROL | best/read |
|---|---:|---:|---:|---|
| B07 | 1.000 | 0.667 | 0.667 | SOURCE_ONLY |
| B08 | 1.000 | 1.000 | 1.000 | SOURCE_ONLY, TMF_CLAIMS, DOC_CONTROL |
| B09 | 0.333 | 1.000 | 1.000 | TMF_CLAIMS, DOC_CONTROL |
| B10 | 1.000 | 1.000 | 1.000 | SOURCE_ONLY, TMF_CLAIMS, DOC_CONTROL |
| B11 | 0.000 | 0.667 | 0.667 | TMF_CLAIMS, DOC_CONTROL |
| B12 | 0.333 | 0.333 | 0.667 | DOC_CONTROL |
| B13 | 1.000 | 0.333 | 0.667 | SOURCE_ONLY |

## Pairwise task outcomes

- TMF_CLAIMS_vs_SOURCE_ONLY: TMF better on 2 tasks, tied on 3, worse on 2.
- TMF_CLAIMS_vs_DOC_CONTROL: TMF better on 0 tasks, tied on 5, worse on 2.

## Interpretation

- Against SOURCE_ONLY, TMF_CLAIMS is directionally better by task: better=2, tie=3, worse=2.
- Against DOC_CONTROL, TMF_CLAIMS is not better in this repeat set: better=0, tie=5, worse=2.
- The repeated run confirms single-run noise is real: individual TMF/DOC/SOURCE runs sometimes fail compile/valid/trap despite prior success.
- Current evidence supports shallow TMF value over source-only on some boundary tasks, but does not yet show TMF is superior to a strong hand-written DOC_CONTROL. Before mutation, either increase task difficulty/less-leading Phase B or improve TMF claim richness beyond plain-text docs.

## Per-run rows

- r1 B07 / DOC_CONTROL: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r1_B07_DOC_CONTROL/B07__DOC_CONTROL.raw.json
- r1 B07 / SOURCE_ONLY: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r1_B07_SOURCE_ONLY/B07__SOURCE_ONLY.raw.json
- r1 B07 / TMF_CLAIMS: pass=False valid=False compile=False trap=False raw=results/raw/boundary_precision_repeat_r1_B07_TMF_CLAIMS/B07__TMF_CLAIMS.raw.json
- r2 B07 / DOC_CONTROL: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r2_B07_DOC_CONTROL/B07__DOC_CONTROL.raw.json
- r2 B07 / SOURCE_ONLY: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r2_B07_SOURCE_ONLY/B07__SOURCE_ONLY.raw.json
- r2 B07 / TMF_CLAIMS: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r2_B07_TMF_CLAIMS/B07__TMF_CLAIMS.raw.json
- r3 B07 / DOC_CONTROL: pass=False valid=False compile=False trap=False raw=results/raw/boundary_precision_repeat_r3_B07_DOC_CONTROL/B07__DOC_CONTROL.raw.json
- r3 B07 / SOURCE_ONLY: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r3_B07_SOURCE_ONLY/B07__SOURCE_ONLY.raw.json
- r3 B07 / TMF_CLAIMS: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r3_B07_TMF_CLAIMS/B07__TMF_CLAIMS.raw.json
- r1 B08 / DOC_CONTROL: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r1_B08_DOC_CONTROL/B08__DOC_CONTROL.raw.json
- r1 B08 / SOURCE_ONLY: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r1_B08_SOURCE_ONLY/B08__SOURCE_ONLY.raw.json
- r1 B08 / TMF_CLAIMS: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r1_B08_TMF_CLAIMS/B08__TMF_CLAIMS.raw.json
- r2 B08 / DOC_CONTROL: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r2_B08_DOC_CONTROL/B08__DOC_CONTROL.raw.json
- r2 B08 / SOURCE_ONLY: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r2_B08_SOURCE_ONLY/B08__SOURCE_ONLY.raw.json
- r2 B08 / TMF_CLAIMS: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r2_B08_TMF_CLAIMS/B08__TMF_CLAIMS.raw.json
- r3 B08 / DOC_CONTROL: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r3_B08_DOC_CONTROL/B08__DOC_CONTROL.raw.json
- r3 B08 / SOURCE_ONLY: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r3_B08_SOURCE_ONLY/B08__SOURCE_ONLY.raw.json
- r3 B08 / TMF_CLAIMS: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r3_B08_TMF_CLAIMS/B08__TMF_CLAIMS.raw.json
- r1 B09 / DOC_CONTROL: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r1_B09_DOC_CONTROL/B09__DOC_CONTROL.raw.json
- r1 B09 / SOURCE_ONLY: pass=False valid=False compile=True trap=False raw=results/raw/boundary_precision_repeat_r1_B09_SOURCE_ONLY/B09__SOURCE_ONLY.raw.json
- r1 B09 / TMF_CLAIMS: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r1_B09_TMF_CLAIMS/B09__TMF_CLAIMS.raw.json
- r2 B09 / DOC_CONTROL: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r2_B09_DOC_CONTROL/B09__DOC_CONTROL.raw.json
- r2 B09 / SOURCE_ONLY: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r2_B09_SOURCE_ONLY/B09__SOURCE_ONLY.raw.json
- r2 B09 / TMF_CLAIMS: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r2_B09_TMF_CLAIMS/B09__TMF_CLAIMS.raw.json
- r3 B09 / DOC_CONTROL: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r3_B09_DOC_CONTROL/B09__DOC_CONTROL.raw.json
- r3 B09 / SOURCE_ONLY: pass=False valid=False compile=False trap=True raw=results/raw/boundary_precision_repeat_r3_B09_SOURCE_ONLY/B09__SOURCE_ONLY.raw.json
- r3 B09 / TMF_CLAIMS: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r3_B09_TMF_CLAIMS/B09__TMF_CLAIMS.raw.json
- r1 B10 / DOC_CONTROL: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r1_B10_DOC_CONTROL/B10__DOC_CONTROL.raw.json
- r1 B10 / SOURCE_ONLY: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r1_B10_SOURCE_ONLY/B10__SOURCE_ONLY.raw.json
- r1 B10 / TMF_CLAIMS: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r1_B10_TMF_CLAIMS/B10__TMF_CLAIMS.raw.json
- r2 B10 / DOC_CONTROL: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r2_B10_DOC_CONTROL/B10__DOC_CONTROL.raw.json
- r2 B10 / SOURCE_ONLY: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r2_B10_SOURCE_ONLY/B10__SOURCE_ONLY.raw.json
- r2 B10 / TMF_CLAIMS: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r2_B10_TMF_CLAIMS/B10__TMF_CLAIMS.raw.json
- r3 B10 / DOC_CONTROL: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r3_B10_DOC_CONTROL/B10__DOC_CONTROL.raw.json
- r3 B10 / SOURCE_ONLY: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r3_B10_SOURCE_ONLY/B10__SOURCE_ONLY.raw.json
- r3 B10 / TMF_CLAIMS: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r3_B10_TMF_CLAIMS/B10__TMF_CLAIMS.raw.json
- r1 B11 / DOC_CONTROL: pass=False valid=True compile=True trap=False raw=results/raw/boundary_precision_repeat_r1_B11_DOC_CONTROL/B11__DOC_CONTROL.raw.json
- r1 B11 / SOURCE_ONLY: pass=False valid=False compile=True trap=False raw=results/raw/boundary_precision_repeat_r1_B11_SOURCE_ONLY/B11__SOURCE_ONLY.raw.json
- r1 B11 / TMF_CLAIMS: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r1_B11_TMF_CLAIMS/B11__TMF_CLAIMS.raw.json
- r2 B11 / DOC_CONTROL: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r2_B11_DOC_CONTROL/B11__DOC_CONTROL.raw.json
- r2 B11 / SOURCE_ONLY: pass=False valid=True compile=True trap=False raw=results/raw/boundary_precision_repeat_r2_B11_SOURCE_ONLY/B11__SOURCE_ONLY.raw.json
- r2 B11 / TMF_CLAIMS: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r2_B11_TMF_CLAIMS/B11__TMF_CLAIMS.raw.json
- r3 B11 / DOC_CONTROL: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r3_B11_DOC_CONTROL/B11__DOC_CONTROL.raw.json
- r3 B11 / SOURCE_ONLY: pass=False valid=False compile=True trap=False raw=results/raw/boundary_precision_repeat_r3_B11_SOURCE_ONLY/B11__SOURCE_ONLY.raw.json
- r3 B11 / TMF_CLAIMS: pass=False valid=False compile=False trap=False raw=results/raw/boundary_precision_repeat_r3_B11_TMF_CLAIMS/B11__TMF_CLAIMS.raw.json
- r1 B12 / DOC_CONTROL: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r1_B12_DOC_CONTROL/B12__DOC_CONTROL.raw.json
- r1 B12 / SOURCE_ONLY: pass=False valid=False compile=False trap=False raw=results/raw/boundary_precision_repeat_r1_B12_SOURCE_ONLY/B12__SOURCE_ONLY.raw.json
- r1 B12 / TMF_CLAIMS: pass=False valid=False compile=True trap=False raw=results/raw/boundary_precision_repeat_r1_B12_TMF_CLAIMS/B12__TMF_CLAIMS.raw.json
- r2 B12 / DOC_CONTROL: pass=False valid=False compile=True trap=True raw=results/raw/boundary_precision_repeat_r2_B12_DOC_CONTROL/B12__DOC_CONTROL.raw.json
- r2 B12 / SOURCE_ONLY: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r2_B12_SOURCE_ONLY/B12__SOURCE_ONLY.raw.json
- r2 B12 / TMF_CLAIMS: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r2_B12_TMF_CLAIMS/B12__TMF_CLAIMS.raw.json
- r3 B12 / DOC_CONTROL: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r3_B12_DOC_CONTROL/B12__DOC_CONTROL.raw.json
- r3 B12 / SOURCE_ONLY: pass=False valid=True compile=True trap=False raw=results/raw/boundary_precision_repeat_r3_B12_SOURCE_ONLY/B12__SOURCE_ONLY.raw.json
- r3 B12 / TMF_CLAIMS: pass=False valid=True compile=True trap=False raw=results/raw/boundary_precision_repeat_r3_B12_TMF_CLAIMS/B12__TMF_CLAIMS.raw.json
- r1 B13 / DOC_CONTROL: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r1_B13_DOC_CONTROL/B13__DOC_CONTROL.raw.json
- r1 B13 / SOURCE_ONLY: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r1_B13_SOURCE_ONLY/B13__SOURCE_ONLY.raw.json
- r1 B13 / TMF_CLAIMS: pass=False valid=False compile=True trap=False raw=results/raw/boundary_precision_repeat_r1_B13_TMF_CLAIMS/B13__TMF_CLAIMS.raw.json
- r2 B13 / DOC_CONTROL: pass=False valid=False compile=False trap=True raw=results/raw/boundary_precision_repeat_r2_B13_DOC_CONTROL/B13__DOC_CONTROL.raw.json
- r2 B13 / SOURCE_ONLY: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r2_B13_SOURCE_ONLY/B13__SOURCE_ONLY.raw.json
- r2 B13 / TMF_CLAIMS: pass=False valid=True compile=True trap=False raw=results/raw/boundary_precision_repeat_r2_B13_TMF_CLAIMS/B13__TMF_CLAIMS.raw.json
- r3 B13 / DOC_CONTROL: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r3_B13_DOC_CONTROL/B13__DOC_CONTROL.raw.json
- r3 B13 / SOURCE_ONLY: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r3_B13_SOURCE_ONLY/B13__SOURCE_ONLY.raw.json
- r3 B13 / TMF_CLAIMS: pass=True valid=True compile=True trap=True raw=results/raw/boundary_precision_repeat_r3_B13_TMF_CLAIMS/B13__TMF_CLAIMS.raw.json
