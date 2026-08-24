# R20 Scenario 1 Mutation

## Mutation goal

Make refresh completion timing matter so that a source-only edit is likely to place the new hook on the wrong side of the refresh boundary.

## Mutation family

Use an asynchronous refresh path in the Guava cache fixture.

Concrete shape:
- keep the `CacheBuilder.refreshAfterWrite(...)` contract intact
- use a `CacheLoader` whose `reload(...)` path is not guaranteed to complete inline
- ensure the refresh result is published only when the returned future completes

## Why this is a trap

A source-only agent reading only the A-side refresh entry point may assume the refresh hook can fire as soon as `LocalCache.refresh(...)` starts.

But the correct placement depends on the future completion and publication path in `LoadingValueReference.loadFuture(...)` / `CacheLoader.reload(...)`.

So if the agent ignores the C/D boundary, it is likely to add the hook too early.

## Mutation frozen rule

Do not change the mutation after the run starts.

If the mutation does not force completion timing to matter, it is invalid as a tunnel-vision test.
