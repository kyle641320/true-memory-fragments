# Java Enterprise Capability Roadmap

## Completed foundation: versioned API relationship bindings

Schema v2 now represents route declarations and resolved handlers as independent role-typed bindings. The first consumer is the exact-import WebFlux `RouterFunctions` literal subset. Nesting/prefixes, filters/resources, dynamic predicates, lambdas, and classpath-aware overload resolution remain deferred.

TMF's Java support is a conservative source-analysis system. Source-derived facts may be observed; framework conventions and incomplete semantic resolution must remain attributed or unresolved. The implementation must never fabricate edges to improve apparent coverage.

## Supported Baseline

- Tree-sitter Java nodes for top-level and nested types, methods, constructors, fields, and constants.
- Conservative source-defined `inherits`, `calls`, `reads`, `writes`, `overrides`, and `uses_type` relationships.
- Cross-file source index with FQN, explicit-import, same-package, Maven/Gradle module, and source-set metadata.
- Spring route, dependency-injection, Kafka topic, and mechanical contract windows already documented by their tests.
- Freshness, reconciliation, reverse graph queries, unresolved reasons, and optional dependency degradation.

## Project Model Contract

`JavaProjectModel` is the source of truth for source-defined Java locations.

- Maven modules are discovered from literal `<modules><module>…</module></modules>` entries.
- Gradle modules are discovered from literal `include(…)` or `include ':module'` declarations.
- Standard `src/main/java` and `src/test/java` source sets are classified explicitly.
- Other `src/<name>/java` layouts retain the source-set name.
- Maven and Gradle generated-source layouts are marked generated instead of silently treated as handwritten main code.
- Repositories without build descriptors remain supported as one unknown root module.
- Dynamic Gradle logic, Maven profiles, plugins that add source roots, dependency classpaths, and generated-but-untracked files remain unresolved until a later phase.

## Delivery Phases

### Phase 1 — Project and Symbol Model

- [x] Literal Maven/Gradle multi-module discovery.
- [x] Main/test/custom/generated source-set classification.
- [x] Module metadata on source-defined symbols.
- [x] Build-descriptor freshness and cached model invalidation.
- [x] Module dependency graph from conservative literal build descriptors.
- [x] External dependency/JDK symbol placeholders with provenance (diagnostic only; never source-resolved).
- [x] Configurable include/exclude policy for generated, test, custom, and unclassified sources.

### Phase 2 — Java Semantic Resolution

- [x] Shared syntax type model for primitives, arrays, varargs, nested/FQN types, wildcard bounds, and generic erasure; semantic symbol binding remains conservative.
- [x] Bounded signature-aware overload resolution, varargs, boxing, and widening; unsupported semantic shapes remain explicitly unresolved.
  - [x] Stable signature-qualified identity for overloaded methods while preserving legacy IDs for non-overloaded methods.
  - [x] Strict exact matching for statically observed literal, declared-variable/parameter, and `new` argument types.
  - [x] Bounded source-only applicability/ranking for exact, primitive widening, boxing, unboxing, unboxing-plus-widening, resolvable source-defined reference upcasts, and source-declared varargs expansion across method and explicit constructor calls. Fixed-arity applicability—including safe invariant exact-array invocation—precedes variable arity; trailing arguments convert to the component type and each phase uses Pareto ranking. Shorter source hierarchy paths are preferred; unknown/null/generic references, unsafe generic varargs, ambiguous symbols, inapplicable sets, equal/crossing ties, and external symbols remain unresolved.
  - [x] Bounded method-generic substitution for one source-declared type variable in direct parameter positions, requiring one consistent known simple reference type and checking a simple source-resolvable upper bound. Equally applicable non-generic overloads win conservatively; constructors, class/multiple/nested type variables, generic varargs, return-context inference, substituted return emission, hierarchy joins, and recursive/intersection/external bounds remain unresolved.
  - [x] Safe exact-array varargs invocation for invariant, unambiguous source-observed declared/local/parameter and explicit new-array types; covariance, generic-array inference, unknown dimensions, and classpath-only shapes remain unresolved.
