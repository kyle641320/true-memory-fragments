# BOUNDARY_PRECISION_REPEATS_CLASSIFIED_REPORT


## Interpretation warning

Do **not** interpret the raw TMF_CLAIMS pass rate as TMF semantic value. Later raw-transcript review found the TMF_CLAIMS raw failures in the B12/B13 original rerun were agent/edit protocol or source-shape failures, not TMF semantic boundary failures.

For B12/B13 original rerun, the adjusted TMF interpretation is: raw pass `7/10`, protocol-clean raw pass `6/6`, semantic-known `7 pass / 0 fail`. SOURCE_ONLY and DOC_CONTROL each had one genuine B12 semantic boundary failure.

See `BOUNDARY_PRECISION_B12_B13_CONCLUSION.md`, `TMF_ADJUSTED_SEMANTIC_REVIEW_B12_B13_ORIGINAL_RERUN.md`, and `NON_TMF_FAILURE_REVIEW_B12_B13_ORIGINAL_RERUN.md` before drawing conclusions.

Mode: repeat-existing
Runs: 63
Valid answers: 51/63
Compile OK: 57/63
Trap passes: 49/63
Protocol-noise runs: 26/63
Semantic boundary-fail runs: 5/63
Differentiation by task: `{"B07": true, "B08": false, "B09": false, "B10": false, "B11": true, "B12": true, "B13": false}`

## Failure classification

Primary bucket by arm:

```json
{
  "DOC_CONTROL": {
    "pass": 17,
    "edit_protocol_fail": 3,
    "semantic_boundary_fail": 1
  },
  "SOURCE_ONLY": {
    "pass": 14,
    "edit_protocol_fail": 4,
    "no_effect_false_completion": 1,
    "semantic_boundary_fail": 2
  },
  "TMF_CLAIMS": {
    "edit_protocol_fail": 4,
    "pass": 15,
    "compile_fail": 1,
    "semantic_boundary_fail": 1
  }
}
```

All categories by arm:

```json
{
  "SOURCE_ONLY": {
    "edit_protocol_fail": 6,
    "parse_or_invalid_action_noise": 3,
    "no_effect_false_completion": 2,
    "compile_fail": 2,
    "semantic_boundary_fail": 2,
    "no_final": 1
  },
  "TMF_CLAIMS": {
    "edit_protocol_fail": 5,
    "compile_fail": 2,
    "parse_or_invalid_action_noise": 4,
    "no_final": 1,
    "no_effect_false_completion": 2,
    "semantic_boundary_fail": 2
  },
  "DOC_CONTROL": {
    "edit_protocol_fail": 6,
    "parse_or_invalid_action_noise": 4,
    "compile_fail": 2,
    "tool_error_noise": 2,
    "semantic_boundary_fail": 1,
    "no_final": 1,
    "finalization_or_validator_inconsistency": 1
  }
}
```

Examples by primary non-pass bucket:

```json
{
  "TMF_CLAIMS": {
    "edit_protocol_fail": [
      "B07",
      "B12",
      "B13",
      "B13"
    ],
    "compile_fail": [
      "B11"
    ],
    "semantic_boundary_fail": [
      "B12"
    ]
  },
  "DOC_CONTROL": {
    "edit_protocol_fail": [
      "B07",
      "B12",
      "B13"
    ],
    "semantic_boundary_fail": [
      "B11"
    ]
  },
  "SOURCE_ONLY": {
    "edit_protocol_fail": [
      "B09",
      "B09",
      "B11",
      "B12"
    ],
    "no_effect_false_completion": [
      "B11"
    ],
    "semantic_boundary_fail": [
      "B11",
      "B12"
    ]
  }
}
```

## Rows

- B07 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.167 files=['Subscriber.java'] bytes_read=6083 calls=9 wall=29.179s raw=results/raw/boundary_precision_repeat_r1_B07_DOC_CONTROL/B07__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_lambda_before_invoke": true, "not_before_executor_execute": true, "not_post_or_dispatcher_only": true}
- B07 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.167 files=['Subscriber.java'] bytes_read=8586 calls=13 wall=52.13s raw=results/raw/boundary_precision_repeat_r1_B07_SOURCE_ONLY/B07__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_lambda_before_invoke": true, "not_before_executor_execute": true, "not_post_or_dispatcher_only": true}
  - failure_categories=["edit_protocol_fail"]
