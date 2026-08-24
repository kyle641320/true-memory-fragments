# R20 Scenario 1 Arm Tasks

## Shared task

Add a refresh-completion hook to the Guava cache refresh path.

The hook must fire after refresh completion/publication, not merely after refresh initiation.

## SOURCE_ONLY task

- Read the t0 chain understanding.
- Edit the cache refresh path using only the A-side view.
- Do not assume any stale detection or forced reread.
- Add the hook where it seems natural from `CacheBuilder.refreshAfterWrite(...)` and the top-level refresh entry point.

This arm is expected to be vulnerable to placing the hook too early.

## TMF_PROTECT task

- Read the t0 chain understanding.
- Also read the bounded fragment for the refresh completion boundary.
- If TMF detects a stale boundary, reread the C/D completion path before editing.
- Add the hook only after the completion/publication boundary is freshly understood.

This arm is expected to place the hook on the correct side of completion.

## What to compare

- Where the hook is inserted
- Whether it fires before or after completion/publication
- Whether the mechanical oracle passes
