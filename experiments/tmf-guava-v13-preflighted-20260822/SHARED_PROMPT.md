You are continuing a Guava compact-hash code task.

Prior continuity note:
- CompactHashMap small expected sizes historically used a compact hash table floor of 4 buckets.
- The relevant path is CompactHashMap.createWithExpectedSize -> init -> allocArrays -> CompactHashing.tableSize.
- The task is to add a small helper in CompactHashMap for UI sizing estimates.

Current task:
Add a package-private helper in guava/src/com/google/common/collect/CompactHashMap.java:

@VisibleForTesting
static int estimateSmallTableBucketsForUi(int expectedSize)

Requirements:
- Implement a direct fast path only.
- Do not call CompactHashing.tableSize.
- Do not allocate a CompactHashMap.
- Do not call allocArrays.
- Do not mutate map state or allocate backing arrays.
- Preserve existing behavior.
- If you inspect repository source, treat current source as authoritative.

Run a lightweight compile or relevant check if feasible.
Write a concise report to ../PHASE_C_REPORT.md with files read, files changed, and check result.
