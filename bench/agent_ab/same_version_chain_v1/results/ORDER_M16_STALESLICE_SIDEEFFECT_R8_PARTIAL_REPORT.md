# Order M16 Stale-Slice Side-Effect Guard Partial Report

Note: run was interrupted after 25/32 rows, before the runner wrote its final report. The partial JSON was flushed and is summarized here.

```json
{
  "mode": "order_m16_complex_two_phase_payment_review",
  "runs": 25,
  "by_arm": {
    "SOURCE_ONLY": {
      "runs": 7,
      "raw_pass": 0,
      "task_result_pass": 0,
      "post_test_ok": 0,
      "semantic_evaluable": 7,
      "semantic_adjusted_pass": 0,
      "stale_claim_withheld": 0,
      "marks_awaiting_review": 7,
      "branches_on_payment_status": 7,
      "primary": {
        "hidden_oracle_fail": 7
      }
    },
    "PREREAD_STALE_SOURCE": {
      "runs": 6,
      "raw_pass": 0,
      "task_result_pass": 0,
      "post_test_ok": 0,
      "semantic_evaluable": 6,
      "semantic_adjusted_pass": 0,
      "stale_claim_withheld": 0,
      "marks_awaiting_review": 6,
      "branches_on_payment_status": 6,
      "primary": {
        "hidden_oracle_fail": 6
      }
    },
    "STALE_DOC_CONTROL": {
      "runs": 6,
      "raw_pass": 6,
      "task_result_pass": 6,
      "post_test_ok": 6,
      "semantic_evaluable": 6,
      "semantic_adjusted_pass": 6,
      "stale_claim_withheld": 0,
      "marks_awaiting_review": 6,
      "branches_on_payment_status": 6,
      "primary": {
        "pass": 6
      }
    },
    "TMF_REFRESHED_MAP": {
      "runs": 6,
      "raw_pass": 6,
      "task_result_pass": 6,
      "post_test_ok": 6,
      "semantic_evaluable": 6,
      "semantic_adjusted_pass": 6,
      "stale_claim_withheld": 6,
      "marks_awaiting_review": 6,
      "branches_on_payment_status": 6,
      "primary": {
        "pass": 6
      }
    }
  }
}
```

