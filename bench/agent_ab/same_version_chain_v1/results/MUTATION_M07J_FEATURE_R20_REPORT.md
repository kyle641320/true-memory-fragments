# Mutation Freshness M07j Report

Deterministic synthetic fixture: same M07 fixture family, but the task is a realistic feature-intent request rather than a line/location-specific edit request. `raw_pass` remains a strict protocol score; `task_result_pass`, `wrong_wrapper_site`, and `stale_claim_withheld` are the semantic/stale-gate view. The user-level task does not name the correct helper or target call; duplicate edits are suppressed after the first successful edit in a turn, and broker preflight is recovered before assignment if needed.

```json
{
  "mode": "mutation_m07j",
  "runs": 60,
  "final_gate": "hard",
  "result_loop": null,
  "max_turns": 6,
  "max_no_progress": null,
  "by_arm": {
    "SOURCE_ONLY": {
      "runs": 20,
      "raw_pass": 18,
      "task_result_pass": 18,
      "post_test_ok": 18,
      "semantic_evaluable": 4,
      "semantic_adjusted_pass": 4,
      "compile_ok": 20,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 0,
      "duplicate_edit_suppressed": 0,
      "broker_preflight_recovered": 0,
      "result_ok_but_raw_failed": 0,
      "primary": {
        "pass": 18,
        "no_final": 2
      }
    },
    "STALE_DOC_CONTROL": {
      "runs": 20,
      "raw_pass": 9,
      "task_result_pass": 10,
      "post_test_ok": 10,
      "semantic_evaluable": 12,
      "semantic_adjusted_pass": 2,
      "compile_ok": 20,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 10,
      "duplicate_edit_suppressed": 9,
      "broker_preflight_recovered": 0,
      "result_ok_but_raw_failed": 1,
      "primary": {
        "pass": 9,
        "edit_protocol_fail": 5,
        "semantic_boundary_fail": 5,
        "no_final_after_success": 1
      }
    },
    "TMF_STALE_GATED": {
      "runs": 20,
      "raw_pass": 20,
      "task_result_pass": 20,
      "post_test_ok": 20,
      "semantic_evaluable": 16,
      "semantic_adjusted_pass": 16,
      "compile_ok": 20,
      "stale_claim_withheld": 20,
      "wrong_wrapper_site": 0,
      "duplicate_edit_suppressed": 0,
      "broker_preflight_recovered": 0,
      "result_ok_but_raw_failed": 0,
      "primary": {
        "pass": 20
      }
    }
  }
}
```

