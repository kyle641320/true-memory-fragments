# Java Persistence declaration compatibility

TMF attaches additive, declaration-only metadata to existing Java node claims under `body.graph.persistence_declaration`; unsupported evidence is retained under `persistence_declaration_unresolved`. Existing node IDs, token hashes, bindings, freshness, and reconciliation remain authoritative.

The partial subset requires exact explicit `jakarta.persistence` or `javax.persistence` imports. It recognizes `Entity`, `Embeddable`, `MappedSuperclass`, `Id`, `EmbeddedId`, `IdClass`, `Table`, `Column`, and `JoinColumn`; names/schema/catalog/table/reference values must be string literals and `IdClass` must be a class literal. Wildcard/decoy imports, expressions, ORM runtime behavior, relationships, access strategy, converters, generated values, inheritance behavior, and database schema are not inferred.

## MyBatis annotations

Additive metadata is attached under `body.graph.mybatis_declaration`; rejected evidence is retained under `mybatis_declaration_unresolved`. Owners require the exact explicit `org.apache.ibatis.annotations.Mapper` import. Methods require exact explicit imports of `Select`, `Insert`, `Update`, or `Delete`, and only directly proven string or string-array values are retained as `opaque_declaration_only`.

Constants, concatenation, expressions, providers, `<script>`, `<foreach>`, composed/meta/lookalike annotations, and wildcard imports fail closed with explicit reasons. TMF never infers SQL execution, tables, columns, reads/writes, result mappings, transactions, or runtime calls. XML mapper linkage is deferred because the current schema cannot carry independent Java/XML bindings, freshness/deletion, and exact namespace+statement anchors without unsound partial linkage. Existing node IDs, source anchors, hashes, freshness, and reconciliation remain authoritative.

## Production-qualification evidence

Independent held-out Maven and Gradle sources live under `fixtures/java-persistence-heldout/`; they are intentionally separate from unit-test source strings. Run `python3 tools/verify_java_persistence_qualification.py` offline. The versioned `tmf.java-persistence-qualification.v1` report measures exact expected metadata and unresolved reasons, precision/resolution, worktree freshness, mutation, deletion reconciliation, stable node IDs/anchors, deterministic repeatability, and absence of fabricated database/runtime semantics. The checked report is `reports/java-persistence-qualification/report.{json,md}`.

| Adapter | Qualified bounded subset | Explicitly not claimed |
|---|---|---|
| JPA/Jakarta | exact explicit `javax.persistence`/`jakarta.persistence` imports and literal declaration metadata | ORM runtime, relationships, generated values, access strategy, schema truth |
| Spring Data | exact repository inheritance/generics, derived method names, literal opaque `@Query` metadata | query execution/plans, inferred tables/columns/read/write edges |
| MyBatis annotations | exact `@Mapper` plus literal `Select`/`Insert`/`Update`/`Delete` strings as opaque metadata | SQL parsing, tables/columns/read/write/runtime edges, providers/scripts/dynamic values |
| MyBatis XML | deferred | independent Java/XML bindings, namespace/statement anchors, freshness and deletion |
