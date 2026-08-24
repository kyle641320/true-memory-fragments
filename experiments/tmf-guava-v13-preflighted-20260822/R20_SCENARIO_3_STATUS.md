# R20 Scenario 3 Status

## Current state

- SOURCE_ONLY: completed and hit the intended bug side.
- TMF_PROTECT: pending.

## Why this is promising

Unlike Scenario 1 and 2, the SOURCE_ONLY arm did not naturally converge to the correct completion listener path. It placed the hook in the local refresh return path instead.

That is the first sign that the info split is now strong enough to separate arms.

## Next

Wait for TMF_PROTECT patch, then run the mechanical oracle.
