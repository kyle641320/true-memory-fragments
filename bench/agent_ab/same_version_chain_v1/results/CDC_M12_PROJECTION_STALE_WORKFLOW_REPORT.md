# CDC M12 Projection Stale Workflow Report

Workflow fixture from `benchmarks/java-workflow-fixtures/cdc-search-index-projection-consistency`. The old Phase-A claim says ProductProjectionConsumer applies every event then unconditionally calls saveVersion. The current task requires stale-event guard, tombstone handling, and checkpoint advancement only after successful search-index update using the compare-and-set repository contract. This is an admission smoke candidate: if stale-control arms do not measurably preserve/use the legacy saveVersion workflow, do not scale it as TMF evidence.

```json
{
  "mode": "cdc_m12_projection_stale_workflow",
  "runs": 16,
  "final_gate": "hard",
  "max_turns": 10,
  "by_arm": {
    "SOURCE_ONLY": {
      "runs": 4,
      "raw_pass": 4,
      "task_result_pass": 4,
      "post_test_ok": 4,
      "semantic_evaluable": 4,
      "semantic_adjusted_pass": 4,
      "stale_claim_withheld": 0,
      "uses_legacy_save": 0,
      "duplicate_edit_suppressed": 0,
      "extra_actions_ignored": 8,
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
      "uses_legacy_save": 0,
      "duplicate_edit_suppressed": 0,
      "extra_actions_ignored": 3,
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
      "uses_legacy_save": 0,
      "duplicate_edit_suppressed": 0,
      "extra_actions_ignored": 6,
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
      "uses_legacy_save": 0,
      "duplicate_edit_suppressed": 0,
      "extra_actions_ignored": 3,
      "result_ok_but_raw_failed": 0,
      "primary": {
        "pass": 4
      }
    }
  }
}
```

