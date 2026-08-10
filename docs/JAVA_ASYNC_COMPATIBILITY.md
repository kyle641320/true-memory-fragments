# Java Spring Async declaration compatibility

TMF supports a deliberately bounded, source-only Spring `@Async` declaration slice.

## Supported
- Exact explicit `org.springframework.scheduling.annotation.Async` imports.
- Direct annotations on source-defined classes and methods, including overload-safe owner identity.
- No argument, or mechanically parseable literal string `value`/`executor` qualifier retained as opaque metadata.
- Stable owner-derived IDs, exact annotation token hashes/anchors, mutation freshness, deletion and reconciliation.
- Method declarations carry the source-metadata precedence marker already used by the transaction declaration schema; it is not runtime interpretation.

## Fail closed / deferred
Dynamic constants, placeholders/SpEL, wildcard/static or conflicting imports, duplicate/conflicting aliases, same-simple-name decoys, malformed/unsupported values, ambiguous owners, inherited/composed annotations, external symbols, and `@EnableAsync` inference produce no declaration claim. TMF infers no async calls, executor binding, threads, scheduling, proxy behavior, exceptions, ordering, or other runtime semantics.

Rollback is removal of the async resolver/deriver/ID integration and its isolated tests, fixture, verifier and documentation; prior claims remain compatible because this adds a new claim prefix and metadata only.
