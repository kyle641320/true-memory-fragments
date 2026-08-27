# Guava M09 Cross-File Chain Stale Report

Bounded real-Guava EventBus fixture. Source mutation moves the PerThreadQueuedDispatcher subscriber dispatch edge from the inline queue-drain loop into a two-hop helper chain (`dispatchQueuedSubscriber` -> `dispatchPreparedSubscriber`), while the old dispatch loop remains live and compilable. A no-op `hook()` helper is predeclared so the task tests call-site selection rather than hook-definition protocol. The task prompt is intentionally low-information: it does not name Dispatcher.java, dispatchEvent, queue drain details, or the correct helper. The stale doc arm points at the old inline queue-loop boundary; TMF stale-gated arm withholds the stale bound claim.

```json
{
  "mode": "guava_m09_lowinfo_cross_chain_stale",
  "runs": 30,
  "final_gate": "hard",
  "max_turns": 10,
  "by_arm": {
    "SOURCE_ONLY": {
      "runs": 10,
      "raw_pass": 9,
      "task_result_pass": 9,
      "post_test_ok": 9,
      "semantic_evaluable": 2,
      "semantic_adjusted_pass": 2,
      "compile_ok": 10,
      "stale_claim_withheld": 0,
      "wrong_inline_loop_site": 0,
      "duplicate_edit_suppressed": 1,
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
      "semantic_evaluable": 3,
      "semantic_adjusted_pass": 0,
      "compile_ok": 10,
      "stale_claim_withheld": 0,
      "wrong_inline_loop_site": 9,
      "duplicate_edit_suppressed": 3,
      "result_ok_but_raw_failed": 0,
      "primary": {
        "semantic_boundary_fail": 3,
        "edit_protocol_fail": 7
      }
    },
    "TMF_STALE_GATED": {
      "runs": 10,
      "raw_pass": 9,
      "task_result_pass": 9,
      "post_test_ok": 9,
      "semantic_evaluable": 7,
      "semantic_adjusted_pass": 7,
      "compile_ok": 10,
      "stale_claim_withheld": 10,
      "wrong_inline_loop_site": 0,
      "duplicate_edit_suppressed": 3,
      "result_ok_but_raw_failed": 0,
      "primary": {
        "pass": 9,
        "edit_protocol_fail": 1
      }
    }
  }
}
```

