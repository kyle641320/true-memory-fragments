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
| `cross_origin` | direct exact-import, literal-only `@CrossOrigin` declaration metadata |
| `init_binder`, `model_attribute`, `response_body`, `response_status` | direct exact-import Spring Web declaration metadata on supported source owners |
| `rest_controller`, `rest_controller_advice` | direct exact-import composed web stereotype presence; focused limits are documented in `JAVA_REST_CONTROLLER_COMPATIBILITY.md` and `JAVA_REST_CONTROLLER_ADVICE_COMPATIBILITY.md` |
| `scope`, `lazy`, `primary` | direct exact-import bean declaration metadata with literal-only attributes where applicable |
| `post_construct`, `pre_destroy` | direct exact-import Jakarta or Javax lifecycle declaration metadata, with namespace retained |
| `session_attributes` | direct exact-import, literal-only `@SessionAttributes` declaration metadata |

Each key has a same-named `tools/verify_java_<key>_qualification.py` gate and an independent `fixtures/java-<key-with-hyphens>-heldout/` Maven/Gradle corpus. Exact accepted owners and attributes remain adapter-specific and fail closed: wildcard/static/conflicting imports, local decoys, unsupported targets or attributes, dynamic values, duplicates, ambiguous owners, and composed/meta/inherited forms are not promoted. These facts do not establish scanning, bean creation, dependency injection, MVC dispatch, CORS enforcement, data binding, status handling, serialization, session behavior, lifecycle invocation/order, proxying, or any other runtime effect.

## Spring Data repositories
Supported declaration-only bases: `Repository`, `CrudRepository`, `ListCrudRepository`, `PagingAndSortingRepository`, and `JpaRepository` under their exact explicit Spring Data imports. Domain/ID bindings require source resolution; wildcard/type-variable/unresolved bindings are reported unresolved. Exact JPA `@Query` literal `value`/`nativeQuery` is retained opaquely; composed/dynamic/classpath-only forms are not inferred.
