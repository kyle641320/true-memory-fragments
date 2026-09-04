# R21 rehearsal SOURCE_ONLY

You are running one controlled benchmark arm.

Read `TASK_BASE.md`. You may use only the task card plus this stale note:

> Stale note: refresh completion happens after `Segment.refresh(...)` calls `loadAsync(...)`; placing `recordRefreshCompletionHook(key);` right after `loadAsync(...)` should observe publication.

Do not read the TMF locator JSON. Do not inspect unrelated source. Produce exactly:
- `patch.diff` — unified diff for `guava/src/com/google/common/cache/LocalCache.java`
- `NOTE.md` — short explanation and METRICS_JSON line

Do not modify the source tree directly.