## Rows
- rep 1 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__SOURCE_ONLY__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_STALE_GATED: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__TMF_STALE_GATED__r1.raw.json
- rep 2 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__SOURCE_ONLY__r2.raw.json
- rep 2 STALE_DOC_CONTROL: raw=False task_result=False semantic=False compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__STALE_DOC_CONTROL__r2.raw.json
- rep 2 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__TMF_STALE_GATED__r2.raw.json
- rep 3 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__SOURCE_ONLY__r3.raw.json
- rep 3 STALE_DOC_CONTROL: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__STALE_DOC_CONTROL__r3.raw.json
- rep 3 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__TMF_STALE_GATED__r3.raw.json
- rep 4 SOURCE_ONLY: raw=False task_result=False semantic=None compile=True fresh=False failure=no_final reason={"correct_helper_site": false, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 0} raw_path=results/raw/mutation_m07j_feature_r20/M07__SOURCE_ONLY__r4.raw.json
- rep 4 STALE_DOC_CONTROL: raw=False task_result=False semantic=False compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__STALE_DOC_CONTROL__r4.raw.json
- rep 4 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__TMF_STALE_GATED__r4.raw.json
- rep 5 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__SOURCE_ONLY__r5.raw.json
- rep 5 STALE_DOC_CONTROL: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__STALE_DOC_CONTROL__r5.raw.json
- rep 5 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__TMF_STALE_GATED__r5.raw.json
- rep 6 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__SOURCE_ONLY__r6.raw.json
- rep 6 STALE_DOC_CONTROL: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__STALE_DOC_CONTROL__r6.raw.json
- rep 6 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__TMF_STALE_GATED__r6.raw.json
- rep 7 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__SOURCE_ONLY__r7.raw.json
- rep 7 STALE_DOC_CONTROL: raw=False task_result=False semantic=False compile=True fresh=False failure=semantic_boundary_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__STALE_DOC_CONTROL__r7.raw.json
- rep 7 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__TMF_STALE_GATED__r7.raw.json
- rep 8 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__SOURCE_ONLY__r8.raw.json
- rep 8 STALE_DOC_CONTROL: raw=False task_result=False semantic=False compile=True fresh=False failure=semantic_boundary_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__STALE_DOC_CONTROL__r8.raw.json
- rep 8 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__TMF_STALE_GATED__r8.raw.json
- rep 9 SOURCE_ONLY: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__SOURCE_ONLY__r9.raw.json
- rep 9 STALE_DOC_CONTROL: raw=False task_result=False semantic=False compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__STALE_DOC_CONTROL__r9.raw.json
- rep 9 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__TMF_STALE_GATED__r9.raw.json
- rep 10 SOURCE_ONLY: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__SOURCE_ONLY__r10.raw.json
- rep 10 STALE_DOC_CONTROL: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__STALE_DOC_CONTROL__r10.raw.json
- rep 10 TMF_STALE_GATED: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__TMF_STALE_GATED__r10.raw.json
- rep 11 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__SOURCE_ONLY__r11.raw.json
- rep 11 STALE_DOC_CONTROL: raw=False task_result=False semantic=False compile=True fresh=False failure=semantic_boundary_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__STALE_DOC_CONTROL__r11.raw.json
- rep 11 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__TMF_STALE_GATED__r11.raw.json
- rep 12 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__SOURCE_ONLY__r12.raw.json
- rep 12 STALE_DOC_CONTROL: raw=False task_result=False semantic=False compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__STALE_DOC_CONTROL__r12.raw.json
- rep 12 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__TMF_STALE_GATED__r12.raw.json
- rep 13 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__SOURCE_ONLY__r13.raw.json
- rep 13 STALE_DOC_CONTROL: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__STALE_DOC_CONTROL__r13.raw.json
- rep 13 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__TMF_STALE_GATED__r13.raw.json
- rep 14 SOURCE_ONLY: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__SOURCE_ONLY__r14.raw.json
- rep 14 STALE_DOC_CONTROL: raw=False task_result=False semantic=False compile=True fresh=False failure=semantic_boundary_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__STALE_DOC_CONTROL__r14.raw.json
- rep 14 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__TMF_STALE_GATED__r14.raw.json
- rep 15 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__SOURCE_ONLY__r15.raw.json
- rep 15 STALE_DOC_CONTROL: raw=False task_result=False semantic=False compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__STALE_DOC_CONTROL__r15.raw.json
- rep 15 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__TMF_STALE_GATED__r15.raw.json
- rep 16 SOURCE_ONLY: raw=False task_result=False semantic=None compile=True fresh=False failure=no_final reason={"correct_helper_site": false, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 0} raw_path=results/raw/mutation_m07j_feature_r20/M07__SOURCE_ONLY__r16.raw.json
- rep 16 STALE_DOC_CONTROL: raw=False task_result=True semantic=None compile=True fresh=False failure=no_final_after_success reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__STALE_DOC_CONTROL__r16.raw.json
- rep 16 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__TMF_STALE_GATED__r16.raw.json
- rep 17 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__SOURCE_ONLY__r17.raw.json
- rep 17 STALE_DOC_CONTROL: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__STALE_DOC_CONTROL__r17.raw.json
- rep 17 TMF_STALE_GATED: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__TMF_STALE_GATED__r17.raw.json
- rep 18 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__SOURCE_ONLY__r18.raw.json
- rep 18 STALE_DOC_CONTROL: raw=False task_result=False semantic=False compile=True fresh=False failure=semantic_boundary_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__STALE_DOC_CONTROL__r18.raw.json
- rep 18 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__TMF_STALE_GATED__r18.raw.json
- rep 19 SOURCE_ONLY: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__SOURCE_ONLY__r19.raw.json
- rep 19 STALE_DOC_CONTROL: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__STALE_DOC_CONTROL__r19.raw.json
- rep 19 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__TMF_STALE_GATED__r19.raw.json
- rep 20 SOURCE_ONLY: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__SOURCE_ONLY__r20.raw.json
- rep 20 STALE_DOC_CONTROL: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__STALE_DOC_CONTROL__r20.raw.json
- rep 20 TMF_STALE_GATED: raw=True task_result=True semantic=None compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_r20/M07__TMF_STALE_GATED__r20.raw.json
