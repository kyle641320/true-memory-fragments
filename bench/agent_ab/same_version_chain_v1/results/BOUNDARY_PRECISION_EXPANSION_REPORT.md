# Boundary Precision Expansion Report

Scope: same-version boundary-precision tasks B07-B13, two-arm comparison SOURCE_ONLY vs TMF_CLAIMS.

Note: B11 uses the v2 rerun after fixing multi-site boundary wording/claims and relaxing the generic exactly-one-call hook constraint. B09 was re-audited after fixing diff-line plus-prefix tolerance; both arms had correctly inserted the catch-before-handler hook.

## Summary

| task | SOURCE_ONLY | TMF_CLAIMS | outcome |
|---|---:|---:|---|
| B07 | True | True | both |
| B08 | True | True | both |
| B09 | True | True | both |
| B10 | True | True | both |
| B11 | False | True | TMF_only |
| B12 | False | True | TMF_only |
| B13 | True | True | both |

## Aggregate

- tasks: 7
- TMF_only: 2
- both_pass: 5
- source_only: 0
- neither: 0

Interpretation: current expanded sample provides limited positive shallow-boundary evidence for TMF: TMF-only positives are B11 and B12, while five tasks are easy enough that SOURCE_ONLY also passes. There are no remaining SOURCE_ONLY-only tasks after fixing the B09 audit. This is encouraging but still not decisive enough for mutation; next iteration should add less-leading boundary tasks where Phase B describes the goal and TMF carries the precise edge/site details.

## Rows

- B07 / SOURCE_ONLY: valid=True compile=True trap=True files=['Subscriber.java'] raw=results/raw/boundary_precision_B07_SOURCE_ONLY/B07__SOURCE_ONLY.raw.json
  - reason={"subscriber_changed": true, "hookish": true, "inside_lambda_before_invoke": true, "not_before_executor_execute": true, "not_post_or_dispatcher_only": true}
- B07 / TMF_CLAIMS: valid=True compile=True trap=True files=['Subscriber.java'] raw=results/raw/boundary_precision_B07_TMF_CLAIMS/B07__TMF_CLAIMS.raw.json
  - reason={"subscriber_changed": true, "hookish": true, "inside_lambda_before_invoke": true, "not_before_executor_execute": true, "not_post_or_dispatcher_only": true}
- B08 / SOURCE_ONLY: valid=True compile=True trap=True files=['Subscriber.java'] raw=results/raw/boundary_precision_B08_SOURCE_ONLY/B08__SOURCE_ONLY.raw.json
  - reason={"subscriber_changed": true, "hookish": true, "after_invoke_success_boundary": true, "not_before_invoke": true, "not_in_failure_catch": true}
- B08 / TMF_CLAIMS: valid=True compile=True trap=True files=['Subscriber.java'] raw=results/raw/boundary_precision_B08_TMF_CLAIMS/B08__TMF_CLAIMS.raw.json
  - reason={"subscriber_changed": true, "hookish": true, "after_invoke_success_boundary": true, "not_before_invoke": true, "not_in_failure_catch": true}
- B09 / SOURCE_ONLY: valid=True compile=True trap=True files=['Subscriber.java'] raw=results/raw/boundary_precision_B09_SOURCE_ONLY/B09__SOURCE_ONLY.raw.json
  - reason={"subscriber_changed": true, "hookish": true, "catch_before_handleSubscriberException": true, "not_before_invoke": true, "not_eventbus_only": true}
- B09 / TMF_CLAIMS: valid=True compile=True trap=True files=['Subscriber.java'] raw=results/raw/boundary_precision_B09_TMF_CLAIMS/B09__TMF_CLAIMS.raw.json
  - reason={"subscriber_changed": true, "hookish": true, "catch_before_handleSubscriberException": true, "not_before_invoke": true, "not_eventbus_only": true}
- B10 / SOURCE_ONLY: valid=True compile=True trap=True files=['EventBus.java'] raw=results/raw/boundary_precision_B10_SOURCE_ONLY/B10__SOURCE_ONLY.raw.json
  - reason={"eventbus_changed": true, "hookish": true, "before_dead_event_repost": true, "not_post_entry": true, "not_subscriber_or_dispatcher_only": true}
- B10 / TMF_CLAIMS: valid=True compile=True trap=True files=['EventBus.java'] raw=results/raw/boundary_precision_B10_TMF_CLAIMS/B10__TMF_CLAIMS.raw.json
  - reason={"eventbus_changed": true, "hookish": true, "before_dead_event_repost": true, "not_post_entry": true, "not_subscriber_or_dispatcher_only": true}
- B11 / SOURCE_ONLY: valid=True compile=True trap=False files=['Dispatcher.java'] raw=results/raw/boundary_precision_B11_SOURCE_ONLY_v2/B11__SOURCE_ONLY.raw.json
  - reason={"dispatcher_changed": true, "hookish": true, "before_subscriber_dispatchEvent_or_full_helper": false, "replaced_dispatch_sites": 2, "not_subscriber_only": true, "not_eventbus_only": true, "helper_recurses_instead_of_calling_subscriber_dispatchEvent": true}
- B11 / TMF_CLAIMS: valid=True compile=True trap=True files=['Dispatcher.java'] raw=results/raw/boundary_precision_B11_TMF_CLAIMS_v2/B11__TMF_CLAIMS.raw.json
  - reason={"dispatcher_changed": true, "hookish": true, "before_subscriber_dispatchEvent_or_full_helper": true, "replaced_dispatch_sites": 3, "not_subscriber_only": true, "not_eventbus_only": true}
- B12 / SOURCE_ONLY: valid=True compile=True trap=False files=['Subscriber.java'] raw=results/raw/boundary_precision_B12_SOURCE_ONLY/B12__SOURCE_ONLY.raw.json
  - reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": false, "direct_hook_before_checkNotNull_expr_is_too_early": true, "not_outer_dispatchEvent": true}
- B12 / TMF_CLAIMS: valid=True compile=True trap=True files=['Subscriber.java'] raw=results/raw/boundary_precision_B12_TMF_CLAIMS/B12__TMF_CLAIMS.raw.json
  - reason={"subscriber_changed": true, "hookish": true, "hoisted_nullcheck_then_hook_then_MethodInvoke": true, "direct_hook_before_checkNotNull_expr_is_too_early": false, "not_outer_dispatchEvent": true}
- B13 / SOURCE_ONLY: valid=True compile=True trap=True files=['Subscriber.java'] raw=results/raw/boundary_precision_B13_SOURCE_ONLY/B13__SOURCE_ONLY.raw.json
  - reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
- B13 / TMF_CLAIMS: valid=True compile=True trap=True files=['Subscriber.java'] raw=results/raw/boundary_precision_B13_TMF_CLAIMS/B13__TMF_CLAIMS.raw.json
  - reason={"subscriber_changed": true, "hookish": true, "inside_invokeSubscriberMethod_after_MethodInvoke": true, "not_catch_path": true, "not_outer_dispatchEvent": true}
