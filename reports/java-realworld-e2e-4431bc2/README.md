# Independent real-world Java E2E validation — TMF `4431bc2`

## Verdict

**No: TMF does not completely and accurately understand a Java project.** It is useful as a freshness-bound, source-observed structural index and locator, but is not a compiler/JDT replacement. On two fixed real Spring projects it was excellent on sampled declarations, literal HTTP routes, and deliberate negatives, but weak on ordinary call edges and only moderate as an Agent question retriever.

## Reproduction

```bash
cd /root/.openclaw/workspace/worktrees/tmf-java-nodes-step0
python3 tools/run_java_qualifications.py > reports/java-realworld-e2e-4431bc2/java-qualifications.log 2>&1
python3 -m unittest discover -s tests > reports/java-realworld-e2e-4431bc2/unittest.log 2>&1
python3 reports/java-realworld-e2e-4431bc2/run_evaluation.py | tee reports/java-realworld-e2e-4431bc2/run.log
```

Environment and every assertion/result are in `report.json`. Golden entries are literals authored from direct source inspection in `run_evaluation.py`; they are not generated from TMF claims.

## Projects

- Spring Petclinic Modulith, SHA `58c3310e36c7d827959df6af4d64bdeb8d81f1ea`, 57 Java source files (58 file-scope claims), 673 total claims. Covers OOP/domain fields, controllers, constructor DI, Spring Data repositories, scheduling and transactions.
- JHipster sample app, SHA `f8da577c944ecc4db46fc961a1ba022d5bbf8964`, 136 Java source files (169 file-scope claims), 3,396 total claims. Covers REST, DI/services, configuration properties, transactions and JPA/Spring Data persistence.

Both were pre-existing locally cloned upstream projects; no network dependency was needed.

## Capability-contract audit

- **Source-observed:** files, classes/interfaces, methods/constructors, fields/constants; literal Spring routes; selected syntactically resolvable calls/reads/writes/type uses.
- **Partial:** cross-file calls; inheritance/override; DI, configuration, transaction and persistence annotations/framework conventions; overloads/generics/dispatch.
- **Semantic overlay:** `tmf.java-semantic-facts.v1` accepts an externally attributed, provenance-bound overlay. The contract explicitly says JDT/javac/SCIP E2E providers are unavailable here. Overlay support is not built-in semantic understanding.
- **Unsupported as proof:** compiler-equivalent binding/type checking; runtime bean graph and AOP proxies; transaction effectiveness; runtime JPA queries/persistence; reflection/generated/Lombok behavior.

## Golden results

85 assertions total (73 positive, 12 negative):

- Positive recall: **68/73 = 93.15%**
- Negative precision/rejection: **12/12 = 100%**
- Overall accuracy: **80/85 = 94.12%**
- Petclinic: **38/41 = 92.68%**
- JHipster: **42/44 = 95.45%**
- Classes: 23/23; interfaces: 7/7; methods: 18/18; fields: 8/8
- Literal Spring routes: 9/9
- `uses_type`: 2/2
- **Calls: 6/6 = 100% after current-source re-derivation**

The previous five call false negatives were caused by old stored claims masking the upgraded analyzer. After derivation-version invalidation they pass. Current five false negatives are JHipster composed/class+method Spring routes: `/api/bank-accounts`, `/api/labels`, `/api/operations`, `/api/account`, and `/api/admin/users`. This is now the clearest sampled extractor gap. The former `Pet -> Visit.getDate` golden was erroneous (no such call exists in `Pet.java`) and was replaced with the source-verified `Pet -> Pet.getVisits` call. See `report.json.failures` and each assertion's `source_locations`.

“Precision” here is deliberately bounded to the manually sampled positive/negative manifest; it must not be read as whole-repository precision. Unresolved framework/runtime semantics are outside the claim set and listed above rather than scored as success.

## Freshness mutation

A disposable Petclinic clone mutated only `Owner.getPets`, then warmed and was deleted.

- Stale precision: **100%** (23 stale Owner-bound, 0 unrelated stale)
- Changed-file claim invalidation ratio: **23/51 = 45.10%**
- Over-invalidation outside the changed file: **0/622 = 0%**
- Post-warm stale claims: **0**; one file rederived, 57 skipped

Interpretation: locality/precision is strong. The 45.10% figure is **not semantic stale recall** and must not be presented as such: only one method token was changed, while the denominator contains every claim bound anywhere in `Owner.java`. Claims with unchanged finer-grained function/token bindings correctly remain fresh. This experiment proves local invalidation and no observed spillover; it does not yet prove that every semantically affected downstream claim is invalidated.

## Agent retrieval

16 natural-language questions, top-k=10:

- **MRR: 0.4450**
- **Recall@10: 75.00% (12/16)**

Misses included locating `Owner`, `OwnerRepository`, `BankAccount`, `MailService`, and `ExceptionTranslator`. Retrieval is lexical/router/embedding-assisted and useful, but cannot be assumed to return the governing source fact for an arbitrary Agent question.

## Baseline (not real-world proof)

- Java qualification runner: **46/46 qualification groups passed** (see log).
- Full unittest: **483 passed in 79.763s**.

These establish regression health only. Fixture qualification passes are not evidence of complete real-project understanding.

## Scope and confidence

This is a **first representative held-out sample**, not proof across the Java ecosystem. It covers two Spring-centric projects, 85 manually authored assertions, six sampled call edges, one mutation shape, and 16 retrieval questions. It does not cover Android, large multi-module builds, reflection/code generation, Lombok-heavy projects, mixed Kotlin/Java, complex generics/overloads, or compiler-attributed runtime dispatch. The strong declaration scores are credible for this sample; the exact call-graph and retrieval percentages need a larger stratified corpus before being treated as stable population estimates.

## Most serious weaknesses

1. **Composed/class+method Spring route extraction is the clearest current sampled defect** in this held-out sample (16.67%); unresolved receiver/type binding and cross-file dispatch leave ordinary OOP/service calls absent.
2. **Spring semantics are mostly declaration/source observations**, not proof of bean wiring, proxy/AOP transaction behavior, or persistence behavior.
3. **Retrieval misses 31.25% at top 10** even when the correct declaration exists in memory.
4. **No bundled attributed semantic provider** closes the gap; the overlay contract only validates supplied facts.
5. Source-observed confidence/claims must not be marketed or consumed as compiler-complete semantic understanding.

## Raw artifacts

- `report.json`: environment, SHAs, 85 assertions, claim IDs, source anchors/locations, false negatives, retrieval rankings, mutation raw result and metrics.
- `run_evaluation.py`: reproducible independent golden/evaluator.
- `run.log`, `java-qualifications.log`, `unittest.log`: raw command output.

## Round-2 cache-version result

Java claims now carry `java.derive.v2`; the complete warm manifest records the same pipeline version. A version mismatch makes affected Java claims stale and causes `warm` to rederive Java-owned paths only, leaving Python/JSON/TOML slices untouched. Cross-file dependent owners are conservatively scheduled when a bound dependency changes. Tests prove a mixed Java/Python repository rederives 1/2 files on a Java version bump, then returns to a no-op.

The mutation result is **81/110 = 73.64% changed-file claim invalidation ratio**, explicitly not semantic stale recall; spillover was **0/961**, repair derived 8 dependency-relevant files and skipped 50, with zero stale claims afterward.
