# Scheduler M14 Two-Phase Stale Context Report

Fixture: `benchmarks/java-workflow-fixtures/scheduler-partial-failure-idempotency`.

This runner implements the corrected two-phase human-task design: Phase A is old-source orientation only, then the runner mutates/restores post contracts and Phase B receives a deliberately vague human-style notification-loss/duplicate bug report rather than file/method instructions.

```json
{
  "mode": "scheduler_m14_two_phase_stale_context",
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
      "uses_claim": 1,
      "mark_before_send": 0,
      "uses_find_pending": 0,
      "extra_actions_ignored": 0,
      "result_ok_but_raw_failed": 0,
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
      "uses_claim": 1,
      "mark_before_send": 0,
      "uses_find_pending": 0,
      "extra_actions_ignored": 0,
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
      "stale_claim_withheld": 0,
      "uses_claim": 1,
      "mark_before_send": 0,
      "uses_find_pending": 0,
      "extra_actions_ignored": 0,
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
      "stale_claim_withheld": 1,
      "uses_claim": 1,
      "mark_before_send": 0,
      "uses_find_pending": 0,
      "extra_actions_ignored": 0,
      "result_ok_but_raw_failed": 0,
      "primary": {
        "pass": 1
      }
    }
  }
}
```

## Rows
- rep 1 SOURCE_ONLY: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"has_claim_api": true, "uses_claim": true, "uses_find_pending": false, "mark_before_send": false, "send_before_mark": true, "catches_runtime": false, "legacy_helper": false} raw_path=results/raw/scheduler_m14_two_phase_smoke_r1/SCHEDULER_M14__SOURCE_ONLY__r1.raw.json
- rep 1 PREREAD_STALE_SOURCE: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"has_claim_api": true, "uses_claim": true, "uses_find_pending": false, "mark_before_send": false, "send_before_mark": true, "catches_runtime": false, "legacy_helper": false} raw_path=results/raw/scheduler_m14_two_phase_smoke_r1/SCHEDULER_M14__PREREAD_STALE_SOURCE__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"has_claim_api": true, "uses_claim": true, "uses_find_pending": false, "mark_before_send": false, "send_before_mark": true, "catches_runtime": false, "legacy_helper": false} raw_path=results/raw/scheduler_m14_two_phase_smoke_r1/SCHEDULER_M14__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_STALE_GATED: raw=True task_result=True semantic=True post=True withheld=True failure=pass placement={"has_claim_api": true, "uses_claim": true, "uses_find_pending": false, "mark_before_send": false, "send_before_mark": true, "catches_runtime": false, "legacy_helper": false} raw_path=results/raw/scheduler_m14_two_phase_smoke_r1/SCHEDULER_M14__TMF_STALE_GATED__r1.raw.json
