# Mutation Freshness M07f Design — Result-Oriented Continue Loop

## Motivation

M07e exposed an important evaluator issue: `raw_pass` conflates two different properties:

1. Whether the workspace reached a verifiable task result.
2. Whether the agent completed final-message protocol (`test` + `final`).

For product-like execution, the primary question should be: did the task get done? A human supervisor can see when the workspace has a correct result; missing `final` should be tracked separately as protocol completion noise.

## Proposed M07f semantics

M07f should model a realistic executor loop:

- The initial prompt contains all semantic task/evidence condition information.
- Later prompts may only be generic continuations, e.g. “Continue; the task is not complete yet.”
- Later prompts must not inject new task-specific facts, anchors, code locations, or evidence.
- The evaluator should run deterministic post-tests after each turn and stop once the workspace has a verifiable result.
- Scoring separates:
  - `task_result_pass`: workspace reached verifiable correct result.
  - `raw/final_protocol_pass`: agent completed final protocol.
  - `wrong_wrapper_site`: stale semantic failure mode.
  - `withheld`: TMF freshness gate behavior.

## Implementation notes

A draft runner exists at:

`bench/agent_ab/same_version_chain_v1/mutation_m07f_runner.py`

It copies M07e and adds:

- `--result-loop`
- post-turn `deterministic_test(root)` auto-stop when task result passes
- generic continue nudges only after initial prompt
- `task_result_pass` metric

Important correction from smoke testing:

- A continuation prompt that only says “Continue” without the action schema measures tool-protocol amnesia rather than task completion.
- Keeping the action schema visible is acceptable because it adds no new semantic task evidence; it only preserves the interaction protocol.

## Smoke finding

Initial M07f smoke was intentionally stopped because the generic continue loop can become slow/noisy if the agent enters repeated failed-anchor attempts. This should not be used as headline data yet.

Before R20/R30 rerun, the runner needs one of these controls:

1. Per-turn broker timeout / total per-run timeout.
2. A max consecutive no-progress budget, e.g. stop after N turns with no successful edit and no post-test improvement.
3. Optional structured edit affordance or anchor-based patch action to reduce exact-text brittleness, if the goal is product execution rather than exact-edit protocol stress.

## Recommended next experiment

Run M07f only after adding no-progress controls:

- `--result-loop`
- `--final-gate hard`
- `--max-no-progress 4` or equivalent
- report `task_result_pass` as primary
- report `raw/final_protocol_pass` as secondary

Expected headline if stable:

- TMF should preserve `withheld=20/20` and `wrong_wrapper_site=0/20`.
- With result-loop scoring, correct diffs that lack `final` should count as task-result pass.
- Stale-doc control may improve under validation/continue loop, which is expected; the freshness-only contrast remains M07e off-gate.
