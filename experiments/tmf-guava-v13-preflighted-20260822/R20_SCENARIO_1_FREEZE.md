# R20 Scenario 1 Freeze

## Scenario name
Refresh boundary ordering

## Fixture chain
- A: `CacheBuilder`
- B: `LocalCache`
- C: `LoadingValueReference`
- D: `CacheLoader`
- E: `LoadingCache`

## Core mutation idea

Mutate the refresh boundary so that a stale mental model of `CacheBuilder` alone would place an added A-side action on the wrong side of the refresh boundary.

The scenario should force the agent to care about whether refresh has already been scheduled / published before the new A-side call is inserted.

## Task shape

Ask the agent to change the A-side cache setup / cache-user code so that it adds one new behavior near the refresh boundary.

The correct patch depends on the mutated C/D boundary.

## Mechanical oracle idea

Check whether the new A-side call is:
- before refresh scheduling/publishing
- after refresh scheduling/publishing
- or incorrectly placed across the boundary

The oracle must be source-mechanical, not LLM-based.

## Status

Frozen as the first tunnel-vision-prevention scenario.