- [x] Source-declared constructor nodes and conservative exact-match call edges for `new`, explicit `this(...)`, and explicit `super(...)`; implicit/default constructors and broader applicability remain unresolved.
- [x] Interface default methods and deterministic transitive override resolution for source-defined ancestor chains; nearest unique matches resolve, convergent diamonds de-duplicate, and distinct/overloaded ambiguity remains unresolved.
- [x] Lambdas, method references, anonymous classes, records, sealed types, and annotations. Each item has a bounded conservative syntax slice; richer callable/runtime semantics remain deferred as described below.
  - [x] Parser-safety slice: lambda bodies are deferred boundaries and are no longer misattributed as runtime calls of the enclosing method; lambda expressions remain explicit unresolved evidence. Method references are likewise retained as unresolved non-invocation evidence because the current schema has no honest reference relationship. Stable lambda nodes and reference resolution require a callable-context/reference-edge schema first.
  - [x] Records + sealed-types slice: records use stable class/type identities, explicit compact constructors and `implements` are retained, and component declared types become record-level type-use evidence. No implicit record members are synthesized. Sealed/non-sealed declarations keep normal class/interface semantics; source-resolved `permits` entries are represented as explicit subtype edges, while ambiguous/external entries remain unresolved and never become calls. Record annotations beyond their effect on stable syntax hashes, implicit canonical constructors, and richer modifier metadata remain deferred.
  - [x] Annotation slice: source annotation declarations reuse stable interface/type identity; declaration, parameter, record-component, and bounded type-use annotations resolve only to unique source symbols and emit `annotation_type` evidence. External, wildcard-only, ambiguous, meta/classpath semantics remain unresolved. Element values and nested annotation metadata never become runtime calls; retention, inheritance, processors, repeatability, and reflection are not inferred.
- [x] Exception-syntax traversal and conservative control-flow-aware read/write classification. Try/catch/finally, try-with-resources, throw operands, branch/loop bodies, declarations/initializers, simple and compound assignment, and update expressions are traversed syntactically; compound/update targets are both read and written. Catch/resource names and ordinary locals/parameters shadow fields, while lambda and anonymous-class executable bodies are deferred boundaries. The graph schema does not represent CFG or exception dispatch, so TMF intentionally emits no runtime throw-to-catch/finally edges and retains deferred-boundary evidence as unresolved.
- [x] Optional compiler/SCIP/JDT semantic tier kept separate from syntax evidence (provider-neutral external facts v1 ingestion; default-off; true JDT E2E unavailable in this environment).

### Phase 3 — Enterprise Framework Adapters

