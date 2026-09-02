# Outbox M15 Two-Phase Contract Shift Report

Fixture: synthetic bounded Maven order-outbox contract shift. Phase A old behavior is valid: createOrder saves and immediately publishes. Phase B changes EventPublisher contract so order-created events must use publishAfterCommit; the human task is vague and does not name methods/APIs.

```json
{
  "mode": "outbox_m15_two_phase_contract_shift",
  "runs": 16,
  "by_arm": {
    "SOURCE_ONLY": {
      "runs": 4,
      "raw_pass": 4,
      "task_result_pass": 4,
      "post_test_ok": 4,
      "semantic_evaluable": 4,
      "semantic_adjusted_pass": 4,
      "stale_claim_withheld": 0,
      "uses_after_commit": 4,
      "uses_immediate_publish": 0,
      "primary": {
        "pass": 4
      }
    },
    "PREREAD_STALE_SOURCE": {
      "runs": 4,
      "raw_pass": 4,
      "task_result_pass": 4,
      "post_test_ok": 4,
      "semantic_evaluable": 4,
      "semantic_adjusted_pass": 4,
      "stale_claim_withheld": 0,
      "uses_after_commit": 4,
      "uses_immediate_publish": 0,
      "primary": {
        "pass": 4
      }
    },
    "STALE_DOC_CONTROL": {
      "runs": 4,
      "raw_pass": 4,
      "task_result_pass": 4,
      "post_test_ok": 4,
      "semantic_evaluable": 4,
      "semantic_adjusted_pass": 4,
      "stale_claim_withheld": 0,
      "uses_after_commit": 4,
      "uses_immediate_publish": 0,
      "primary": {
        "pass": 4
      }
    },
    "TMF_STALE_GATED": {
      "runs": 4,
      "raw_pass": 4,
      "task_result_pass": 4,
      "post_test_ok": 4,
      "semantic_evaluable": 4,
      "semantic_adjusted_pass": 4,
      "stale_claim_withheld": 4,
      "uses_after_commit": 4,
      "uses_immediate_publish": 0,
      "primary": {
        "pass": 4
      }
    }
  }
}
```