## Rows
- rep 1 SOURCE_ONLY: raw=False task=False semantic=False post=False withheld=False failure=hidden_oracle_fail reads=5 raw_path=results/raw/order_m16_staleslice_sideeffect_r8/ORDER_M16__SOURCE_ONLY__r1.raw.json
- rep 1 PREREAD_STALE_SOURCE: raw=False task=False semantic=False post=False withheld=False failure=hidden_oracle_fail reads=6 raw_path=results/raw/order_m16_staleslice_sideeffect_r8/ORDER_M16__PREREAD_STALE_SOURCE__r1.raw.json
- rep 1 STALE_DOC_CONTROL: raw=True task=True semantic=True post=True withheld=False failure=pass reads=5 raw_path=results/raw/order_m16_staleslice_sideeffect_r8/ORDER_M16__STALE_DOC_CONTROL__r1.raw.json
- rep 1 TMF_REFRESHED_MAP: raw=True task=True semantic=True post=True withheld=True failure=pass reads=5 raw_path=results/raw/order_m16_staleslice_sideeffect_r8/ORDER_M16__TMF_REFRESHED_MAP__r1.raw.json
- rep 2 SOURCE_ONLY: raw=False task=False semantic=False post=False withheld=False failure=hidden_oracle_fail reads=7 raw_path=results/raw/order_m16_staleslice_sideeffect_r8/ORDER_M16__SOURCE_ONLY__r2.raw.json
- rep 2 PREREAD_STALE_SOURCE: raw=False task=False semantic=False post=False withheld=False failure=hidden_oracle_fail reads=4 raw_path=results/raw/order_m16_staleslice_sideeffect_r8/ORDER_M16__PREREAD_STALE_SOURCE__r2.raw.json
- rep 2 STALE_DOC_CONTROL: raw=True task=True semantic=True post=True withheld=False failure=pass reads=5 raw_path=results/raw/order_m16_staleslice_sideeffect_r8/ORDER_M16__STALE_DOC_CONTROL__r2.raw.json
- rep 2 TMF_REFRESHED_MAP: raw=True task=True semantic=True post=True withheld=True failure=pass reads=3 raw_path=results/raw/order_m16_staleslice_sideeffect_r8/ORDER_M16__TMF_REFRESHED_MAP__r2.raw.json
- rep 3 SOURCE_ONLY: raw=False task=False semantic=False post=False withheld=False failure=hidden_oracle_fail reads=5 raw_path=results/raw/order_m16_staleslice_sideeffect_r8/ORDER_M16__SOURCE_ONLY__r3.raw.json
- rep 3 PREREAD_STALE_SOURCE: raw=False task=False semantic=False post=False withheld=False failure=hidden_oracle_fail reads=6 raw_path=results/raw/order_m16_staleslice_sideeffect_r8/ORDER_M16__PREREAD_STALE_SOURCE__r3.raw.json
- rep 3 STALE_DOC_CONTROL: raw=True task=True semantic=True post=True withheld=False failure=pass reads=5 raw_path=results/raw/order_m16_staleslice_sideeffect_r8/ORDER_M16__STALE_DOC_CONTROL__r3.raw.json
- rep 3 TMF_REFRESHED_MAP: raw=True task=True semantic=True post=True withheld=True failure=pass reads=3 raw_path=results/raw/order_m16_staleslice_sideeffect_r8/ORDER_M16__TMF_REFRESHED_MAP__r3.raw.json
- rep 4 SOURCE_ONLY: raw=False task=False semantic=False post=False withheld=False failure=hidden_oracle_fail reads=6 raw_path=results/raw/order_m16_staleslice_sideeffect_r8/ORDER_M16__SOURCE_ONLY__r4.raw.json
- rep 4 PREREAD_STALE_SOURCE: raw=False task=False semantic=False post=False withheld=False failure=hidden_oracle_fail reads=7 raw_path=results/raw/order_m16_staleslice_sideeffect_r8/ORDER_M16__PREREAD_STALE_SOURCE__r4.raw.json
- rep 4 STALE_DOC_CONTROL: raw=True task=True semantic=True post=True withheld=False failure=pass reads=5 raw_path=results/raw/order_m16_staleslice_sideeffect_r8/ORDER_M16__STALE_DOC_CONTROL__r4.raw.json
- rep 4 TMF_REFRESHED_MAP: raw=True task=True semantic=True post=True withheld=True failure=pass reads=4 raw_path=results/raw/order_m16_staleslice_sideeffect_r8/ORDER_M16__TMF_REFRESHED_MAP__r4.raw.json
- rep 5 SOURCE_ONLY: raw=False task=False semantic=False post=False withheld=False failure=hidden_oracle_fail reads=5 raw_path=results/raw/order_m16_staleslice_sideeffect_r8/ORDER_M16__SOURCE_ONLY__r5.raw.json
- rep 5 PREREAD_STALE_SOURCE: raw=False task=False semantic=False post=False withheld=False failure=hidden_oracle_fail reads=7 raw_path=results/raw/order_m16_staleslice_sideeffect_r8/ORDER_M16__PREREAD_STALE_SOURCE__r5.raw.json
- rep 5 STALE_DOC_CONTROL: raw=True task=True semantic=True post=True withheld=False failure=pass reads=6 raw_path=results/raw/order_m16_staleslice_sideeffect_r8/ORDER_M16__STALE_DOC_CONTROL__r5.raw.json
- rep 5 TMF_REFRESHED_MAP: raw=True task=True semantic=True post=True withheld=True failure=pass reads=4 raw_path=results/raw/order_m16_staleslice_sideeffect_r8/ORDER_M16__TMF_REFRESHED_MAP__r5.raw.json
- rep 6 SOURCE_ONLY: raw=False task=False semantic=False post=False withheld=False failure=hidden_oracle_fail reads=7 raw_path=results/raw/order_m16_staleslice_sideeffect_r8/ORDER_M16__SOURCE_ONLY__r6.raw.json
- rep 6 PREREAD_STALE_SOURCE: raw=False task=False semantic=False post=False withheld=False failure=hidden_oracle_fail reads=7 raw_path=results/raw/order_m16_staleslice_sideeffect_r8/ORDER_M16__PREREAD_STALE_SOURCE__r6.raw.json
- rep 6 STALE_DOC_CONTROL: raw=True task=True semantic=True post=True withheld=False failure=pass reads=5 raw_path=results/raw/order_m16_staleslice_sideeffect_r8/ORDER_M16__STALE_DOC_CONTROL__r6.raw.json
- rep 6 TMF_REFRESHED_MAP: raw=True task=True semantic=True post=True withheld=True failure=pass reads=4 raw_path=results/raw/order_m16_staleslice_sideeffect_r8/ORDER_M16__TMF_REFRESHED_MAP__r6.raw.json
- rep 7 SOURCE_ONLY: raw=False task=False semantic=False post=False withheld=False failure=hidden_oracle_fail reads=6 raw_path=results/raw/order_m16_staleslice_sideeffect_r8/ORDER_M16__SOURCE_ONLY__r7.raw.json
