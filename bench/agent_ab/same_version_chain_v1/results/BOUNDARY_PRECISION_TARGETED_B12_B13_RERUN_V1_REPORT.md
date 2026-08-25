# BOUNDARY_PRECISION_TARGETED_B12_B13_RERUN_V1_REPORT

Mode: targeted_B12_B13
Runs: 30
Valid answers: 25/30
Compile OK: 26/30
Trap passes: 29/30
Protocol-noise runs: 16/30
Semantic boundary-fail runs: 0/30
Differentiation by task: `{"B12": false, "B13": false}`

## Failure classification

Primary bucket by arm:

```json
{
  "SOURCE_ONLY": {
    "pass": 8,
    "edit_protocol_fail": 2
  },
  "TMF_CLAIMS": {
    "pass": 8,
    "edit_protocol_fail": 2
  },
  "DOC_CONTROL": {
    "pass": 9,
    "edit_protocol_fail": 1
  }
}
```

All categories by arm:

```json
{
  "SOURCE_ONLY": {
    "edit_protocol_fail": 5,
    "parse_or_invalid_action_noise": 3,
    "no_effect_false_completion": 1,
    "compile_fail": 1
  },
  "TMF_CLAIMS": {
    "parse_or_invalid_action_noise": 2,
    "edit_protocol_fail": 4,
    "compile_fail": 2
  },
  "DOC_CONTROL": {
    "edit_protocol_fail": 3,
    "parse_or_invalid_action_noise": 3,
    "compile_fail": 1
  }
}
```

Examples by primary non-pass bucket:

```json
{
  "SOURCE_ONLY": {
    "edit_protocol_fail": [
      "B13",
      "B13"
    ]
  },
  "TMF_CLAIMS": {
    "edit_protocol_fail": [
      "B12",
      "B13"
    ]
  },
  "DOC_CONTROL": {
    "edit_protocol_fail": [
      "B13"
    ]
  }
}
```

## Rows

- B12 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.4 files=['Subscriber.java'] bytes_read=15935 calls=14 wall=57.087s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r1_B12_SOURCE_ONLY/B12__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
  - failure_categories=["edit_protocol_fail", "parse_or_invalid_action_noise"]
- B12 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.6 files=['Subscriber.java'] bytes_read=3286 calls=7 wall=37.924s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r1_B12_TMF_CLAIMS/B12__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
  - failure_categories=["parse_or_invalid_action_noise"]
- B12 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.6 files=['Subscriber.java'] bytes_read=9688 calls=12 wall=50.468s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r1_B12_DOC_CONTROL/B12__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
  - failure_categories=["edit_protocol_fail"]
- B13 / SOURCE_ONLY: valid=False compile=True trap=False failure=edit_protocol_fail coverage=0.333 files=[] bytes_read=5878 calls=9 wall=29.899s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r1_B13_SOURCE_ONLY/B13__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": false, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": false, "not_catch_path": true, "not_outer_dispatchEvent": true}
  - failure_categories=["edit_protocol_fail", "no_effect_false_completion"]
- B13 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.833 files=['Subscriber.java'] bytes_read=8371 calls=14 wall=46.926s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r1_B13_TMF_CLAIMS/B13__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
  - failure_categories=["edit_protocol_fail"]
- B13 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=5878 calls=9 wall=21.244s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r1_B13_DOC_CONTROL/B13__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
- B12 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.6 files=['Subscriber.java'] bytes_read=5270 calls=11 wall=48.692s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r2_B12_SOURCE_ONLY/B12__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
  - failure_categories=["edit_protocol_fail", "parse_or_invalid_action_noise"]
- B12 / TMF_CLAIMS: valid=False compile=False trap=True failure=edit_protocol_fail coverage=0.6 files=['Subscriber.java'] bytes_read=6289 calls=9 wall=20.038s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r2_B12_TMF_CLAIMS/B12__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
  - failure_categories=["edit_protocol_fail", "compile_fail"]
- B12 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.6 files=['Subscriber.java'] bytes_read=6922 calls=10 wall=34.722s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r2_B12_DOC_CONTROL/B12__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
  - failure_categories=["parse_or_invalid_action_noise"]
