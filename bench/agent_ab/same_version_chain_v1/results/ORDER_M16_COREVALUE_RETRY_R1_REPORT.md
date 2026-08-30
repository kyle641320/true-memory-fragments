# Order M16 Complex Two-Phase Hidden-Oracle Report

Fixture: synthetic bounded Maven order creation chain. Phase A old behavior is benign: every created payment intent is final, order creation reserves inventory, marks READY, saves, and immediately publishes ORDER_CREATED. Phase B mutates the downstream payment intent contract so some intents remain under review; hidden JUnit tests require those orders to be AWAITING_REVIEW and suppress ORDER_CREATED while preserving normal confirmed orders.

Protocol notes: the user prompt is vague and does not name files/methods/APIs/status names; hidden oracle tests are not listed/readable by the agent; compile action runs `mvn -q -DskipTests compile` only; final post-test injects and runs hidden JUnit tests.

```json
{
  "mode": "order_m16_complex_two_phase_payment_review",
  "runs": 4,
  "by_arm": {
    "SOURCE_ONLY": {
      "runs": 1,
      "raw_pass": 0,
      "task_result_pass": 0,
      "post_test_ok": 0,
      "semantic_evaluable": 1,
      "semantic_adjusted_pass": 0,
      "stale_claim_withheld": 0,
      "marks_awaiting_review": 0,
      "branches_on_payment_status": 1,
      "primary": {
        "hidden_oracle_fail": 1
      }
    },
    "PREREAD_STALE_SOURCE": {
      "runs": 1,
      "raw_pass": 0,
      "task_result_pass": 0,
      "post_test_ok": 0,
      "semantic_evaluable": 1,
      "semantic_adjusted_pass": 0,
      "stale_claim_withheld": 0,
      "marks_awaiting_review": 0,
      "branches_on_payment_status": 1,
      "primary": {
        "hidden_oracle_fail": 1
      }
    },
    "STALE_DOC_CONTROL": {
      "runs": 1,
      "raw_pass": 1,
      "task_result_pass": 1,
      "post_test_ok": 1,
      "semantic_evaluable": 1,
      "semantic_adjusted_pass": 1,
      "stale_claim_withheld": 0,
      "marks_awaiting_review": 1,
      "branches_on_payment_status": 1,
      "primary": {
        "pass": 1
      }
    },
    "TMF_REFRESHED_MAP": {
      "runs": 1,
      "raw_pass": 0,
      "task_result_pass": 0,
      "post_test_ok": 1,
      "semantic_evaluable": 1,
      "semantic_adjusted_pass": 0,
      "stale_claim_withheld": 1,
      "marks_awaiting_review": 1,
      "branches_on_payment_status": 0,
      "primary": {
        "compile_action_fail": 1
      }
    }
  }
}
```

## Rows
- rep 1 SOURCE_ONLY: raw=False task=False semantic=False post=False withheld=False failure=hidden_oracle_fail placement={"branches_on_payment_status": true, "marks_awaiting_review": false, "marks_ready": true, "publishes_order_created": true, "conditional_publish_after_status": true, "visible_tests_present": false} raw_path=results/raw/order_m16_corevalue_retry_r1/ORDER_M16__SOURCE_ONLY__r1.raw.json
- rep 1 PREREAD_STALE_SOURCE: raw=False task=False semantic=False post=False withheld=False failure=hidden_oracle_fail placement={"branches_on_payment_status": true, "marks_awaiting_review": false, "marks_ready": true, "publishes_order_created": true, "conditional_publish_after_status": true, "visible_tests_present": false} raw_path=results/raw/order_m16_corevalue_retry_r1/ORDER_M16__PREREAD_STALE_SOURCE__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=True task=True semantic=True post=True withheld=False failure=pass placement={"branches_on_payment_status": true, "marks_awaiting_review": true, "marks_ready": true, "publishes_order_created": true, "conditional_publish_after_status": true, "visible_tests_present": false} raw_path=results/raw/order_m16_corevalue_retry_r1/ORDER_M16__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_REFRESHED_MAP: raw=False task=False semantic=False post=False withheld=True failure=compile_action_fail placement={"branches_on_payment_status": false, "marks_awaiting_review": true, "marks_ready": true, "publishes_order_created": true, "conditional_publish_after_status": false, "visible_tests_present": false} raw_path=results/raw/order_m16_corevalue_retry_r1/ORDER_M16__TMF_REFRESHED_MAP__r1.raw.json
