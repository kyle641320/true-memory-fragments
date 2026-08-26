# Mutation Freshness M07f Report

Deterministic synthetic fixture: old claim binds to pre-mutation wrapper; mutation moves prepared reflective boundary into helper while stale wrapper anchor remains compilable. M07f can run result_loop mode: only initial prompt carries task/evidence; later prompts are generic continue nudges; scoring includes task_result_pass.

```json
{
  "mode": "mutation_freshness_m07f",
  "runs": 6,
  "final_gate": "off",
  "result_loop": true,
  "by_arm": {
    "SOURCE_ONLY": {
      "runs": 2,
      "raw_pass": 0,
      "task_result_pass": 0,
      "post_test_ok": 0,
      "semantic_evaluable": 0,
      "semantic_adjusted_pass": 0,
      "compile_ok": 2,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 0,
      "primary": {
        "edit_protocol_fail": 2
      }
    },
    "STALE_DOC_CONTROL": {
      "runs": 2,
      "raw_pass": 0,
      "task_result_pass": 0,
      "post_test_ok": 0,
      "semantic_evaluable": 1,
      "semantic_adjusted_pass": 0,
      "compile_ok": 2,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 1,
      "primary": {
        "no_final": 1,
        "semantic_boundary_fail": 1
      }
    },
    "TMF_STALE_GATED": {
      "runs": 2,
      "raw_pass": 0,
      "task_result_pass": 0,
      "post_test_ok": 0,
      "semantic_evaluable": 0,
      "semantic_adjusted_pass": 0,
      "compile_ok": 2,
      "stale_claim_withheld": 2,
      "wrong_wrapper_site": 0,
      "primary": {
        "edit_protocol_fail": 2
      }
    }
  }
}
```

## Rows
- rep 1 SOURCE_ONLY: raw=False task_result=False semantic=None compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 0} raw_path=results/raw/mutation_freshness_m07f_off_r2/M07__SOURCE_ONLY__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=False task_result=False semantic=None compile=True fresh=False failure=no_final reason={"correct_helper_site": false, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 0} raw_path=results/raw/mutation_freshness_m07f_off_r2/M07__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_STALE_GATED: raw=False task_result=False semantic=None compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 0} raw_path=results/raw/mutation_freshness_m07f_off_r2/M07__TMF_STALE_GATED__r1.raw.json
- rep 2 SOURCE_ONLY: raw=False task_result=False semantic=None compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 0} raw_path=results/raw/mutation_freshness_m07f_off_r2/M07__SOURCE_ONLY__r2.raw.json
- rep 2 STALE_DOC_CONTROL: raw=False task_result=False semantic=False compile=True fresh=False failure=semantic_boundary_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07f_off_r2/M07__STALE_DOC_CONTROL__r2.raw.json
- rep 2 TMF_STALE_GATED: raw=False task_result=False semantic=None compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 0} raw_path=results/raw/mutation_freshness_m07f_off_r2/M07__TMF_STALE_GATED__r2.raw.json
