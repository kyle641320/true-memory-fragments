# Claim 5 Proof — TMF failures are not stale-gating failures

## Claim

Observed TMF failures in the recent M21 runs are downstream semantic/read-selection/ordering failures, not stale claim injection failures.

## Proof standard

For TMF failed rows:

- `stale_claim_withheld` remains true.
- The failure is attributable to patch semantics, read-selection, ordering, or harness behavior.
- There is no evidence that a stale claim was injected as authoritative current context.

## M21 clean R4 evidence

File:

- `results/order_m21_stale_api_trap_classfix_checkerfix_r4.json`

TMF rows:

- 4/4 had `stale_claim_withheld=true`.
- 2/4 passed.
- 2/4 failed hidden oracle.

Failure shape for failed TMF rows:

- Agent read `OrderService`, `PaymentIntentService`, and `Order`.
- Agent did not read `FulfillmentPolicy`.
- Agent correctly introduced current review-state handling (`AWAITING_REVIEW`).
- Agent left event publication guarded only by old `fulfillmentPolicy.shouldPublishOrderCreated(order)`.
- Hidden oracle failed because old compatibility gate still returned true.

## Required-read budget probe evidence

A temporary M21 runner probe increased TMF required reads from 3 to 6 and was later reverted.

Result:

- TMF 1/2 pass.
- The failed probe row did read `FulfillmentPolicy` and used `canStartFulfillment`, but called it before `order.markReady()`, causing confirmed orders not to publish.

This demonstrates a separate ordering/side-effect sequencing issue, not stale claim injection.

## Result

Claim 5 is supported/proven for recent M21 failures:

> TMF stale-gating worked; remaining failures were downstream semantic read-selection or ordering failures.

## Boundary

This conclusion is per-failure and must not be generalized blindly. Future TMF failures still require raw/diff inspection before attribution.
