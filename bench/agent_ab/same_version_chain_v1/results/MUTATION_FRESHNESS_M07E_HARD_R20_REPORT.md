# Mutation Freshness M07 Report

Deterministic synthetic fixture: old claim binds to pre-mutation wrapper; mutation moves prepared reflective boundary into helper while stale wrapper anchor remains compilable.

```json
{
  "mode": "mutation_freshness_m07",
  "runs": 60,
  "final_gate": "hard",
  "by_arm": {
    "SOURCE_ONLY": {
      "runs": 20,
      "raw_pass": 18,
      "semantic_evaluable": 18,
      "semantic_adjusted_pass": 18,
      "compile_ok": 20,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 1,
      "primary": {
        "pass": 18,
        "edit_protocol_fail": 1,
        "no_final": 1
      }
    },
    "STALE_DOC_CONTROL": {
      "runs": 20,
      "raw_pass": 18,
      "semantic_evaluable": 18,
      "semantic_adjusted_pass": 18,
      "compile_ok": 20,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 1,
      "primary": {
        "pass": 18,
        "no_final": 1,
        "edit_protocol_fail": 1
      }
    },
    "TMF_STALE_GATED": {
      "runs": 20,
      "raw_pass": 19,
      "semantic_evaluable": 19,
      "semantic_adjusted_pass": 19,
      "compile_ok": 20,
      "stale_claim_withheld": 20,
      "wrong_wrapper_site": 0,
      "primary": {
        "pass": 19,
        "edit_protocol_fail": 1
      }
    }
  }
}
```

