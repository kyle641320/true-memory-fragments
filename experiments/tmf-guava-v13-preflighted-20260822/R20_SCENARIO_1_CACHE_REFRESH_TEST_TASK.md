# R20 Scenario 1: CacheRefreshTest Task

## Fixture host

- `guava-tests/test/com/google/common/cache/CacheRefreshTest.java`

## Why this host

- Already exercises `refreshAfterWrite`.
- Already contains deterministic refresh timing via `FakeTicker`.
- Can support a mechanical oracle around refresh completion.

## Task

Add a refresh-completion observation hook to the test fixture so that we can distinguish:
- refresh initiation
- refresh completion/publication

The hook should be checked against the async completion boundary.

## SOURCE_ONLY expected risk

A source-only agent may attach the hook to the refresh initiation path because that is the visible A-side entry point.

## TMF_PROTECT expected behavior

TMF should force reread of the completion boundary and place the hook where refresh is actually completed or published.

## Oracle idea

The test should fail if the hook fires at initiation rather than completion/publication.

## Status

Frozen as the concrete test-host task for Scenario 1.
