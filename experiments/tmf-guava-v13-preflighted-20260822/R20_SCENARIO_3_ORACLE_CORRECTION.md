# R20 Scenario 3 Oracle Correction Note

## What happened

During Scenario 3 review, an intermediate oracle run was applied to reconstructed full-file artifacts instead of judging the patch-local placement directly.

That produced a misleading `completion_path` result for SOURCE_ONLY.

## Why it was wrong

The SOURCE_ONLY patch itself clearly placed the hook in the local `Segment.refresh(...)` return path:

```java
V refreshed = getUninterruptibly(result);
recordRefreshCompletionHook(key);
return refreshed;
```

That is the stale/local path, not the async completion listener path.

The reconstructed full-file oracle run did not preserve the patch-local context as the authoritative evidence.

## Correct ground truth

- SOURCE_ONLY: FAIL — hook in `Segment.refresh(...)` local return path.
- TMF_PROTECT: PASS — hook in `LocalCache.Segment.loadAsync(...)` listener/completion path.

## Protocol fix

For future SOURCE_ONLY vs TMF_PROTECT placement experiments:

1. Judge direct patch placement first.
2. Only use reconstructed full files as secondary sanity checks.
3. If reconstructed-file oracle conflicts with direct patch placement, inspect the reconstruction before trusting the oracle output.
4. Store the decisive diff snippet in the result report.
