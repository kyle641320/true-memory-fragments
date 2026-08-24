# R20 refresh-chain fixture sketch

Chosen causal chain:
- `CacheBuilder.refreshAfterWrite(...)`
- `LocalCache.refresh(K key)`
- `LoadingValueReference.loadFuture(...)`
- `CacheLoader.reload(K key, V oldValue)`

Why this chain is good for tunnel-vision prevention:
- The semantic boundary is real and multi-file.
- A stale model of one file can cause the new call to be placed on the wrong side of the refresh boundary.
- The correct patch depends on understanding how `reload` is used during refresh.

Potential A-file edit shape:
- add a helper / new call in the cache-user layer
- the right placement depends on whether the cache entry is being refreshed synchronously or asynchronously
- source-only reasoning is likely to miss the boundary in `LocalCache` or `CacheLoader`

Need next:
- pick the exact 4-5 fixture files
- define the t0 read task and discard its answer
- choose a mutation in C that flips the correct placement in A
- define a mechanical oracle over call ordering / refresh boundary behavior