- [ ] Spring bean registry, constructor/field/method injection, qualifiers, and configuration properties.
  - [x] First bounded adapter slice: exact explicitly imported stereotype/configuration-property class beans and exact-type `@Autowired`/`@Inject` field evidence. Same-simple-name decoys and external/missing types are not promoted; unresolved injection is explicit and no runtime calls are fabricated.
  - [x] Second bounded adapter slice: same-source explicit `@Bean` producer methods, explicitly annotated constructor/method parameters, and literal `@Qualifier` disambiguation over exact source-declared types and explicit bean names. Ambiguous, external, generic/container/provider, implicit-constructor, and classpath cases remain unresolved; no scanning, lifecycle, conditions/profiles/proxies, implicit calls, or generated constructors are inferred.
  - [x] Project-wide tracked-source bean registry with safe cross-file exact-type producer/component resolution; explicit imports and literal qualifier names are preserved, while decoys and ambiguity remain unresolved.
  - [x] Bounded ConfigurationProperties declaration metadata: exact explicit imports plus literal `prefix`/`value` on classes/records and unambiguous explicit `@Bean` factories. Runtime binding and broader property relationships remain deferred.
  - [x] First bounded annotated Spring MVC/WebFlux endpoint slice: exact explicit imports of `@Controller`/`@RestController` and `RequestMapping`/`GetMapping`/`PostMapping`/`PutMapping`/`DeleteMapping`/`PatchMapping` produce stable V2 API nodes linking literal class/method path or value arrays to a unique source handler node identity. `RequestMapping` requires literal deterministic HTTP methods; overloaded handler names are rejected rather than guessed. Same-simple-name decoys, dynamic paths/methods, ambiguous aliases, composed/meta annotations, classpath inference, media/params/headers semantics, inheritance/proxies/scanning, and runtime calls remain unresolved/deferred.
  - [ ] Functional WebFlux `RouterFunction` remains deliberately deferred. Even direct literal `RouterFunctions.route(RequestPredicates.GET("/x"), handler::method)` and builder `GET`/`POST` forms can place route and handler evidence in different files, while the current API schema carries one source binding/hash and no resolved handler binding. Emitting one would misstate freshness/deletion. Lambdas, variables/composed predicates, nested routes/path prefixes, dynamic paths, filters/resources, classpath inference, and overloaded method references are additionally rejected. Targeted no-API/no-call coverage locks this boundary until the schema can represent both bindings.
- [ ] Complete Spring MVC/WebFlux endpoint and handler relationships beyond the bounded annotated slice.
- [ ] Kafka producer/consumer/group/payload relations.
  - [x] First bounded source-evidence slice: exact-import literal `@KafkaListener` topics/literal group IDs and exact two-argument `KafkaTemplate.send` literal topics, with unambiguous declaration/observed payload types, method anchors, freshness, and reconciliation. Runtime semantics and broader overloads remain deferred.
- [ ] JPA/Hibernate entities, repositories, transactions, and query relations.
- [ ] MyBatis mapper/XML/SQL relations.
- [ ] RPC clients/servers, cache usage, scheduling, and transaction boundaries.
  - [x] Conservative Spring Cache declaration slice: exact imports, literal cache name arrays, opaque literal key/condition/unless metadata, stable annotation anchors/hashes, and fail-closed negatives. Runtime cache calls/effects remain deferred.
  - [x] Conservative Spring scheduling declaration slice: exact `@Scheduled` import, source methods, opaque literal fixed-rate/fixed-delay/initial-delay/cron/zone/time-unit metadata, stable anchors/hashes, and explicit fail-closed negatives. Runtime schedule semantics remain deferred.
  - [x] Conservative Spring transaction declaration slice: exact `@Transactional` import, direct class/method literal metadata, overload-safe owner IDs, exact anchors/hashes, and fail-closed aliases/decoys/dynamic values. Runtime transaction semantics remain deferred.
- [ ] Reflection/code-generation boundaries surfaced explicitly rather than guessed.

### Phase 4 — Production Qualification

- [ ] Versioned Java graph schema and compatibility matrix.
- [ ] Incremental indexing with module-level invalidation and concurrency tests.
- [ ] Large-repository memory/time budgets and bounded query latency.
- [ ] Held-out Maven, Gradle, Spring, Kafka, JPA, and MyBatis fixtures.
  - [x] Bounded persistence-adapter slice: independent Maven/Gradle fixtures cover exact-import JPA/Jakarta, Spring Data metadata, and MyBatis annotations; Spring/Kafka breadth remains incomplete.
- [ ] Precision, resolution-rate, unresolved-reason, freshness, mutation, and deletion gates.
  - [x] Persistence-adapter slice gates these dimensions plus stable IDs/anchors, deterministic repeatability, and no fabricated SQL/database/runtime edges.
- [ ] Offline verifier, release evidence, migration notes, and rollback procedure.
  - [x] Persistence-adapter offline verifier/report and rollback notes; the overall Java production gate remains open.

