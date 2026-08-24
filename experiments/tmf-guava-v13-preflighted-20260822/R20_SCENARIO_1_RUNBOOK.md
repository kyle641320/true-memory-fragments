# R20 Scenario 1 Runbook

## Scenario

Refresh completion hook placement under asynchronous cache refresh.

## Files in play

- `CacheBuilder.java`
- `LocalCache.java`
- `LoadingValueReference` inside `LocalCache.java`
- `CacheLoader.java`
- `LoadingCache.java`

## Frozen task

Add a new refresh-completion hook to the refresh path.

The hook must be placed after refresh completion/publication, not merely after refresh initiation.

## Frozen mutation

Use an asynchronous `CacheLoader.reload(...)` path so that completion timing matters.

## Arms

### SOURCE_ONLY
- Read t0 chain understanding only
- No TMF stale detection
- No forced reread
- Patch directly from the stale view

### TMF_PROTECT
- Read t0 chain understanding plus bounded fragment for the stale boundary
- If the boundary is stale, TMF blocks continuation
- TMF forces reread of the affected boundary before patching

## Mechanical oracle

The hook is correct only if it fires after refresh completion/publication.

Reject if the hook fires:
- at refresh initiation
- before future completion
- before publication of the refreshed value

## Expected failure mode for SOURCE_ONLY

Hook placed too early at the top-level refresh entry point.

## Expected TMF behavior

TMF should force reread of the reload / completion boundary and move the hook to the correct side.

## Status

Frozen for execution.