## Rows
- rep 1 SOURCE_ONLY: raw=True task=True semantic=True post=True withheld=False failure=pass placement={"has_after_commit_api": true, "uses_after_commit": true, "uses_immediate_publish": false, "helper_present": true, "create_order_transactional": true} raw_path=results/raw/outbox_m15_two_phase_r4/OUTBOX_M15__SOURCE_ONLY__r1.raw.json
- rep 1 PREREAD_STALE_SOURCE: raw=True task=True semantic=True post=True withheld=False failure=pass placement={"has_after_commit_api": true, "uses_after_commit": true, "uses_immediate_publish": false, "helper_present": true, "create_order_transactional": true} raw_path=results/raw/outbox_m15_two_phase_r4/OUTBOX_M15__PREREAD_STALE_SOURCE__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=True task=True semantic=True post=True withheld=False failure=pass placement={"has_after_commit_api": true, "uses_after_commit": true, "uses_immediate_publish": false, "helper_present": true, "create_order_transactional": true} raw_path=results/raw/outbox_m15_two_phase_r4/OUTBOX_M15__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_STALE_GATED: raw=True task=True semantic=True post=True withheld=True failure=pass placement={"has_after_commit_api": true, "uses_after_commit": true, "uses_immediate_publish": false, "helper_present": true, "create_order_transactional": true} raw_path=results/raw/outbox_m15_two_phase_r4/OUTBOX_M15__TMF_STALE_GATED__r1.raw.json
- rep 2 SOURCE_ONLY: raw=True task=True semantic=True post=True withheld=False failure=pass placement={"has_after_commit_api": true, "uses_after_commit": true, "uses_immediate_publish": false, "helper_present": true, "create_order_transactional": true} raw_path=results/raw/outbox_m15_two_phase_r4/OUTBOX_M15__SOURCE_ONLY__r2.raw.json
- rep 2 PREREAD_STALE_SOURCE: raw=True task=True semantic=True post=True withheld=False failure=pass placement={"has_after_commit_api": true, "uses_after_commit": true, "uses_immediate_publish": false, "helper_present": true, "create_order_transactional": true} raw_path=results/raw/outbox_m15_two_phase_r4/OUTBOX_M15__PREREAD_STALE_SOURCE__r2.raw.json
- rep 2 STALE_DOC_CONTROL: raw=True task=True semantic=True post=True withheld=False failure=pass placement={"has_after_commit_api": true, "uses_after_commit": true, "uses_immediate_publish": false, "helper_present": true, "create_order_transactional": true} raw_path=results/raw/outbox_m15_two_phase_r4/OUTBOX_M15__STALE_DOC_CONTROL__r2.raw.json
- rep 2 TMF_STALE_GATED: raw=True task=True semantic=True post=True withheld=True failure=pass placement={"has_after_commit_api": true, "uses_after_commit": true, "uses_immediate_publish": false, "helper_present": true, "create_order_transactional": true} raw_path=results/raw/outbox_m15_two_phase_r4/OUTBOX_M15__TMF_STALE_GATED__r2.raw.json
- rep 3 SOURCE_ONLY: raw=True task=True semantic=True post=True withheld=False failure=pass placement={"has_after_commit_api": true, "uses_after_commit": true, "uses_immediate_publish": false, "helper_present": true, "create_order_transactional": true} raw_path=results/raw/outbox_m15_two_phase_r4/OUTBOX_M15__SOURCE_ONLY__r3.raw.json
- rep 3 PREREAD_STALE_SOURCE: raw=True task=True semantic=True post=True withheld=False failure=pass placement={"has_after_commit_api": true, "uses_after_commit": true, "uses_immediate_publish": false, "helper_present": true, "create_order_transactional": true} raw_path=results/raw/outbox_m15_two_phase_r4/OUTBOX_M15__PREREAD_STALE_SOURCE__r3.raw.json
- rep 3 STALE_DOC_CONTROL: raw=True task=True semantic=True post=True withheld=False failure=pass placement={"has_after_commit_api": true, "uses_after_commit": true, "uses_immediate_publish": false, "helper_present": true, "create_order_transactional": true} raw_path=results/raw/outbox_m15_two_phase_r4/OUTBOX_M15__STALE_DOC_CONTROL__r3.raw.json
- rep 3 TMF_STALE_GATED: raw=True task=True semantic=True post=True withheld=True failure=pass placement={"has_after_commit_api": true, "uses_after_commit": true, "uses_immediate_publish": false, "helper_present": true, "create_order_transactional": true} raw_path=results/raw/outbox_m15_two_phase_r4/OUTBOX_M15__TMF_STALE_GATED__r3.raw.json
- rep 4 SOURCE_ONLY: raw=True task=True semantic=True post=True withheld=False failure=pass placement={"has_after_commit_api": true, "uses_after_commit": true, "uses_immediate_publish": false, "helper_present": true, "create_order_transactional": true} raw_path=results/raw/outbox_m15_two_phase_r4/OUTBOX_M15__SOURCE_ONLY__r4.raw.json
- rep 4 PREREAD_STALE_SOURCE: raw=True task=True semantic=True post=True withheld=False failure=pass placement={"has_after_commit_api": true, "uses_after_commit": true, "uses_immediate_publish": false, "helper_present": true, "create_order_transactional": true} raw_path=results/raw/outbox_m15_two_phase_r4/OUTBOX_M15__PREREAD_STALE_SOURCE__r4.raw.json
- rep 4 STALE_DOC_CONTROL: raw=True task=True semantic=True post=True withheld=False failure=pass placement={"has_after_commit_api": true, "uses_after_commit": true, "uses_immediate_publish": false, "helper_present": true, "create_order_transactional": true} raw_path=results/raw/outbox_m15_two_phase_r4/OUTBOX_M15__STALE_DOC_CONTROL__r4.raw.json
- rep 4 TMF_STALE_GATED: raw=True task=True semantic=True post=True withheld=True failure=pass placement={"has_after_commit_api": true, "uses_after_commit": true, "uses_immediate_publish": false, "helper_present": true, "create_order_transactional": true} raw_path=results/raw/outbox_m15_two_phase_r4/OUTBOX_M15__TMF_STALE_GATED__r4.raw.json
