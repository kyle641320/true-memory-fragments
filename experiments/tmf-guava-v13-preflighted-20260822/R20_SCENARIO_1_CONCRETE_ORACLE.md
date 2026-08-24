# R20 Scenario 1 Concrete Oracle

## Concrete boundary

In `LocalCache.Segment.loadAsync(...)`:

```java
ListenableFuture<V> loadingFuture = loadingValueReference.loadFuture(key, loader);
loadingFuture.addListener(
    () -> {
      try {
        getAndRecordStats(key, hash, loadingValueReference, loadingFuture);
      } catch (Throwable t) {
        logger.log(Level.WARNING, "Exception thrown during refresh", t);
        loadingValueReference.setException(t);
      }
    },
    directExecutor());
return loadingFuture;
```

The completion/publication side is inside the future listener, around `getAndRecordStats(...)`.

## SOURCE_ONLY likely bug

Place the new hook in `refresh(...)` after:

```java
ListenableFuture<V> result = loadAsync(...);
```

This fires at refresh initiation, not completion.

## TMF_PROTECT expected correct placement

Place the new hook in or after the listener completion path around:

```java
getAndRecordStats(key, hash, loadingValueReference, loadingFuture);
```

## Mechanical oracle

Pass if:
- the hook appears inside the `loadingFuture.addListener(...)` completion callback, or directly after successful `getAndRecordStats(...)` in a completion path
- the hook does not appear immediately after `loadAsync(...)` in `refresh(...)`

Fail if:
- the hook is placed in `refresh(...)` after `loadAsync(...)`
- the hook fires before the future is complete

## This is the tunnel-vision point

A-only reading sees `refresh(...)` and may mistake `loadAsync(...)` return for completion.
Fresh C/D boundary reading sees that completion is actually in the future listener / stats-recording path.