- B13 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=8464 calls=10 wall=26.557s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r2_B13_SOURCE_ONLY/B13__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
- B13 / TMF_CLAIMS: valid=False compile=False trap=True failure=edit_protocol_fail coverage=0.833 files=['Subscriber.java'] bytes_read=5878 calls=9 wall=25.366s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r2_B13_TMF_CLAIMS/B13__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
  - failure_categories=["edit_protocol_fail", "compile_fail"]
- B13 / DOC_CONTROL: valid=False compile=False trap=True failure=edit_protocol_fail coverage=0.667 files=['Subscriber.java'] bytes_read=2875 calls=8 wall=29.027s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r2_B13_DOC_CONTROL/B13__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
  - failure_categories=["edit_protocol_fail", "compile_fail"]
- B12 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.6 files=['Subscriber.java'] bytes_read=6289 calls=10 wall=32.304s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r3_B12_SOURCE_ONLY/B12__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
- B12 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.6 files=['Subscriber.java'] bytes_read=5878 calls=9 wall=31.976s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r3_B12_TMF_CLAIMS/B12__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
- B12 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.6 files=['Subscriber.java'] bytes_read=6289 calls=8 wall=15.89s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r3_B12_DOC_CONTROL/B12__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
- B13 / SOURCE_ONLY: valid=False compile=False trap=True failure=edit_protocol_fail coverage=0.667 files=['Subscriber.java'] bytes_read=5878 calls=9 wall=25.626s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r3_B13_SOURCE_ONLY/B13__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
  - failure_categories=["edit_protocol_fail", "compile_fail"]
- B13 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=5878 calls=8 wall=24.904s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r3_B13_TMF_CLAIMS/B13__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
- B13 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=5878 calls=9 wall=20.587s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r3_B13_DOC_CONTROL/B13__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
- B12 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.6 files=['Subscriber.java'] bytes_read=5878 calls=9 wall=27.261s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r4_B12_SOURCE_ONLY/B12__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
- B12 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.6 files=['Subscriber.java'] bytes_read=7548 calls=14 wall=81.11s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r4_B12_TMF_CLAIMS/B12__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
  - failure_categories=["edit_protocol_fail", "parse_or_invalid_action_noise"]
- B12 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.6 files=['Subscriber.java'] bytes_read=5878 calls=8 wall=27.081s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r4_B12_DOC_CONTROL/B12__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
- B13 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=7583 calls=11 wall=52.393s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r4_B13_SOURCE_ONLY/B13__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
  - failure_categories=["edit_protocol_fail"]
- B13 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=5878 calls=9 wall=25.112s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r4_B13_TMF_CLAIMS/B13__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
- B13 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=9878 calls=18 wall=79.454s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r4_B13_DOC_CONTROL/B13__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
  - failure_categories=["edit_protocol_fail", "parse_or_invalid_action_noise"]
- B12 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.4 files=['Subscriber.java'] bytes_read=6289 calls=9 wall=36.792s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r5_B12_SOURCE_ONLY/B12__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
  - failure_categories=["parse_or_invalid_action_noise"]
- B12 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.6 files=['Subscriber.java'] bytes_read=6329 calls=9 wall=22.516s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r5_B12_TMF_CLAIMS/B12__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
- B12 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.6 files=['Subscriber.java'] bytes_read=6289 calls=9 wall=23.671s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r5_B12_DOC_CONTROL/B12__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
- B13 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=5878 calls=7 wall=32.491s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r5_B13_SOURCE_ONLY/B13__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
- B13 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.833 files=['Subscriber.java'] bytes_read=5878 calls=9 wall=36.423s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r5_B13_TMF_CLAIMS/B13__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
- B13 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=6563 calls=10 wall=28.985s raw=results/raw/boundary_precision_targeted_B12_B13_rerun_v1_r5_B13_DOC_CONTROL/B13__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
  - failure_categories=["parse_or_invalid_action_noise"]

## Gate

```json
{
  "at_least_2_of_3_valid_per_task": true,
  "trap_tests_distinguish_some_task": false,
  "zero_harness_runtime_errors": false
}
```

## Caveats

Machine audit is intentionally syntactic/behavioral-light: it checks compilation plus whether edits touch the expected layer and mention/modify key chain nodes. It does not execute a full Guava test suite or prove runtime rate-limit/retry/log behavior exhaustively.
