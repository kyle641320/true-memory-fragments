# M21 No-TMF-Change Assessment

## Scope

This follow-up intentionally does **not** modify TMF body code under `tmf/`.
The only code-level change is in the synthetic M21 benchmark runner/checker:

- `bench/agent_ab/same_version_chain_v1/order_m21_stale_api_trap_runner.py`

## Benchmark fixes applied

1. Failure classification cleanup:
   - Recovered compile failures no longer take primary `compile_action_fail`.
   - If a later compile succeeds and the hidden oracle fails with a diff, primary is `hidden_oracle_fail`.
   - Compile-before-edit / no-successful-edit final-gate lock is classified as `final_gate_deadlock`.

2. Deterministic checker cleanup:
   - The checker now accepts equivalent current review-contract branches using `requiresManualReview(...)` / `manualReview`, not only direct `getStatus()` / `PaymentIntentStatus` checks.
   - This prevents hidden-JUnit-passing solutions from being mislabeled as semantic failures.

3. TMF budget probe was reverted:
   - A temporary probe changed M21 runner `max_required_reads` from 3 to 6.
   - It was restored to 3 after the probe.
   - The probe result is preserved only as experimental evidence.

## Key evidence

### Existing R2 replay after checker fix

File:

- `results/order_m21_stale_api_trap_classfix_r2_checkerfix_replay.json`
- `results/ORDER_M21_STALE_API_TRAP_CLASSFIX_R2_CHECKERFIX_REPLAY_REPORT.md`

Summary:

- SOURCE_ONLY: 2/2 pass
- PREREAD_STALE_SOURCE: 0/2, hidden_oracle_fail
- STALE_DOC_CONTROL: 0/2, hidden_oracle_fail
- TMF_REFRESHED_MAP: 2/2 pass

### Clean R4 after classification/checker fixes

File:

- `results/order_m21_stale_api_trap_classfix_checkerfix_r4.json`
- `results/ORDER_M21_STALE_API_TRAP_CLASSFIX_CHECKERFIX_R4_REPORT.md`

Summary:

- SOURCE_ONLY: 2/4 pass
- PREREAD_STALE_SOURCE: 0/4, hidden_oracle_fail
- STALE_DOC_CONTROL: 0/4, hidden_oracle_fail
- TMF_REFRESHED_MAP: 2/4 pass, 2 hidden_oracle_fail

TMF failed samples r1/r3 had the same root shape:

- Agent read OrderService / PaymentIntentService / Order.
- Agent did not read FulfillmentPolicy.
- Agent correctly branched on current payment status and marked AWAITING_REVIEW.
- Agent left ORDER_CREATED guarded only by stale `fulfillmentPolicy.shouldPublishOrderCreated(order)`.
- Hidden tests failed because that old compatibility API still returns true.

### Required-read budget probe

File:

- `results/order_m21_stale_api_trap_required6_probe_r2.json`
- `results/ORDER_M21_STALE_API_TRAP_REQUIRED6_PROBE_R2_REPORT.md`

Summary:

- TMF_REFRESHED_MAP: 1/2 pass

Interpretation:

- Increasing required reads to include FulfillmentPolicy is not sufficient by itself.
- One pass case read FulfillmentPolicy and used `canStartFulfillment` correctly.
- One fail case also read FulfillmentPolicy and used `canStartFulfillment`, but called it before `order.markReady()`, so confirmed orders did not publish.
- Therefore the remaining issue is not only stale-API discovery; it also involves state-transition / side-effect ordering.

## Conclusion

Do **not** modify TMF body code yet.

M21 currently provides enough signal to keep the benchmark as a regression probe, but not enough evidence for a broad TMF body change. If a later TMF change is considered, it should be narrow and separately validated:

1. Elevate policy/gate symbols that directly guard event-publish side effects into the stale-slice required-read set.
2. Add ordering guidance when the current gate predicate depends on state transitions, e.g. `order.getStatus() == READY` must be evaluated after the READY transition.
3. Validate on M21 plus adjacent side-effect benchmarks before treating this as a general TMF rule.
