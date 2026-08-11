# Round 9 — offline module probes and multi-source attributed facts

## Result and boundary

Implemented a **read-only, explicit opt-in, offline-only vertical slice**. This is not complete Maven/Gradle build integration: the provider never executes Maven, Gradle, wrappers, plugins, annotation processors, or dependency downloads, and it does not infer dependency graphs from build text.

## Real checkout/cache audit

Fixed local checkouts were inspected before provider work:

- Petclinic: `spring-petclinic-modulith`, both `mvnw`/`gradlew`, `pom.xml` and `build.gradle` present; local `~/.m2/repository` and Gradle module cache present.
- JHipster: `jhipster-sample-app`, `mvnw` and `pom.xml` present; local Maven cache present.
- Explicit discovery reports `partial` for both: build file/wrapper/cache identity is observable, but completeness of all transitive/plugin dependencies cannot be proven without executing build logic. Therefore real-project attributed output is **0 documents / 0 facts**, fail-closed reason `offline_static_discovery_does_not_guess_dependency_graph`. No network or wrapper was invoked.

## Slice

- `tools/javac_semantic_facts.py` accepts multiple source paths and optional repeated classpath entries.
- Classpath entries are canonical absolute paths sorted deterministically; files and directory contents are SHA-256 hashed into a stable canonical identity. Missing entries fail closed. Build discovery hashes the selected build file and records wrapper/cache presence.
- `--module ... --discover-only` is the only Maven/Gradle discovery path and is explicit/read-only.
- `TmfJavacFacts` batches sources in one `JavacTask`, with `-proc:none`, emits per-file attributed calls and cross-file `overrides` facts. The fixture proves `Impl.speak` overrides `Api.speak` and polymorphic `api.speak()` targets `p.Api`.
- Batch freshness includes every participating source SHA-256, classpath fingerprint, and build identity. Ingestion rejects a batch when any participant changes. Provider regeneration changes identity when classpath contents or build file changes.
- Annotation processing/generated sources are disabled; generated sources are not guessed.

## Verification

- Targeted semantic/provider tests: 11 passed; Round 9-specific tests cover discovery, missing classpath, multi-file override, polymorphic call, participant staleness, and classpath mutation.
- Java qualifications: 46/46 passed, 731/731 checks.
- Full suite: 499 tests passed in 56.548s.
- Real E2E probes: Petclinic and JHipster discovery succeeded as partial; attributed compilation intentionally not attempted because classpath completeness remained unknown. Output count: 0 facts for each, with the explicit failure reason above.

## Remaining

Safe future work requires a separately reviewed offline build-tool adapter capable of proving dependency/plugin cache completeness and exporting classpaths without running untrusted project build logic. Generated-source identity and annotation-processing policy also remain outside this slice.
