# Design Intent V1 Experiment Plan

Status: pre-registered plan for the next TMF value replication wave. This file freezes interpretation rules before any larger follow-up run is treated as evidence.

## Question

`GUAVA_M10_PREREAD_R50` gives scoped positive evidence for stale-context safety on one real Guava fixture. The remaining unproven claims are:

1. Whether TMF stably lowers bug rate across more real task types / fixtures / repositories.
2. Whether that bug-rate reduction is strong enough to justify long-term productization.
3. Whether ROI is significant after counting injection tokens, wall time, source reads, and harness/protocol noise.

## Current evidence boundary

- Treat `GUAVA_M10_PREREAD_R50` as valid scoped evidence that stale claims/docs can pollute boundary selection and that TMF stale-gating can block that pollution on one real Guava EventBus task.
- Do not treat M10 as proof of broad productivity, token savings, source reread reduction, stable adoption, or product ROI.
- Do not infer product value from raw pass alone. Report raw pass, protocol-clean pass, semantic/task pass, and protocol-noise categories separately.

## Arms

Primary experiments use four arms:

1. `SOURCE_ONLY`
   - No old context or TMF injection.
   - Agent must infer from current source.

2. `PREREAD_STALE_SOURCE`
   - Simulates the same cognitive subject continuing from an old source-derived conclusion.
   - Receives an old source excerpt and old boundary conclusion.

3. `STALE_DOC_CONTROL`
   - Receives stale prose / handbook-style guidance without freshness binding.
   - Measures generic stale context pollution.

4. `TMF_STALE_GATED`
   - Receives stale-gate warning and withheld-claim metadata only.
   - Must not receive the stale boundary content.
   - Each raw row should explicitly record:
     - `stale_claim_present`
     - `stale_claim_fresh`
     - `stale_claim_withheld`
     - `withheld_claim_id`
     - `stale_bindings`

Optional later arm, only after the primary stale-gating endpoint is replicated:

5. `TMF_FRESH_LOCALIZED`
   - Uses a fresh updated localized claim after Phase-B reread.
   - Measures localized reread/productivity, not primary stale-gating safety.

## Fixture admission gates

A fixture is eligible for a larger run only if smoke shows all of the following:

1. The mutated repository compiles before agent edits.
2. The old Phase-A claim is bound to exact source/hash and becomes stale after mutation.
3. The stale site remains plausible and compilable after mutation.
4. The correct site is different from the stale site and is checked by deterministic post-test/golden audit.
5. At least one stale-context control arm shows measurable stale-site error in smoke or calibration.
6. Protocol noise is bounded enough to interpret semantic outcomes.

If stale controls do not fail, the fixture is a negative calibration fixture, not TMF evidence. Do not increase repeats just to search for a signal.

## Metrics

### Semantic/task layer

- `task_result_pass`
- `post_test_ok`
- `correct_current_site`
- `wrong_stale_site`
- `wrong_other_site`
- `bug_introduced`
- `stale_trust_error`
- `localized_reread_success`

Primary endpoint:

- TMF stale-site bug rate versus `PREREAD_STALE_SOURCE` and `STALE_DOC_CONTROL`.

### Harness/protocol layer

- `raw_pass`
- `protocol_clean`
- `semantic_evaluable`
- `no_final`
- `no_final_after_success`
- `edit_protocol_fail`
- `parse_or_invalid_action_noise`
- `no_tool_use`
- `duplicate_edit_suppressed`
- `invalid_path`
- `result_ok_but_raw_failed`

Interpretation rule:

- `task_result_pass/post_test_ok` is the user-visible task result.
- `raw_pass` remains strict protocol score.
- Pure `no_final_after_success` or invalid-prose noise must be reported as harness/protocol noise, not semantic failure.

### ROI/product layer

- `prompt_tokens`
- `completion_tokens`
- estimated TMF injection tokens
- `source_reads`
- `source_bytes`
- `tool_calls`
- `wall_seconds`
- compile/test passes
- stale bugs avoided
- protocol-noise count

No productivity or ROI claim is allowed unless the measured stale-bug reduction is large enough to offset injection/runtime overhead under an explicit scenario model.

## Scale and stopping rules

1. Calibration smoke:
   - `1-3 repeats × 4 arms × fixture`.
   - Purpose: admit/reject fixture, not prove value.

2. Formal replication:
   - At least 3 independent real fixture families before any broad claim.
   - Start with `30 repeats × 4 arms × fixture`.
   - Increase to `50` only if noise gates pass and the fixture has a demonstrated stale trap.

