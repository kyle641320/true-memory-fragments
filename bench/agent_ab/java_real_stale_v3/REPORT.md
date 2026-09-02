# Java Real Stale A/B v3 Smoke — 2026-09-02

Verdict: **AGENT_PAIR_NOT_COMPLETED__DETERMINISTIC_TASK_VALIDATED**.

This is a frozen small smoke for a discriminating real-repo stale-context task, not a broad causal claim.

## What was built

- Real repository copy: `/root/.openclaw/workspace/experiments/tmf-java-real-v3/petclinic-event-type`.
- Base: Petclinic modulith `58c3310e36c7d827959df6af4d64bdeb8d81f1ea`.
- Pre-mutation `.tmf` store was warmed in the repo-local store.
- Mutation commit renames the old visit-booking event contract from `VisitBooked` to `VisitScheduled` across producer and vet consumers.
- Prompts were frozen for one paired task: `RV3F01_SOURCE_ONLY` vs `RV3F01_TMF_MAP`.

## Deterministic task validation

`results/deterministic_eval.json` validates that this is a real stale task:

- Old claims mentioning `VisitBooked`: 19.
- Event-contract relevant old claims: 5.
- Event-contract relevant stale old claims: 5/5.
- Current event type in source: `VisitScheduled`.
- Current producer/listener/consumer source files contain no `VisitBooked` references.
- Deterministic verdict: `DETERMINISTIC_STALE_TASK_VALID`.

Relevant stale old claims include the `VisitBooked` declaration, event publish/listen edges, and Java `uses_type` edges for listener/assignment consumers.

## Agent execution attempt

`run_agents.py` attempted the paired native OpenClaw agent run. The first `SOURCE_ONLY` arm exceeded the configured transport timeout (`openclaw agent --timeout 240`, subprocess timeout 285s) before producing a usable payload. Per protocol, this is a transport/runtime timeout, not a scored SOURCE_ONLY failure. The pair is therefore incomplete and no A/B superiority claim is made from this attempt.

## Interpretation

This advances the real-repo stale A/B work by producing a bounded, source-validated discriminating fixture/protocol. It does **not** yet prove real-repo stale-context superiority, because the paired agent run did not complete.

Next step: rerun with a more reliable runner/session strategy or smaller prompt/tool budget, then score only valid paired payloads.

## Compact-prompt rerun (2026-09-02 15:51)

The prompts were shortened and `run_agents.py` was made timeout-safe. The rerun still did not produce a valid pair:

- `RV3F01_SOURCE_ONLY`: subprocess timeout, exit 124 after ~285s, empty payload.
- `RV3F01_TMF_MAP`: CLI exit 0 after ~262s, but agent JSON reported `status=timeout`, `summary=aborted`, `stopReason=rpc`, `timeoutPhase=provider`; payload was only the standard timeout message.

`evaluate_agents.py` treats both as invalid transport, because valid payloads require CLI transport success **and** JSON `status=ok` / `summary=completed`. Current valid pairs: 0. No A/B superiority claim is made.
