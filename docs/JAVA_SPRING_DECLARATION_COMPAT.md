# Java Spring declaration compatibility

Schema remains `tmf.schema.v2`; metadata is additive under `body.graph.spring_declaration` and unresolved evidence under `spring_declaration_unresolved`. Node and injection edge IDs remain the existing stable path/identity/kind hashes. Source node bindings provide anchors and normal blob/hash freshness; injection claims retain independent injector/bean bindings, so mutation or deletion stales the relationship. Coverage is `partial`, effect is `declaration_only`, and confidence is capped at 0.6.

Supported only with exact explicit imports and literal values: Profile, Scope, Lazy, DependsOn, Primary, Transactional, Conditional/ConditionalOnProperty/ConditionalOnClass (literal strings only). Class literals/classpath checks, meta/composed annotations, SpEL/placeholders, dynamic constants, activation, ordering, inherited annotations, and proxy/interception semantics are deferred rather than inferred.


## Aggregate qualifier traceability

`tools/java_qualification_manifest.json` names each independently gated qualifier. The declaration adapters added in the current unreleased worktree map to bounded capabilities as follows:

| Manifest key | Bounded source evidence |
| --- | --- |
| `bean` | direct exact-import `@Bean` factory declaration |
| `component`, `configuration`, `controller`, `repository_stereotype`, `service` | direct exact-import Spring stereotype declaration |
| `configuration_properties` | direct exact-import, literal `prefix`/`value` configuration-property declaration |
| `autowired` | metadata-free direct Spring `@Autowired` presence on a constructor, method, or single-declarator field; `required` metadata and injection behavior are not inferred |
| `cross_origin` | direct exact-import, literal-only `@CrossOrigin` declaration metadata |
| `init_binder`, `model_attribute`, `response_body`, `response_status` | direct exact-import Spring Web declaration metadata on supported source owners |
| `rest_controller`, `rest_controller_advice` | direct exact-import composed web stereotype presence; focused limits are documented in `JAVA_REST_CONTROLLER_COMPATIBILITY.md` and `JAVA_REST_CONTROLLER_ADVICE_COMPATIBILITY.md` |
| `inject` | metadata-free direct `jakarta.inject.Inject` presence on a constructor, method, or single-declarator field; no injection behavior is inferred |
| `named` | metadata-free direct `jakarta.inject.Named` presence on a class, method, or single-declarator field; the legal empty default is accepted but no name is inferred |
| `singleton` | metadata-free direct `jakarta.inject.Singleton` presence on a class; no scope or instance behavior is inferred |
| `scope`, `lazy`, `primary` | direct exact-import bean declaration metadata with literal-only attributes where applicable |
| `post_construct`, `pre_destroy` | metadata-free direct exact-import `jakarta.annotation` lifecycle-method presence; legacy `javax.annotation` and lifecycle behavior are not inferred |
| `resource` | metadata-free direct `jakarta.annotation.Resource` presence on a class, method, or single-declarator field |
| `session_attributes` | direct exact-import, literal-only `@SessionAttributes` declaration metadata |

Each key has a same-named `tools/verify_java_<key>_qualification.py` gate and an independent `fixtures/java-<key-with-hyphens>-heldout/` Maven/Gradle corpus. Those fast qualifiers analyze source and validate build-file paths; they do **not** execute Gradle. Real compilation is an explicit integration gate: `TMF_GRADLE=/root/.local/bin/gradle python3 tools/verify_java_gradle_integration.py`. It runs `gradle --no-daemon --max-workers=1 --console=plain clean build` only for the manifest's bounded `gradle_integration_verifiers` set (`autowired`, `resource`, `inject`, `singleton`, `named`, `post_construct`, and `pre_destroy` in this batch), keeping downloads and daemon startup out of unit tests. Older fixtures with historically incomplete Gradle dependencies remain technical debt and are not claimed as compiled.

Exact accepted owners and attributes remain adapter-specific and fail closed: wildcard/static/conflicting imports, local decoys, unsupported targets or attributes, dynamic values, duplicates, ambiguous owners, and composed/meta/inherited forms are not promoted. `autowired`, `resource`, and `inject` additionally reject all metadata, static owners, anonymous/local owners, and multi-declarator fields so every accepted owner has one stable identity. `named` accepts only metadata-free use (the annotation's legal empty default), classes/methods/single-declarator fields, and infers no name; explicit values, parameters, anonymous/local owners, and unsupported type targets fail closed. `singleton` accepts direct classes only and rejects metadata, interfaces, records, enums, local classes, and all non-class targets. These facts do not establish scanning, bean creation, dependency injection, constructor selection, method invocation, naming/lookup, MVC dispatch, CORS enforcement, data binding, status handling, serialization, session behavior, lifecycle invocation/order, proxying, or any other runtime effect.

## Spring Data repositories
Supported declaration-only bases: `Repository`, `CrudRepository`, `ListCrudRepository`, `PagingAndSortingRepository`, and `JpaRepository` under their exact explicit Spring Data imports. Domain/ID bindings require source resolution; wildcard/type-variable/unresolved bindings are reported unresolved. Exact JPA `@Query` literal `value`/`nativeQuery` is retained opaquely; composed/dynamic/classpath-only forms are not inferred.
