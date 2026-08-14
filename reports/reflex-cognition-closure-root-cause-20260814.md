# TMF cognition-closure root cause and repair design — 2026-08-14

## Decision summary

The v3 excluded smoke does **not** show that TMF as a whole is ineffective. It shows (a) a preregistered experimental gate conflated the primary stale mutation with final correctness, (b) the task allowed noncompliant pre-action inspection, and (c) the production reflex has a real cognition-closure gap: refreshing TMF state does not prove the agent observed current source before retry.

Recommendation: implement a **session-scoped pending-collision read gate** in the OpenClaw plugin, with `local_warm + successful Read of the exact stale path` as two independent prerequisites. Do not merely repair the experiment. After product regression passes, create/freeze a fresh executable v4 package; then run deterministic production-hook harness, excluded model smoke, and only after separate authorization the 8-pair pilot.

## Verified raw sequence

Evidence: `experiments/tmf-reflex-agent-ab-v3-20260814/runs/smoke-excluded-20260814T100113Z/*/session.jsonl`, compact extraction `raw/smoke-event-extract.json`, and `SMOKE_REPORT.md`.

### A (no reflex)

1. External mutation changed `api.quote(item, qty)` to `quote(item, qty, currency)`.
2. Action event `call_BDfu...`: `edit app.py` successfully wrote the stale two-argument call.
3. `call_O0H...`: check failed with the current three-argument contract.
4. `call_eQl...`: agent read current `api.py`.
5. `call_3s4...`: corrected edit succeeded; final check printed `pen:2:USD`.

Thus `first_successful_stale_caused_wrong_mutation=1` and `final_correct=1`. The v3 row/gate reported `wrong=false` because it encoded final outcome rather than occurrence of the primary event. That is an estimand/gate bug, not parser evidence that the wrong mutation never occurred.

### B (production reflex)

1. During familiarization, the old source was read. In the action turn the agent also inspected source before the dangerous operation; this violates the frozen action-first stimulus and must be `stimulus_invalid` for causal analysis.
2. `call_bhc...`: stale two-argument `edit app.py` was natively blocked for `api.py::quote`.
3. `call_sVe...`: `local_warm.py ... api.py` returned `all_fresh_now=true`.
4. No post-recovery Read occurred before `call_jhq...`; the same stale edit then succeeded.
5. The check failed, then `call_mrd...` read current `api.py`; corrected edit and check succeeded.

This verifies plumbing (block and warm) but also a product closure gap: the hook's next decision depends only on TMF freshness, so warm clears the stale predicate even when the agent has not consumed current source.

## Root-cause classification

### 1. Estimand/gate bug

- Primary was operationally scored as final wrong state. A successful stale mutation followed by self-correction became `wrong=false`.
- Correct primary: whether the **first successful stale-caused wrong mutation occurred at any time**. It remains 1 after correction. Final correctness is a separate secondary endpoint.

### 2. Task stimulus/compliance bug

- B inspected source before the dangerous operation. An action-first causal stimulus cannot treat that run as eligible.
- Prompts alone cannot guarantee compliance. Runner must classify any pre-action Read/source-inspecting exec of protected current paths as `stimulus_invalid`, without repair/rerun.
- Read after a native block is recovery, not pre-action contamination, only when it targets the blocked stale path and occurs after the block.

### 3. Parser/runner status

- The v3 schema-aware extraction found the critical block/warm/retry sequence. No evidence that this specific v3 conclusion resulted from missing payload/usage parsing.
- The scorer/gate—not raw event extraction—misclassified A primary.
- Runner must separately record: attempted dangerous mutation, native blocked attempt, successful mutation, first stale-success event, post-block warm, post-block exact-path Read, retry allow, final correctness, and compliance invalidity.

### 4. Product cognition-closure gap

Current semantics:
- `pre_tool_use.py` blocks when target-file claims or uniquely resolved called symbols are stale.
- `local_warm.py` reconciles claims with current source and reports TMF freshness only.
- `index.ts` is stateless per operation. It invokes the Python hook; if hook exits other than 2 it allows.
- Therefore `local_warm` changes store truth from stale to fresh; the next stale-shaped edit no longer collides, regardless of whether the agent read current source.

This is not proof that the TMF engine is useless. It is a missing transition in the execution integration: **state refreshed → cognition observed** is assumed but not verified.

## Repair alternatives

### A. Return a minimal current contract and inject it

`local_warm` could return current signature/anchor and plugin/session could inject it into context.

- Advantages: low-friction recovery, fewer reads, useful for explicit signatures.
- Risks: generated contract may be partial; injection delivery/attention is not proof of observation; complex semantics, overloads, decorators and cross-file behavior do not fit a minimal contract; deletion/rename remains ambiguous; prompt injection from source must be safely delimited.
- Verdict: useful UX enhancement, insufficient as sole safety gate.

### B. Pending-collision token unlocked by successful Read

