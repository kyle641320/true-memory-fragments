# RPC M13 Two-Phase Stale Context Report

Fixture: `benchmarks/java-workflow-fixtures/rpc-retry-transaction`.

This runner implements the corrected two-phase human-task design: Phase A is old-source orientation only, then the runner mutates/restores post contracts and Phase B receives a human-style bug report rather than file/method instructions.

```json
{
  "mode": "rpc_m13_two_phase_stale_context",
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
      "sync_transactional": 0,
      "catches_exception": 0,
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
      "sync_transactional": 0,
      "catches_exception": 0,
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
      "sync_transactional": 0,
      "catches_exception": 0,
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
      "sync_transactional": 0,
      "catches_exception": 0,
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
- rep 1 SOURCE_ONLY: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"sync_transactional": false, "catches_exception": false, "catches_io": true, "low_retry_bound_static_hint": false, "throws_declared": true, "writer_boundary": true, "direct_repository_in_sync": false} raw_path=results/raw/rpc_m13_two_phase_smoke_r1/RPC_M13__SOURCE_ONLY__r1.raw.json
- rep 1 PREREAD_STALE_SOURCE: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"sync_transactional": false, "catches_exception": false, "catches_io": true, "low_retry_bound_static_hint": true, "throws_declared": true, "writer_boundary": true, "direct_repository_in_sync": false} raw_path=results/raw/rpc_m13_two_phase_smoke_r1/RPC_M13__PREREAD_STALE_SOURCE__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"sync_transactional": false, "catches_exception": false, "catches_io": true, "low_retry_bound_static_hint": true, "throws_declared": true, "writer_boundary": true, "direct_repository_in_sync": false} raw_path=results/raw/rpc_m13_two_phase_smoke_r1/RPC_M13__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_STALE_GATED: raw=True task_result=True semantic=True post=True withheld=True failure=pass placement={"sync_transactional": false, "catches_exception": false, "catches_io": true, "low_retry_bound_static_hint": false, "throws_declared": true, "writer_boundary": true, "direct_repository_in_sync": false} raw_path=results/raw/rpc_m13_two_phase_smoke_r1/RPC_M13__TMF_STALE_GATED__r1.raw.json
