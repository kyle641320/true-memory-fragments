# Mutation Freshness M07g Report

Deterministic synthetic fixture: same M07 fixture family, but result-loop now behaves like post-verification human补做: the runner does not surface per-turn result state to the agent during continuation. The only feedback is a generic continue prompt;验收只判结果，不提前喂对错。

```json
{
  "mode": "mutation_freshness_m07h",
  "runs": 9,
  "final_gate": "hard",
  "result_loop": null,
  "max_turns": 5,
  "max_no_progress": null,
  "by_arm": {
    "SOURCE_ONLY": {
      "runs": 3,
      "raw_pass": 2,
      "task_result_pass": 3,
      "post_test_ok": 3,
      "semantic_evaluable": 2,
      "semantic_adjusted_pass": 2,
      "compile_ok": 3,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 0,
      "primary": {
        "pass": 2,
        "no_final": 1
      }
    },
    "STALE_DOC_CONTROL": {
      "runs": 3,
      "raw_pass": 3,
      "task_result_pass": 3,
      "post_test_ok": 3,
      "semantic_evaluable": 3,
      "semantic_adjusted_pass": 3,
      "compile_ok": 3,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 0,
      "primary": {
        "pass": 3
      }
    },
    "TMF_STALE_GATED": {
      "runs": 3,
      "raw_pass": 3,
      "task_result_pass": 3,
      "post_test_ok": 3,
      "semantic_evaluable": 3,
      "semantic_adjusted_pass": 3,
      "compile_ok": 3,
      "stale_claim_withheld": 3,
      "wrong_wrapper_site": 0,
      "primary": {
        "pass": 3
      }
    }
  }
}
```

## Rows
- rep 1 SOURCE_ONLY: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_protofix_check/M07__SOURCE_ONLY__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_protofix_check/M07__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_protofix_check/M07__TMF_STALE_GATED__r1.raw.json
- rep 2 SOURCE_ONLY: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_protofix_check/M07__SOURCE_ONLY__r2.raw.json
- rep 2 STALE_DOC_CONTROL: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_protofix_check/M07__STALE_DOC_CONTROL__r2.raw.json
- rep 2 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_protofix_check/M07__TMF_STALE_GATED__r2.raw.json
- rep 3 SOURCE_ONLY: raw=False task_result=True semantic=None compile=True fresh=False failure=no_final reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_protofix_check/M07__SOURCE_ONLY__r3.raw.json
- rep 3 STALE_DOC_CONTROL: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_protofix_check/M07__STALE_DOC_CONTROL__r3.raw.json
- rep 3 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_protofix_check/M07__TMF_STALE_GATED__r3.raw.json
