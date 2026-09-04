# R21 clean rehearsal SOURCE_ONLY note

Placed `recordRefreshCompletionHook(key);` in `getAndRecordStats(...)` immediately after `storeLoadedValue(...)` returns. This is after the loaded value has been stored/published by the cache path, rather than after `loadAsync(...)` starts the asynchronous refresh. I rejected the stale note placement in `refresh(...)` because `loadAsync(...)` only registers/starts the async load and returns a future; completion is handled by the listener calling `getAndRecordStats(...)`.

Cited source ranges used for placement decision:
- `/root/.openclaw/workspace/repos/guava/guava/src/com/google/common/cache/LocalCache.java:2314-2327`
- `/root/.openclaw/workspace/repos/guava/guava/src/com/google/common/cache/LocalCache.java:2335-2350`
- `/root/.openclaw/workspace/repos/guava/guava/src/com/google/common/cache/LocalCache.java:2385-2395`
- `/root/.openclaw/workspace/repos/guava/guava/src/com/google/common/cache/LocalCache.java:3148-3235`

METRICS_JSON: {"raw_status":"ok","protocol_clean":true,"semantic_status":"pass","failure_attribution":"none","changed_files":["patch.diff","NOTE.md","VERIFY.sh","VERIFY.log"],"reread_files":["/root/.openclaw/workspace/repos/guava/guava/src/com/google/common/cache/LocalCache.java"],"reread_lines":162,"tool_calls":8,"budget_exhausted":false,"placement_summary":"Hook placed after storeLoadedValue(...) in getAndRecordStats(...), the listener-driven refresh completion/publication path; not after loadAsync(...) in refresh(...).","citations":["/root/.openclaw/workspace/repos/guava/guava/src/com/google/common/cache/LocalCache.java:2314-2327","/root/.openclaw/workspace/repos/guava/guava/src/com/google/common/cache/LocalCache.java:2335-2350","/root/.openclaw/workspace/repos/guava/guava/src/com/google/common/cache/LocalCache.java:2385-2395","/root/.openclaw/workspace/repos/guava/guava/src/com/google/common/cache/LocalCache.java:3148-3235"]}
