# Mutation Freshness M07f Report

Deterministic synthetic fixture: old claim binds to pre-mutation wrapper; mutation moves prepared reflective boundary into helper while stale wrapper anchor remains compilable. M07f can run result_loop mode: only initial prompt carries task/evidence; later prompts are generic continue nudges; scoring includes task_result_pass.

```json
{
  "mode": "mutation_freshness_m07f",
  "runs": 3,
  "final_gate": "hard",
  "result_loop": true,
  "max_turns": 5,
  "max_no_progress": 2,
  "by_arm": {
    "SOURCE_ONLY": {
      "runs": 1,
      "raw_pass": 1,
      "task_result_pass": 1,
      "post_test_ok": 1,
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
      "task_result_pass": 1,
      "post_test_ok": 1,
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
      "task_result_pass": 1,
      "post_test_ok": 1,
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
- rep 1 SOURCE_ONLY: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07f_hard_smoke2/M07__SOURCE_ONLY__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07f_hard_smoke2/M07__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07f_hard_smoke2/M07__TMF_STALE_GATED__r1.raw.json
