# Guava M08 Feature Stale Report

Bounded real-Guava EventBus fixture. Source mutation moves the reflective `method.invoke` from `Subscriber.invokeSubscriberMethod` into a helper `invokeMethodReflectively`, while the wrapper remains live and compilable. The task is feature intent only; the stale doc arm points at the old wrapper boundary; TMF stale-gated arm withholds the stale bound claim.

```json
{
  "mode": "guava_m08_feature_stale",
  "runs": 30,
  "final_gate": "hard",
  "max_turns": 10,
  "by_arm": {
    "SOURCE_ONLY": {
      "runs": 10,
      "raw_pass": 9,
      "task_result_pass": 9,
      "post_test_ok": 9,
      "semantic_evaluable": 4,
      "semantic_adjusted_pass": 4,
      "compile_ok": 10,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 1,
      "duplicate_edit_suppressed": 3,
      "result_ok_but_raw_failed": 0,
      "primary": {
        "pass": 9,
        "edit_protocol_fail": 1
      }
    },
    "STALE_DOC_CONTROL": {
      "runs": 10,
      "raw_pass": 0,
      "task_result_pass": 0,
      "post_test_ok": 0,
      "semantic_evaluable": 5,
      "semantic_adjusted_pass": 0,
      "compile_ok": 10,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 10,
      "duplicate_edit_suppressed": 4,
      "result_ok_but_raw_failed": 0,
      "primary": {
        "edit_protocol_fail": 9,
        "semantic_boundary_fail": 1
      }
    },
    "TMF_STALE_GATED": {
      "runs": 10,
      "raw_pass": 8,
      "task_result_pass": 8,
      "post_test_ok": 8,
      "semantic_evaluable": 0,
      "semantic_adjusted_pass": 0,
      "compile_ok": 9,
      "stale_claim_withheld": 10,
      "wrong_wrapper_site": 0,
      "duplicate_edit_suppressed": 5,
      "result_ok_but_raw_failed": 0,
      "primary": {
        "pass": 8,
        "no_final": 1,
        "edit_protocol_fail": 1
      }
    }
  }
}
```

## Rows
- rep 1 SOURCE_ONLY: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__SOURCE_ONLY__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=False task_result=False semantic=None compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_STALE_GATED: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__TMF_STALE_GATED__r1.raw.json
- rep 2 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__SOURCE_ONLY__r2.raw.json
- rep 2 STALE_DOC_CONTROL: raw=False task_result=False semantic=None compile=True fresh=False failure=semantic_boundary_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__STALE_DOC_CONTROL__r2.raw.json
- rep 2 TMF_STALE_GATED: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__TMF_STALE_GATED__r2.raw.json
- rep 3 SOURCE_ONLY: raw=False task_result=False semantic=None compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__SOURCE_ONLY__r3.raw.json
- rep 3 STALE_DOC_CONTROL: raw=False task_result=False semantic=None compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__STALE_DOC_CONTROL__r3.raw.json
- rep 3 TMF_STALE_GATED: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__TMF_STALE_GATED__r3.raw.json
- rep 4 SOURCE_ONLY: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__SOURCE_ONLY__r4.raw.json
- rep 4 STALE_DOC_CONTROL: raw=False task_result=False semantic=False compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__STALE_DOC_CONTROL__r4.raw.json
- rep 4 TMF_STALE_GATED: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__TMF_STALE_GATED__r4.raw.json
- rep 5 SOURCE_ONLY: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__SOURCE_ONLY__r5.raw.json
- rep 5 STALE_DOC_CONTROL: raw=False task_result=False semantic=False compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__STALE_DOC_CONTROL__r5.raw.json
- rep 5 TMF_STALE_GATED: raw=False task_result=False semantic=None compile=True fresh=False failure=no_final reason={"correct_helper_site": false, "wrong_wrapper_site": false, "hook_defs": 0, "hook_calls": 0, "hook_defs_added": 0, "hook_calls_added": 0} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__TMF_STALE_GATED__r5.raw.json
- rep 6 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__SOURCE_ONLY__r6.raw.json
- rep 6 STALE_DOC_CONTROL: raw=False task_result=False semantic=False compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__STALE_DOC_CONTROL__r6.raw.json
- rep 6 TMF_STALE_GATED: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__TMF_STALE_GATED__r6.raw.json
- rep 7 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__SOURCE_ONLY__r7.raw.json
- rep 7 STALE_DOC_CONTROL: raw=False task_result=False semantic=None compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__STALE_DOC_CONTROL__r7.raw.json
- rep 7 TMF_STALE_GATED: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__TMF_STALE_GATED__r7.raw.json
- rep 8 SOURCE_ONLY: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__SOURCE_ONLY__r8.raw.json
- rep 8 STALE_DOC_CONTROL: raw=False task_result=False semantic=None compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__STALE_DOC_CONTROL__r8.raw.json
- rep 8 TMF_STALE_GATED: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__TMF_STALE_GATED__r8.raw.json
- rep 9 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__SOURCE_ONLY__r9.raw.json
- rep 9 STALE_DOC_CONTROL: raw=False task_result=False semantic=False compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__STALE_DOC_CONTROL__r9.raw.json
- rep 9 TMF_STALE_GATED: raw=False task_result=False semantic=None compile=False fresh=False failure=edit_protocol_fail reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs": 0, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__TMF_STALE_GATED__r9.raw.json
- rep 10 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__SOURCE_ONLY__r10.raw.json
- rep 10 STALE_DOC_CONTROL: raw=False task_result=False semantic=False compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__STALE_DOC_CONTROL__r10.raw.json
- rep 10 TMF_STALE_GATED: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m08_feature_r10/GUAVA_M08__TMF_STALE_GATED__r10.raw.json
