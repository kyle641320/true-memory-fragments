# Java/Spring bounded phase handoff

Status: **bounded implementation complete; overall Java/enterprise support remains partial**. This is a source handoff, not a new published release.

## Implemented in this worktree

- Conservative tracked-source Java project/module/source-set model, syntax type model, and source symbol index.
- Bounded source-only Java relationships and resolution for inheritance/permits, overrides, calls/constructors, fields reads/writes, type uses, annotations, records/sealed types, exception-syntax traversal, overload applicability, varargs, and a narrow method-generic substitution slice.
- Bounded Spring bean/injection registry: exact explicitly imported stereotypes, explicit `@Bean` producers, annotated injection sites, exact source types, literal qualifiers, and explicit unresolved evidence.
- Bounded annotated Spring MVC/WebFlux API nodes for exact imported controllers/mappings, literal paths and deterministic HTTP methods, linked to unique source handlers.
- Completed bounded `@ConfigurationProperties` declaration metadata: exact explicit import, literal `prefix`/`value`, classes/records, and unambiguous explicit `@Bean` factory methods. Stable attributed relationships are declaration evidence only.

## Conservative limits

Java relationship coverage remains **partial**, and this phase does not establish enterprise readiness. It does not provide compiler/JDT/SCIP semantics, dependency classpaths, dynamic build logic, scanning, conditions/profiles, proxies, lifecycle behavior, reflection/code generation, runtime calls, or complete framework semantics. ConfigurationProperties support does **not** infer binder execution, environment/property keys, relaxed names, member writes, validation, enablement/scanning, nesting, or classpath effects. Dynamic values, decoys, ambiguity, and unsupported targets remain absent or unresolved.

Functional WebFlux `RouterFunction` support is bounded to exact imported, flat builder forms with independently freshness-bound route and handler evidence; ambiguity, unsupported nesting/composition, and dynamic predicates fail closed. Kafka, JPA/Hibernate, MyBatis, RPC, cache, scheduling, transaction, security, and resilience evidence in this worktree remains declaration/source bounded and does not establish runtime behavior.

## Packaging audit

`uv.lock` is an untracked package-manager artifact and remains excluded from the source handoff. Existing caches, virtual environments, build output, egg metadata, state databases, and generated validation reports are excluded from source-only verification, not deleted from the worktree. `python3 tools/verify_java_source_only_smoke.py` recreates the bounded verification inputs in an index-free temporary directory, clears inherited `PYTHONPATH` so repository modules must come from that export, and runs the aggregate runner, focused tests, and compileall there. Installed project dependencies remain prerequisites, as declared by `pyproject.toml`.

## Verification

Exact commands and outcomes are recorded in `RELEASE_MANIFEST.txt`.
