# Mutation Freshness M07g Report

Deterministic synthetic fixture: same M07 fixture family, but result-loop now behaves like post-verification human补做: the runner does not surface per-turn result state to the agent during continuation. The only feedback is a generic continue prompt;验收只判结果，不提前喂对错。

```json
{
  "mode": "mutation_freshness_m07h",
  "runs": 30,
  "final_gate": "hard",
  "result_loop": null,
  "max_turns": 5,
  "max_no_progress": null,
  "by_arm": {
    "SOURCE_ONLY": {
      "runs": 10,
      "raw_pass": 10,
      "task_result_pass": 10,
      "post_test_ok": 10,
      "semantic_evaluable": 10,
      "semantic_adjusted_pass": 10,
      "compile_ok": 10,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 0,
      "primary": {
        "pass": 10
      }
    },
    "STALE_DOC_CONTROL": {
      "runs": 10,
      "raw_pass": 7,
      "task_result_pass": 8,
      "post_test_ok": 8,
      "semantic_evaluable": 7,
      "semantic_adjusted_pass": 7,
      "compile_ok": 10,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 0,
      "primary": {
        "pass": 7,
        "edit_protocol_fail": 1,
        "no_final": 2
      }
    },
    "TMF_STALE_GATED": {
      "runs": 10,
      "raw_pass": 8,
      "task_result_pass": 10,
      "post_test_ok": 10,
      "semantic_evaluable": 8,
      "semantic_adjusted_pass": 8,
      "compile_ok": 10,
      "stale_claim_withheld": 10,
      "wrong_wrapper_site": 0,
      "primary": {
        "edit_protocol_fail": 1,
        "pass": 8,
        "no_final": 1
      }
    }
  }
}
```

## Rows
- rep 1 SOURCE_ONLY: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__SOURCE_ONLY__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_STALE_GATED: raw=False task_result=True semantic=None compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__TMF_STALE_GATED__r1.raw.json
- rep 2 SOURCE_ONLY: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__SOURCE_ONLY__r2.raw.json
- rep 2 STALE_DOC_CONTROL: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__STALE_DOC_CONTROL__r2.raw.json
- rep 2 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__TMF_STALE_GATED__r2.raw.json
- rep 3 SOURCE_ONLY: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__SOURCE_ONLY__r3.raw.json
- rep 3 STALE_DOC_CONTROL: raw=False task_result=False semantic=None compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": false, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 0} raw_path=results/raw/mutation_m07i_smoke_fix/M07__STALE_DOC_CONTROL__r3.raw.json
- rep 3 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__TMF_STALE_GATED__r3.raw.json
- rep 4 SOURCE_ONLY: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__SOURCE_ONLY__r4.raw.json
- rep 4 STALE_DOC_CONTROL: raw=False task_result=False semantic=None compile=True fresh=False failure=no_final reason={"correct_helper_site": false, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 0} raw_path=results/raw/mutation_m07i_smoke_fix/M07__STALE_DOC_CONTROL__r4.raw.json
- rep 4 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__TMF_STALE_GATED__r4.raw.json
- rep 5 SOURCE_ONLY: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__SOURCE_ONLY__r5.raw.json
- rep 5 STALE_DOC_CONTROL: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__STALE_DOC_CONTROL__r5.raw.json
- rep 5 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__TMF_STALE_GATED__r5.raw.json
- rep 6 SOURCE_ONLY: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__SOURCE_ONLY__r6.raw.json
- rep 6 STALE_DOC_CONTROL: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__STALE_DOC_CONTROL__r6.raw.json
- rep 6 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__TMF_STALE_GATED__r6.raw.json
- rep 7 SOURCE_ONLY: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__SOURCE_ONLY__r7.raw.json
- rep 7 STALE_DOC_CONTROL: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__STALE_DOC_CONTROL__r7.raw.json
- rep 7 TMF_STALE_GATED: raw=False task_result=True semantic=None compile=True fresh=False failure=no_final reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__TMF_STALE_GATED__r7.raw.json
- rep 8 SOURCE_ONLY: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__SOURCE_ONLY__r8.raw.json
- rep 8 STALE_DOC_CONTROL: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__STALE_DOC_CONTROL__r8.raw.json
- rep 8 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__TMF_STALE_GATED__r8.raw.json
- rep 9 SOURCE_ONLY: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__SOURCE_ONLY__r9.raw.json
- rep 9 STALE_DOC_CONTROL: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__STALE_DOC_CONTROL__r9.raw.json
- rep 9 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__TMF_STALE_GATED__r9.raw.json
- rep 10 SOURCE_ONLY: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__SOURCE_ONLY__r10.raw.json
- rep 10 STALE_DOC_CONTROL: raw=False task_result=True semantic=None compile=True fresh=False failure=no_final reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__STALE_DOC_CONTROL__r10.raw.json
- rep 10 TMF_STALE_GATED: raw=True task_result=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_m07i_smoke_fix/M07__TMF_STALE_GATED__r10.raw.json