3. Stop / fix runner before interpretation if:
   - compile of mutated baseline is not 100%; or
   - protocol-unclean rate is too high to separate semantic failure from harness noise; or
   - stale controls do not show stale-site errors in smoke.

## Initial calibration outcome

### M11 exception-handler boundary smoke

Path: `bench/agent_ab/same_version_chain_v1/guava_m11_exception_preread_runner.py`

Smoke tag: `guava_m11_exception_smoke_r1`

Observed summary:

- `SOURCE_ONLY`: `task_result_pass=0/1`, no edit/final.
- `PREREAD_STALE_SOURCE`: `task_result_pass=1/1`, `wrong_wrapper_site=0/1`.
- `STALE_DOC_CONTROL`: `task_result_pass=1/1`, `wrong_wrapper_site=0/1`.
- `TMF_STALE_GATED`: `task_result_pass=1/1`, `wrong_wrapper_site=0/1`, stale claim withheld.

Ruling:

- M11 is a negative calibration fixture. It does not form a stale trap because stale-context arms still found the current helper site.
- Do not scale M11 as positive TMF evidence.
- Keep M11 only as an example that real-looking mutations must pass fixture-admission gates before costly replication.

## Next accepted work

1. Harden future runners to store explicit stale-claim fields per raw row.
2. Search for/admit at least two additional real fixture families where stale controls measurably fail in smoke.
3. Only after three admitted real fixture families pass smoke, run formal `R30` replication and report raw/protocol/semantic/ROI layers separately.

### M12 CDC projection workflow smoke

Path: `bench/agent_ab/same_version_chain_v1/cdc_m12_projection_runner.py`

Smoke tag: `cdc_m12_projection_smoke_r1`

Observed summary:

- `SOURCE_ONLY`: `task_result_pass=1/1`; fixed the workflow and passed post-test, with one parse/noise category.
- `PREREAD_STALE_SOURCE`: `task_result_pass=0/1`; failed through edit/protocol noise and incomplete repository contract update.
- `STALE_DOC_CONTROL`: `task_result_pass=0/1`; preserved/failed around the legacy `saveVersion` workflow (`uses_legacy_save=1/1`).
- `TMF_STALE_GATED`: `task_result_pass=1/1`, `post_test_ok=1/1`, `stale_claim_withheld=1/1`; raw failed only as `no_final_after_success` after a correct diff.

Ruling:

- M12 is a promising but not-yet-admitted positive candidate.
- It shows the intended stale-context contrast in smoke: stale doc control remained anchored to the legacy checkpoint workflow while TMF stale-gated produced a passing task result.
- However harness noise is still too high: duplicate edits, invalid paths, compile-before-complete, and no-final-after-success affect interpretation.
- Do not scale M12 to R30/R50 until the runner enforces lower-noise one-action continuation or otherwise separates correct-task-result from protocol-noise more cleanly.

Next action for M12:

1. Tighten runner protocol to reduce multi-action duplicate-edit noise and no-final-after-success.
2. Re-run M12 smoke with the same frozen task/fixture.
3. Admit M12 only if stale controls continue to show stale-workflow failure and TMF/SOURCE pass with acceptable protocol noise.

### M12 protocol2 smoke

Path: `bench/agent_ab/same_version_chain_v1/cdc_m12_projection_runner.py`

Smoke tag: `cdc_m12_projection_smoke_r1_protocol2`

Protocol change:

- Runner executes only the first JSON action per turn and records ignored extra actions separately.
- Duplicate edit suppression noise disappeared in R1.
- Compile success prompts the next turn to emit exactly one final action.

Observed summary:

- `SOURCE_ONLY`: `raw_pass=1/1`, `task_result_pass=1/1`, `semantic_evaluable=1/1`.
- `PREREAD_STALE_SOURCE`: `raw_pass=1/1`, `task_result_pass=1/1`, `semantic_evaluable=1/1`.
- `STALE_DOC_CONTROL`: `raw_pass=1/1`, `task_result_pass=1/1`, `semantic_evaluable=1/1`.
- `TMF_STALE_GATED`: `raw_pass=1/1`, `task_result_pass=1/1`, `semantic_evaluable=1/1`, `stale_claim_withheld=1/1`.

Ruling:

- Protocol2 successfully reduced harness noise.
- But M12 is not admitted as positive stale-trap evidence under protocol2, because stale-control arms also passed. The earlier stale-doc failure was not stable after protocol cleanup.
- Keep M12 as a useful runner/protocol calibration, not as proof that TMF lowers bug rate on CDC projection workflows.