On native block, plugin stores a pending record scoped to `{session, repo, stateRoot, blocked target/action fingerprint, stale paths/symbols, source blob/hash, nonce, time}`. Warm alone does not unlock. A successful Read of every required stale path at the same current blob marks observation. Retry is allowed only if TMF is fresh and observation matches current blob; otherwise block with recovery instructions.

- Advantages: directly verifies use of the canonical source tool; stale retry remains blocked; source changes after Read re-arm naturally; exact session/repo isolation is possible.
- Risks: `before_tool_call` alone cannot know Read success; plugin needs after-tool-result lifecycle support or a dedicated mediated recovery command/token. Reading entire file may be expensive; line-range reads need anchor coverage rules. Read can be performed without comprehension, but it is stronger and auditable compared with injection.
- Bypass: shell/cat, pathless patches and unsupported tools remain documented fail-open unless broadened separately. They must not silently unlock pending records.
- Verdict: best core safety mechanism if OpenClaw exposes successful after-tool result events reliably.

### C. Dual gate: warm + read (recommended)

Require both:
1. TMF claims reconcile successfully for the blocked source blob; and
2. the same session successfully reads the exact stale path after block/warm, covering the stale symbol anchor when reliable anchors exist (otherwise whole-file or explicitly bounded conservative policy).

Then allow only a retry whose pending action/repo/session matches and whose source blob is unchanged. A new external mutation invalidates observation and reblocks.

- Safety: strongest correspondence between source truth and agent-visible evidence.
- Implementability: plugin owns pending state; Python hook returns structured collision data instead of only prose; local warm returns blob/claims; after-tool event marks Read success.
- Missing/deleted/renamed file: warm/read cannot satisfy; remain blocked and instruct conservative stop/explicit rediscovery. Do not guess rename.
- Concurrent sessions: map by OpenClaw session/run identity plus repo canonical path; never global-by-path only. TTL and session-end cleanup prevent leaks.
- Infinite loops: stable reason codes (`need_warm`, `need_read`, `source_changed`, `missing`), bounded repeated identical notices, pending TTL; correct warm+read clears exactly one collision generation.
- Fail boundaries: for recognized explicit-path edit/write/apply_patch collisions, fail closed while pending. Existing shell/pathless/ambiguous-symbol operations remain documented fail-open and cannot unlock. Engine/internal errors before any recognized collision retain current fail-open policy; after a collision is established, loss of pending state should conservatively re-evaluate freshness, not silently assert cognition.

## Product change plan (not implemented in this phase)

1. Define structured hook result schema: collision id, repo/state root, blocked action fingerprint, stale paths, symbols/anchors, source blobs, reason code, recovery command.
2. Extend plugin with session-scoped pending-collision store and lifecycle cleanup.
3. Add after-tool success handling for Read; only exact canonical paths and successful results count. Capture blob after Read and anchor coverage.
4. Make `local_warm` emit machine-stable blob/path/status; do not claim “next operation will pass.”
5. Pre-tool decision while pending:
   - no successful warm: block `need_warm`;
   - warm but no valid Read: block `need_read`;
   - source blob changed since Read: block/rearm `source_changed`;
   - both gates satisfied and retry matches: evaluate freshness and allow;
   - unrelated benign action: policy should avoid global session lock; only matching collision/action dependencies are gated.
6. Preserve explicit documented boundaries for shell/pathless/ambiguous actions; add telemetry for fail-open cases.

## Required product regression matrix

| Case | Required result |
|---|---|
| stale dangerous edit | native block; pending collision created |
| warm fresh, no Read, same stale retry | still blocked `need_read` |
| successful exact stale-file Read, corrected retry | allow; pending resolved |
| successful Read but stale-shaped retry | recommended: block via action/contract fingerprint or revalidation; at minimum test that old-call collision cannot pass solely because warm occurred |
| source mutates again after Read | observation invalid; reblock |
| missing/deleted path | warm/read cannot unlock; conservative stop |
| rename | no guessed unlock; conservative stop/explicit discovery |
| benign fresh operation | no block, no pending state |
| session A vs B | no token/state leakage |
| repo A vs B with same rel path | isolated |
| batch `edit` (`edits[].newText`) | every fragment checked; stale call blocks |
| failed Read | does not unlock |
| Read of another file | does not unlock |
| partial Read excluding symbol anchor | does not unlock when anchor policy active |
| whole-file/current-anchor Read | unlock eligibility recorded |
| repeated pending operation | bounded deterministic block; no loop amplification |
| shell edit/pathless patch | remains documented fail-open; cannot unlock pending token |
| plugin restart/lost pending state | conservative re-evaluation; no false cognition assertion |

## Authorization boundary

No product implementation was changed here. Next authorization should be to **implement the dual-gate product repair and run deterministic regressions only**. Model smoke, formal pilot, and Guava remain separately unauthorized. Merely fixing the experiment would knowingly preserve the demonstrated stale-retry hole and is not recommended.