- B07 / TMF_CLAIMS: valid=False compile=False trap=False failure=edit_protocol_fail coverage=0.167 files=['Subscriber.java'] bytes_read=6083 calls=9 wall=27.566s raw=results/raw/boundary_precision_repeat_r1_B07_TMF_CLAIMS/B07__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_lambda_before_invoke": false, "not_before_executor_execute": true, "not_post_or_dispatcher_only": true}
  - failure_categories=["edit_protocol_fail", "compile_fail"]
- B07 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.167 files=['Subscriber.java'] bytes_read=9699 calls=14 wall=46.591s raw=results/raw/boundary_precision_repeat_r2_B07_DOC_CONTROL/B07__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_lambda_before_invoke": true, "not_before_executor_execute": true, "not_post_or_dispatcher_only": true}
  - failure_categories=["edit_protocol_fail", "parse_or_invalid_action_noise"]
- B07 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.167 files=['Subscriber.java'] bytes_read=4790 calls=11 wall=36.826s raw=results/raw/boundary_precision_repeat_r2_B07_SOURCE_ONLY/B07__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_lambda_before_invoke": true, "not_before_executor_execute": true, "not_post_or_dispatcher_only": true}
  - failure_categories=["parse_or_invalid_action_noise"]
- B07 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.167 files=['Subscriber.java'] bytes_read=616 calls=8 wall=20.685s raw=results/raw/boundary_precision_repeat_r2_B07_TMF_CLAIMS/B07__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_lambda_before_invoke": true, "not_before_executor_execute": true, "not_post_or_dispatcher_only": true}
- B07 / DOC_CONTROL: valid=False compile=False trap=False failure=edit_protocol_fail coverage=0.167 files=['Subscriber.java'] bytes_read=6083 calls=8 wall=22.107s raw=results/raw/boundary_precision_repeat_r3_B07_DOC_CONTROL/B07__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_lambda_before_invoke": false, "not_before_executor_execute": true, "not_post_or_dispatcher_only": true}
  - failure_categories=["edit_protocol_fail", "compile_fail"]
- B07 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.333 files=['Subscriber.java'] bytes_read=11658 calls=10 wall=22.471s raw=results/raw/boundary_precision_repeat_r3_B07_SOURCE_ONLY/B07__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_lambda_before_invoke": true, "not_before_executor_execute": true, "not_post_or_dispatcher_only": true}
- B07 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.167 files=['Subscriber.java'] bytes_read=6083 calls=9 wall=20.618s raw=results/raw/boundary_precision_repeat_r3_B07_TMF_CLAIMS/B07__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_lambda_before_invoke": true, "not_before_executor_execute": true, "not_post_or_dispatcher_only": true}
- B08 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.0 files=['Subscriber.java'] bytes_read=6752 calls=9 wall=34.734s raw=results/raw/boundary_precision_repeat_r1_B08_DOC_CONTROL/B08__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "after_invoke_success_boundary": true, "not_before_invoke": true, "not_in_failure_catch": true}
  - failure_categories=["parse_or_invalid_action_noise"]
