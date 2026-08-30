# Order M21 Stale-Doc-Mislead Hidden-Oracle Report

Fixture: synthetic bounded Maven order creation chain with deliberately overconfident stale-doc control. Phase A old behavior is benign: every created payment intent is final, order creation reserves inventory, marks READY, saves, and immediately publishes ORDER_CREATED. Phase B mutates the downstream payment intent contract so some intents remain under review; hidden JUnit tests require those orders to be AWAITING_REVIEW and suppress ORDER_CREATED while preserving normal confirmed orders. Use of the new FulfillmentPolicy API is reported separately as implementation evidence, not required for semantic pass.

Protocol notes: the user prompt is vague and does not name files/methods/APIs/status names; STALE_DOC_CONTROL receives an intentionally overconfident old handbook note that forbids guarding ORDER_CREATED; hidden oracle tests are not listed/readable by the agent; compile action runs `mvn -q -DskipTests compile` only; final post-test injects and runs hidden JUnit tests.

```json
{
  "mode": "order_m21_stale_api_trap_fulfillment_gate",
  "runs": 16,
  "by_arm": {
    "SOURCE_ONLY": {
      "runs": 4,
      "raw_pass": 2,
      "task_result_pass": 2,
      "post_test_ok": 2,
      "semantic_evaluable": 4,
      "semantic_adjusted_pass": 2,
      "stale_claim_withheld": 0,
      "marks_awaiting_review": 2,
      "branches_on_payment_status": 2,
      "primary": {
        "hidden_oracle_fail": 2,
        "pass": 2
      }
    },
    "PREREAD_STALE_SOURCE": {
      "runs": 4,
      "raw_pass": 0,
      "task_result_pass": 0,
      "post_test_ok": 0,
      "semantic_evaluable": 4,
      "semantic_adjusted_pass": 0,
      "stale_claim_withheld": 0,
      "marks_awaiting_review": 0,
      "branches_on_payment_status": 1,
      "primary": {
        "hidden_oracle_fail": 4
      }
    },
    "STALE_DOC_CONTROL": {
      "runs": 4,
      "raw_pass": 0,
      "task_result_pass": 0,
      "post_test_ok": 0,
      "semantic_evaluable": 4,
      "semantic_adjusted_pass": 0,
      "stale_claim_withheld": 0,
      "marks_awaiting_review": 3,
      "branches_on_payment_status": 3,
      "primary": {
        "hidden_oracle_fail": 4
      }
    },
    "TMF_REFRESHED_MAP": {
      "runs": 4,
      "raw_pass": 2,
      "task_result_pass": 2,
      "post_test_ok": 2,
      "semantic_evaluable": 4,
      "semantic_adjusted_pass": 2,
      "stale_claim_withheld": 4,
      "marks_awaiting_review": 4,
      "branches_on_payment_status": 4,
      "primary": {
        "hidden_oracle_fail": 2,
        "pass": 2
      }
    }
  }
}
```

