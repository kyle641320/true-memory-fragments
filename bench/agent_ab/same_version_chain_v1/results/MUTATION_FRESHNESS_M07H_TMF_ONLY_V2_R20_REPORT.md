# M07h TMF only v2 report

{
  "mode": "mutation_freshness_m07h",
  "runs": 20,
  "final_gate": "hard",
  "result_loop": null,
  "max_turns": 5,
  "max_no_progress": null,
  "by_arm": {
    "SOURCE_ONLY": {
      "runs": 0,
      "raw_pass": 0,
      "task_result_pass": 0,
      "post_test_ok": 0,
      "semantic_evaluable": 0,
      "semantic_adjusted_pass": 0,
      "compile_ok": 0,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 0,
      "primary": {}
    },
    "STALE_DOC_CONTROL": {
      "runs": 0,
      "raw_pass": 0,
      "task_result_pass": 0,
      "post_test_ok": 0,
      "semantic_evaluable": 0,
      "semantic_adjusted_pass": 0,
      "compile_ok": 0,
      "stale_claim_withheld": 0,
      "wrong_wrapper_site": 0,
      "primary": {}
    },
    "TMF_STALE_GATED": {
      "runs": 20,
      "raw_pass": 16,
      "task_result_pass": 16,
      "post_test_ok": 16,
      "semantic_evaluable": 19,
      "semantic_adjusted_pass": 16,
      "compile_ok": 20,
      "stale_claim_withheld": 20,
      "wrong_wrapper_site": 0,
      "primary": {
        "edit_protocol_fail": 1,
        "pass": 16,
        "semantic_boundary_fail": 3
      }
    }
  }
}