## Rows
- rep 1 SOURCE_ONLY: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__SOURCE_ONLY__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_STALE_GATED: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__TMF_STALE_GATED__r1.raw.json
- rep 2 SOURCE_ONLY: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__SOURCE_ONLY__r2.raw.json
- rep 2 STALE_DOC_CONTROL: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__STALE_DOC_CONTROL__r2.raw.json
- rep 2 TMF_STALE_GATED: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__TMF_STALE_GATED__r2.raw.json
- rep 3 SOURCE_ONLY: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__SOURCE_ONLY__r3.raw.json
- rep 3 STALE_DOC_CONTROL: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__STALE_DOC_CONTROL__r3.raw.json
- rep 3 TMF_STALE_GATED: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__TMF_STALE_GATED__r3.raw.json
- rep 4 SOURCE_ONLY: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__SOURCE_ONLY__r4.raw.json
- rep 4 STALE_DOC_CONTROL: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__STALE_DOC_CONTROL__r4.raw.json
- rep 4 TMF_STALE_GATED: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__TMF_STALE_GATED__r4.raw.json
- rep 5 SOURCE_ONLY: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__SOURCE_ONLY__r5.raw.json
- rep 5 STALE_DOC_CONTROL: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__STALE_DOC_CONTROL__r5.raw.json
- rep 5 TMF_STALE_GATED: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__TMF_STALE_GATED__r5.raw.json
- rep 6 SOURCE_ONLY: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__SOURCE_ONLY__r6.raw.json
- rep 6 STALE_DOC_CONTROL: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__STALE_DOC_CONTROL__r6.raw.json
- rep 6 TMF_STALE_GATED: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__TMF_STALE_GATED__r6.raw.json
- rep 7 SOURCE_ONLY: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__SOURCE_ONLY__r7.raw.json
- rep 7 STALE_DOC_CONTROL: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__STALE_DOC_CONTROL__r7.raw.json
- rep 7 TMF_STALE_GATED: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__TMF_STALE_GATED__r7.raw.json
- rep 8 SOURCE_ONLY: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__SOURCE_ONLY__r8.raw.json
- rep 8 STALE_DOC_CONTROL: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__STALE_DOC_CONTROL__r8.raw.json
- rep 8 TMF_STALE_GATED: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__TMF_STALE_GATED__r8.raw.json
- rep 9 SOURCE_ONLY: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__SOURCE_ONLY__r9.raw.json
- rep 9 STALE_DOC_CONTROL: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__STALE_DOC_CONTROL__r9.raw.json
- rep 9 TMF_STALE_GATED: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__TMF_STALE_GATED__r9.raw.json
- rep 10 SOURCE_ONLY: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__SOURCE_ONLY__r10.raw.json
- rep 10 STALE_DOC_CONTROL: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__STALE_DOC_CONTROL__r10.raw.json
- rep 10 TMF_STALE_GATED: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__TMF_STALE_GATED__r10.raw.json
- rep 11 SOURCE_ONLY: raw=False semantic=None compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__SOURCE_ONLY__r11.raw.json
- rep 11 STALE_DOC_CONTROL: raw=False semantic=None compile=True fresh=False failure=no_final reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__STALE_DOC_CONTROL__r11.raw.json
- rep 11 TMF_STALE_GATED: raw=False semantic=None compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__TMF_STALE_GATED__r11.raw.json
- rep 12 SOURCE_ONLY: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__SOURCE_ONLY__r12.raw.json
- rep 12 STALE_DOC_CONTROL: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__STALE_DOC_CONTROL__r12.raw.json
- rep 12 TMF_STALE_GATED: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__TMF_STALE_GATED__r12.raw.json
- rep 13 SOURCE_ONLY: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__SOURCE_ONLY__r13.raw.json
- rep 13 STALE_DOC_CONTROL: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__STALE_DOC_CONTROL__r13.raw.json
- rep 13 TMF_STALE_GATED: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__TMF_STALE_GATED__r13.raw.json
- rep 14 SOURCE_ONLY: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__SOURCE_ONLY__r14.raw.json
- rep 14 STALE_DOC_CONTROL: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__STALE_DOC_CONTROL__r14.raw.json
- rep 14 TMF_STALE_GATED: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__TMF_STALE_GATED__r14.raw.json
- rep 15 SOURCE_ONLY: raw=False semantic=None compile=True fresh=False failure=no_final reason={"correct_helper_site": false, "wrong_wrapper_site": true, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__SOURCE_ONLY__r15.raw.json
- rep 15 STALE_DOC_CONTROL: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__STALE_DOC_CONTROL__r15.raw.json
- rep 15 TMF_STALE_GATED: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__TMF_STALE_GATED__r15.raw.json
- rep 16 SOURCE_ONLY: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__SOURCE_ONLY__r16.raw.json
- rep 16 STALE_DOC_CONTROL: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__STALE_DOC_CONTROL__r16.raw.json
- rep 16 TMF_STALE_GATED: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__TMF_STALE_GATED__r16.raw.json
- rep 17 SOURCE_ONLY: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__SOURCE_ONLY__r17.raw.json
- rep 17 STALE_DOC_CONTROL: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__STALE_DOC_CONTROL__r17.raw.json
- rep 17 TMF_STALE_GATED: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__TMF_STALE_GATED__r17.raw.json
- rep 18 SOURCE_ONLY: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__SOURCE_ONLY__r18.raw.json
- rep 18 STALE_DOC_CONTROL: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__STALE_DOC_CONTROL__r18.raw.json
- rep 18 TMF_STALE_GATED: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__TMF_STALE_GATED__r18.raw.json
- rep 19 SOURCE_ONLY: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__SOURCE_ONLY__r19.raw.json
- rep 19 STALE_DOC_CONTROL: raw=False semantic=None compile=True fresh=False failure=edit_protocol_fail reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__STALE_DOC_CONTROL__r19.raw.json
- rep 19 TMF_STALE_GATED: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__TMF_STALE_GATED__r19.raw.json
- rep 20 SOURCE_ONLY: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__SOURCE_ONLY__r20.raw.json
- rep 20 STALE_DOC_CONTROL: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__STALE_DOC_CONTROL__r20.raw.json
- rep 20 TMF_STALE_GATED: raw=True semantic=True compile=True fresh=False failure=pass reason={"correct_helper_site": true, "wrong_wrapper_site": false, "hook_defs_added": 0, "hook_calls_added": 1} raw_path=results/raw/mutation_freshness_m07e_hard_r20/M07__TMF_STALE_GATED__r20.raw.json
