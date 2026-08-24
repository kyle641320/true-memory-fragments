# R20 Scenario 2 Freeze

## Scenario name
Inline-result vs async-publication confusion

## Why Scenario 1 did not separate arms

Scenario 1 exposed the completion listener too directly. SOURCE_ONLY also found the correct completion-side placement.

## Stronger tunnel-vision trap

Use the misleading local shape of `Segment.refresh(...)`:

```java
ListenableFuture<V> result = loadAsync(...);
if (result.isDone()) {
  return getUninterruptibly(result);
}
return null;
```

A source-only agent seeing this local view may treat `result.isDone()` or the return path as the refresh-completion boundary.

But the actual publication/completion side for async refresh is in `loadAsync(...)`'s listener around:

```java
getAndRecordStats(key, hash, loadingValueReference, loadingFuture);
```

## Arms

### SOURCE_ONLY
Only receives the `refresh(...)` local view and task wording around returned refreshed value.
Expected bug: place hook in `refresh(...)` around `result.isDone()` / `getUninterruptibly(result)`.

### TMF_PROTECT
Receives stale-boundary block and rereads `loadAsync(...)` completion fragment.
Expected correct patch: place hook in the `loadAsync(...)` listener completion path.

## Mechanical oracle

Same oracle as Scenario 1:
- fail if hook is in `refresh(...)`
- pass if hook is in `loadAsync(...)` completion listener

## Status

Frozen as stronger Scenario 2.
