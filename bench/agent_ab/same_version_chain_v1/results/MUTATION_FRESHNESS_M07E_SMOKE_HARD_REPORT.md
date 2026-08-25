# Mutation Freshness M07 Report

Deterministic synthetic fixture: old claim binds to pre-mutation wrapper; mutation moves prepared reflective boundary into helper while stale wrapper anchor remains compilable.

```json
{
  "mode": "mutation_freshness_m07",
  "runs": 3,
  "final_gate": "hard",
  "by_arm": {
    "SOURCE_ONLY": {
      "runs": 1,
      "raw_pass": 1,
      "semantic_evaluable": 1,
      "semantic_adjusted_pass": 1,
      "compile_ok": 1,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 0,
      "primary": {
        "pass": 1
      }
    },
    "STALE_DOC_CONTROL": {
      "runs": 1,
      "raw_pass": 1,
      "semantic_evaluable": 1,
      "semantic_adjusted_pass": 1,
      "compile_ok": 1,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 0,
      "primary": {
        "pass": 1
      }
    },
    "TMF_STALE_GATED": {
      "runs": 1,
      "raw_pass": 1,
      "semantic_evaluable": 1,
      "semantic_adjusted_pass": 1,
      "compile_ok": 1,
      "stale_claim_withheld": 1,
      "wrong_wrapper_site": 0,
      "primary": {
        "pass": 1
      }
    }
  }
}
```

## Rows
- rep 1 SOURCE_ONLY: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_smoke_hard/M07__SOURCE_ONLY__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_smoke_hard/M07__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_STALE_GATED: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_smoke_hard/M07__TMF_STALE_GATED__r1.raw.json
