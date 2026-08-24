# R20 Scenario 3 SOURCE_ONLY Result

## Patch placement

SOURCE_ONLY placed `recordRefreshCompletionHook(key)` in `Segment.refresh(...)` on the local return path:

```java
if (result.isDone()) {
  try {
    V refreshed = getUninterruptibly(result);
    recordRefreshCompletionHook(key);
    return refreshed;
  } catch (Throwable t) {
    ...
  }
}
```

## Oracle interpretation

This is the wrong side of the boundary for the experiment:
- hook is in the local refresh return path
- not in the `loadAsync(...)` completion listener path

So SOURCE_ONLY exhibited the intended tunnel-vision-shaped bug.
