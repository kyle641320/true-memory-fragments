# RPC M13 Two-Phase Stale Context Report

Fixture: `benchmarks/java-workflow-fixtures/rpc-retry-transaction`.

This runner implements the corrected two-phase human-task design: Phase A is old-source orientation only, then the runner mutates/restores post contracts and Phase B receives a human-style bug report rather than file/method instructions.

```json
{
  "mode": "rpc_m13_two_phase_stale_context",
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
      "sync_transactional": 0,
      "catches_exception": 0,
      "extra_actions_ignored": 0,
      "result_ok_but_raw_failed": 0,
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
      "sync_transactional": 0,
      "catches_exception": 0,
      "extra_actions_ignored": 5,
      "result_ok_but_raw_failed": 0,
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
      "sync_transactional": 0,
      "catches_exception": 0,
      "extra_actions_ignored": 0,
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
      "sync_transactional": 0,
      "catches_exception": 0,
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
- rep 1 SOURCE_ONLY: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"sync_transactional": false, "catches_exception": false, "catches_io": true, "low_retry_bound_static_hint": true, "throws_declared": true, "writer_boundary": true, "direct_repository_in_sync": false} raw_path=results/raw/rpc_m13_two_phase_stale_context/RPC_M13__SOURCE_ONLY__r1.raw.json
- rep 1 PREREAD_STALE_SOURCE: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"sync_transactional": false, "catches_exception": false, "catches_io": true, "low_retry_bound_static_hint": true, "throws_declared": true, "writer_boundary": true, "direct_repository_in_sync": false} raw_path=results/raw/rpc_m13_two_phase_stale_context/RPC_M13__PREREAD_STALE_SOURCE__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"sync_transactional": false, "catches_exception": false, "catches_io": true, "low_retry_bound_static_hint": true, "throws_declared": true, "writer_boundary": true, "direct_repository_in_sync": false} raw_path=results/raw/rpc_m13_two_phase_stale_context/RPC_M13__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_STALE_GATED: raw=True task_result=True semantic=True post=True withheld=True failure=pass placement={"sync_transactional": false, "catches_exception": false, "catches_io": true, "low_retry_bound_static_hint": false, "throws_declared": true, "writer_boundary": true, "direct_repository_in_sync": false} raw_path=results/raw/rpc_m13_two_phase_stale_context/RPC_M13__TMF_STALE_GATED__r1.raw.json
- rep 2 SOURCE_ONLY: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"sync_transactional": false, "catches_exception": false, "catches_io": true, "low_retry_bound_static_hint": true, "throws_declared": true, "writer_boundary": true, "direct_repository_in_sync": false} raw_path=results/raw/rpc_m13_two_phase_stale_context/RPC_M13__SOURCE_ONLY__r2.raw.json
- rep 2 PREREAD_STALE_SOURCE: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"sync_transactional": false, "catches_exception": false, "catches_io": true, "low_retry_bound_static_hint": false, "throws_declared": true, "writer_boundary": true, "direct_repository_in_sync": false} raw_path=results/raw/rpc_m13_two_phase_stale_context/RPC_M13__PREREAD_STALE_SOURCE__r2.raw.json
- rep 2 STALE_DOC_CONTROL: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"sync_transactional": false, "catches_exception": false, "catches_io": true, "low_retry_bound_static_hint": true, "throws_declared": true, "writer_boundary": true, "direct_repository_in_sync": false} raw_path=results/raw/rpc_m13_two_phase_stale_context/RPC_M13__STALE_DOC_CONTROL__r2.raw.json
- rep 2 TMF_STALE_GATED: raw=True task_result=True semantic=True post=True withheld=True failure=pass placement={"sync_transactional": false, "catches_exception": false, "catches_io": true, "low_retry_bound_static_hint": true, "throws_declared": true, "writer_boundary": true, "direct_repository_in_sync": false} raw_path=results/raw/rpc_m13_two_phase_stale_context/RPC_M13__TMF_STALE_GATED__r2.raw.json
- rep 3 SOURCE_ONLY: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"sync_transactional": false, "catches_exception": false, "catches_io": true, "low_retry_bound_static_hint": true, "throws_declared": true, "writer_boundary": true, "direct_repository_in_sync": false} raw_path=results/raw/rpc_m13_two_phase_stale_context/RPC_M13__SOURCE_ONLY__r3.raw.json
- rep 3 PREREAD_STALE_SOURCE: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"sync_transactional": false, "catches_exception": false, "catches_io": true, "low_retry_bound_static_hint": true, "throws_declared": true, "writer_boundary": true, "direct_repository_in_sync": false} raw_path=results/raw/rpc_m13_two_phase_stale_context/RPC_M13__PREREAD_STALE_SOURCE__r3.raw.json
- rep 3 STALE_DOC_CONTROL: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"sync_transactional": false, "catches_exception": false, "catches_io": true, "low_retry_bound_static_hint": true, "throws_declared": true, "writer_boundary": true, "direct_repository_in_sync": false} raw_path=results/raw/rpc_m13_two_phase_stale_context/RPC_M13__STALE_DOC_CONTROL__r3.raw.json
- rep 3 TMF_STALE_GATED: raw=True task_result=True semantic=True post=True withheld=True failure=pass placement={"sync_transactional": false, "catches_exception": false, "catches_io": true, "low_retry_bound_static_hint": true, "throws_declared": true, "writer_boundary": true, "direct_repository_in_sync": false} raw_path=results/raw/rpc_m13_two_phase_stale_context/RPC_M13__TMF_STALE_GATED__r3.raw.json
- rep 4 SOURCE_ONLY: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"sync_transactional": false, "catches_exception": false, "catches_io": true, "low_retry_bound_static_hint": false, "throws_declared": true, "writer_boundary": true, "direct_repository_in_sync": false} raw_path=results/raw/rpc_m13_two_phase_stale_context/RPC_M13__SOURCE_ONLY__r4.raw.json
- rep 4 PREREAD_STALE_SOURCE: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"sync_transactional": false, "catches_exception": false, "catches_io": true, "low_retry_bound_static_hint": true, "throws_declared": true, "writer_boundary": true, "direct_repository_in_sync": false} raw_path=results/raw/rpc_m13_two_phase_stale_context/RPC_M13__PREREAD_STALE_SOURCE__r4.raw.json
- rep 4 STALE_DOC_CONTROL: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"sync_transactional": false, "catches_exception": false, "catches_io": true, "low_retry_bound_static_hint": true, "throws_declared": true, "writer_boundary": true, "direct_repository_in_sync": false} raw_path=results/raw/rpc_m13_two_phase_stale_context/RPC_M13__STALE_DOC_CONTROL__r4.raw.json
- rep 4 TMF_STALE_GATED: raw=True task_result=True semantic=True post=True withheld=True failure=pass placement={"sync_transactional": false, "catches_exception": false, "catches_io": true, "low_retry_bound_static_hint": true, "throws_declared": true, "writer_boundary": true, "direct_repository_in_sync": false} raw_path=results/raw/rpc_m13_two_phase_stale_context/RPC_M13__TMF_STALE_GATED__r4.raw.json