Next action:

- Continue fixture search; prioritize tasks where stale controls keep failing after protocol cleanup.
- Do not scale M12 R30/R50 unless a new, pre-registered mutation makes the stale-site trap stable without increasing harness noise.

## Design correction: human-style two-phase task prompt

User correction, 2026-08-28:

- The task prompt must imitate how a human gives work: say what problem to solve, not exactly how or where to solve it.
- The agent should first read source and form its own working understanding.
- Only after that first source-reading phase should the experiment mutate source/contracts.
- Phase-B task wording must not name the target file/method/boundary, must not reveal the expected implementation shape, and must not explicitly instruct source reread beyond normal task execution.

Revised experiment shape:

1. Phase A, pre-mutation orientation:
   - Agent receives a broad orientation prompt, for example: "Take a quick look at the user sync workflow and understand how remote profile sync currently works. Do not edit yet."
   - Runner allows read/list/search/compile only; edits/final are rejected.
   - Runner records what source files/symbols were read and derives/records a stale Phase-A claim from the old source.

2. Phase B, post-mutation human task:
   - Runner mutates the fixture after Phase A is complete.
   - Agent receives a concise human-style task, for example: "用户同步偶尔会卡死事务，远程失败还会被吞掉。帮我把同步逻辑修稳：网络抖动可以短重试，业务异常不能吞；远程调用不要压在数据库事务里；最终失败要让调用方知道。"
   - The prompt must not say which class/method to edit, must not mention exact annotations/helper names unless they are part of the user's natural bug report, and must not say "current source changed" as a corrective hint.

3. Arm differences:
   - `SOURCE_ONLY`: Phase-B sees only the human task.
   - `PREREAD_STALE_SOURCE`: Phase-B keeps the agent's Phase-A transcript/memory from old source.
   - `STALE_DOC_CONTROL`: Phase-B additionally gets a natural stale handbook/maintenance note.
   - `TMF_STALE_GATED`: Phase-B gets only a production-style freshness warning/withheld metadata; stale content remains hidden.

Interpretation update:

- M11/M12 are now treated as calibration under the older design and are not sufficient for human-task realism.
- Future M13+ fixtures must satisfy this two-phase human-style design before any R30/R50 replication.

### M13 RPC retry/transaction two-phase runner

Path: `bench/agent_ab/same_version_chain_v1/rpc_m13_two_phase_runner.py`

Design intent:

- Implements the corrected two-phase human-task workflow on `benchmarks/java-workflow-fixtures/rpc-retry-transaction`.
- Phase A exposes only the pre-mutation user-sync source and asks for orientation/read-only understanding; edit/final actions are rejected and post-mutation contract tests are hidden.
- After at least one meaningful source read plus orientation, the runner mutates `UserSyncService` and restores the post-mutation contract test, then checks that the Phase-A TMF claim is stale.
- Phase B uses a human-style Chinese bug report about stuck transactions, retrying network jitter, not swallowing business/final failures, and keeping remote calls outside DB transactions. It does not name the target file/method or prescribe the implementation shape.
- Four primary arms are preserved: `SOURCE_ONLY`, `PREREAD_STALE_SOURCE`, `STALE_DOC_CONTROL`, and `TMF_STALE_GATED`. The stale-gated arm receives withheld-claim metadata only; stale content remains hidden.
- This is a first-pass admission/smoke runner, not a large-sample evidence run. Scale only if deterministic setup passes and stale controls show a stable stale-workflow failure under the one-action protocol.

### M13 two-phase RPC retry/transaction smoke

Path: `bench/agent_ab/same_version_chain_v1/rpc_m13_two_phase_runner.py`

Smoke tag: `rpc_m13_two_phase_smoke_r1`

Design check:

- Phase A used old-source orientation only: the post-mutation contract test was hidden and edit/final were disallowed.
- After Phase A, the runner mutated/restored the post-task source/contracts.
- Phase B used a human-style task prompt in Chinese: it described stuck transactions, swallowed remote failures, bounded retries for network jitter, business exceptions not swallowed, remote calls outside DB transactions, and final failures surfaced to callers.
- Phase B did not name the target file/method or prescribe exact implementation shape.

Observed summary:

- `SOURCE_ONLY`: `raw_pass=1/1`, `task_result_pass=1/1`, `semantic_evaluable=1/1`.
- `PREREAD_STALE_SOURCE`: `raw_pass=1/1`, `task_result_pass=1/1`, `semantic_evaluable=1/1`.
- `STALE_DOC_CONTROL`: `raw_pass=1/1`, `task_result_pass=1/1`, `semantic_evaluable=1/1`.
- `TMF_STALE_GATED`: `raw_pass=1/1`, `task_result_pass=1/1`, `semantic_evaluable=1/1`, `stale_claim_withheld=1/1`.

