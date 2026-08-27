# Guava M09 Cross-File Chain Stale Report

Bounded real-Guava EventBus fixture. Source mutation moves the PerThreadQueuedDispatcher subscriber dispatch edge from the inline queue-drain loop into a two-hop helper chain (`dispatchQueuedSubscriber` -> `dispatchPreparedSubscriber`), while the old dispatch loop remains live and compilable. A no-op `hook()` helper is predeclared so the task tests call-site selection rather than hook-definition protocol. The task prompt is intentionally low-information: it does not name Dispatcher.java, dispatchEvent, queue drain details, or the correct helper. The stale doc arm points at the old inline queue-loop boundary; TMF stale-gated arm withholds the stale bound claim.

```json
{
  "mode": "guava_m09_lowinfo_cross_chain_stale",
  "runs": 3,
  "final_gate": "hard",
  "max_turns": 10,
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
      "wrong_inline_loop_site": 0,
      "duplicate_edit_suppressed": 0,
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
      "semantic_evaluable": 0,
      "semantic_adjusted_pass": 0,
      "compile_ok": 1,
      "stale_claim_withheld": 0,
      "wrong_inline_loop_site": 1,
      "duplicate_edit_suppressed": 0,
      "result_ok_but_raw_failed": 0,
      "primary": {
        "semantic_boundary_fail": 1
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
      "wrong_inline_loop_site": 0,
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
- rep 1 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_prepared_site": true, "wrong_inline_loop_site": false, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_smoke/GUAVA_M09__SOURCE_ONLY__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=False task_result=False semantic=None compile=True fresh=False failure=semantic_boundary_fail reason={"correct_prepared_site": false, "wrong_inline_loop_site": true, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_smoke/GUAVA_M09__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_prepared_site": true, "wrong_inline_loop_site": false, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_smoke/GUAVA_M09__TMF_STALE_GATED__r1.raw.json
