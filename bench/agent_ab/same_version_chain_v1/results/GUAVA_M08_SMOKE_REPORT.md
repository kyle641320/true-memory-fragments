# Guava M08 Feature Stale Report

Bounded real-Guava EventBus fixture. Source mutation moves the reflective `method.invoke` from `Subscriber.invokeSubscriberMethod` into a helper `invokeMethodReflectively`, while the wrapper remains live and compilable. The task is feature intent only; the stale doc arm points at the old wrapper boundary; TMF stale-gated arm withholds the stale bound claim.

```json
{
  "mode": "guava_m08_feature_stale",
  "runs": 3,
  "final_gate": "hard",
  "max_turns": 8,
  "by_arm": {
    "SOURCE_ONLY": {
      "runs": 1,
      "raw_pass": 1,
      "task_result_pass": 1,
      "post_test_ok": 1,
      "semantic_evaluable": 0,
      "semantic_adjusted_pass": 0,
      "compile_ok": 1,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 0,
      "duplicate_edit_suppressed": 1,
      "result_ok_but_raw_failed": 0,
      "primary": {
        "pass": 1
      }
    },
    "STALE_DOC_CONTROL": {
      "runs": 1,
      "raw_pass": 0,
      "task_result_pass": 0,
      "post_test_ok": 0,
      "semantic_evaluable": 1,
      "semantic_adjusted_pass": 0,
      "compile_ok": 1,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 1,
      "duplicate_edit_suppressed": 1,
      "result_ok_but_raw_failed": 0,
      "primary": {
        "edit_protocol_fail": 1
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
      "duplicate_edit_suppressed": 0,
      "result_ok_but_raw_failed": 1,
      "primary": {
        "no_final_after_success": 1
      }
    }
  }
}
```

## Rows
- rep 1 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_smoke/GUAVA_M08__SOURCE_ONLY__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=False task_result=False semantic=False compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_smoke/GUAVA_M08__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_STALE_GATED: raw=False task_result=True semantic=None compile=True fresh=False failure=no_final_after_success reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_smoke/GUAVA_M08__TMF_STALE_GATED__r1.raw.json