## Rows
- rep 1 SOURCE_ONLY: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"uses_legacy_save": false, "has_cas_method": true, "uses_latest_version": true, "uses_cas_advance": true, "has_stale_guard": true, "advances_after_projection": false} raw_path=results/raw/cdc_m12_projection_stale_workflow/CDC_M12__SOURCE_ONLY__r1.raw.json
- rep 1 PREREAD_STALE_SOURCE: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"uses_legacy_save": false, "has_cas_method": true, "uses_latest_version": true, "uses_cas_advance": true, "has_stale_guard": true, "advances_after_projection": false} raw_path=results/raw/cdc_m12_projection_stale_workflow/CDC_M12__PREREAD_STALE_SOURCE__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"uses_legacy_save": false, "has_cas_method": true, "uses_latest_version": true, "uses_cas_advance": true, "has_stale_guard": true, "advances_after_projection": false} raw_path=results/raw/cdc_m12_projection_stale_workflow/CDC_M12__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_STALE_GATED: raw=True task_result=True semantic=True post=True withheld=True failure=pass placement={"uses_legacy_save": false, "has_cas_method": true, "uses_latest_version": true, "uses_cas_advance": true, "has_stale_guard": true, "advances_after_projection": false} raw_path=results/raw/cdc_m12_projection_stale_workflow/CDC_M12__TMF_STALE_GATED__r1.raw.json
- rep 2 SOURCE_ONLY: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"uses_legacy_save": false, "has_cas_method": true, "uses_latest_version": true, "uses_cas_advance": true, "has_stale_guard": true, "advances_after_projection": false} raw_path=results/raw/cdc_m12_projection_stale_workflow/CDC_M12__SOURCE_ONLY__r2.raw.json
- rep 2 PREREAD_STALE_SOURCE: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"uses_legacy_save": false, "has_cas_method": true, "uses_latest_version": true, "uses_cas_advance": true, "has_stale_guard": true, "advances_after_projection": false} raw_path=results/raw/cdc_m12_projection_stale_workflow/CDC_M12__PREREAD_STALE_SOURCE__r2.raw.json
- rep 2 STALE_DOC_CONTROL: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"uses_legacy_save": false, "has_cas_method": true, "uses_latest_version": true, "uses_cas_advance": true, "has_stale_guard": true, "advances_after_projection": false} raw_path=results/raw/cdc_m12_projection_stale_workflow/CDC_M12__STALE_DOC_CONTROL__r2.raw.json
- rep 2 TMF_STALE_GATED: raw=True task_result=True semantic=True post=True withheld=True failure=pass placement={"uses_legacy_save": false, "has_cas_method": true, "uses_latest_version": true, "uses_cas_advance": true, "has_stale_guard": true, "advances_after_projection": false} raw_path=results/raw/cdc_m12_projection_stale_workflow/CDC_M12__TMF_STALE_GATED__r2.raw.json
- rep 3 SOURCE_ONLY: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"uses_legacy_save": false, "has_cas_method": true, "uses_latest_version": true, "uses_cas_advance": true, "has_stale_guard": true, "advances_after_projection": false} raw_path=results/raw/cdc_m12_projection_stale_workflow/CDC_M12__SOURCE_ONLY__r3.raw.json
- rep 3 PREREAD_STALE_SOURCE: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"uses_legacy_save": false, "has_cas_method": true, "uses_latest_version": true, "uses_cas_advance": true, "has_stale_guard": true, "advances_after_projection": false} raw_path=results/raw/cdc_m12_projection_stale_workflow/CDC_M12__PREREAD_STALE_SOURCE__r3.raw.json
- rep 3 STALE_DOC_CONTROL: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"uses_legacy_save": false, "has_cas_method": true, "uses_latest_version": true, "uses_cas_advance": true, "has_stale_guard": true, "advances_after_projection": false} raw_path=results/raw/cdc_m12_projection_stale_workflow/CDC_M12__STALE_DOC_CONTROL__r3.raw.json
- rep 3 TMF_STALE_GATED: raw=True task_result=True semantic=True post=True withheld=True failure=pass placement={"uses_legacy_save": false, "has_cas_method": true, "uses_latest_version": true, "uses_cas_advance": true, "has_stale_guard": true, "advances_after_projection": false} raw_path=results/raw/cdc_m12_projection_stale_workflow/CDC_M12__TMF_STALE_GATED__r3.raw.json
- rep 4 SOURCE_ONLY: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"uses_legacy_save": false, "has_cas_method": true, "uses_latest_version": true, "uses_cas_advance": true, "has_stale_guard": true, "advances_after_projection": false} raw_path=results/raw/cdc_m12_projection_stale_workflow/CDC_M12__SOURCE_ONLY__r4.raw.json
- rep 4 PREREAD_STALE_SOURCE: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"uses_legacy_save": false, "has_cas_method": true, "uses_latest_version": true, "uses_cas_advance": true, "has_stale_guard": true, "advances_after_projection": false} raw_path=results/raw/cdc_m12_projection_stale_workflow/CDC_M12__PREREAD_STALE_SOURCE__r4.raw.json
- rep 4 STALE_DOC_CONTROL: raw=True task_result=True semantic=True post=True withheld=False failure=pass placement={"uses_legacy_save": false, "has_cas_method": true, "uses_latest_version": true, "uses_cas_advance": true, "has_stale_guard": true, "advances_after_projection": false} raw_path=results/raw/cdc_m12_projection_stale_workflow/CDC_M12__STALE_DOC_CONTROL__r4.raw.json
- rep 4 TMF_STALE_GATED: raw=True task_result=True semantic=True post=True withheld=True failure=pass placement={"uses_legacy_save": false, "has_cas_method": true, "uses_latest_version": true, "uses_cas_advance": true, "has_stale_guard": true, "advances_after_projection": false} raw_path=results/raw/cdc_m12_projection_stale_workflow/CDC_M12__TMF_STALE_GATED__r4.raw.json
