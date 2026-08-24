# R20 Scenario 1 Result

## Status

Both arms produced completion-side placements for the refresh-completion hook.

### SOURCE_ONLY
- Patch placed `recordRefreshCompletionHook(key)` inside the `loadAsync(...)` completion listener.
- This is a completion/publication-side placement.
- It is not the expected tunnel-vision failure shape.

### TMF_PROTECT
- Patch also placed the hook inside the completion listener.
- This matches the expected correct placement.

## Interpretation

This first scenario does not separate bug rate between arms.
It is therefore not yet a successful tunnel-vision discrimination test.

What happened:
- the task and oracle were correct enough to detect completion-side placement
- but the SOURCE_ONLY arm still learned the completion boundary and produced the correct placement

## Next diagnosis

The next scenario needs a stronger tunnel-vision trap, where:
- the A-side view makes the wrong placement look natural
- the C-side reread actually changes the patch decision
- the source-only arm is more likely to misplace the hook

## Core lesson

The oracle works, but Scenario 1 did not create enough asymmetry between SOURCE_ONLY and TMF_PROTECT.