## Rows
- rep 1 SOURCE_ONLY: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_prepared_site": true, "wrong_inline_loop_site": false, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__SOURCE_ONLY__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=False task_result=False semantic=None compile=True fresh=False failure=semantic_boundary_fail reason={"correct_prepared_site": false, "wrong_inline_loop_site": true, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_prepared_site": true, "wrong_inline_loop_site": false, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__TMF_STALE_GATED__r1.raw.json
- rep 2 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_prepared_site": true, "wrong_inline_loop_site": false, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__SOURCE_ONLY__r2.raw.json
- rep 2 STALE_DOC_CONTROL: raw=False task_result=False semantic=None compile=True fresh=False failure=edit_protocol_fail reason={"correct_prepared_site": false, "wrong_inline_loop_site": true, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__STALE_DOC_CONTROL__r2.raw.json
- rep 2 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_prepared_site": true, "wrong_inline_loop_site": false, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__TMF_STALE_GATED__r2.raw.json
- rep 3 SOURCE_ONLY: raw=False task_result=False semantic=None compile=True fresh=False failure=edit_protocol_fail reason={"correct_prepared_site": false, "wrong_inline_loop_site": false, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 0, "hook_defs_added": 0, "hook_calls_added": 0} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__SOURCE_ONLY__r3.raw.json
- rep 3 STALE_DOC_CONTROL: raw=False task_result=False semantic=None compile=True fresh=False failure=edit_protocol_fail reason={"correct_prepared_site": false, "wrong_inline_loop_site": true, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__STALE_DOC_CONTROL__r3.raw.json
- rep 3 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_prepared_site": true, "wrong_inline_loop_site": false, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__TMF_STALE_GATED__r3.raw.json
- rep 4 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_prepared_site": true, "wrong_inline_loop_site": false, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__SOURCE_ONLY__r4.raw.json
- rep 4 STALE_DOC_CONTROL: raw=False task_result=False semantic=None compile=True fresh=False failure=edit_protocol_fail reason={"correct_prepared_site": false, "wrong_inline_loop_site": true, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__STALE_DOC_CONTROL__r4.raw.json
- rep 4 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_prepared_site": true, "wrong_inline_loop_site": false, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__TMF_STALE_GATED__r4.raw.json
- rep 5 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_prepared_site": true, "wrong_inline_loop_site": false, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__SOURCE_ONLY__r5.raw.json
- rep 5 STALE_DOC_CONTROL: raw=False task_result=False semantic=False compile=True fresh=False failure=semantic_boundary_fail reason={"correct_prepared_site": false, "wrong_inline_loop_site": true, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__STALE_DOC_CONTROL__r5.raw.json
- rep 5 TMF_STALE_GATED: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_prepared_site": true, "wrong_inline_loop_site": false, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__TMF_STALE_GATED__r5.raw.json
- rep 6 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_prepared_site": true, "wrong_inline_loop_site": false, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__SOURCE_ONLY__r6.raw.json
- rep 6 STALE_DOC_CONTROL: raw=False task_result=False semantic=False compile=True fresh=False failure=edit_protocol_fail reason={"correct_prepared_site": false, "wrong_inline_loop_site": true, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__STALE_DOC_CONTROL__r6.raw.json
- rep 6 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_prepared_site": true, "wrong_inline_loop_site": false, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__TMF_STALE_GATED__r6.raw.json
- rep 7 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_prepared_site": true, "wrong_inline_loop_site": false, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__SOURCE_ONLY__r7.raw.json
- rep 7 STALE_DOC_CONTROL: raw=False task_result=False semantic=None compile=True fresh=False failure=semantic_boundary_fail reason={"correct_prepared_site": false, "wrong_inline_loop_site": true, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__STALE_DOC_CONTROL__r7.raw.json
- rep 7 TMF_STALE_GATED: raw=False task_result=False semantic=None compile=True fresh=False failure=edit_protocol_fail reason={"correct_prepared_site": false, "wrong_inline_loop_site": false, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 0, "hook_defs_added": 0, "hook_calls_added": 0} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__TMF_STALE_GATED__r7.raw.json
- rep 8 SOURCE_ONLY: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_prepared_site": true, "wrong_inline_loop_site": false, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__SOURCE_ONLY__r8.raw.json
- rep 8 STALE_DOC_CONTROL: raw=False task_result=False semantic=False compile=True fresh=False failure=edit_protocol_fail reason={"correct_prepared_site": false, "wrong_inline_loop_site": true, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__STALE_DOC_CONTROL__r8.raw.json
- rep 8 TMF_STALE_GATED: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_prepared_site": true, "wrong_inline_loop_site": false, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__TMF_STALE_GATED__r8.raw.json
- rep 9 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_prepared_site": true, "wrong_inline_loop_site": false, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__SOURCE_ONLY__r9.raw.json
- rep 9 STALE_DOC_CONTROL: raw=False task_result=False semantic=None compile=True fresh=False failure=edit_protocol_fail reason={"correct_prepared_site": false, "wrong_inline_loop_site": false, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 0, "hook_defs_added": 0, "hook_calls_added": 0} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__STALE_DOC_CONTROL__r9.raw.json
- rep 9 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_prepared_site": true, "wrong_inline_loop_site": false, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__TMF_STALE_GATED__r9.raw.json
- rep 10 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_prepared_site": true, "wrong_inline_loop_site": false, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__SOURCE_ONLY__r10.raw.json
- rep 10 STALE_DOC_CONTROL: raw=False task_result=False semantic=None compile=True fresh=False failure=edit_protocol_fail reason={"correct_prepared_site": false, "wrong_inline_loop_site": true, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__STALE_DOC_CONTROL__r10.raw.json
- rep 10 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_prepared_site": true, "wrong_inline_loop_site": false, "wrong_other_dispatch_site": false, "hook_defs": 1, "hook_calls": 1, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/guava_m09_lowinfo_r10/GUAVA_M09__TMF_STALE_GATED__r10.raw.json
