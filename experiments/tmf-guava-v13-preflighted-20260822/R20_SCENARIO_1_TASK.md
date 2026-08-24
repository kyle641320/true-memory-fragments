# R20 Scenario 1 Task Card

## Scenario name
Refresh completion hook placement

## Fixture chain
- A: `com.google.common.cache.CacheBuilder`
- B: `com.google.common.cache.LocalCache`
- C: `com.google.common.cache.LoadingValueReference`
- D: `com.google.common.cache.CacheLoader`
- E: `com.google.common.cache.LoadingCache`

## Why this is a tunnel-vision trap

At t0, an agent looking only at `CacheBuilder.refreshAfterWrite(...)` and the top-level refresh path can easily assume a refresh is effectively complete when `LocalCache.refresh(...)` returns.

But the real completion point depends on `LoadingValueReference.loadFuture(...)` and `CacheLoader.reload(...)`:
- synchronous reload may complete inline
- asynchronous reload may complete later through the returned future

So an A-only mental model can place a new hook on the wrong side of the refresh boundary.

## Mutation

Use a refresh boundary mutation that makes completion timing matter:
- keep the top-level `refreshAfterWrite` path intact
- vary the `CacheLoader.reload(...)` behavior so that completion is not guaranteed to be inline
- the mutation must make a naive A-only placement of the new hook wrong

## Modification task

Add a new refresh-completion hook in the cache refresh path.

The hook should be placed so that it fires only when the refresh result is actually complete/published, not merely when `LocalCache.refresh(...)` has initiated the refresh.

The task must be phrased so that:
- SOURCE_ONLY may place the hook too early, based only on A-side reading
- TMF_PROTECT is forced to reread the boundary in C/D and therefore places the hook on the correct side of refresh completion

## Mechanical oracle

The oracle must verify that the hook fires at the correct phase:
- not merely after refresh initiation
- but after refresh completion / publication according to the boundary contract

Mechanical checks may include:
- source-position assertions around the future completion callback
- unit tests proving the hook fires only after the refresh future is resolved
- pattern checks around `loadAsync`, `loadFuture`, and `reload`

## Success condition

TMF_PROTECT should produce fewer oracle violations than SOURCE_ONLY.

If TMF is slightly more expensive but produces fewer bugs, that is still a win.
