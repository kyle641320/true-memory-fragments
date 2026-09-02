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

## Push-based subagent rerun (2026-09-02 16:12)

Because the CLI runner suffered provider/transport timeouts, RV3F01 was rerun through native push-based subagents. Result:

- `SOURCE_ONLY`: completed and produced a valid answer. It blocked the stale `VisitBooked` note, identified current `VisitScheduled`, cited producer/listener/consumer files, and provided `METRICS_JSON` with `stale_blocked=true`. Evidence: `raw/subagent_RV3F01_SOURCE_ONLY.answer.txt`.
- `TMF_MAP`: failed before final answer. It did execute the TMF freshness command and surfaced stale `VisitBooked`-relevant claims, but the subagent turn aborted before producing the required final response and metrics. Evidence: `raw/subagent_RV3F01_TMF_MAP.abort.json`.

Scoring: `results/subagent_eval.json` records `valid_pairs=0`, `superiority_claim=false`, verdict `SUBAGENT_PAIR_INCOMPLETE__SOURCE_ONLY_VALID__TMF_MAP_ABORTED`. This is still a runtime/harness blocker, not evidence for or against TMF semantic value.

## TMF_MAP minimal retry completed (2026-09-02 16:47)

To avoid rerunning the already-valid SOURCE_ONLY answer, only the missing TMF arm was retried with a minimal prompt: one freshness check plus at most four source files and no broad repository search.

Result: valid pair is now available by pairing the previous valid `SOURCE_ONLY` subagent answer with `TMF_MAP_MIN_RETRY`.

- `SOURCE_ONLY`: valid and correct; blocked stale `VisitBooked`, identified `VisitScheduled`; metrics: 6 source files, 413 source lines, 4 tool calls.
- `TMF_MAP_MIN_RETRY`: valid and correct; freshness check blocked stale `VisitBooked`, then reread only four source files; metrics: 4 source files, 218 source lines, 2 tool calls.

Scoring: both arms were correct, so there is no correctness superiority claim. Efficiency observation: TMF_MAP_MIN_RETRY reached the same required conclusion with fewer reread lines and fewer tool calls under the constrained retry protocol. Evidence: `results/subagent_min_retry_eval.json`, `raw/subagent_RV3F01_SOURCE_ONLY.answer.txt`, `raw/subagent_RV3F01_TMF_MAP_MIN_RETRY.answer.txt`.