## Enterprise Release Gate

The Java feature may be called enterprise-ready only when all Phase 1 and Phase 2 items are complete, selected Phase 3 adapters have explicit compatibility declarations, and Phase 4 gates pass on held-out repositories. Until then, product surfaces must label Java relationship coverage `partial` and preserve unresolved reasons.

### Completed bounded item: Spring ConfigurationProperties metadata

Exact explicitly imported Spring Boot `@ConfigurationProperties` declarations now expose literal prefix/value metadata for classes/records and explicit unambiguous `@Bean` factory methods. Evidence remains attributed/partial and intentionally does not model runtime binding, member writes, keys, scanning, validation, relaxed variants, nesting, classpath effects, or calls. Decoys, dynamic expressions, ambiguity, and unsupported targets do not produce relationships.
  - [x] Declaration-only Spring lifecycle/condition/profile/scope/primary/lazy/depends-on and transaction-boundary metadata, with literal-only values and fail-closed `@Primary` exact-source resolution. Runtime activation/order/proxy/inheritance semantics remain deferred.

- [x] Spring Data repository declaration metadata phase (source-only exact imports and resolvable generics; opaque queries).
- [x] Bounded MyBatis annotation declaration metadata: exact explicit `@Mapper` and literal `@Select`/`@Insert`/`@Update`/`@Delete` values only; SQL remains opaque and no database/runtime semantics are inferred.
- [ ] MyBatis XML linkage is deferred: the current metadata schema cannot honestly represent independent Java/XML freshness and deletion plus exact namespace and statement anchors, so no partial relationship is emitted.

## Bounded RPC client/server declaration slice
- [x] Exact-import Spring Cloud OpenFeign `@FeignClient` interface declarations with literal service name and optional literal URL/path, plus exact-import literal Spring mapping metadata on unique declared methods.
- [x] Reuse the existing annotated Spring server endpoint representation without asserting that matching paths imply a runtime connection.
- [ ] Runtime networking, service discovery/load balancing, serialization, authentication, retries and fallbacks; placeholders/SpEL, composed annotations, inherited methods and overload resolution remain deliberately unsupported.

### Completed bounded item: Spring Async declaration metadata
- [x] Exact explicit `@Async` imports on directly annotated source classes/methods, with literal executor qualifier retained opaquely, overload-safe identity, anchors/hashes, freshness and fail-closed adversarial coverage.
- [ ] Async runtime calls, executor resolution, thread/scheduling/proxy/exception/ordering semantics, `EnableAsync`, inheritance/composition and external symbols remain deliberately deferred.

### Completed bounded item: Spring Retry declaration metadata
- [x] Exact explicit `@Retryable`/`@Recover` imports on directly annotated source classes/methods, with mechanically parseable literal/class-literal attributes retained opaquely, stable overload-safe identities, anchors/hashes, freshness and fail-closed qualification.
- [ ] Runtime retries, attempt/backoff evaluation, exception matching, recovery dispatch, proxies/AOP, calls, inheritance/composition and external symbols remain deliberately deferred.

### Completed bounded item: Resilience4j CircuitBreaker declaration metadata
- [x] Exact explicit `@CircuitBreaker` import on direct source classes/methods, requiring a literal `name` and optionally retaining literal `fallbackMethod` opaquely, with overload-safe IDs, exact anchors/token hashes, freshness, reconciliation, adversarial coverage, and held-out qualification.
- [ ] Circuit state, thresholds/failure classification, fallback resolution/dispatch, configuration activation, proxies/AOP, calls, inheritance/composition, expressions/placeholders, and external symbols remain deliberately deferred.