- B08 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.0 files=['Subscriber.java'] bytes_read=5700 calls=11 wall=34.674s raw=results/raw/boundary_precision_repeat_r1_B08_SOURCE_ONLY/B08__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "after_invoke_success_boundary": true, "not_before_invoke": true, "not_in_failure_catch": true}
- B08 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.0 files=['Subscriber.java'] bytes_read=6083 calls=8 wall=28.3s raw=results/raw/boundary_precision_repeat_r1_B08_TMF_CLAIMS/B08__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "after_invoke_success_boundary": true, "not_before_invoke": true, "not_in_failure_catch": true}
- B08 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.143 files=['Subscriber.java'] bytes_read=13690 calls=12 wall=42.327s raw=results/raw/boundary_precision_repeat_r2_B08_DOC_CONTROL/B08__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "after_invoke_success_boundary": true, "not_before_invoke": true, "not_in_failure_catch": true}
- B08 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.0 files=['Subscriber.java'] bytes_read=6083 calls=8 wall=19.008s raw=results/raw/boundary_precision_repeat_r2_B08_SOURCE_ONLY/B08__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "after_invoke_success_boundary": true, "not_before_invoke": true, "not_in_failure_catch": true}
- B08 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.143 files=['Subscriber.java'] bytes_read=7738 calls=9 wall=25.472s raw=results/raw/boundary_precision_repeat_r2_B08_TMF_CLAIMS/B08__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "after_invoke_success_boundary": true, "not_before_invoke": true, "not_in_failure_catch": true}
- B08 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.0 files=['Subscriber.java'] bytes_read=6083 calls=8 wall=22.874s raw=results/raw/boundary_precision_repeat_r3_B08_DOC_CONTROL/B08__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "after_invoke_success_boundary": true, "not_before_invoke": true, "not_in_failure_catch": true}
- B08 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.0 files=['Subscriber.java'] bytes_read=6083 calls=9 wall=21.643s raw=results/raw/boundary_precision_repeat_r3_B08_SOURCE_ONLY/B08__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "after_invoke_success_boundary": true, "not_before_invoke": true, "not_in_failure_catch": true}
- B08 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.0 files=['Subscriber.java'] bytes_read=6083 calls=10 wall=30.69s raw=results/raw/boundary_precision_repeat_r3_B08_TMF_CLAIMS/B08__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "after_invoke_success_boundary": true, "not_before_invoke": true, "not_in_failure_catch": true}
- B09 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.167 files=['Subscriber.java'] bytes_read=8592 calls=11 wall=43.354s raw=results/raw/boundary_precision_repeat_r1_B09_DOC_CONTROL/B09__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "catch_before_handleSubscriberException": true, "not_before_invoke": true, "not_eventbus_only": true}
  - failure_categories=["edit_protocol_fail"]
- B09 / SOURCE_ONLY: valid=False compile=True trap=False failure=edit_protocol_fail coverage=0.5 files=[] bytes_read=7503 calls=9 wall=20.855s raw=results/raw/boundary_precision_repeat_r1_B09_SOURCE_ONLY/B09__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": false, "hookish": true, "catch_before_handleSubscriberException": false, "not_before_invoke": true, "not_eventbus_only": true}
  - failure_categories=["edit_protocol_fail", "no_effect_false_completion"]
- B09 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.167 files=['Subscriber.java'] bytes_read=18692 calls=10 wall=31.482s raw=results/raw/boundary_precision_repeat_r1_B09_TMF_CLAIMS/B09__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "catch_before_handleSubscriberException": true, "not_before_invoke": true, "not_eventbus_only": true}
- B09 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.333 files=['Subscriber.java'] bytes_read=8301 calls=9 wall=25.091s raw=results/raw/boundary_precision_repeat_r2_B09_DOC_CONTROL/B09__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "catch_before_handleSubscriberException": true, "not_before_invoke": true, "not_eventbus_only": true}
- B09 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.167 files=['Subscriber.java'] bytes_read=6083 calls=8 wall=25.817s raw=results/raw/boundary_precision_repeat_r2_B09_SOURCE_ONLY/B09__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "catch_before_handleSubscriberException": true, "not_before_invoke": true, "not_eventbus_only": true}
- B09 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.167 files=['Subscriber.java'] bytes_read=6083 calls=9 wall=32.811s raw=results/raw/boundary_precision_repeat_r2_B09_TMF_CLAIMS/B09__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "catch_before_handleSubscriberException": true, "not_before_invoke": true, "not_eventbus_only": true}
- B09 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.167 files=['Subscriber.java'] bytes_read=6083 calls=8 wall=36.499s raw=results/raw/boundary_precision_repeat_r3_B09_DOC_CONTROL/B09__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "catch_before_handleSubscriberException": true, "not_before_invoke": true, "not_eventbus_only": true}
- B09 / SOURCE_ONLY: valid=False compile=False trap=True failure=edit_protocol_fail coverage=0.333 files=['Subscriber.java'] bytes_read=9236 calls=9 wall=34.404s raw=results/raw/boundary_precision_repeat_r3_B09_SOURCE_ONLY/B09__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "catch_before_handleSubscriberException": true, "not_before_invoke": true, "not_eventbus_only": true}
  - failure_categories=["edit_protocol_fail", "compile_fail"]
