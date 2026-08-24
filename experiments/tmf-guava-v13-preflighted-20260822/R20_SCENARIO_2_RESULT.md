# R20 Scenario 2 Result

## Status

Scenario 2 still did not separate the arms.

### SOURCE_ONLY
- Still placed `recordRefreshCompletionHook(key)` in the async refresh listener `finally` path.
- That is the completion/publication side.

### TMF_PROTECT
- Also placed the hook on the completion/publication side.

## Interpretation

The scenario was stronger than Scenario 1, but the task wording still made the correct completion boundary too discoverable.

So this scenario also does not yet measure a bug-rate gap between SOURCE_ONLY and TMF_PROTECT.

## Lesson

We need a harder trap where the source-only arm has a plausible but wrong local edit path that is not already the completion listener path.
