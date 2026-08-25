# BOUNDARY_PRECISION_TARGETED_B12_B13_ORIGINAL_RERUN_V1_REPORT


## Interpretation warning

Do **not** interpret the raw TMF_CLAIMS pass rate as TMF semantic value. Later raw-transcript review found the TMF_CLAIMS raw failures in the B12/B13 original rerun were agent/edit protocol or source-shape failures, not TMF semantic boundary failures.

For B12/B13 original rerun, the adjusted TMF interpretation is: raw pass `7/10`, protocol-clean raw pass `6/6`, semantic-known `7 pass / 0 fail`. SOURCE_ONLY and DOC_CONTROL each had one genuine B12 semantic boundary failure.

See `BOUNDARY_PRECISION_B12_B13_CONCLUSION.md`, `TMF_ADJUSTED_SEMANTIC_REVIEW_B12_B13_ORIGINAL_RERUN.md`, and `NON_TMF_FAILURE_REVIEW_B12_B13_ORIGINAL_RERUN.md` before drawing conclusions.

Mode: targeted_B12_B13
Runs: 30
Valid answers: 26/30
Compile OK: 27/30
Trap passes: 27/30
Protocol-noise runs: 9/30
Semantic boundary-fail runs: 2/30
Differentiation by task: `{"B12": false, "B13": false}`

## Failure classification

Primary bucket by arm:

```json
{
  "SOURCE_ONLY": {
    "pass": 9,
    "semantic_boundary_fail": 1
  },
  "TMF_CLAIMS": {
    "edit_protocol_fail": 3,
    "pass": 7
  },
  "DOC_CONTROL": {
    "edit_protocol_fail": 1,
    "pass": 8,
    "semantic_boundary_fail": 1
  }
}
```

All categories by arm:

```json
{
  "TMF_CLAIMS": {
    "edit_protocol_fail": 4,
    "compile_fail": 2,
    "no_effect_false_completion": 1
  },
  "DOC_CONTROL": {
    "edit_protocol_fail": 3,
    "compile_fail": 1,
    "parse_or_invalid_action_noise": 2,
    "semantic_boundary_fail": 1
  },
  "SOURCE_ONLY": {
    "semantic_boundary_fail": 1,
    "parse_or_invalid_action_noise": 1
  }
}
```

Examples by primary non-pass bucket:

```json
{
  "TMF_CLAIMS": {
    "edit_protocol_fail": [
      "B12",
      "B12",
      "B13"
    ]
  },
  "DOC_CONTROL": {
    "edit_protocol_fail": [
      "B12"
    ],
    "semantic_boundary_fail": [
      "B12"
    ]
  },
  "SOURCE_ONLY": {
    "semantic_boundary_fail": [
      "B12"
    ]
  }
}
```

## Rows

- B12 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.4 files=['Subscriber.java'] bytes_read=5878 calls=9 wall=43.757s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r1_B12_SOURCE_ONLY/B12__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
- B12 / TMF_CLAIMS: valid=False compile=False trap=True failure=edit_protocol_fail coverage=0.4 files=['Subscriber.java'] bytes_read=6289 calls=10 wall=34.268s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r1_B12_TMF_CLAIMS/B12__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
  - failure_categories=["edit_protocol_fail", "compile_fail"]
- B12 / DOC_CONTROL: valid=False compile=False trap=True failure=edit_protocol_fail coverage=0.6 files=['Subscriber.java'] bytes_read=5878 calls=8 wall=47.848s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r1_B12_DOC_CONTROL/B12__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
  - failure_categories=["edit_protocol_fail", "compile_fail"]
- B13 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=5878 calls=9 wall=23.439s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r1_B13_SOURCE_ONLY/B13__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
- B13 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=10417 calls=10 wall=27.772s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r1_B13_TMF_CLAIMS/B13__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
- B13 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=7580 calls=10 wall=31.458s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r1_B13_DOC_CONTROL/B13__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
- B12 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.6 files=['Subscriber.java'] bytes_read=5878 calls=7 wall=36.29s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r2_B12_SOURCE_ONLY/B12__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
- B12 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.6 files=['Subscriber.java'] bytes_read=5878 calls=9 wall=34.91s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r2_B12_TMF_CLAIMS/B12__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
- B12 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.6 files=['Subscriber.java'] bytes_read=13866 calls=13 wall=42.848s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r2_B12_DOC_CONTROL/B12__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
  - failure_categories=["parse_or_invalid_action_noise"]
- B13 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=5878 calls=9 wall=43.934s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r2_B13_SOURCE_ONLY/B13__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
- B13 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=8464 calls=8 wall=24.862s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r2_B13_TMF_CLAIMS/B13__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
- B13 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=10201 calls=9 wall=18.408s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r2_B13_DOC_CONTROL/B13__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
- B12 / SOURCE_ONLY: valid=True compile=True trap=False failure=semantic_boundary_fail coverage=0.4 files=['Subscriber.java'] bytes_read=6289 calls=11 wall=64.779s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r3_B12_SOURCE_ONLY/B12__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": false, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
  - failure_categories=["semantic_boundary_fail"]
