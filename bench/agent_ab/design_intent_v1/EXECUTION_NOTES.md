# design_intent_v1 EXECUTION_NOTES

Date: 2026-08-20 (Asia/Shanghai)
Repo: `/root/.openclaw/workspace/worktrees/tmf-java-nodes-step0`
Subject: **real Guava EventBus source** from `/root/.openclaw/workspace/worktrees/guava/guava/src/com/google/common/eventbus`.
Guava commit observed: `f1ad7da4942e8658a27ce20e0c1082c063650db8`.
Frozen TMF mechanism constraint: base commit `45ab3e4` treated as the frozen mechanism reference; this experiment did not modify TMF engine code.

## Clarification applied

Requester clarified that the experiment should use Guava EventBus directly as the target, not a self-invented toy fixture. The harness now copies the real EventBus package source from the local Guava checkout into per-task base/mutated trees. Mutations are applied to real Guava source files only.

## Implemented components

- `tasks.json`
  - Defines three real Guava EventBus scenarios:
    - B01 / P0: `EventBus.post -> SubscriberRegistry.getSubscribers -> Dispatcher.dispatch -> Subscriber.dispatchEvent -> invokeSubscriberMethod`; mutate `Dispatcher.ImmediateDispatcher` from fan-out to first-subscriber-only.
    - B02 / P1: `EventBus.post -> Dispatcher.dispatch -> Subscriber.dispatchEvent -> Executor.execute -> invokeSubscriberMethod`; rename `Subscriber.dispatchEvent` without updating dispatcher callers.
    - B03 / P2: `AsyncEventBus -> EventBus.post -> LegacyAsyncDispatcher.dispatch -> Subscriber.dispatchEvent -> Executor.execute`; diagnose async boundary movement.
  - Each scenario has Phase A question, Phase B mutation, Phase B question, anchored chain, design-intent golden/rubric keywords.

- `make_fixtures.py`
  - Copies real Guava EventBus package sources from `/root/.openclaw/workspace/worktrees/guava/guava/src/com/google/common/eventbus`.
  - Builds `fixtures/<task>/base` and `fixtures/<task>/mutated`.
  - Applies unique string-anchor mutations.
  - Writes `fixtures/MANIFEST.json` with source path and SHA-256s.

- `runner.py`
  - Phase A materialises source-bound `design_rationale` claims; Phase A answer is discarded.
  - Phase B runs three arms:
    - `SOURCE_ONLY`: real Guava base source, no memory.
    - `TMF_STALE`: real Guava mutated source, stale design claim withheld by freshness gate.
    - `TMF_FRESH`: real Guava base source, fresh source-bound design claim injected.
  - Supports `read_range` to measure localized stale rereads more fairly than full-file reads.
  - Records freshness, source read bytes, valid final status, machine design score, chain completeness, stale trust errors, and javac check.

- `validate.py`
  - Checks fixtures, mutation uniqueness/application, changed SHA-256s, and mutation coverage of claim anchors.
  - Writes `preflight.json`.
  - Supports `--write-freeze` / `--verify-freeze`.

- `score.py`
  - Generates human-audit templates.

## Commands run

```bash
python3 bench/agent_ab/design_intent_v1/make_fixtures.py
python3 bench/agent_ab/design_intent_v1/validate.py --write-freeze
python3 bench/agent_ab/design_intent_v1/runner.py --smoke --tag smoke-n2-real-guava
python3 bench/agent_ab/design_intent_v1/score.py bench/agent_ab/design_intent_v1/results/smoke-n2-real-guava.json
```

## Smoke run result: real Guava EventBus

Smoke N=2 used B01 and B02.

High-level outcome: **FAILED mandatory smoke gates; stopped after smoke.**

Observed positives:

- Staleness detection worked for both stale arms: 2/2 = 100%.
- No stale-trust errors were detected: 0/2.
- All six arms produced valid final answers after adding `read_range`.
- All arms scored machine design score 2, indicating the real Guava code/comments make the design intent discoverable from source as well as from TMF.

Observed failures:

- `TMF_STALE` reread bytes were not <50% of `SOURCE_ONLY` in either task.
  - B01: SOURCE_ONLY 14,821 bytes; TMF_STALE 13,995 bytes (~94%).
  - B02: SOURCE_ONLY 12,456 bytes; TMF_STALE 10,321 bytes (~83%).
- `TMF_FRESH` did not beat `SOURCE_ONLY` on chain completeness; both were already high.
- SOURCE_ONLY scored 2 on both tasks, violating the original expected separation (`SOURCE_ONLY < 1.0`).

## Failure mode

This real-source smoke shows a different failure mode from the initial coarse fixture smoke:

1. The staleness gate is working.
2. Real Guava EventBus has strong in-source documentation/comments, so SOURCE_ONLY can recover design intent without TMF.
3. `read_range` improved validity but not enough to satisfy the stale reread <50% gate because agents still read multiple chain files to answer confidently.
4. The current tasks are too easy for SOURCE_ONLY and therefore do not isolate TMF's design-intent advantage.

## Stop decision

Per constraint, because smoke failed, no full B01/B02/B03 × 3-arm run was executed.

## Artifacts

- Preflight: `preflight.json`
- Freeze manifest: `FROZEN.sha256`
- Fixture manifest: `fixtures/MANIFEST.json`
- Real Guava smoke JSON: `results/smoke-n2-real-guava.json`
- Human audit template: `results/smoke-n2-real-guava.human_audit.md`
- Smoke report: `results/SMOKE_REPORT.md`

## Recommended next revision

Before another smoke, revise scenarios so SOURCE_ONLY cannot answer from local comments alone:

1. Ask Phase B questions that require connecting a changed middle node to a non-obvious upstream edit/test, not just explaining existing design.
2. Use mutation/test tasks that punish tunnel vision, e.g. modifying `EventBus.post` after `Dispatcher` or `Subscriber` changed.
3. Keep real Guava source, but score behavioral correctness or patch correctness in addition to prose design intent.
4. Keep `read_range`, but add symbol-focused anchors from TMF so stale reread can realistically stay below 50%.

## Stop update from requester session

The current A/B experiment implementation is stopped. See `STOP_DECISION.md`. The main conclusion is that TMF call-chain continuity/tunnel-vision prevention is not well matched to this standard automated A/B protocol; prefer a case study or explicit documentation of validation limits. No further full runs should be executed without a revised direction.
