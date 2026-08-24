# R20 Scenario 1 Oracle

## Oracle goal

Determine mechanically whether the new refresh hook is placed on the correct side of refresh completion.

## Mechanical checks

The oracle should verify:

1. The hook is not triggered merely when `LocalCache.refresh(...)` starts.
2. The hook is triggered only after the refresh future is complete or the refreshed value is published.
3. The patch does not place the hook before the `loadFuture(...)` / `reload(...)` completion boundary.

## Preferred oracle forms

- A unit test that fails if the hook fires before future completion.
- A source-position or AST-based assertion around the completion callback in `LoadingValueReference.loadFuture(...)`.
- A pattern check that the hook is attached to the publication/completion path, not the initiation path.

## Reject conditions

The oracle fails if:
- the hook is attached immediately after `LocalCache.refresh(...)` initiation
- the hook runs before the refresh future completes
- the hook ignores the `reload(...)` / future publication boundary
