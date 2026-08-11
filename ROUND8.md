# Round 8 — compiler-attributed Java facts

## Result

This round **really uses compiler attribution**: `tools/javac-helper/TmfJavacFacts.java` runs the JDK 17 `JavaCompiler`/`JavacTask.parse()+analyze()` API and asks `Trees.getElement(TreePath)` for each method invocation. The executable fixture resolves the overloaded `put("...")` call to owner `p.Overload`, erased JVM descriptor `(Ljava/lang/String;)V`; this is not inferred by TMF's source parser. It is intentionally an opt-in producer plus the existing provider-neutral importer, not an automatic build-system integration.

## Audit and provider choice

Existing work already supplied default-off `tmf.java-semantic-facts.v1` directory ingestion, path/range/symbol validation, source SHA-256 rejection, provider-conflict fail-closed behavior, attributed confidence cap, verifier, compatibility docs, and syntax-overlay coexistence. CLI/config do not auto-run a compiler and remain unchanged. Environment: OpenJDK/javac 17.0.18, Maven 3.8.7 and Gradle 8.14.3 are available; no `scip` binary and no local ECJ/JDT jar was found. The JDK API is therefore the smallest reproducible offline provider.

## Tier, conflict, and unknown protocol

1. `java-treesitter-syntactic` is **source-observed**: authoritative only for source text/anchors/declarations it directly observes. It remains present regardless of provider outcome.
2. `compiler-attributed` is an attributed overlay. It has priority only for the semantic identity of the *same exact anchored occurrence* (for example overload selection). It never deletes, rewrites, raises confidence of, or impersonates an AST claim.
3. Accepted attributed calls require exact source hash, compiler/tool versions, classpath and build identities, source range plus byte/character offsets, and source/target owners plus erased JVM descriptors. Missing fields mean `unknown`, not a weaker resolved fact.
4. Stale source hash, malformed/ambiguous identities, differing provider fact sets, missing classpath, or compilation diagnostics yield no attributed claims. Existing AST facts survive unchanged. Two identical providers may deduplicate; disagreement is `conflicting_providers`, never voting.
5. Freshness is bound to source SHA-256 in both document/body and claim binding (`hash_kind=sha256`), plus classpath/build identity as immutable provenance. A classpath change requires regeneration; ingestion never guesses the current classpath.

## Slice and negatives

- Producer: `tools/javac_semantic_facts.py` compiles/caches a tiny Java helper locally, invokes javac attribution, and emits v1 JSON.
- Fixture: `fixtures/java-semantic-round8/src/p/Overload.java` includes interface implementation and overloads; emitted target is specifically `put(String)`.
- Importer now requires attributable anchor and owner/descriptor identity and labels accepted claims `compiler-attributed`.
- Tests cover real javac overload attribution end-to-end, deterministic coexistence with AST, ambiguous IDs/missing attributed identity, compile failure/missing classpath behavior, conflicting providers, and stale source facts.

## Verification

- Targeted: `8` tests passed (`tests.test_java_semantic_facts`, `tests.test_javac_semantic_provider`).
- Java qualification: `46/46` verifiers passed, `731/731` checks.
- Full suite: `496` tests passed in 49.870s.
- Petclinic and JHipster probes were attempted without dependency classpaths. Both javac attribution runs failed closed and emitted no facts, as designed. Their dependency classpaths were not synthesized/downloaded because this round prohibits relying on network and automatic Maven/Gradle classpath integration is outside the minimal slice.

## Remaining boundary

This is one real compiler-attributed vertical fact, not complete compiler integration. Multi-file source paths, build-module discovery, generated sources, annotation processing, classpath canonicalization beyond the exact supplied string, override/implementation facts, and automatic warm/CLI provider execution remain future work. The current helper intentionally emits no document if *any* javac error diagnostic occurs.
