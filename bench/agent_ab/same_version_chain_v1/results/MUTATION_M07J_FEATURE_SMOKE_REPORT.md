# Mutation Freshness M07j Report

Deterministic synthetic fixture: same M07 fixture family, but the task is a realistic feature-intent request rather than a line/location-specific edit request. `raw_pass` remains a strict protocol score; `task_result_pass`, `wrong_wrapper_site`, and `stale_claim_withheld` are the semantic/stale-gate view. The user-level task does not name the correct helper or target call; duplicate edits are suppressed after the first successful edit in a turn, and broker preflight is recovered before assignment if needed.

```json
{
  "mode": "mutation_m07j",
  "runs": 6,
  "final_gate": "hard",
  "result_loop": null,
  "max_turns": 6,
  "max_no_progress": null,
  "by_arm": {
    "SOURCE_ONLY": {
      "runs": 2,
      "raw_pass": 2,
      "task_result_pass": 2,
      "post_test_ok": 2,
      "semantic_evaluable": 2,
      "semantic_adjusted_pass": 2,
      "compile_ok": 2,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 0,
      "duplicate_edit_suppressed": 0,
      "broker_preflight_recovered": 0,
      "result_ok_but_raw_failed": 0,
      "primary": {
        "pass": 2
      }
    },
    "STALE_DOC_CONTROL": {
      "runs": 2,
      "raw_pass": 1,
      "task_result_pass": 1,
      "post_test_ok": 1,
      "semantic_evaluable": 2,
      "semantic_adjusted_pass": 1,
      "compile_ok": 2,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 1,
      "duplicate_edit_suppressed": 3,
      "broker_preflight_recovered": 0,
      "result_ok_but_raw_failed": 0,
      "primary": {
        "pass": 1,
        "edit_protocol_fail": 1
      }
    },
    "TMF_STALE_GATED": {
      "runs": 2,
      "raw_pass": 2,
      "task_result_pass": 2,
      "post_test_ok": 2,
      "semantic_evaluable": 2,
      "semantic_adjusted_pass": 2,
      "compile_ok": 2,
      "stale_claim_withheld": 2,
      "wrong_wrapper_site": 0,
      "duplicate_edit_suppressed": 0,
      "broker_preflight_recovered": 0,
      "result_ok_but_raw_failed": 0,
      "primary": {
        "pass": 2
      }
    }
  }
}
```

## Rows
- rep 1 SOURCE_ONLY: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_smoke/M07__SOURCE_ONLY__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_smoke/M07__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_smoke/M07__TMF_STALE_GATED__r1.raw.json
- rep 2 SOURCE_ONLY: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_smoke/M07__SOURCE_ONLY__r2.raw.json
- rep 2 STALE_DOC_CONTROL: raw=False task_result=False semantic=False compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_smoke/M07__STALE_DOC_CONTROL__r2.raw.json
- rep 2 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07j_feature_smoke/M07__TMF_STALE_GATED__r2.raw.json
