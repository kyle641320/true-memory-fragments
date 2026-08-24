# R20 Scenario 3 Result

## Scenario

Stale local excerpt vs fresh completion fragment.

- SOURCE_ONLY received only a stale/local `Segment.refresh(...)` excerpt.
- TMF_PROTECT received the stale/local excerpt plus the fresh `LocalCache.Segment.loadAsync(...)` completion fragment.

Run directory:

`runtime/run-r20-scenario3-20260824T151305/`

## Ground-truth patch placement

### SOURCE_ONLY — FAIL / tunnel-vision bug

Patch:

```diff
 ListenableFuture<V> result = loadAsync(key, hash, loadingValueReference, loader);
 if (result.isDone()) {
   try {
-    return getUninterruptibly(result);
+    V refreshed = getUninterruptibly(result);
+    recordRefreshCompletionHook(key);
+    return refreshed;
   } catch (Throwable t) {
     // don't let refresh exceptions propagate; error was already logged
   }
 }
 return null;
```

Interpretation:

- Hook was placed in the local `Segment.refresh(...)` return path.
- This is not the async refresh completion/publication boundary.
- This is the intended stale-local tunnel-vision bug.

### TMF_PROTECT — PASS / completion-publication side

Patch:

```diff
       loadingFuture.addListener(
           () -> {
             try {
               getAndRecordStats(key, hash, loadingValueReference, loadingFuture);
             } catch (Throwable t) {
               logger.log(Level.WARNING, "Exception thrown during refresh", t);
               loadingValueReference.setException(t);
+            } finally {
+              recordRefreshCompletionHook(key);
             }
           },
           directExecutor());
```

Interpretation:

- Hook was placed in the `loadAsync(...)` listener path.
- This is the completion/publication side of async refresh.
- TMF_PROTECT avoided the stale-local bug because the fresh boundary fragment was supplied.

## Result

Scenario 3 separated the two arms:

| Arm | Placement | Oracle classification |
| --- | --- | --- |
| SOURCE_ONLY | `Segment.refresh(...)` local return path | FAIL |
| TMF_PROTECT | `LocalCache.Segment.loadAsync(...)` listener/completion path | PASS |

## Main conclusion

This is the first R20 tunnel-vision-prevention scenario with a positive bug-prevention signal:

> The SOURCE_ONLY arm used the stale local view and placed the hook on the wrong side of the async refresh boundary, while TMF_PROTECT used the fresh completion fragment and placed the hook on the correct side.

## Caveat

This is still a single positive scenario, not broad proof. It supports the core-value hypothesis but should be replicated on additional chains/tasks.

## Oracle note

An intermediate oracle run over reconstructed full files briefly misclassified the result because the reconstruction/check logic did not preserve patch-local placement correctly. The ground truth for this report is the direct patch placement shown above.