Ruling:

- M13 validates the corrected two-phase human-style runner shape and has low harness noise.
- M13 is still not admitted as positive stale-trap evidence because stale controls also passed.
- This suggests the current RPC task is too self-evident from the human bug report/tests, so old context is not strong enough to induce a stable bug.

Next design implication:

- The next fixture must keep the two-phase human-style structure but avoid making the post-task oracle obvious in the human prompt/test names.
- Prefer a task where the user's request is ambiguous at the surface level and the stale memory points to a plausible but now-wrong local fix, while the correct fix requires rereading a changed downstream/internal node.

### M14 scheduler partial-failure/idempotency two-phase runner

Path: `bench/agent_ab/same_version_chain_v1/scheduler_m14_two_phase_runner.py`

Design intent:

- Keeps the corrected two-phase human-task structure from M13.
- Phase A exposes old `NotificationScheduler.runOnce`: it finds pending tasks, marks each task sent, then sends.
- After Phase A, runner mutates source into a helper-based legacy workflow and restores post-task contracts.
- Phase B human-style task is deliberately vague: "线上通知任务偶尔会丢、偶尔又重复发。帮我把这块调度逻辑修稳一点，失败时不要把状态搞乱，后续重跑也别重复打扰用户。"
- The prompt does not name the file/method, does not mention `claimPendingBatch`, and does not tell the agent to send-before-mark.
- The stale doc/control memory points toward preserving mark-before-send/pending-batch workflow.

Admission expectation:

- A valid stale trap would show stale-context arms preserving `markSent` before `send` or failing to introduce `claimPendingBatch`, while SOURCE/TMF solve from current contracts/source.

### M14 scheduler two-phase smoke result

Path: `bench/agent_ab/same_version_chain_v1/scheduler_m14_two_phase_runner.py`

Smoke tag: `scheduler_m14_two_phase_smoke_r1`

Observed summary:

- `SOURCE_ONLY`: `raw_pass=1/1`, `task_result_pass=1/1`, `semantic_evaluable=1/1`.
- `PREREAD_STALE_SOURCE`: `raw_pass=1/1`, `task_result_pass=1/1`, `semantic_evaluable=1/1`.
- `STALE_DOC_CONTROL`: `raw_pass=1/1`, `task_result_pass=1/1`, `semantic_evaluable=1/1`.
- `TMF_STALE_GATED`: `raw_pass=1/1`, `task_result_pass=1/1`, `semantic_evaluable=1/1`, `stale_claim_withheld=1/1`.

Ruling:

- M14 has low harness noise and follows the corrected two-phase human-style protocol.
- M14 is not admitted as positive stale-trap evidence: stale preread and stale doc controls still solved the task.
- Raw orientations show the agents themselves noticed the old mark-before-send problem in Phase A, so the stale memory was not misleading; it was partly diagnostic. The vague Phase-B task plus visible tests/current source were still enough for every arm to converge.

Design implication:

- The experiment should stop trying to create traps where the stale Phase-A understanding already contains obvious bug cues.
- Next candidate must make Phase-A old behavior look correct/benign, then Phase-B mutation changes a downstream/internal contract so the old memory points to a plausible but wrong local fix.
- The human task should describe only a symptom, and current tests/source should reveal the new contract only after targeted reread.

### M15 outbox contract-shift two-phase smoke result

Path: `bench/agent_ab/same_version_chain_v1/outbox_m15_two_phase_runner.py`

Smoke tag: `outbox_m15_two_phase_smoke_r1`

Observed summary:

- `SOURCE_ONLY`: `raw_pass=1/1`, `task_result_pass=1/1`, `semantic_evaluable=1/1`.
- `PREREAD_STALE_SOURCE`: `raw_pass=1/1`, `task_result_pass=1/1`, `semantic_evaluable=1/1`.
- `STALE_DOC_CONTROL`: `raw_pass=1/1`, `task_result_pass=1/1`, `semantic_evaluable=1/1`.
- `TMF_STALE_GATED`: `raw_pass=1/1`, `task_result_pass=1/1`, `semantic_evaluable=1/1`, `stale_claim_withheld=1/1`.

Ruling:

