# TMF boundary pruning

## Boundary retained

- Provider-neutral Java semantic-facts ingestion, validation, provenance, freshness, conflict handling, and retrieval remain unchanged.
- The optional external javac producer remains in `tools/javac_semantic_facts.py` with its JDK helper in `tools/javac-helper/TmfJavacFacts.java`.
- The producer accepts caller-supplied source paths and explicit `--classpath` entries, validates/fingerprints those entries, disables annotation processing, and fails closed on compilation errors.
- `--module ... --discover-only` remains a static, read-only observation mode. It reports `partial`, returns no inferred classpath, and executes no Maven, Gradle, or wrapper command.

## Removed

- All uncommitted Round 11 changes were discarded, including `ROUND11.md`, its test, resolver/test modifications, and the historical E2E report modification.
- Committed Round 10 build-resolution experiment was removed:
  - `tools/offline_maven_classpath.py`
  - `tests/test_offline_maven_classpath_round10.py`
  - `ROUND10.md`
- The javac producer no longer imports a Maven resolver, exposes build-resolution/cache flags, or automatically injects a discovered classpath.
- Round 8/9 documentation and the changelog now state that build-system model evaluation, dependency resolution, cache inference, generated sources, and annotation processing are permanently out of scope. Callers/build tools must provide classpaths explicitly.

## Boundary regressions added

- The javac CLI help is checked to ensure removed Maven-resolution flags are absent.
- Discover-only output is checked to contain no `classpath` field.
- Fake Maven/Gradle executables and a wrapper marker verify that discover-only executes no build tool.

## Verification

- javac/provider targeted tests: **12 passed**.
- Qualification runner tests: **22 passed**.
- Java qualifications: **46/46 verifiers passed**, **731/731 checks**.
- Full unittest discovery: **500 passed**.
- Real Petclinic/JHipster E2E: **89/89 assertions passed**; positive recall, negative precision, and overall accuracy all **1.0**; retrieval Recall@10 **0.75**; mutation stale-after-rewarm **0**. The generated historical report was restored afterward.
- Repository search: no `offline_maven_classpath`, removed resolution flag, or removed cache flag remains in the current tree.
- Packaging: minimal wheel built successfully with `pip wheel --no-deps --no-build-isolation`; **41 files**, no removed resolver content. An sdist was not produced because the `build` frontend is unavailable and the project has no legacy `setup.py`/`setup.cfg` entrypoint.
- `git diff --check`: passed.
- No commit or push was performed.
