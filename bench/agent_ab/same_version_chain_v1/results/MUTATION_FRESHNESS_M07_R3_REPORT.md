# Mutation Freshness M07 Report

Deterministic synthetic fixture: old claim binds to pre-mutation wrapper; mutation moves prepared reflective boundary into helper while stale wrapper anchor remains compilable.

```json
{
  "mode": "mutation_freshness_m07",
  "runs": 9,
  "by_arm": {
    "SOURCE_ONLY": {
      "runs": 3,
      "raw_pass": 2,
      "semantic_evaluable": 2,
      "semantic_adjusted_pass": 2,
      "compile_ok": 3,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 0,
      "primary": {
        "edit_protocol_fail": 1,
        "pass": 2
      }
    },
    "STALE_DOC_CONTROL": {
      "runs": 3,
      "raw_pass": 1,
      "semantic_evaluable": 3,
      "semantic_adjusted_pass": 1,
      "compile_ok": 3,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 2,
      "primary": {
        "semantic_boundary_fail": 2,
        "pass": 1
      }
    },
    "TMF_STALE_GATED": {
      "runs": 3,
      "raw_pass": 2,
      "semantic_evaluable": 2,
      "semantic_adjusted_pass": 2,
      "compile_ok": 3,
      "stale_claim_withheld": 3,
      "wrong_wrapper_site": 0,
      "primary": {
        "pass": 2,
        "edit_protocol_fail": 1
      }
    }
  }
}
```

## Rows
- rep 1 SOURCE_ONLY: raw=False semantic=None compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 0} raw_path=results/raw/mutation_freshness_m07_r3/M07__SOURCE_ONLY__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=False semantic=False compile=True fresh=False failure=semantic_boundary_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07_r3/M07__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_STALE_GATED: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07_r3/M07__TMF_STALE_GATED__r1.raw.json
- rep 2 SOURCE_ONLY: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07_r3/M07__SOURCE_ONLY__r2.raw.json
- rep 2 STALE_DOC_CONTROL: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07_r3/M07__STALE_DOC_CONTROL__r2.raw.json
- rep 2 TMF_STALE_GATED: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07_r3/M07__TMF_STALE_GATED__r2.raw.json
- rep 3 SOURCE_ONLY: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07_r3/M07__SOURCE_ONLY__r3.raw.json
- rep 3 STALE_DOC_CONTROL: raw=False semantic=False compile=True fresh=False failure=semantic_boundary_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07_r3/M07__STALE_DOC_CONTROL__r3.raw.json
- rep 3 TMF_STALE_GATED: raw=False semantic=None compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 0} raw_path=results/raw/mutation_freshness_m07_r3/M07__TMF_STALE_GATED__r3.raw.json
