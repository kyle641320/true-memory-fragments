# Claim 5 Proof Update — 2026-09-01

## Claim

The new M16/M21 TMF failures are not stale-gating failures. They are downstream implementation, oracle, or edit-placement failures after stale claims were correctly withheld.

## Evidence files

- `results/order_m16_corevalue_r4.json`
- `results/ORDER_M16_COREVALUE_R4_REPORT.md`
- `results/raw/order_m16_corevalue_r4/ORDER_M16__TMF_REFRESHED_MAP__r1.raw.json`
- `results/raw/order_m16_corevalue_r4/ORDER_M16__TMF_REFRESHED_MAP__r2.raw.json`
- `results/order_m21_stale_api_trap_r4.json`
- `results/ORDER_M21_STALE_API_TRAP_R4_REPORT.md`
- `results/raw/order_m21_stale_api_trap_r4/ORDER_M21__TMF_REFRESHED_MAP__r1.raw.json`

## M16 R4 TMF failures

Rows:

- `ORDER_M16__TMF_REFRESHED_MAP__r1.raw.json`
- `ORDER_M16__TMF_REFRESHED_MAP__r2.raw.json`

Observed:

- `stale_claim_withheld=true` in both rows.
- `freshness.fresh=false` in both rows.
- The agent read current `OrderService`, `PaymentIntentService`, and `Order` symbols.
- The patch moved payment-intent creation before inventory reservation and added a `PENDING_REVIEW` branch that marks `AWAITING_REVIEW`, saves, and returns without publishing.
- Compile succeeded, but hidden JUnit oracle failed.

Attribution:

- This is not stale claim injection. The stale claim was withheld.
- The failure is best classified as incomplete hidden-oracle satisfaction / task semantics mismatch. The agent made a plausible current-source fix but did not satisfy every hidden invariant.

## M21 R4 TMF failure

Row:

- `ORDER_M21__TMF_REFRESHED_MAP__r1.raw.json`

Observed:

- `stale_claim_withheld=true`.
- `freshness.fresh=false`.
- The transcript contained a noisy multi-action turn; extra actions were ignored by the broker.
- The first final was rejected because no successful edit had landed.
- The eventual successful edit landed in `PaymentIntentService.java`, marking the order as awaiting review when the payment intent is pending review.
- Hidden oracle still failed because `OrderService` did not branch on the current review contract and did not mark pending-review orders as awaiting review at the required boundary.

Attribution:

- This is an execution/edit-placement failure plus protocol noise, not stale-gating failure.
- The TMF freshness mechanism did its job: the stale claim was withheld.

## Updated conclusion

Claim 5 remains supported:

> In the inspected 2026-09-01 TMF failures, stale-memory containment worked. The misses were downstream agent execution/placement/semantic-completion failures, not stale claim injection failures.

Boundary: this attribution applies only to inspected rows. Future failures still require raw/diff inspection before classification.
