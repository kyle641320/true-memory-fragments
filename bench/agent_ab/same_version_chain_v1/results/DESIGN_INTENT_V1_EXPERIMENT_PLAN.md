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