- B09 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.5 files=['Subscriber.java'] bytes_read=8129 calls=10 wall=30.424s raw=results/raw/boundary_precision_repeat_r3_B09_TMF_CLAIMS/B09__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "catch_before_handleSubscriberException": true, "not_before_invoke": true, "not_eventbus_only": true}
- B10 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.4 files=['EventBus.java'] bytes_read=3060 calls=9 wall=26.95s raw=results/raw/boundary_precision_repeat_r1_B10_DOC_CONTROL/B10__DOC_CONTROL.raw.json
  - trap_reason={"eventbus_changed": true, "hookish": true, "before_dead_event_repost": true, "not_post_entry": true, "not_subscriber_or_dispatcher_only": true}
  - failure_categories=["tool_error_noise"]
- B10 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.4 files=['EventBus.java'] bytes_read=10422 calls=11 wall=47.271s raw=results/raw/boundary_precision_repeat_r1_B10_SOURCE_ONLY/B10__SOURCE_ONLY.raw.json
  - trap_reason={"eventbus_changed": true, "hookish": true, "before_dead_event_repost": true, "not_post_entry": true, "not_subscriber_or_dispatcher_only": true}
  - failure_categories=["edit_protocol_fail"]
- B10 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.4 files=['EventBus.java'] bytes_read=14443 calls=16 wall=48.429s raw=results/raw/boundary_precision_repeat_r1_B10_TMF_CLAIMS/B10__TMF_CLAIMS.raw.json
  - trap_reason={"eventbus_changed": true, "hookish": true, "before_dead_event_repost": true, "not_post_entry": true, "not_subscriber_or_dispatcher_only": true}
  - failure_categories=["edit_protocol_fail", "parse_or_invalid_action_noise"]
- B10 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.4 files=['EventBus.java'] bytes_read=6350 calls=10 wall=35.828s raw=results/raw/boundary_precision_repeat_r2_B10_DOC_CONTROL/B10__DOC_CONTROL.raw.json
  - trap_reason={"eventbus_changed": true, "hookish": true, "before_dead_event_repost": true, "not_post_entry": true, "not_subscriber_or_dispatcher_only": true}
- B10 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.4 files=['EventBus.java'] bytes_read=15044 calls=10 wall=34.255s raw=results/raw/boundary_precision_repeat_r2_B10_SOURCE_ONLY/B10__SOURCE_ONLY.raw.json
  - trap_reason={"eventbus_changed": true, "hookish": true, "before_dead_event_repost": true, "not_post_entry": true, "not_subscriber_or_dispatcher_only": true}
- B10 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.8 files=['EventBus.java'] bytes_read=4353 calls=8 wall=17.479s raw=results/raw/boundary_precision_repeat_r2_B10_TMF_CLAIMS/B10__TMF_CLAIMS.raw.json
  - trap_reason={"eventbus_changed": true, "hookish": true, "before_dead_event_repost": true, "not_post_entry": true, "not_subscriber_or_dispatcher_only": true}
- B10 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.4 files=['EventBus.java'] bytes_read=6663 calls=9 wall=18.986s raw=results/raw/boundary_precision_repeat_r3_B10_DOC_CONTROL/B10__DOC_CONTROL.raw.json
  - trap_reason={"eventbus_changed": true, "hookish": true, "before_dead_event_repost": true, "not_post_entry": true, "not_subscriber_or_dispatcher_only": true}
