# Mutation Freshness M07g Report

Deterministic synthetic fixture: same M07 fixture family, but result-loop now behaves like post-verification human补做: the runner does not surface per-turn result state to the agent during continuation. The only feedback is a generic continue prompt;验收只判结果，不提前喂对错。

```json
{
  "mode": "mutation_freshness_m07g",
  "runs": 3,
  "final_gate": "hard",
  "result_loop": true,
  "max_turns": 5,
  "max_no_progress": 2,
  "by_arm": {
    "SOURCE_ONLY": {
      "runs": 1,
      "raw_pass": 0,
      "task_result_pass": 1,
      "post_test_ok": 1,
      "semantic_evaluable": 0,
      "semantic_adjusted_pass": 0,
      "compile_ok": 1,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 0,
      "primary": {
        "edit_protocol_fail": 1
      }
    },
    "STALE_DOC_CONTROL": {
      "runs": 1,
      "raw_pass": 0,
      "task_result_pass": 1,
      "post_test_ok": 1,
      "semantic_evaluable": 0,
      "semantic_adjusted_pass": 0,
      "compile_ok": 1,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 0,
      "primary": {
        "no_final": 1
      }
    },
    "TMF_STALE_GATED": {
      "runs": 1,
      "raw_pass": 0,
      "task_result_pass": 1,
      "post_test_ok": 1,
      "semantic_evaluable": 0,
      "semantic_adjusted_pass": 0,
      "compile_ok": 1,
      "stale_claim_withheld": 1,
      "wrong_wrapper_site": 0,
      "primary": {
        "no_final": 1
      }
    }
  }
}
```

## Rows
- rep 1 SOURCE_ONLY: raw=False task_result=True semantic=None compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07g_hidden_smoke/M07__SOURCE_ONLY__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=False task_result=True semantic=None compile=True fresh=False failure=no_final reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07g_hidden_smoke/M07__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_STALE_GATED: raw=False task_result=True semantic=None compile=True fresh=False failure=no_final reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07g_hidden_smoke/M07__TMF_STALE_GATED__r1.raw.json
