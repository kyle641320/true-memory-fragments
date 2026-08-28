# Outbox M15 Two-Phase Contract Shift Report

Fixture: synthetic bounded Maven order-outbox contract shift. Phase A old behavior is valid: createOrder saves and immediately publishes. Phase B changes EventPublisher contract so order-created events must use publishAfterCommit; the human task is vague and does not name methods/APIs.

```json
{
  "mode": "outbox_m15_two_phase_contract_shift",
  "runs": 4,
  "by_arm": {
    "SOURCE_ONLY": {
      "runs": 1,
      "raw_pass": 1,
      "task_result_pass": 1,
      "post_test_ok": 1,
      "semantic_evaluable": 1,
      "semantic_adjusted_pass": 1,
      "stale_claim_withheld": 0,
      "uses_after_commit": 1,
      "uses_immediate_publish": 0,
      "primary": {
        "pass": 1
      }
    },
    "PREREAD_STALE_SOURCE": {
      "runs": 1,
      "raw_pass": 1,
      "task_result_pass": 1,
      "post_test_ok": 1,
      "semantic_evaluable": 1,
      "semantic_adjusted_pass": 1,
      "stale_claim_withheld": 0,
      "uses_after_commit": 1,
      "uses_immediate_publish": 0,
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
      "stale_claim_withheld": 0,
      "uses_after_commit": 1,
      "uses_immediate_publish": 0,
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
      "stale_claim_withheld": 1,
      "uses_after_commit": 1,
      "uses_immediate_publish": 0,
      "primary": {
        "pass": 1
      }
    }
  }
}
```

## Rows
- rep 1 SOURCE_ONLY: raw=True task=True semantic=True post=True withheld=False failure=pass placement={"has_after_commit_api": true, "uses_after_commit": true, "uses_immediate_publish": false, "helper_present": true, "create_order_transactional": true} raw_path=results/raw/outbox_m15_two_phase_smoke_r1/OUTBOX_M15__SOURCE_ONLY__r1.raw.json
- rep 1 PREREAD_STALE_SOURCE: raw=True task=True semantic=True post=True withheld=False failure=pass placement={"has_after_commit_api": true, "uses_after_commit": true, "uses_immediate_publish": false, "helper_present": true, "create_order_transactional": true} raw_path=results/raw/outbox_m15_two_phase_smoke_r1/OUTBOX_M15__PREREAD_STALE_SOURCE__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=True task=True semantic=True post=True withheld=False failure=pass placement={"has_after_commit_api": true, "uses_after_commit": true, "uses_immediate_publish": false, "helper_present": true, "create_order_transactional": true} raw_path=results/raw/outbox_m15_two_phase_smoke_r1/OUTBOX_M15__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_STALE_GATED: raw=True task=True semantic=True post=True withheld=True failure=pass placement={"has_after_commit_api": true, "uses_after_commit": true, "uses_immediate_publish": false, "helper_present": true, "create_order_transactional": true} raw_path=results/raw/outbox_m15_two_phase_smoke_r1/OUTBOX_M15__TMF_STALE_GATED__r1.raw.json