- B10 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.4 files=['EventBus.java'] bytes_read=17444 calls=12 wall=43.464s raw=results/raw/boundary_precision_repeat_r3_B10_SOURCE_ONLY/B10__SOURCE_ONLY.raw.json
  - trap_reason={"eventbus_changed": true, "hookish": true, "before_dead_event_repost": true, "not_post_entry": true, "not_subscriber_or_dispatcher_only": true}
- B10 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.4 files=['EventBus.java'] bytes_read=3097 calls=7 wall=33.911s raw=results/raw/boundary_precision_repeat_r3_B10_TMF_CLAIMS/B10__TMF_CLAIMS.raw.json
  - trap_reason={"eventbus_changed": true, "hookish": true, "before_dead_event_repost": true, "not_post_entry": true, "not_subscriber_or_dispatcher_only": true}
  - failure_categories=["parse_or_invalid_action_noise"]
- B11 / DOC_CONTROL: valid=True compile=True trap=False failure=semantic_boundary_fail coverage=0.143 files=['Dispatcher.java'] bytes_read=8466 calls=11 wall=38.504s raw=results/raw/boundary_precision_repeat_r1_B11_DOC_CONTROL/B11__DOC_CONTROL.raw.json
  - trap_reason={"dispatcher_changed": true, "hookish": true, "before_subscriber_dispatchEvent_or_full_helper": false, "replaced_dispatch_sites": 3, "not_subscriber_only": true, "not_eventbus_only": true}
  - failure_categories=["semantic_boundary_fail", "tool_error_noise"]
- B11 / SOURCE_ONLY: valid=False compile=True trap=False failure=no_effect_false_completion coverage=0.143 files=[] bytes_read=13719 calls=6 wall=42.584s raw=results/raw/boundary_precision_repeat_r1_B11_SOURCE_ONLY/B11__SOURCE_ONLY.raw.json
  - trap_reason={"dispatcher_changed": false, "hookish": true, "before_subscriber_dispatchEvent_or_full_helper": false, "replaced_dispatch_sites": 0, "not_subscriber_only": false, "not_eventbus_only": false}
  - failure_categories=["no_effect_false_completion"]
- B11 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.143 files=['Dispatcher.java'] bytes_read=9031 calls=11 wall=29.055s raw=results/raw/boundary_precision_repeat_r1_B11_TMF_CLAIMS/B11__TMF_CLAIMS.raw.json
  - trap_reason={"dispatcher_changed": true, "hookish": true, "before_subscriber_dispatchEvent_or_full_helper": true, "replaced_dispatch_sites": 2, "not_subscriber_only": true, "not_eventbus_only": true}
- B11 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.143 files=['Dispatcher.java'] bytes_read=8466 calls=11 wall=28.12s raw=results/raw/boundary_precision_repeat_r2_B11_DOC_CONTROL/B11__DOC_CONTROL.raw.json
  - trap_reason={"dispatcher_changed": true, "hookish": true, "before_subscriber_dispatchEvent_or_full_helper": true, "replaced_dispatch_sites": 3, "not_subscriber_only": true, "not_eventbus_only": true}
- B11 / SOURCE_ONLY: valid=True compile=True trap=False failure=semantic_boundary_fail coverage=0.143 files=['Dispatcher.java'] bytes_read=22453 calls=14 wall=47.0s raw=results/raw/boundary_precision_repeat_r2_B11_SOURCE_ONLY/B11__SOURCE_ONLY.raw.json
  - trap_reason={"dispatcher_changed": true, "hookish": true, "before_subscriber_dispatchEvent_or_full_helper": false, "replaced_dispatch_sites": 3, "not_subscriber_only": true, "not_eventbus_only": true}
  - failure_categories=["semantic_boundary_fail"]
- B11 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.143 files=['Dispatcher.java'] bytes_read=14981 calls=11 wall=29.412s raw=results/raw/boundary_precision_repeat_r2_B11_TMF_CLAIMS/B11__TMF_CLAIMS.raw.json
  - trap_reason={"dispatcher_changed": true, "hookish": true, "before_subscriber_dispatchEvent_or_full_helper": true, "replaced_dispatch_sites": 2, "not_subscriber_only": true, "not_eventbus_only": true}
