# Mutation Freshness M07 Report

Deterministic synthetic fixture: old claim binds to pre-mutation wrapper; mutation moves prepared reflective boundary into helper while stale wrapper anchor remains compilable.

```json
{
  "mode": "mutation_freshness_m07",
  "runs": 15,
  "by_arm": {
    "SOURCE_ONLY": {
      "runs": 5,
      "raw_pass": 3,
      "semantic_evaluable": 4,
      "semantic_adjusted_pass": 3,
      "compile_ok": 5,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 1,
      "primary": {
        "pass": 3,
        "edit_protocol_fail": 2
      }
    },
    "STALE_DOC_CONTROL": {
      "runs": 5,
      "raw_pass": 1,
      "semantic_evaluable": 4,
      "semantic_adjusted_pass": 1,
      "compile_ok": 5,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 3,
      "primary": {
        "edit_protocol_fail": 1,
        "pass": 1,
        "semantic_boundary_fail": 3
      }
    },
    "TMF_STALE_GATED": {
      "runs": 5,
      "raw_pass": 4,
      "semantic_evaluable": 4,
      "semantic_adjusted_pass": 4,
      "compile_ok": 5,
      "stale_claim_withheld": 5,
      "wrong_wrapper_site": 0,
      "primary": {
        "pass": 4,
        "edit_protocol_fail": 1
      }
    }
  }
}
```

## Rows
- rep 1 SOURCE_ONLY: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07c/M07__SOURCE_ONLY__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=False semantic=None compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 0} raw_path=results/raw/mutation_freshness_m07c/M07__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_STALE_GATED: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07c/M07__TMF_STALE_GATED__r1.raw.json
- rep 2 SOURCE_ONLY: raw=False semantic=None compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 0} raw_path=results/raw/mutation_freshness_m07c/M07__SOURCE_ONLY__r2.raw.json
- rep 2 STALE_DOC_CONTROL: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07c/M07__STALE_DOC_CONTROL__r2.raw.json
- rep 2 TMF_STALE_GATED: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07c/M07__TMF_STALE_GATED__r2.raw.json
- rep 3 SOURCE_ONLY: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07c/M07__SOURCE_ONLY__r3.raw.json
- rep 3 STALE_DOC_CONTROL: raw=False semantic=False compile=True fresh=False failure=semantic_boundary_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07c/M07__STALE_DOC_CONTROL__r3.raw.json
- rep 3 TMF_STALE_GATED: raw=False semantic=None compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 0} raw_path=results/raw/mutation_freshness_m07c/M07__TMF_STALE_GATED__r3.raw.json
- rep 4 SOURCE_ONLY: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07c/M07__SOURCE_ONLY__r4.raw.json
- rep 4 STALE_DOC_CONTROL: raw=False semantic=False compile=True fresh=False failure=semantic_boundary_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07c/M07__STALE_DOC_CONTROL__r4.raw.json
- rep 4 TMF_STALE_GATED: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07c/M07__TMF_STALE_GATED__r4.raw.json
- rep 5 SOURCE_ONLY: raw=False semantic=False compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07c/M07__SOURCE_ONLY__r5.raw.json
- rep 5 STALE_DOC_CONTROL: raw=False semantic=False compile=True fresh=False failure=semantic_boundary_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07c/M07__STALE_DOC_CONTROL__r5.raw.json
- rep 5 TMF_STALE_GATED: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07c/M07__TMF_STALE_GATED__r5.raw.json
