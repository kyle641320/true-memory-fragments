# Mutation Freshness V1 Report

## Purpose

Test TMF's unique stale detection + freshness binding + automatic invalidation value. This is not a TMF-vs-document accuracy test.

## Mutation

A pre-mutation B12 claim says `Subscriber.invokeSubscriberMethod` directly contains `method.invoke(target, checkNotNull(event))`. The fixture is then mutated so `invokeSubscriberMethod` calls `invokeReflectively(event)`, and the concrete `Method.invoke` call moves into `invokeReflectively`.

Expected TMF behavior: the old claim is stale because the bound Java method hash changed; TMF_STALE_GATED must withhold it and warn the agent to read source. Stale DOC_CONTROL receives the old note without freshness binding.

## Summary

```json
{
  "mode": "mutation_freshness_v1",
  "runs": 9,
  "by_arm": {
    "SOURCE_ONLY": {
      "runs": 3,
      "raw_pass": 3,
      "compile_ok": 3,
      "trap_pass": 3,
      "fresh_claim_injected": 0,
      "stale_claim_withheld": 0,
      "primary": {
        "pass": 3
      }
    },
    "STALE_DOC_CONTROL": {
      "runs": 3,
      "raw_pass": 2,
      "compile_ok": 3,
      "trap_pass": 2,
      "fresh_claim_injected": 0,
      "stale_claim_withheld": 0,
      "primary": {
        "pass": 2,
        "edit_protocol_fail": 1
      }
    },
    "TMF_STALE_GATED": {
      "runs": 3,
      "raw_pass": 3,
      "compile_ok": 3,
      "trap_pass": 3,
      "fresh_claim_injected": 0,
      "stale_claim_withheld": 3,
      "primary": {
        "pass": 3
      }
    }
  }
}
```

## Rows
- rep 1 SOURCE_ONLY: pass=True compile=True trap=True fresh=False failure=pass raw=results/raw/mutation_freshness_v1/M01__SOURCE_ONLY__r1.raw.json
  - reason={"subscriber_changed": true, "helper_changed": true, "hoisted_hook_inside_invokeReflectively": true, "direct_hook_before_checkNotNull_expr_in_helper_too_early": false, "stale_hook_before_invokeReflectively_wrong": false}
- rep 1 STALE_DOC_CONTROL: pass=True compile=True trap=True fresh=False failure=pass raw=results/raw/mutation_freshness_v1/M01__STALE_DOC_CONTROL__r1.raw.json
  - reason={"subscriber_changed": true, "helper_changed": true, "hoisted_hook_inside_invokeReflectively": true, "direct_hook_before_checkNotNull_expr_in_helper_too_early": false, "stale_hook_before_invokeReflectively_wrong": false}
- rep 1 TMF_STALE_GATED: pass=True compile=True trap=True fresh=False failure=pass raw=results/raw/mutation_freshness_v1/M01__TMF_STALE_GATED__r1.raw.json
  - reason={"subscriber_changed": true, "helper_changed": true, "hoisted_hook_inside_invokeReflectively": true, "direct_hook_before_checkNotNull_expr_in_helper_too_early": false, "stale_hook_before_invokeReflectively_wrong": false}
- rep 2 SOURCE_ONLY: pass=True compile=True trap=True fresh=False failure=pass raw=results/raw/mutation_freshness_v1/M01__SOURCE_ONLY__r2.raw.json
  - reason={"subscriber_changed": true, "helper_changed": true, "hoisted_hook_inside_invokeReflectively": true, "direct_hook_before_checkNotNull_expr_in_helper_too_early": false, "stale_hook_before_invokeReflectively_wrong": false}
- rep 2 STALE_DOC_CONTROL: pass=True compile=True trap=True fresh=False failure=pass raw=results/raw/mutation_freshness_v1/M01__STALE_DOC_CONTROL__r2.raw.json
  - reason={"subscriber_changed": true, "helper_changed": true, "hoisted_hook_inside_invokeReflectively": true, "direct_hook_before_checkNotNull_expr_in_helper_too_early": false, "stale_hook_before_invokeReflectively_wrong": false}
- rep 2 TMF_STALE_GATED: pass=True compile=True trap=True fresh=False failure=pass raw=results/raw/mutation_freshness_v1/M01__TMF_STALE_GATED__r2.raw.json
  - reason={"subscriber_changed": true, "helper_changed": true, "hoisted_hook_inside_invokeReflectively": true, "direct_hook_before_checkNotNull_expr_in_helper_too_early": false, "stale_hook_before_invokeReflectively_wrong": false}
- rep 3 SOURCE_ONLY: pass=True compile=True trap=True fresh=False failure=pass raw=results/raw/mutation_freshness_v1/M01__SOURCE_ONLY__r3.raw.json
  - reason={"subscriber_changed": true, "helper_changed": true, "hoisted_hook_inside_invokeReflectively": true, "direct_hook_before_checkNotNull_expr_in_helper_too_early": false, "stale_hook_before_invokeReflectively_wrong": false}
- rep 3 STALE_DOC_CONTROL: pass=False compile=True trap=False fresh=False failure=edit_protocol_fail raw=results/raw/mutation_freshness_v1/M01__STALE_DOC_CONTROL__r3.raw.json
  - reason={"subscriber_changed": false, "helper_changed": false, "hoisted_hook_inside_invokeReflectively": false, "direct_hook_before_checkNotNull_expr_in_helper_too_early": false, "stale_hook_before_invokeReflectively_wrong": false}
- rep 3 TMF_STALE_GATED: pass=True compile=True trap=True fresh=False failure=pass raw=results/raw/mutation_freshness_v1/M01__TMF_STALE_GATED__r3.raw.json
  - reason={"subscriber_changed": true, "helper_changed": true, "hoisted_hook_inside_invokeReflectively": true, "direct_hook_before_checkNotNull_expr_in_helper_too_early": false, "stale_hook_before_invokeReflectively_wrong": false}