- B11 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.143 files=['Dispatcher.java'] bytes_read=16932 calls=12 wall=29.047s raw=results/raw/boundary_precision_repeat_r3_B11_DOC_CONTROL/B11__DOC_CONTROL.raw.json
  - trap_reason={"dispatcher_changed": true, "hookish": true, "before_subscriber_dispatchEvent_or_full_helper": true, "replaced_dispatch_sites": 2, "not_subscriber_only": true, "not_eventbus_only": true}
- B11 / SOURCE_ONLY: valid=False compile=True trap=False failure=edit_protocol_fail coverage=0.143 files=['Dispatcher.java'] bytes_read=25864 calls=13 wall=39.761s raw=results/raw/boundary_precision_repeat_r3_B11_SOURCE_ONLY/B11__SOURCE_ONLY.raw.json
  - trap_reason={"dispatcher_changed": true, "hookish": true, "before_subscriber_dispatchEvent_or_full_helper": false, "replaced_dispatch_sites": 2, "not_subscriber_only": true, "not_eventbus_only": true}
  - failure_categories=["edit_protocol_fail", "no_final", "parse_or_invalid_action_noise"]
- B11 / TMF_CLAIMS: valid=False compile=False trap=False failure=compile_fail coverage=0.143 files=['Dispatcher.java'] bytes_read=21711 calls=7 wall=34.238s raw=results/raw/boundary_precision_repeat_r3_B11_TMF_CLAIMS/B11__TMF_CLAIMS.raw.json
  - trap_reason={"dispatcher_changed": true, "hookish": true, "before_subscriber_dispatchEvent_or_full_helper": false, "replaced_dispatch_sites": 0, "not_subscriber_only": true, "not_eventbus_only": true}
  - failure_categories=["compile_fail", "no_final", "parse_or_invalid_action_noise"]
- B12 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.6 files=['Subscriber.java'] bytes_read=12657 calls=15 wall=54.333s raw=results/raw/boundary_precision_repeat_r1_B12_DOC_CONTROL/B12__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
- B12 / SOURCE_ONLY: valid=False compile=False trap=False failure=edit_protocol_fail coverage=0.4 files=['Subscriber.java'] bytes_read=11042 calls=14 wall=44.138s raw=results/raw/boundary_precision_repeat_r1_B12_SOURCE_ONLY/B12__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": false, "direct_hook_before_checkNotNull_expr_is_too_early": true, "not_outer_dispatchEvent": true}
  - failure_categories=["edit_protocol_fail", "compile_fail"]
- B12 / TMF_CLAIMS: valid=False compile=True trap=False failure=edit_protocol_fail coverage=0.4 files=[] bytes_read=8691 calls=8 wall=17.971s raw=results/raw/boundary_precision_repeat_r1_B12_TMF_CLAIMS/B12__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": false, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": false, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
  - failure_categories=["edit_protocol_fail", "no_effect_false_completion"]
- B12 / DOC_CONTROL: valid=False compile=True trap=True failure=edit_protocol_fail coverage=0.4 files=['Subscriber.java'] bytes_read=14532 calls=16 wall=56.468s raw=results/raw/boundary_precision_repeat_r2_B12_DOC_CONTROL/B12__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
  - failure_categories=["edit_protocol_fail", "no_final", "finalization_or_validator_inconsistency", "parse_or_invalid_action_noise"]
- B12 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.6 files=['Subscriber.java'] bytes_read=5878 calls=11 wall=48.635s raw=results/raw/boundary_precision_repeat_r2_B12_SOURCE_ONLY/B12__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
- B12 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.6 files=['Subscriber.java'] bytes_read=6289 calls=10 wall=43.599s raw=results/raw/boundary_precision_repeat_r2_B12_TMF_CLAIMS/B12__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
- B12 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.4 files=['Subscriber.java'] bytes_read=6289 calls=8 wall=31.188s raw=results/raw/boundary_precision_repeat_r3_B12_DOC_CONTROL/B12__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
- B12 / SOURCE_ONLY: valid=True compile=True trap=False failure=semantic_boundary_fail coverage=0.4 files=['Subscriber.java'] bytes_read=6289 calls=10 wall=24.699s raw=results/raw/boundary_precision_repeat_r3_B12_SOURCE_ONLY/B12__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": false, "direct_hook_before_checkNotNull_expr_is_too_early": true, "not_outer_dispatchEvent": true}
  - failure_categories=["semantic_boundary_fail"]
