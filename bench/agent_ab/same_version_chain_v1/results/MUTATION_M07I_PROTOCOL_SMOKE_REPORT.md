# Mutation Freshness M07i Report

Deterministic synthetic fixture: same M07 fixture family with strict metric separation. `raw_pass` remains a strict protocol score; `task_result_pass`, `wrong_wrapper_site`, and `stale_claim_withheld` are the semantic/stale-gate view. Duplicate edits are suppressed after the first successful edit in a turn, and broker preflight is recovered before assignment if needed.

```json
{
  "mode": "mutation_m07i",
  "runs": 3,
  "final_gate": "hard",
  "result_loop": null,
  "max_turns": 5,
  "max_no_progress": null,
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
      "duplicate_edit_suppressed": 2,
      "broker_preflight_recovered": 0,
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
      "duplicate_edit_suppressed": 0,
      "broker_preflight_recovered": 0,
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
      "semantic_evaluable": 1,
      "semantic_adjusted_pass": 1,
      "compile_ok": 1,
      "stale_claim_withheld": 1,
      "wrong_wrapper_site": 0,
      "duplicate_edit_suppressed": 0,
      "broker_preflight_recovered": 0,
      "result_ok_but_raw_failed": 0,
      "primary": {
        "pass": 1
      }
    }
  }
}
```

## Rows
- rep 1 SOURCE_ONLY: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_protocol_smoke/M07__SOURCE_ONLY__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_protocol_smoke/M07__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_protocol_smoke/M07__TMF_STALE_GATED__r1.raw.json