- B12 / TMF_CLAIMS: valid=False compile=False trap=True failure=edit_protocol_fail coverage=0.6 files=['Subscriber.java'] bytes_read=6289 calls=10 wall=63.281s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r3_B12_TMF_CLAIMS/B12__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
  - failure_categories=["edit_protocol_fail", "compile_fail"]
- B12 / DOC_CONTROL: valid=True compile=True trap=False failure=semantic_boundary_fail coverage=0.4 files=['Subscriber.java'] bytes_read=6289 calls=10 wall=41.677s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r3_B12_DOC_CONTROL/B12__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": false, "direct_hook_before_checkNotNull_expr_is_too_early": true, "not_outer_dispatchEvent": true}
  - failure_categories=["semantic_boundary_fail"]
- B13 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=6289 calls=13 wall=60.42s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r3_B13_SOURCE_ONLY/B13__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
- B13 / TMF_CLAIMS: valid=False compile=True trap=False failure=edit_protocol_fail coverage=0.333 files=[] bytes_read=10158 calls=11 wall=35.415s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r3_B13_TMF_CLAIMS/B13__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": false, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": false, "not_catch_path": true, "not_outer_dispatchEvent": true}
  - failure_categories=["edit_protocol_fail", "no_effect_false_completion"]
- B13 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=10027 calls=10 wall=30.349s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r3_B13_DOC_CONTROL/B13__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
- B12 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.6 files=['Subscriber.java'] bytes_read=5878 calls=8 wall=32.215s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r4_B12_SOURCE_ONLY/B12__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
- B12 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.4 files=['Subscriber.java'] bytes_read=15607 calls=19 wall=78.336s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r4_B12_TMF_CLAIMS/B12__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
- B12 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.6 files=['Subscriber.java'] bytes_read=5878 calls=8 wall=60.812s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r4_B12_DOC_CONTROL/B12__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
- B13 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=7987 calls=10 wall=42.43s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r4_B13_SOURCE_ONLY/B13__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
- B13 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=5878 calls=9 wall=21.808s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r4_B13_TMF_CLAIMS/B13__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
- B13 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=5426 calls=12 wall=52.771s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r4_B13_DOC_CONTROL/B13__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
  - failure_categories=["edit_protocol_fail", "parse_or_invalid_action_noise"]
- B12 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.6 files=['Subscriber.java'] bytes_read=5878 calls=7 wall=38.914s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r5_B12_SOURCE_ONLY/B12__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
- B12 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.6 files=['Subscriber.java'] bytes_read=8607 calls=12 wall=99.539s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r5_B12_TMF_CLAIMS/B12__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
  - failure_categories=["edit_protocol_fail"]
- B12 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.6 files=['Subscriber.java'] bytes_read=5878 calls=7 wall=48.947s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r5_B12_DOC_CONTROL/B12__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
- B13 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=6289 calls=8 wall=32.749s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r5_B13_SOURCE_ONLY/B13__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
  - failure_categories=["parse_or_invalid_action_noise"]
- B13 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=5878 calls=8 wall=31.584s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r5_B13_TMF_CLAIMS/B13__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
- B13 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=8371 calls=13 wall=52.232s raw=results/raw/boundary_precision_targeted_B12_B13_original_rerun_v1_r5_B13_DOC_CONTROL/B13__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
  - failure_categories=["edit_protocol_fail"]

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

## TMF adjusted semantic addendum

A manual raw-transcript review of the three TMF_CLAIMS raw failures found no TMF semantic boundary failure:

- `B12 r1`: correct boundary shape (`checkNotNull` hoisted before hook, then `Method.invoke`); failed because helper definition exact-text edit did not match current method signature, causing compile failure.
- `B12 r3`: correct boundary shape (`checkNotNull` hoisted before hook, then `Method.invoke`); failed because helper definition anchor was non-unique / then stale, causing compile failure.
- `B13 r3`: no effective source change; edits assumed a return-expression / private-returning source shape that does not exist in the current fixture, so exact edits failed.

Adjusted interpretation for TMF_CLAIMS on this original rerun:

- Raw pass: `7/10`
- Protocol-clean raw pass: `6/6`
- Semantic-known pass/fail: `7 pass / 0 fail`; protocol-unclean/unknown: `3`

Therefore the TMF raw failures in this rerun should be counted as agent/edit protocol failures, not TMF semantic failures. See `TMF_ADJUSTED_SEMANTIC_REVIEW_B12_B13_ORIGINAL_RERUN.md` for evidence.