- M15 follows the stronger contract-shift idea: Phase A old behavior is benign/correct, then Phase B changes `EventPublisher` to add `publishAfterCommit`.
- It still is not admitted as positive stale-trap evidence because all stale arms passed.
- Root cause: the visible test/interface made the new API/contract too obvious. Agents read `OrderServiceContractTest` and/or `EventPublisher` and directly replaced `publish` with `publishAfterCommit` despite stale context.

Next design correction:

- To measure stale-memory bug prevention rather than test-following, the next runner should separate visible compile feedback from hidden semantic oracle.
- Phase B may expose current source/interfaces, but not a test whose name/assertions spell out the exact replacement API.
- The deterministic post-test/oracle should be hidden from the agent, while the agent only gets compile feedback or a vague human bug report.
- Otherwise strong agents will simply read the contract test and neutralize stale-context effects in every arm.

## Design correction: task complexity and hidden oracle

User correction, 2026-08-28 21:59:

- M11-M15 were too easy. They mostly collapsed into one-call-site or obvious API replacement tasks.
- Strong agents could read visible tests/interfaces and self-correct despite stale context.
- Future fixtures must increase realistic workflow complexity rather than merely hide names.

M16 target shape:

- Multi-node order creation chain: entry service, inventory reservation, payment intent, event publisher, repository/model.
- Phase A old contract is benign/correct: payment intent creation always returns final/confirmed, so publishing `ORDER_CREATED` immediately after successful creation is reasonable.
- Phase B changes a downstream/internal contract: payment intent creation may return a review/pending state; only confirmed orders may publish fulfillment-triggering created events.
- Human task prompt only describes symptoms, e.g. "some orders start fulfillment while payment is still under review; fix creation chain without breaking normal orders". It must not name files/methods/APIs/status constants.
- Visible compile feedback must not expose the hidden semantic oracle. The agent may read current source, but not a visible test that spells out the answer.
- Hidden post-test checks semantic behavior after final.

Admission expectation:

- Stale controls should often preserve old immediate event publication or over-localize the fix.
- SOURCE_ONLY may solve with enough current-source reread.
- TMF_STALE_GATED should withhold old create-order claim and encourage current-source inference without exposing stale content.

### M16 complex order-chain hidden-oracle runner added

Path: `bench/agent_ab/same_version_chain_v1/order_m16_complex_two_phase_runner.py`

Design intent:

- M16 implements the next correction after M15: the fixture is a bounded but multi-file Maven Java order creation chain rather than a one-call-site API replacement.
- Phase A remains benign/correct: payment intent creation is final, so the old chain reserves inventory, creates the intent, marks the order ready, saves, and immediately publishes the fulfillment-triggering created event.
- Phase B mutates the downstream payment intent contract so it may return a review state. Hidden oracle tests require review orders to remain awaiting review and suppress the created event, while confirmed orders keep the normal event path.
- The human task prompt is symptom-only and intentionally does not name files, methods, APIs, or status constants.
- Agent compile feedback runs compile only (`mvn -q -DskipTests compile`). Semantic JUnit tests remain hidden under `.m16_hidden/` and are copied into `src/test` only by the runner's final post-test.
- Arms remain `SOURCE_ONLY`, `PREREAD_STALE_SOURCE`, `STALE_DOC_CONTROL`, and `TMF_STALE_GATED`; the TMF-gated arm reports the stale old create-order claim as withheld rather than injecting stale semantic content.

Verification performed for runner setup only (no sample run): `python3 -m py_compile .../order_m16_complex_two_phase_runner.py` and `python3 .../order_m16_complex_two_phase_runner.py --setup-check`.

### M16 complex order-chain hidden-oracle smoke result

Path: `bench/agent_ab/same_version_chain_v1/order_m16_complex_two_phase_runner.py`

Smoke tag: `order_m16_complex_smoke_r1`

Design check:

- Multi-node bounded Maven fixture: `OrderService`, inventory reservation, payment intent, order repository/model/statuses, event publisher.
- Phase A old behavior is benign/correct: payment intent is always confirmed; order is marked READY and `ORDER_CREATED` is published immediately.
- Phase B changes downstream payment-intent contract so it may return pending review; pending-review orders must be saved as `AWAITING_REVIEW` and must not publish fulfillment-triggering `ORDER_CREATED`.
- Human task is vague and symptom-like; visible tests are hidden from the agent; compile action runs compile only.

Observed R1 summary:

- `SOURCE_ONLY`: failed hidden oracle. It branched on payment status and marked awaiting review, but still published `ORDER_CREATED` unconditionally.
- `PREREAD_STALE_SOURCE`: failed hidden oracle. It branched and returned early for pending review, but placed payment intent before inventory reservation / failed normal confirmed-order expectations.
- `STALE_DOC_CONTROL`: passed hidden oracle. Despite stale doc encouraging immediate publish, it read enough current source and conditionally published only for confirmed payment intent.
- `TMF_STALE_GATED`: failed hidden oracle. It withheld the stale claim and branched correctly on status, but still published `ORDER_CREATED` unconditionally.

Ruling:

- M16 succeeds at increasing task complexity and avoiding visible-oracle leakage.
- M16 R1 is not positive TMF evidence. It is a hard-task calibration: SOURCE/TMF/preread all partially solved but missed one semantic condition, while stale doc happened to solve fully.
- Do not scale R30/R50 from this exact result. First inspect whether the hidden oracle is too strict/ambiguous or whether the TMF arm needs a fair localized reread arm separate from stale-gated withholding.

Important interpretation:

- This is not a TMF core failure proof either. R1 single sample shows high variance on a difficult hidden-oracle task.
- The useful signal is that the new design finally avoids the all-arms-pass ceiling seen in M11-M15.

#### M16 TMF_STALE_GATED failure root-cause note

Root cause of the R1 TMF failure is not TMF stale-gating itself. The stale claim was correctly withheld (`stale_claim_withheld=true`) and the agent did reread current changed nodes including `PaymentIntentService`, `PaymentIntent`, `Order`, `OrderStatus`, and `PaymentIntentStatus`.

The failure was a downstream semantic-inference miss after correct reread:

- The agent inferred that pending-review orders should be marked `AWAITING_REVIEW` and confirmed orders `READY`.
- It did not infer the second hidden invariant: pending-review orders must also suppress the fulfillment-triggering `ORDER_CREATED` event.
- Its patch left `eventPublisher.publish("ORDER_CREATED", order.getId())` unconditional.
- Hidden oracle failed at `pendingReviewDoesNotStartFulfillmentEvent`: fulfillment must not start while payment intent remains under review.

Comparison:

- `STALE_DOC_CONTROL` read essentially the same current files but edited a larger block and guarded both status and event publication, so it passed.
- `SOURCE_ONLY` made the same semantic miss as TMF and also left unconditional publication.

Interpretation:

- This is a hard-task/hidden-oracle semantic miss by the agent, not evidence that TMF freshness failed.
- It also shows that stale-gated withholding alone is insufficient to guarantee success on complex tasks; if product value depends on solving such tasks, a separate `TMF_FRESH_LOCALIZED` / forced localized reread-and-summarize arm should be evaluated.

#### Design correction after M16: `TMF_STALE_GATED` is not full TMF product behavior

M16 revealed a protocol/design flaw in this experiment wave: the `TMF_STALE_GATED` arm measured only stale-claim suppression. It did **not** measure the complete intended TMF product workflow where stale claim detection should trigger localized current-source reread and refreshed semantic-map reconstruction before editing.

Therefore, M16 R1 must not be interpreted as a full-TMF failure. It is a failure of the limited `stale-gated only` variant on a complex hidden-oracle task.

Corrected future protocol must separate at least these arms:

1. `SOURCE_ONLY`: agent sees only current source.
2. `STALE_DOC_CONTROL`: agent sees stale prior orientation/doc plus current source access.
3. `TMF_STALE_GATED_ONLY`: stale claim is withheld, but no refreshed map is provided. This measures stale-safety only.
4. `TMF_REFRESHED_MAP`: stale claim is withheld; the system then forces or supplies a current localized semantic-map refresh from relevant fresh nodes before the agent edits. This is the closest benchmark arm for full TMF product value.

Required `TMF_REFRESHED_MAP` behavior for M16-like tasks:

- Do not show stale facts such as “payment intent is always CONFIRMED”.
- Preserve the locator/scaffold that a stale claim existed around `OrderService.createOrder` and covered creation order plus downstream event publication.
- Force reread or provide fresh summaries for current `OrderService`, `PaymentIntentService`, `PaymentIntent`, `OrderStatus`, and event publisher nodes.
- Require a short refreshed map before editing, including current payment finality and event-publication conditions.

Until this arm exists and is run, this wave only evaluates stale-context safety and calibration hardness, not full TMF product capability.

#### M16 refreshed-map rerun R1 result

Reran M16 four arms after replacing the incomplete `TMF_STALE_GATED` arm with `TMF_REFRESHED_MAP` behavior. New result files:

- JSON: `bench/agent_ab/same_version_chain_v1/results/order_m16_complex_refreshed_map_smoke_r1.json`
- Report: `bench/agent_ab/same_version_chain_v1/results/ORDER_M16_COMPLEX_REFRESHED_MAP_SMOKE_R1_REPORT.md`

Result:

- `SOURCE_ONLY`: hidden oracle failed. It handled `AWAITING_REVIEW` status but left `ORDER_CREATED` unconditional.
- `PREREAD_STALE_SOURCE`: hidden oracle failed with the same unconditional `ORDER_CREATED` issue.
- `STALE_DOC_CONTROL`: passed hidden oracle and emitted final.
- `TMF_REFRESHED_MAP`: passed hidden oracle and made the correct semantic patch, but raw protocol failed because the agent did not send final after success (`no_final_after_success`). Treat as raw fail / task-result pass / semantic-adjusted pass.

`TMF_REFRESHED_MAP` read the current event publisher node in addition to order/payment/status nodes and produced the complete fix:

```java
PaymentIntent paymentIntent = paymentIntentService.createIntent(order);
if (paymentIntent.getStatus() == PaymentIntentStatus.CONFIRMED) {
    order.markReady();
} else {
    order.markAwaitingReview();
}
orderRepository.save(order);
if (paymentIntent.getStatus() == PaymentIntentStatus.CONFIRMED) {
    eventPublisher.publish("ORDER_CREATED", order.getId());
}
```

Interpretation: after correcting the arm to full refreshed-map behavior, TMF recovers the intended semantic fix on M16. The remaining failure is harness/agent final-protocol noise, not task semantics.

#### M16 protocol-noise fix

The first refreshed-map rerun had `TMF_REFRESHED_MAP` hidden-oracle pass but raw fail due to `no_final_after_success`; inspection showed the correct edit occurred at turn 11, then the agent kept reading and exhausted the 16-turn budget before compile/final. This is protocol/budget noise introduced by requiring full refreshed-map reread.

Protocol fix:

- After a successful edit, reject further read/list/search actions and require compile unless another exact edit is needed.
- After successful compile, reject non-final actions and require final.
- Increase default Phase-B turn budget from 16 to 24 to cover the real cost of localized map refresh plus edit/compile/final.

Validation rerun:

- JSON: `bench/agent_ab/same_version_chain_v1/results/order_m16_complex_protocolfix_budget24_r1.json`
- Report: `bench/agent_ab/same_version_chain_v1/results/ORDER_M16_COMPLEX_PROTOCOLFIX_BUDGET24_R1_REPORT.md`

R1 after fix:

- `SOURCE_ONLY`: fail
- `PREREAD_STALE_SOURCE`: fail
- `STALE_DOC_CONTROL`: raw/task/semantic pass
- `TMF_REFRESHED_MAP`: raw/task/semantic pass

The no-final protocol noise is removed for the full-TMF arm.

#### M16 scale-up admission assessment

M16 is suitable for a limited scale-up, but not yet suitable for a formal large R50 as-is.

What M16 is good for:

- It is the first hard hidden-oracle fixture in this wave where `SOURCE_ONLY` and `PREREAD_STALE_SOURCE` fail while complete `TMF_REFRESHED_MAP` passes after protocol correction.
- It tests the intended full TMF product loop better than prior M11-M15: stale map detection, withholding stale facts, localized current-source reread, refreshed semantic-map use, then edit.
- It exposes a real failure mode for source-only agents: fixing the obvious status branch but missing the downstream fulfillment/event side effect.

What M16 cannot prove alone:

- It does not show TMF is better than `STALE_DOC_CONTROL`; stale doc also passes R1. The proper claim is: complete TMF reaches the same correctness while avoiding direct stale-fact injection.
- It is a synthetic single-family order/payment/event fixture, so it cannot prove broad repo/product ROI.
- One R1 is not enough to establish stability; model variance may flip doc/TMF/source behavior.

Issues to fix before any formal expansion:

1. Failure classification is misleading: SOURCE_ONLY/PREREAD hidden-oracle failures are labeled `compile_fail` because post-test failure is collapsed into compile/test failure. Split `compile_tool_fail`, `hidden_oracle_fail`, and `no_final_after_success`.
2. The `STALE_DOC_CONTROL` note is currently strong and may act as a helpful stale workflow map rather than a purely harmful stale claim. This is acceptable as a realistic stale-doc baseline, but conclusions must not overclaim TMF > doc unless repeated runs show a statistically meaningful gap.
3. Full TMF uses more reads/turns (R1: 13 tool calls, 8 source reads, 7 files) than doc control (10 calls, 6 reads, 6 files). Scale-up should report cost/latency alongside pass rate.

