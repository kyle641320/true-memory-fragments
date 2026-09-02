# Scheduler M14 Two-Phase Stale Context Report

Fixture: `benchmarks/java-workflow-fixtures/scheduler-partial-failure-idempotency`.

This runner implements the corrected two-phase human-task design: Phase A is old-source orientation only, then the runner mutates/restores post contracts and Phase B receives a deliberately vague human-style notification-loss/duplicate bug report rather than file/method instructions.

```json
{
  "mode": "scheduler_m14_two_phase_stale_context",
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
      "uses_claim": 4,
      "mark_before_send": 0,
      "uses_find_pending": 0,
      "extra_actions_ignored": 0,
      "result_ok_but_raw_failed": 0,
      "primary": {
        "pass": 4
      }
    },
    "PREREAD_STALE_SOURCE": {
      "runs": 4,
      "raw_pass": 2,
      "task_result_pass": 3,
      "post_test_ok": 3,
      "semantic_evaluable": 2,
      "semantic_adjusted_pass": 2,
      "stale_claim_withheld": 0,
      "uses_claim": 3,
      "mark_before_send": 0,
      "uses_find_pending": 1,
      "extra_actions_ignored": 6,
      "result_ok_but_raw_failed": 1,
      "primary": {
        "pass": 2,
        "no_final_after_success": 1,
        "edit_protocol_fail": 1
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
      "uses_claim": 4,
      "mark_before_send": 1,
      "uses_find_pending": 0,
      "extra_actions_ignored": 5,
      "result_ok_but_raw_failed": 0,
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
      "uses_claim": 4,
      "mark_before_send": 0,
      "uses_find_pending": 0,
      "extra_actions_ignored": 0,
      "result_ok_but_raw_failed": 0,
      "primary": {
        "pass": 4
      }
    }
  }
}
```

