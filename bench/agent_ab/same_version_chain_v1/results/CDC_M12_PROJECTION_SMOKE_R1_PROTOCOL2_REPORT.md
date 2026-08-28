# CDC M12 Projection Stale Workflow Report

Workflow fixture from `benchmarks/java-workflow-fixtures/cdc-search-index-projection-consistency`. The old Phase-A claim says ProductProjectionConsumer applies every event then unconditionally calls saveVersion. The current task requires stale-event guard, tombstone handling, and checkpoint advancement only after successful search-index update using the compare-and-set repository contract. This is an admission smoke candidate: if stale-control arms do not measurably preserve/use the legacy saveVersion workflow, do not scale it as TMF evidence.

```json
{
  "mode": "cdc_m12_projection_stale_workflow",
  "runs": 4,
  "final_gate": "hard",
  "max_turns": 14,
  "by_arm": {
    "SOURCE_ONLY": {
      "runs": 1,
      "raw_pass": 1,
      "task_result_pass": 1,
      "post_test_ok": 1,
      "semantic_evaluable": 1,
      "semantic_adjusted_pass": 1,
      "stale_claim_withheld": 0,
      "uses_legacy_save": 0,
      "duplicate_edit_suppressed": 0,
      "extra_actions_ignored": 1,
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
      "uses_legacy_save": 0,
      "duplicate_edit_suppressed": 0,
      "extra_actions_ignored": 1,
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
      "uses_legacy_save": 0,
      "duplicate_edit_suppressed": 0,
      "extra_actions_ignored": 1,
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
      "uses_legacy_save": 0,
      "duplicate_edit_suppressed": 0,
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
- rep 1 SOURCE_ONLY: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"uses_legacy_save": false, "has_cas_method": true, "uses_latest_version": true, "uses_cas_advance": true, "has_stale_guard": true, "advances_after_projection": false} raw_path=results/raw/cdc_m12_projection_smoke_r1_protocol2/CDC_M12__SOURCE_ONLY__r1.raw.json
- rep 1 PREREAD_STALE_SOURCE: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"uses_legacy_save": false, "has_cas_method": true, "uses_latest_version": true, "uses_cas_advance": true, "has_stale_guard": true, "advances_after_projection": false} raw_path=results/raw/cdc_m12_projection_smoke_r1_protocol2/CDC_M12__PREREAD_STALE_SOURCE__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"uses_legacy_save": false, "has_cas_method": true, "uses_latest_version": true, "uses_cas_advance": true, "has_stale_guard": true, "advances_after_projection": false} raw_path=results/raw/cdc_m12_projection_smoke_r1_protocol2/CDC_M12__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_STALE_GATED: raw=True task_result=True semantic=True post=True withheld=True failure=pass placement={"uses_legacy_save": false, "has_cas_method": true, "uses_latest_version": true, "uses_cas_advance": true, "has_stale_guard": true, "advances_after_projection": false} raw_path=results/raw/cdc_m12_projection_smoke_r1_protocol2/CDC_M12__TMF_STALE_GATED__r1.raw.json