Recommended next step:

- Run a small calibration expansion first, e.g. R8 or R12, not R50.
- Keep four arms: `SOURCE_ONLY`, `PREREAD_STALE_SOURCE`, `STALE_DOC_CONTROL`, `TMF_REFRESHED_MAP`.
- Primary metrics: hidden-oracle pass, raw pass, protocol-clean pass, source reads/tool calls, and stale-fact exposure.
- Admit to larger R30/R50 only if source/preread failures persist and TMF refreshed-map remains robust across repeats; report stale-doc separately rather than treating it as a strawman.

Decision: M16 is admitted for limited calibration scale-up after classifier cleanup; it is not admitted as a standalone formal product-proof fixture.


### M16 protocolfix budget24 R8 calibration

Classifier cleanup completed before this run: agent-visible compile action status is now separated from final hidden JUnit/post-test status. Hidden oracle failures are reported as `hidden_oracle_fail`, not misleading `compile_fail`; no compile-action failures occurred in this R8. Raw/task/semantic metrics remain separate.

- JSON: `bench/agent_ab/same_version_chain_v1/results/order_m16_complex_protocolfix_budget24_r8.json`
- Report: `bench/agent_ab/same_version_chain_v1/results/ORDER_M16_COMPLEX_PROTOCOLFIX_BUDGET24_R8_REPORT.md`
- Checks: `python3 -m py_compile bench/agent_ab/same_version_chain_v1/order_m16_complex_two_phase_runner.py` passed; `--setup-check` passed.

Observed R8 summary:
- `SOURCE_ONLY`: raw/task/semantic/post `0/8` / `0/8` / `0/8` / `0/8`; primary={'hidden_oracle_fail': 8}; Phase-B avg tool_calls=10.00, source_reads=5.75; total avg tool_calls=16.00, source_reads=10.25; stale_claim_withheld=0/8.
- `PREREAD_STALE_SOURCE`: raw/task/semantic/post `0/8` / `0/8` / `0/8` / `0/8`; primary={'hidden_oracle_fail': 8}; Phase-B avg tool_calls=11.00, source_reads=6.62; total avg tool_calls=17.00, source_reads=11.12; stale_claim_withheld=0/8.
- `STALE_DOC_CONTROL`: raw/task/semantic/post `8/8` / `8/8` / `8/8` / `8/8`; primary={'pass': 8}; Phase-B avg tool_calls=9.12, source_reads=5.12; total avg tool_calls=15.12, source_reads=10.00; stale_claim_withheld=0/8.
- `TMF_REFRESHED_MAP`: raw/task/semantic/post `6/8` / `6/8` / `6/8` / `6/8`; primary={'pass': 6, 'no_final': 2}; Phase-B avg tool_calls=15.00, source_reads=9.25; total avg tool_calls=21.00, source_reads=13.62; stale_claim_withheld=8/8.

Interpretation: source-only and stale-preread remain stable hidden-oracle failures (8/8 fail each), usually because the agent branches on payment status and marks awaiting review but still misses/splits the hidden fulfillment-event invariant. `STALE_DOC_CONTROL` is surprisingly strong here (8/8 pass), so this calibration still does **not** prove TMF > stale docs. `TMF_REFRESHED_MAP` succeeds semantically/raw on 6/8 and withholds stale claims on 8/8, but has two budget/protocol failures where it never edited/compiled/finalized (`no_final` + `no_compile_action`), showing the refreshed-map arm has higher read/turn cost.

Cost/correctness contrast: `TMF_REFRESHED_MAP` Phase-B average cost was 15.00 tool calls / 9.25 source reads versus `STALE_DOC_CONTROL` 9.12 / 5.12; total including Phase A was 21.00 / 13.62 versus 15.12 / 10.00. Correctness was 6/8 for TMF refreshed-map versus 8/8 for stale doc, and 0/8 for source-only/preread. The safe claim is: full TMF often recovers the hidden invariant while avoiding direct stale-fact injection, but with meaningful overhead and current budget brittleness; stale-doc baseline remains competitive on this synthetic fixture.

Recommendation: run R12 only if the goal is narrow budget/protocol calibration (e.g. increase Phase-B turn budget or improve refresh compression first). Do not run R30/R50 on this exact fixture as positive product evidence until the refreshed-map no-edit/no-compile failures are addressed and/or a fixture is found where stale docs are not already 8/8.