## Rows
- rep 1 SOURCE_ONLY: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"has_claim_api": true, "uses_claim": true, "uses_find_pending": false, "mark_before_send": false, "send_before_mark": true, "catches_runtime": false, "legacy_helper": false} raw_path=results/raw/scheduler_m14_two_phase_stale_context/SCHEDULER_M14__SOURCE_ONLY__r1.raw.json
- rep 1 PREREAD_STALE_SOURCE: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"has_claim_api": true, "uses_claim": true, "uses_find_pending": false, "mark_before_send": false, "send_before_mark": true, "catches_runtime": false, "legacy_helper": true} raw_path=results/raw/scheduler_m14_two_phase_stale_context/SCHEDULER_M14__PREREAD_STALE_SOURCE__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"has_claim_api": true, "uses_claim": true, "uses_find_pending": false, "mark_before_send": false, "send_before_mark": true, "catches_runtime": false, "legacy_helper": false} raw_path=results/raw/scheduler_m14_two_phase_stale_context/SCHEDULER_M14__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_STALE_GATED: raw=True task_result=True semantic=True post=True withheld=True failure=pass placement={"has_claim_api": true, "uses_claim": true, "uses_find_pending": false, "mark_before_send": false, "send_before_mark": true, "catches_runtime": false, "legacy_helper": false} raw_path=results/raw/scheduler_m14_two_phase_stale_context/SCHEDULER_M14__TMF_STALE_GATED__r1.raw.json
- rep 2 SOURCE_ONLY: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"has_claim_api": true, "uses_claim": true, "uses_find_pending": false, "mark_before_send": false, "send_before_mark": true, "catches_runtime": false, "legacy_helper": false} raw_path=results/raw/scheduler_m14_two_phase_stale_context/SCHEDULER_M14__SOURCE_ONLY__r2.raw.json
- rep 2 PREREAD_STALE_SOURCE: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"has_claim_api": true, "uses_claim": true, "uses_find_pending": false, "mark_before_send": false, "send_before_mark": true, "catches_runtime": false, "legacy_helper": false} raw_path=results/raw/scheduler_m14_two_phase_stale_context/SCHEDULER_M14__PREREAD_STALE_SOURCE__r2.raw.json
- rep 2 STALE_DOC_CONTROL: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"has_claim_api": true, "uses_claim": true, "uses_find_pending": false, "mark_before_send": true, "send_before_mark": true, "catches_runtime": false, "legacy_helper": true} raw_path=results/raw/scheduler_m14_two_phase_stale_context/SCHEDULER_M14__STALE_DOC_CONTROL__r2.raw.json
- rep 2 TMF_STALE_GATED: raw=True task_result=True semantic=True post=True withheld=True failure=pass placement={"has_claim_api": true, "uses_claim": true, "uses_find_pending": false, "mark_before_send": false, "send_before_mark": true, "catches_runtime": false, "legacy_helper": false} raw_path=results/raw/scheduler_m14_two_phase_stale_context/SCHEDULER_M14__TMF_STALE_GATED__r2.raw.json
- rep 3 SOURCE_ONLY: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"has_claim_api": true, "uses_claim": true, "uses_find_pending": false, "mark_before_send": false, "send_before_mark": true, "catches_runtime": false, "legacy_helper": false} raw_path=results/raw/scheduler_m14_two_phase_stale_context/SCHEDULER_M14__SOURCE_ONLY__r3.raw.json
- rep 3 PREREAD_STALE_SOURCE: raw=False task_result=True semantic=None post=True withheld=False failure=no_final_after_success placement={"has_claim_api": true, "uses_claim": true, "uses_find_pending": false, "mark_before_send": false, "send_before_mark": true, "catches_runtime": false, "legacy_helper": true} raw_path=results/raw/scheduler_m14_two_phase_stale_context/SCHEDULER_M14__PREREAD_STALE_SOURCE__r3.raw.json
- rep 3 STALE_DOC_CONTROL: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"has_claim_api": true, "uses_claim": true, "uses_find_pending": false, "mark_before_send": false, "send_before_mark": true, "catches_runtime": false, "legacy_helper": false} raw_path=results/raw/scheduler_m14_two_phase_stale_context/SCHEDULER_M14__STALE_DOC_CONTROL__r3.raw.json
- rep 3 TMF_STALE_GATED: raw=True task_result=True semantic=True post=True withheld=True failure=pass placement={"has_claim_api": true, "uses_claim": true, "uses_find_pending": false, "mark_before_send": false, "send_before_mark": true, "catches_runtime": false, "legacy_helper": false} raw_path=results/raw/scheduler_m14_two_phase_stale_context/SCHEDULER_M14__TMF_STALE_GATED__r3.raw.json
- rep 4 SOURCE_ONLY: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"has_claim_api": true, "uses_claim": true, "uses_find_pending": false, "mark_before_send": false, "send_before_mark": true, "catches_runtime": false, "legacy_helper": false} raw_path=results/raw/scheduler_m14_two_phase_stale_context/SCHEDULER_M14__SOURCE_ONLY__r4.raw.json
- rep 4 PREREAD_STALE_SOURCE: raw=False task_result=False semantic=None post=False withheld=False failure=edit_protocol_fail placement={"has_claim_api": true, "uses_claim": false, "uses_find_pending": true, "mark_before_send": false, "send_before_mark": true, "catches_runtime": false, "legacy_helper": true} raw_path=results/raw/scheduler_m14_two_phase_stale_context/SCHEDULER_M14__PREREAD_STALE_SOURCE__r4.raw.json
- rep 4 STALE_DOC_CONTROL: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"has_claim_api": true, "uses_claim": true, "uses_find_pending": false, "mark_before_send": false, "send_before_mark": true, "catches_runtime": false, "legacy_helper": false} raw_path=results/raw/scheduler_m14_two_phase_stale_context/SCHEDULER_M14__STALE_DOC_CONTROL__r4.raw.json
- rep 4 TMF_STALE_GATED: raw=True task_result=True semantic=True post=True withheld=True failure=pass placement={"has_claim_api": true, "uses_claim": true, "uses_find_pending": false, "mark_before_send": false, "send_before_mark": true, "catches_runtime": false, "legacy_helper": false} raw_path=results/raw/scheduler_m14_two_phase_stale_context/SCHEDULER_M14__TMF_STALE_GATED__r4.raw.json
