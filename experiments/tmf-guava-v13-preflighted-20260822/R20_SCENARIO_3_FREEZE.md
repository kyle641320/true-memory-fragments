# R20 Scenario 3 Freeze

## Scenario name
Stale local excerpt vs fresh completion fragment

## Why Scenario 1/2 failed to separate arms

SOURCE_ONLY was still able to infer or inspect the completion listener and place the hook correctly.

## Stronger experimental manipulation

Change the information condition:

### SOURCE_ONLY
Receives only a stale/local excerpt of `Segment.refresh(...)`:

```java
ListenableFuture<V> result = loadAsync(...);
if (result.isDone()) {
  return getUninterruptibly(result);
}
return null;
```

SOURCE_ONLY must produce a patch from this excerpt only. It should not inspect the full source.

Expected tunnel-vision bug:
- hook placed in the refresh local return path / initiation path.

### TMF_PROTECT
Receives the stale/local excerpt first, then TMF detects stale/incomplete boundary and provides the fresh `loadAsync(...)` completion fragment:

```java
loadingFuture.addListener(() -> {
  try {
    getAndRecordStats(...);
  } catch (...) {
    ...
  }
}, directExecutor());
```

Expected correct behavior:
- hook placed in the completion listener path.

## Mechanical oracle

Use `scripts/r20_scenario1_oracle.py`:
- FAIL if hook appears in `Segment.refresh(...)`
- PASS if hook appears in `Segment.loadAsync(...)` completion listener

## Interpretation

This scenario tests whether TMF's bounded fresh fragment changes the patch decision, not whether a model can discover the right source on its own.
