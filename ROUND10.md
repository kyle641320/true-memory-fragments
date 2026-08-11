# Round 10 — safe offline build-tool adapter

## Boundary and threat model

Implemented a minimal, explicit `--resolve-offline` Maven vertical slice. It never invokes Maven, Gradle, wrappers, plugins, extensions, annotation processors, arbitrary build scripts, or network clients. Gradle remains conservatively `partial`/unsupported rather than guessed.

The parser rejects DTD/entity declarations before strict `ElementTree` parsing. Repository/module paths and every cache POM/JAR are canonicalized and constrained to their allowed root; missing files, traversal and symlink escape fail closed. Cache artifact symlinks are rejected. Coordinates use a restricted character grammar.

## Accepted Maven subset

Only a plain POM with literal `groupId:artifactId:version` JAR dependencies and compile/runtime scopes is accepted. Profiles, properties, dynamic `${...}` values, parents, dependency management/BOMs, repositories, plugins/plugin management/extensions, classifiers, non-JAR types, and unknown scopes produce `partial`. Every dependency's cached POM and JAR must exist; cached POMs are recursively parsed under the same rules, proving the full accepted transitive closure locally.

Classpath rows are sorted by coordinate and contain canonical paths plus POM/JAR SHA-256. Their canonical JSON has a deterministic SHA-256 fingerprint. The existing provider additionally fingerprints actual classpath content and propagates build/classpath identity into attributed facts. `-proc:none` remains mandatory in the Java helper.

## Checkout/cache audit and real E2E

Audited fixed validation checkouts:

- `spring-petclinic-modulith`: Maven + Gradle declarations and local caches exist; Maven POM contains profiles, parent/properties/plugins and managed dependencies outside the accepted proof subset. Result `partial`, reason `profiles_unsupported`; real attributed facts: **0**.
- `jhipster-sample-app`: Maven declaration and local Maven cache exist; POM contains profiles, parent/properties/plugins and managed dependencies outside the accepted proof subset. Result `partial`, reason `profiles_unsupported`; real attributed facts: **0**.

No wrapper/build command or network access was used. A two-module synthetic fixture proves selected-module resolution, local transitive closure, canonical fingerprinting, and actual javac attributed fact emission; the sibling module is not included.

## Verification

- Round 10 + prior semantic targeted tests: 15 passed (including XXE, dynamic values, missing metadata, symlink escape, restricted constructs, Gradle fail-closed, transitive closure, selected-module real javac).
- Java qualifications: **46/46**, **731/731 checks**.
- Full suite before final fixture addition: **504 tests passed** in 57.505s; final Round 10 test file separately: **6 passed**.

## Files

- `tools/offline_maven_classpath.py`
- `tools/javac_semantic_facts.py`
- `tests/test_offline_maven_classpath_round10.py`

No commit or push was performed, per round constraint.
