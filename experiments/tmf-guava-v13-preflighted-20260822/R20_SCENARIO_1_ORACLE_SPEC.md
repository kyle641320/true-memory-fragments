# R20 Scenario 1 Mechanical Oracle Spec

## Oracle question

Did the new refresh-completion hook fire only after refresh completion/publication, and not at refresh initiation?

## What must be checked

1. The hook is attached to the completion/publication path, not the initiation path.
2. The hook does not fire when `LocalCache.refresh(...)` merely starts the refresh.
3. The hook does fire after the refresh future completes or the refreshed value is published.
4. The patch respects the existing contract around `reload(...)` and the load future.

## Mechanical validation options

Preferred order:

1. Unit test asserting the hook callback is observed only after the future completes.
2. Source-position assertion proving the hook is registered after the completion callback in `LoadingValueReference.loadFuture(...)`.
3. Pattern assertion that the hook is not placed on the top-level `LocalCache.refresh(...)` initiation path.

## Oracle pass condition

- completion/publication path contains the hook
- initiation path does not
- unit test or mechanical check passes

## Oracle fail condition

- hook is present at initiation only
- hook is before future completion
- hook ignores the refresh publication boundary
