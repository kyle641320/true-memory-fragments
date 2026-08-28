# Guava M11 Exception Pre-read Stale Source Report

Bounded real-Guava EventBus fixture. Source mutation moves the configured SubscriberExceptionHandler handoff from EventBus.handleSubscriberException into a helper (`notifySubscriberExceptionHandler`), while the old wrapper remains live and compilable. A no-op `hook()` helper is predeclared so the task tests call-site selection rather than hook-definition protocol. The task prompt is intentionally low-information: it does not name the helper. The stale doc arm points at the old wrapper boundary; TMF stale-gated arm withholds the stale bound claim.

```json
{
  "mode": "guava_m11_exception_preread_stale_source",
  "runs": 4,
  "final_gate": "hard",
  "max_turns": 10,
  "by_arm": {
    "SOURCE_ONLY": {
      "runs": 1,
      "raw_pass": 0,
      "task_result_pass": 0,
      "post_test_ok": 0,
      "semantic_evaluable": 0,
      "semantic_adjusted_pass": 0,
      "compile_ok": 1,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 0,
      "duplicate_edit_suppressed": 0,
      "result_ok_but_raw_failed": 0,
      "primary": {
        "no_final": 1
      }
    },
    "PREREAD_STALE_SOURCE": {
      "runs": 1,
      "raw_pass": 1,
      "task_result_pass": 1,
      "post_test_ok": 1,
      "semantic_evaluable": 0,
      "semantic_adjusted_pass": 0,
      "compile_ok": 1,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 0,
      "duplicate_edit_suppressed": 0,
      "result_ok_but_raw_failed": 0,
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
      "duplicate_edit_suppressed": 1,
      "result_ok_but_raw_failed": 0,
      "primary": {
        "pass": 1
      }
    },
    "TMF_STALE_GATED": {
      "runs": 1,
      "raw_pass": 1,
      "task_result_pass": 1,
      "post_test_ok": 1,
      "semantic_evaluable": 0,
      "semantic_adjusted_pass": 0,
      "compile_ok": 1,
      "stale_claim_withheld": 1,
      "wrong_wrapper_site": 0,
      "duplicate_edit_suppressed": 0,
      "result_ok_but_raw_failed": 0,
      "primary": {
        "pass": 1
      }
    }
  }
}
```

## Rows
- rep 1 SOURCE_ONLY: raw=False task_result=False semantic=None compile=True fresh=False failure=no_final reason={"correct_helper_site": false, "wrong_wrapper_site": false, "hook_defs": 1, "hook_calls": 0, "hook_defs_added": 0, "hook_calls_added": 0} raw_path=results/raw/guava_m11_exception_smoke_r1/GUAVA_M11__SOURCE_ONLY__r1.raw.json
- rep 1 PREREAD_STALE_SOURCE: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m11_exception_smoke_r1/GUAVA_M11__PREREAD_STALE_SOURCE__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m11_exception_smoke_r1/GUAVA_M11__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_STALE_GATED: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m11_exception_smoke_r1/GUAVA_M11__TMF_STALE_GATED__r1.raw.json
