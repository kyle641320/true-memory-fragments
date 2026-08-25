# Mutation Freshness V5 Report

## Purpose

Test TMF's unique stale detection + freshness binding + automatic invalidation value. This is not a TMF-vs-document accuracy test.

## Mutation

A pre-mutation B12 claim says `Subscriber.invokeSubscriberMethod` directly contains `method.invoke(target, checkNotNull(event))`. The fixture is then mutated so `invokeSubscriberMethod` calls `invokeReflectively(event)`, and the concrete `Method.invoke` call moves into `invokeReflectively`.

## Harmful stale-doc control

`STALE_DOC_CONTROL` simulates an agent that trusts a project handbook REQUIRED PATCH SITE when its anchor still exists: insert immediately before `invokeReflectively(event)` in `Subscriber.invokeSubscriberMethod`. That edit compiles but is semantically wrong for a hook that should be adjacent to the actual reflective invocation. `TMF_STALE_GATED` runs the old knowledge through `check_freshness`; when stale, it withholds the claim and emits a stale warning instead.

## Metric separation

- raw pass: valid final + compile OK + semantic trap pass.
- protocol-clean/evaluable: final artifact has diff + compile OK and is not a no-effect/compile/parse failure; intermediate failed edit retries do not remove the run from semantic scoring.
- semantic-adjusted pass: trap pass among protocol-clean semantic-evaluable runs.

## Summary

```json
{
  "mode": "mutation_freshness_v5",
  "runs": 15,
  "metric_notes": {
    "raw_pass": "valid final + compile OK + trap pass",
    "protocol_clean": "excludes edit/no-effect/compile/parse protocol failures",
    "semantic_adjusted_pass": "trap pass among protocol-clean semantic-evaluable runs only"
  },
  "by_arm": {
    "SOURCE_ONLY": {
      "runs": 5,
      "raw_pass": 0,
      "protocol_clean": 5,
      "semantic_evaluable": 5,
      "semantic_adjusted_pass": 0,
      "compile_ok": 5,
      "trap_pass": 0,
      "fresh_claim_injected": 0,
      "stale_claim_withheld": 0,
      "stale_doc_wrong_old_site": 0,
      "stale_doc_anchor_attempt": 0,
      "primary": {
        "edit_protocol_fail": 2,
        "semantic_boundary_fail": 3
      }
    },
    "STALE_DOC_CONTROL": {
      "runs": 5,
      "raw_pass": 0,
      "protocol_clean": 3,
      "semantic_evaluable": 3,
      "semantic_adjusted_pass": 0,
      "compile_ok": 3,
      "trap_pass": 0,
      "fresh_claim_injected": 0,
      "stale_claim_withheld": 0,
      "stale_doc_wrong_old_site": 5,
      "stale_doc_anchor_attempt": 1,
      "primary": {
        "semantic_boundary_fail": 2,
        "edit_protocol_fail": 3
      }
    },
    "TMF_STALE_GATED": {
      "runs": 5,
      "raw_pass": 0,
      "protocol_clean": 5,
      "semantic_evaluable": 5,
      "semantic_adjusted_pass": 0,
      "compile_ok": 5,
      "trap_pass": 0,
      "fresh_claim_injected": 0,
      "stale_claim_withheld": 5,
      "stale_doc_wrong_old_site": 0,
      "stale_doc_anchor_attempt": 1,
      "primary": {
        "edit_protocol_fail": 2,
        "semantic_boundary_fail": 3
      }
    }
  }
}
```

## Rows
- rep 1 SOURCE_ONLY: raw_pass=False protocol_clean=True semantic_pass=False compile=True trap=False fresh=False failure=edit_protocol_fail raw=results/raw/mutation_freshness_v5/M05__SOURCE_ONLY__r1.raw.json
  - reason={"subscriber_changed": true, "helper_changed": true, "hoisted_hook_inside_invokeReflectively": false, "direct_hook_before_checkNotNull_expr_in_helper_too_early": true, "stale_hook_before_invokeReflectively_wrong": false, "stale_doc_anchor_attempt": false}