## Rows
- rep 1 SOURCE_ONLY: raw=False task=False semantic=False post=False withheld=False failure=hidden_oracle_fail placement={"branches_on_payment_status": false, "marks_awaiting_review": false, "marks_ready": true, "publishes_order_created": true, "conditional_publish_after_status": true, "uses_current_fulfillment_policy": true, "uses_stale_policy_gate": false, "visible_tests_present": false} raw_path=results/raw/order_m21_stale_api_trap_classfix_checkerfix_r4/ORDER_M21__SOURCE_ONLY__r1.raw.json
- rep 1 PREREAD_STALE_SOURCE: raw=False task=False semantic=False post=False withheld=False failure=hidden_oracle_fail placement={"branches_on_payment_status": true, "marks_awaiting_review": false, "marks_ready": true, "publishes_order_created": true, "conditional_publish_after_status": true, "uses_current_fulfillment_policy": false, "uses_stale_policy_gate": true, "visible_tests_present": false} raw_path=results/raw/order_m21_stale_api_trap_classfix_checkerfix_r4/ORDER_M21__PREREAD_STALE_SOURCE__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=False task=False semantic=False post=False withheld=False failure=hidden_oracle_fail placement={"branches_on_payment_status": false, "marks_awaiting_review": false, "marks_ready": true, "publishes_order_created": true, "conditional_publish_after_status": false, "uses_current_fulfillment_policy": false, "uses_stale_policy_gate": true, "visible_tests_present": false} raw_path=results/raw/order_m21_stale_api_trap_classfix_checkerfix_r4/ORDER_M21__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_REFRESHED_MAP: raw=False task=False semantic=False post=False withheld=True failure=hidden_oracle_fail placement={"branches_on_payment_status": true, "marks_awaiting_review": true, "marks_ready": true, "publishes_order_created": true, "conditional_publish_after_status": true, "uses_current_fulfillment_policy": false, "uses_stale_policy_gate": true, "visible_tests_present": false} raw_path=results/raw/order_m21_stale_api_trap_classfix_checkerfix_r4/ORDER_M21__TMF_REFRESHED_MAP__r1.raw.json
- rep 2 SOURCE_ONLY: raw=True task=True semantic=True post=True withheld=False failure=pass placement={"branches_on_payment_status": true, "marks_awaiting_review": true, "marks_ready": true, "publishes_order_created": true, "conditional_publish_after_status": true, "uses_current_fulfillment_policy": true, "uses_stale_policy_gate": false, "visible_tests_present": false} raw_path=results/raw/order_m21_stale_api_trap_classfix_checkerfix_r4/ORDER_M21__SOURCE_ONLY__r2.raw.json
- rep 2 PREREAD_STALE_SOURCE: raw=False task=False semantic=False post=False withheld=False failure=hidden_oracle_fail placement={"branches_on_payment_status": false, "marks_awaiting_review": false, "marks_ready": true, "publishes_order_created": true, "conditional_publish_after_status": true, "uses_current_fulfillment_policy": true, "uses_stale_policy_gate": false, "visible_tests_present": false} raw_path=results/raw/order_m21_stale_api_trap_classfix_checkerfix_r4/ORDER_M21__PREREAD_STALE_SOURCE__r2.raw.json
- rep 2 STALE_DOC_CONTROL: raw=False task=False semantic=False post=False withheld=False failure=hidden_oracle_fail placement={"branches_on_payment_status": true, "marks_awaiting_review": true, "marks_ready": true, "publishes_order_created": true, "conditional_publish_after_status": true, "uses_current_fulfillment_policy": false, "uses_stale_policy_gate": true, "visible_tests_present": false} raw_path=results/raw/order_m21_stale_api_trap_classfix_checkerfix_r4/ORDER_M21__STALE_DOC_CONTROL__r2.raw.json
- rep 2 TMF_REFRESHED_MAP: raw=True task=True semantic=True post=True withheld=True failure=pass placement={"branches_on_payment_status": true, "marks_awaiting_review": true, "marks_ready": true, "publishes_order_created": true, "conditional_publish_after_status": true, "uses_current_fulfillment_policy": false, "uses_stale_policy_gate": true, "visible_tests_present": false} raw_path=results/raw/order_m21_stale_api_trap_classfix_checkerfix_r4/ORDER_M21__TMF_REFRESHED_MAP__r2.raw.json
- rep 3 SOURCE_ONLY: raw=True task=True semantic=True post=True withheld=False failure=pass placement={"branches_on_payment_status": true, "marks_awaiting_review": true, "marks_ready": true, "publishes_order_created": true, "conditional_publish_after_status": true, "uses_current_fulfillment_policy": true, "uses_stale_policy_gate": false, "visible_tests_present": false} raw_path=results/raw/order_m21_stale_api_trap_classfix_checkerfix_r4/ORDER_M21__SOURCE_ONLY__r3.raw.json
- rep 3 PREREAD_STALE_SOURCE: raw=False task=False semantic=False post=False withheld=False failure=hidden_oracle_fail placement={"branches_on_payment_status": false, "marks_awaiting_review": false, "marks_ready": true, "publishes_order_created": true, "conditional_publish_after_status": true, "uses_current_fulfillment_policy": true, "uses_stale_policy_gate": false, "visible_tests_present": false} raw_path=results/raw/order_m21_stale_api_trap_classfix_checkerfix_r4/ORDER_M21__PREREAD_STALE_SOURCE__r3.raw.json
- rep 3 STALE_DOC_CONTROL: raw=False task=False semantic=False post=False withheld=False failure=hidden_oracle_fail placement={"branches_on_payment_status": true, "marks_awaiting_review": true, "marks_ready": true, "publishes_order_created": true, "conditional_publish_after_status": true, "uses_current_fulfillment_policy": false, "uses_stale_policy_gate": true, "visible_tests_present": false} raw_path=results/raw/order_m21_stale_api_trap_classfix_checkerfix_r4/ORDER_M21__STALE_DOC_CONTROL__r3.raw.json
- rep 3 TMF_REFRESHED_MAP: raw=False task=False semantic=False post=False withheld=True failure=hidden_oracle_fail placement={"branches_on_payment_status": true, "marks_awaiting_review": true, "marks_ready": true, "publishes_order_created": true, "conditional_publish_after_status": true, "uses_current_fulfillment_policy": false, "uses_stale_policy_gate": true, "visible_tests_present": false} raw_path=results/raw/order_m21_stale_api_trap_classfix_checkerfix_r4/ORDER_M21__TMF_REFRESHED_MAP__r3.raw.json
- rep 4 SOURCE_ONLY: raw=False task=False semantic=False post=False withheld=False failure=hidden_oracle_fail placement={"branches_on_payment_status": false, "marks_awaiting_review": false, "marks_ready": true, "publishes_order_created": true, "conditional_publish_after_status": true, "uses_current_fulfillment_policy": true, "uses_stale_policy_gate": false, "visible_tests_present": false} raw_path=results/raw/order_m21_stale_api_trap_classfix_checkerfix_r4/ORDER_M21__SOURCE_ONLY__r4.raw.json
- rep 4 PREREAD_STALE_SOURCE: raw=False task=False semantic=False post=False withheld=False failure=hidden_oracle_fail placement={"branches_on_payment_status": false, "marks_awaiting_review": false, "marks_ready": true, "publishes_order_created": true, "conditional_publish_after_status": true, "uses_current_fulfillment_policy": true, "uses_stale_policy_gate": false, "visible_tests_present": false} raw_path=results/raw/order_m21_stale_api_trap_classfix_checkerfix_r4/ORDER_M21__PREREAD_STALE_SOURCE__r4.raw.json
- rep 4 STALE_DOC_CONTROL: raw=False task=False semantic=False post=False withheld=False failure=hidden_oracle_fail placement={"branches_on_payment_status": true, "marks_awaiting_review": true, "marks_ready": true, "publishes_order_created": true, "conditional_publish_after_status": true, "uses_current_fulfillment_policy": false, "uses_stale_policy_gate": true, "visible_tests_present": false} raw_path=results/raw/order_m21_stale_api_trap_classfix_checkerfix_r4/ORDER_M21__STALE_DOC_CONTROL__r4.raw.json
- rep 4 TMF_REFRESHED_MAP: raw=True task=True semantic=True post=True withheld=True failure=pass placement={"branches_on_payment_status": true, "marks_awaiting_review": true, "marks_ready": true, "publishes_order_created": true, "conditional_publish_after_status": true, "uses_current_fulfillment_policy": false, "uses_stale_policy_gate": true, "visible_tests_present": false} raw_path=results/raw/order_m21_stale_api_trap_classfix_checkerfix_r4/ORDER_M21__TMF_REFRESHED_MAP__r4.raw.json