- B12 / TMF_CLAIMS: valid=True compile=True trap=False failure=semantic_boundary_fail coverage=0.4 files=['Subscriber.java'] bytes_read=5188 calls=10 wall=51.697s raw=results/raw/boundary_precision_repeat_r3_B12_TMF_CLAIMS/B12__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": false, "direct_hook_before_checkNotNull_expr_is_too_early": true, "not_outer_dispatchEvent": true}
  - failure_categories=["semantic_boundary_fail", "parse_or_invalid_action_noise"]
- B13 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=15071 calls=12 wall=42.543s raw=results/raw/boundary_precision_repeat_r1_B13_DOC_CONTROL/B13__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
  - failure_categories=["edit_protocol_fail", "parse_or_invalid_action_noise"]
- B13 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=12415 calls=9 wall=24.876s raw=results/raw/boundary_precision_repeat_r1_B13_SOURCE_ONLY/B13__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
  - failure_categories=["parse_or_invalid_action_noise"]
- B13 / TMF_CLAIMS: valid=False compile=True trap=False failure=edit_protocol_fail coverage=0.333 files=[] bytes_read=5878 calls=8 wall=31.047s raw=results/raw/boundary_precision_repeat_r1_B13_TMF_CLAIMS/B13__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": false, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": false, "not_catch_path": true, "not_outer_dispatchEvent": true}
  - failure_categories=["edit_protocol_fail", "no_effect_false_completion"]
- B13 / DOC_CONTROL: valid=False compile=False trap=True failure=edit_protocol_fail coverage=0.667 files=['Subscriber.java'] bytes_read=5878 calls=8 wall=30.698s raw=results/raw/boundary_precision_repeat_r2_B13_DOC_CONTROL/B13__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
  - failure_categories=["edit_protocol_fail", "compile_fail"]
- B13 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=5878 calls=9 wall=24.714s raw=results/raw/boundary_precision_repeat_r2_B13_SOURCE_ONLY/B13__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
- B13 / TMF_CLAIMS: valid=True compile=True trap=False failure=edit_protocol_fail coverage=0.333 files=['Subscriber.java'] bytes_read=5878 calls=8 wall=31.486s raw=results/raw/boundary_precision_repeat_r2_B13_TMF_CLAIMS/B13__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": false, "not_catch_path": true, "not_outer_dispatchEvent": true}
  - failure_categories=["edit_protocol_fail", "semantic_boundary_fail"]
- B13 / DOC_CONTROL: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=6289 calls=9 wall=33.497s raw=results/raw/boundary_precision_repeat_r3_B13_DOC_CONTROL/B13__DOC_CONTROL.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
- B13 / SOURCE_ONLY: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=6289 calls=11 wall=21.14s raw=results/raw/boundary_precision_repeat_r3_B13_SOURCE_ONLY/B13__SOURCE_ONLY.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
- B13 / TMF_CLAIMS: valid=True compile=True trap=True failure=pass coverage=0.667 files=['Subscriber.java'] bytes_read=7371 calls=11 wall=27.613s raw=results/raw/boundary_precision_repeat_r3_B13_TMF_CLAIMS/B13__TMF_CLAIMS.raw.json
  - trap_reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}

## Gate

```json
{
  "at_least_2_of_3_valid_per_task": true,
  "trap_tests_distinguish_some_task": true,
  "zero_harness_runtime_errors": false
}
```

## Caveats

Machine audit is intentionally syntactic/behavioral-light: it checks compilation plus whether edits touch the expected layer and mention/modify key chain nodes. It does not execute a full Guava test suite or prove runtime rate-limit/retry/log behavior exhaustively.