- rep 1 STALE_DOC_CONTROL: raw_pass=False protocol_clean=True semantic_pass=False compile=True trap=False fresh=False failure=semantic_boundary_fail raw=results/raw/mutation_freshness_v5/M05__STALE_DOC_CONTROL__r1.raw.json
  - reason={"subscriber_changed": true, "helper_changed": true, "hoisted_hook_inside_invokeReflectively": false, "direct_hook_before_checkNotNull_expr_in_helper_too_early": false, "stale_hook_before_invokeReflectively_wrong": true, "stale_doc_anchor_attempt": false}
- rep 1 TMF_STALE_GATED: raw_pass=False protocol_clean=True semantic_pass=False compile=True trap=False fresh=False failure=edit_protocol_fail raw=results/raw/mutation_freshness_v5/M05__TMF_STALE_GATED__r1.raw.json
  - reason={"subscriber_changed": true, "helper_changed": true, "hoisted_hook_inside_invokeReflectively": false, "direct_hook_before_checkNotNull_expr_in_helper_too_early": true, "stale_hook_before_invokeReflectively_wrong": false, "stale_doc_anchor_attempt": false}
- rep 2 SOURCE_ONLY: raw_pass=False protocol_clean=True semantic_pass=False compile=True trap=False fresh=False failure=edit_protocol_fail raw=results/raw/mutation_freshness_v5/M05__SOURCE_ONLY__r2.raw.json
  - reason={"subscriber_changed": true, "helper_changed": false, "hoisted_hook_inside_invokeReflectively": false, "direct_hook_before_checkNotNull_expr_in_helper_too_early": false, "stale_hook_before_invokeReflectively_wrong": false, "stale_doc_anchor_attempt": false}
- rep 2 STALE_DOC_CONTROL: raw_pass=False protocol_clean=True semantic_pass=False compile=True trap=False fresh=False failure=semantic_boundary_fail raw=results/raw/mutation_freshness_v5/M05__STALE_DOC_CONTROL__r2.raw.json
  - reason={"subscriber_changed": true, "helper_changed": true, "hoisted_hook_inside_invokeReflectively": false, "direct_hook_before_checkNotNull_expr_in_helper_too_early": false, "stale_hook_before_invokeReflectively_wrong": true, "stale_doc_anchor_attempt": true}
- rep 2 TMF_STALE_GATED: raw_pass=False protocol_clean=True semantic_pass=False compile=True trap=False fresh=False failure=semantic_boundary_fail raw=results/raw/mutation_freshness_v5/M05__TMF_STALE_GATED__r2.raw.json
  - reason={"subscriber_changed": true, "helper_changed": true, "hoisted_hook_inside_invokeReflectively": false, "direct_hook_before_checkNotNull_expr_in_helper_too_early": false, "stale_hook_before_invokeReflectively_wrong": false, "stale_doc_anchor_attempt": true}
- rep 3 SOURCE_ONLY: raw_pass=False protocol_clean=True semantic_pass=False compile=True trap=False fresh=False failure=semantic_boundary_fail raw=results/raw/mutation_freshness_v5/M05__SOURCE_ONLY__r3.raw.json
  - reason={"subscriber_changed": true, "helper_changed": true, "hoisted_hook_inside_invokeReflectively": false, "direct_hook_before_checkNotNull_expr_in_helper_too_early": true, "stale_hook_before_invokeReflectively_wrong": false, "stale_doc_anchor_attempt": false}
- rep 3 STALE_DOC_CONTROL: raw_pass=False protocol_clean=False semantic_pass=None compile=False trap=False fresh=False failure=edit_protocol_fail raw=results/raw/mutation_freshness_v5/M05__STALE_DOC_CONTROL__r3.raw.json
  - reason={"subscriber_changed": true, "helper_changed": true, "hoisted_hook_inside_invokeReflectively": false, "direct_hook_before_checkNotNull_expr_in_helper_too_early": false, "stale_hook_before_invokeReflectively_wrong": true, "stale_doc_anchor_attempt": false}
