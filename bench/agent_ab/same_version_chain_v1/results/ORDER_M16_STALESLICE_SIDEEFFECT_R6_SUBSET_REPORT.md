# Order M16 Stale-Slice Side-Effect Guard R6 Subset Report

Complete reps 1-6 extracted from interrupted R8 run; all four arms have exactly six rows.

```json
{
  "mode": "order_m16_staleslice_sideeffect_complete_r6_subset",
  "runs": 24,
  "by_arm": {
    "SOURCE_ONLY": {
      "runs": 6,
      "raw_pass": 0,
      "task_result_pass": 0,
      "post_test_ok": 0,
      "semantic_evaluable": 6,
      "semantic_adjusted_pass": 0,
      "stale_claim_withheld": 0,
      "marks_awaiting_review": 6,
      "branches_on_payment_status": 6,
      "primary": {
        "hidden_oracle_fail": 6
      }
    },
    "PREREAD_STALE_SOURCE": {
      "runs": 6,
      "raw_pass": 0,
      "task_result_pass": 0,
      "post_test_ok": 0,
      "semantic_evaluable": 6,
      "semantic_adjusted_pass": 0,
      "stale_claim_withheld": 0,
      "marks_awaiting_review": 6,
      "branches_on_payment_status": 6,
      "primary": {
        "hidden_oracle_fail": 6
      }
    },
    "STALE_DOC_CONTROL": {
      "runs": 6,
      "raw_pass": 6,
      "task_result_pass": 6,
      "post_test_ok": 6,
      "semantic_evaluable": 6,
      "semantic_adjusted_pass": 6,
      "stale_claim_withheld": 0,
      "marks_awaiting_review": 6,
      "branches_on_payment_status": 6,
      "primary": {
        "pass": 6
      }
    },
    "TMF_REFRESHED_MAP": {
      "runs": 6,
      "raw_pass": 6,
      "task_result_pass": 6,
      "post_test_ok": 6,
      "semantic_evaluable": 6,
      "semantic_adjusted_pass": 6,
      "stale_claim_withheld": 6,
      "marks_awaiting_review": 6,
      "branches_on_payment_status": 6,
      "primary": {
        "pass": 6
      }
    }
  }
}
```
