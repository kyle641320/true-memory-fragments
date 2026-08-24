# R20 Tunnel Vision Prevention Execution Notes

1. Freeze task list.
2. Freeze mutation list.
3. Freeze mechanical oracle.
4. Run SOURCE_ONLY and TMF_PROTECT on each scenario.
5. Measure bug rate, not read savings.
6. Do not rewrite success criteria after seeing results.

Current chain focus:
- CacheBuilder.refreshAfterWrite
- LocalCache.refresh
- LoadingValueReference.loadFuture
- CacheLoader.reload
- LoadingCache.refresh