- rep 3 TMF_STALE_GATED: raw_pass=False protocol_clean=True semantic_pass=False compile=True trap=False fresh=False failure=semantic_boundary_fail raw=results/raw/mutation_freshness_v5/M05__TMF_STALE_GATED__r3.raw.json
  - reason={"subscriber_changed": true, "helper_changed": true, "hoisted_hook_inside_invokeReflectively": false, "direct_hook_before_checkNotNull_expr_in_helper_too_early": true, "stale_hook_before_invokeReflectively_wrong": false, "stale_doc_anchor_attempt": false}
- rep 4 SOURCE_ONLY: raw_pass=False protocol_clean=True semantic_pass=False compile=True trap=False fresh=False failure=semantic_boundary_fail raw=results/raw/mutation_freshness_v5/M05__SOURCE_ONLY__r4.raw.json
  - reason={"subscriber_changed": true, "helper_changed": true, "hoisted_hook_inside_invokeReflectively": false, "direct_hook_before_checkNotNull_expr_in_helper_too_early": true, "stale_hook_before_invokeReflectively_wrong": false, "stale_doc_anchor_attempt": false}
- rep 4 STALE_DOC_CONTROL: raw_pass=False protocol_clean=True semantic_pass=False compile=True trap=False fresh=False failure=edit_protocol_fail raw=results/raw/mutation_freshness_v5/M05__STALE_DOC_CONTROL__r4.raw.json
  - reason={"subscriber_changed": true, "helper_changed": true, "hoisted_hook_inside_invokeReflectively": false, "direct_hook_before_checkNotNull_expr_in_helper_too_early": false, "stale_hook_before_invokeReflectively_wrong": true, "stale_doc_anchor_attempt": false}
- rep 4 TMF_STALE_GATED: raw_pass=False protocol_clean=True semantic_pass=False compile=True trap=False fresh=False failure=semantic_boundary_fail raw=results/raw/mutation_freshness_v5/M05__TMF_STALE_GATED__r4.raw.json
  - reason={"subscriber_changed": true, "helper_changed": true, "hoisted_hook_inside_invokeReflectively": false, "direct_hook_before_checkNotNull_expr_in_helper_too_early": true, "stale_hook_before_invokeReflectively_wrong": false, "stale_doc_anchor_attempt": false}
- rep 5 SOURCE_ONLY: raw_pass=False protocol_clean=True semantic_pass=False compile=True trap=False fresh=False failure=semantic_boundary_fail raw=results/raw/mutation_freshness_v5/M05__SOURCE_ONLY__r5.raw.json
  - reason={"subscriber_changed": true, "helper_changed": true, "hoisted_hook_inside_invokeReflectively": false, "direct_hook_before_checkNotNull_expr_in_helper_too_early": false, "stale_hook_before_invokeReflectively_wrong": false, "stale_doc_anchor_attempt": false}
- rep 5 STALE_DOC_CONTROL: raw_pass=False protocol_clean=False semantic_pass=None compile=False trap=False fresh=False failure=edit_protocol_fail raw=results/raw/mutation_freshness_v5/M05__STALE_DOC_CONTROL__r5.raw.json
  - reason={"subscriber_changed": true, "helper_changed": true, "hoisted_hook_inside_invokeReflectively": false, "direct_hook_before_checkNotNull_expr_in_helper_too_early": false, "stale_hook_before_invokeReflectively_wrong": true, "stale_doc_anchor_attempt": false}
- rep 5 TMF_STALE_GATED: raw_pass=False protocol_clean=True semantic_pass=False compile=True trap=False fresh=False failure=edit_protocol_fail raw=results/raw/mutation_freshness_v5/M05__TMF_STALE_GATED__r5.raw.json
  - reason={"subscriber_changed": true, "helper_changed": false, "hoisted_hook_inside_invokeReflectively": false, "direct_hook_before_checkNotNull_expr_in_helper_too_early": false, "stale_hook_before_invokeReflectively_wrong": false, "stale_doc_anchor_attempt": false}
