# R21 clean rehearsal SOURCE_ONLY

You are running one controlled benchmark arm.

Read:
- `TASK_BASE.md`
- `PROTOCOL.md`

You may use only the task card plus this stale note:

> Stale note: refresh completion happens after `Segment.refresh(...)` calls `loadAsync(...)`; placing `recordRefreshCompletionHook(key);` right after `loadAsync(...)` should observe publication.

You may inspect the exact target source file only as needed to build a valid patch:
`/root/.openclaw/workspace/repos/guava/guava/src/com/google/common/cache/LocalCache.java`

Do not read the TMF locator JSON. Do not inspect sibling `tmf_localized`. Do not modify the source tree directly.

Produce exactly the required protocol files:
- `patch.diff`
- `NOTE.md`
- `VERIFY.sh`
- `VERIFY.log`