### Completed bounded item: Resilience4j RateLimiter declaration metadata
- [x] Exact explicit `@RateLimiter` import on direct source classes/methods, requiring a literal `name` and optionally retaining literal `fallbackMethod` opaquely, with overload-safe IDs, exact anchors/token hashes, freshness, reconciliation, adversarial coverage, and held-out qualification.
- [ ] Runtime permits/waiting/refresh periods, fallback resolution/dispatch, configuration activation, proxies/AOP, calls, inheritance/composition, expressions/placeholders, and external symbols remain deliberately deferred.


### Completed bounded item: Resilience4j Bulkhead declaration metadata
- [x] Exact explicit `@Bulkhead` import on direct source classes/methods, requiring a literal `name` and optionally retaining literal `fallbackMethod` opaquely, with overload-safe IDs, exact anchors/token hashes, freshness, reconciliation, adversarial coverage, and held-out qualification.
- [ ] Runtime concurrency limits, queueing/isolation, fallback resolution/dispatch, configuration activation, proxies/AOP, calls, inheritance/composition, expressions/placeholders, and external symbols remain deliberately deferred.

### Completed bounded item: Resilience4j TimeLimiter declaration metadata
- [x] Exact explicit `@TimeLimiter` import on direct source classes/methods, requiring literal `name` and optionally retaining literal `fallbackMethod` opaquely, with overload-safe IDs, exact anchors/token hashes, freshness/reconciliation, adversarial coverage, and held-out Maven/Gradle qualification.


### Completed bounded item: Resilience4j Retry declaration metadata
- [x] Exact explicit `io.github.resilience4j.retry.annotation.Retry` import on direct source classes/methods, requiring literal `name` and optionally retaining literal `fallbackMethod` opaquely, with a declaration kind distinct from Spring Retryable, overload-safe IDs, exact anchors/token hashes, freshness/reconciliation, adversarial coverage, and held-out Maven/Gradle qualification.
- [ ] Runtime retries/backoff, exception matching/configuration, fallback resolution/dispatch, proxies/AOP, calls, inheritance/composition, expressions/placeholders, and external symbols remain deliberately deferred.

### Completed bounded item: Spring Security `@PreAuthorize` declaration metadata
- [x] Exact explicit import on direct source classes/methods, retaining the sole literal expression opaquely, with overload-safe IDs, exact anchors/token hashes, freshness/deletion reconciliation, and adversarial fail-closed coverage.
- [ ] Runtime authorization, expression interpretation/truth, role hierarchy, proxy/AOP, configuration, calls, inheritance/composition, meta-annotations, placeholders/constants, and external symbols remain deliberately deferred.

### Completed bounded item: Spring Security `@PostAuthorize` declaration metadata
- [x] Exact explicit import on direct source classes/methods, retaining the sole literal expression opaquely, with a distinct stable declaration kind, overload-safe IDs, exact anchors/token hashes, freshness/deletion reconciliation, adversarial coverage, and independent Maven/Gradle qualification.
- [ ] SpEL interpretation, authorization outcomes, security context, role hierarchy, proxy/AOP, configuration, calls, inheritance/composition, meta-annotations, aliases, placeholders/constants, and runtime enforcement remain deliberately unsupported.

### Completed bounded item: Spring Security `@PreFilter` declaration metadata
- [x] Exact explicit import on direct source methods, retaining the sole literal `value` and optional literal `filterTarget` opaquely, with a distinct stable declaration kind, overload-safe IDs, exact anchors/token hashes, freshness/deletion reconciliation, adversarial coverage, and independent Maven/Gradle qualification.
- [ ] SpEL interpretation, filtering/authorization outcomes, target/collection resolution, proxy/AOP, configuration, calls, inheritance/composition, aliases/meta-annotations, placeholders/constants, and runtime enforcement remain deliberately unsupported.

### Completed bounded item: Spring Security `@PostFilter` declaration metadata

Exact-import, direct method `@PostFilter` declarations retain the sole literal `value` opaquely. Unsupported or ambiguous source fails closed; no runtime semantics are inferred. Qualification: `python3 tools/verify_java_post_filter_qualification.py`.
