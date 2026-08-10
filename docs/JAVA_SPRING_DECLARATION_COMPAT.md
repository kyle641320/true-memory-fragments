# Java Spring declaration compatibility

Schema remains `tmf.schema.v2`; metadata is additive under `body.graph.spring_declaration` and unresolved evidence under `spring_declaration_unresolved`. Node and injection edge IDs remain the existing stable path/identity/kind hashes. Source node bindings provide anchors and normal blob/hash freshness; injection claims retain independent injector/bean bindings, so mutation or deletion stales the relationship. Coverage is `partial`, effect is `declaration_only`, and confidence is capped at 0.6.

Supported only with exact explicit imports and literal values: Profile, Scope, Lazy, DependsOn, Primary, Transactional, Conditional/ConditionalOnProperty/ConditionalOnClass (literal strings only). Class literals/classpath checks, meta/composed annotations, SpEL/placeholders, dynamic constants, activation, ordering, inherited annotations, and proxy/interception semantics are deferred rather than inferred.

## Spring Data repositories
Supported declaration-only bases: `Repository`, `CrudRepository`, `ListCrudRepository`, `PagingAndSortingRepository`, and `JpaRepository` under their exact explicit Spring Data imports. Domain/ID bindings require source resolution; wildcard/type-variable/unresolved bindings are reported unresolved. Exact JPA `@Query` literal `value`/`nativeQuery` is retained opaquely; composed/dynamic/classpath-only forms are not inferred.
