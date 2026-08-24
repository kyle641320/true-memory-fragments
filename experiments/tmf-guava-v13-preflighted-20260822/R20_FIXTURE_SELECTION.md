# R20 Fixture Selection

Preferred existing test hosts in Guava:
- `guava-tests/test/com/google/common/cache/CacheRefreshTest.java`
- `guava-tests/test/com/google/common/cache/LocalLoadingCacheTest.java`
- `guava-tests/test/com/google/common/cache/CacheBuilderTest.java`

Why these hosts:
- They already exercise the refresh chain.
- They can host a mechanical oracle around hook placement and completion timing.
- They are more realistic than inventing a tiny standalone fixture.

Likely best candidate:
- `CacheRefreshTest.java`

Reason:
- the name and scope directly match the refresh boundary we want to test.
