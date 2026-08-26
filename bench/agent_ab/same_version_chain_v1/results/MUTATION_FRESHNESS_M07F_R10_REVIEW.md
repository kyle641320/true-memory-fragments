# Mutation Freshness M07f R10 Review

## Question

M07f tests a more product-like executor loop proposed after M07e:

- initial prompt contains all task/evidence semantics;
- later prompts are generic continue nudges only;
- no later prompt may add new anchors, code locations, or evidence;
- runner evaluates workspace state with deterministic post-test after each turn;
- primary metric is `task_result_pass`, while `raw_pass` remains final-protocol completion.

This reflects the expectation that an executor should continue until the task has a verifiable result, and that a human/product evaluator can distinguish “workspace is correct” from “agent failed to send final.”

## Runner configuration

```text
mutation_m07f_runner.py \
  --repeats 10 \
  --final-gate hard \
  --result-loop \
  --max-turns 5 \
  --max-no-progress 2 \
  --tag mutation_freshness_m07f_hard_r10
```

Continuation prompt after the initial turn is generic only, but includes the action schema and prior tool history. This preserves tool protocol without injecting new semantic evidence.

## Result

```json
{
  "SOURCE_ONLY": {
    "raw_pass": "7/10",
    "task_result_pass": "10/10",
    "wrong_wrapper_site": "0/10"
  },
  "STALE_DOC_CONTROL": {
    "raw_pass": "5/10",
    "task_result_pass": "10/10",
    "wrong_wrapper_site": "0/10"
  },
  "TMF_STALE_GATED": {
    "raw_pass": "4/10",
    "task_result_pass": "9/10",
    "stale_claim_withheld": "10/10",
    "wrong_wrapper_site": "0/10"
  }
}
```

## Interpretation

1. `task_result_pass` is much higher than `raw_pass`, confirming that final-protocol completion is too strict for product-style evaluation.
2. In result-loop mode, validation/continue behavior corrected the stale-doc arm: `STALE_DOC_CONTROL` reached task result in `10/10` and wrong-wrapper was `0/10`. This is expected; M07f measures executor-with-validation, not pure stale-doc harm.
3. TMF still preserves the key freshness safety properties:
   - stale claim withheld `10/10`;
   - wrong-wrapper placement `0/10`.
4. TMF task-result was `9/10`, with the sole failure caused by tool-protocol amnesia rather than freshness/semantic failure.

## TMF non-result root cause

The one TMF task-result failure is `M07__TMF_STALE_GATED__r10.raw.json`.

Root cause:

- freshness check worked: `fresh=false`, stale claim withheld;
- no wrong-wrapper edit was made;
- no diff was produced;
- the agent read the current source, identified the correct insertion point in prose, but then stopped emitting JSON tool actions and repeatedly claimed tools were unavailable.

Representative model text:

```text
I found the precise insertion point. I’ll apply the one-line change and verify it with compilation and tests.
I couldn’t modify the workspace because the edit/compile/test tool calls are not available in the current turn.
```

This should be classified as tool-protocol amnesia / invalid-action noise, not a TMF semantic failure.

## Relationship to M07e

- M07e `final_gate=off` remains the best freshness-only A/B: stale docs caused wrong-wrapper `13/20`, TMF had withheld `20/20` and wrong-wrapper `0/20`.
- M07e/M07f hard/result-loop variants are product/executor evidence: deterministic validation and continuation can correct stale-doc wrong placements, so stale-doc harm is no longer isolated.
- M07f adds the important evaluation principle: task-result pass should be primary when the system is designed to continue until a verifiable result exists; raw/final-protocol pass should be secondary.

## Next improvement

If we continue M07f, the next issue is not TMF freshness; it is tool-protocol robustness. Options:

1. Add a stricter continuation prompt that says “respond only with JSON actions” (generic protocol reminder, no semantic hint).
2. Treat prose containing an exact code block as invalid and continue with a protocol-only nudge.
3. Add a structured insertion action to reduce exact-text brittleness if measuring product execution rather than edit-protocol stress.
