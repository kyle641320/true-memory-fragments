# Java Spring Retry declaration compatibility

TMF supports a bounded source-only Spring Retry declaration slice: exact explicit imports of `org.springframework.retry.annotation.Retryable` and `Recover`, directly annotated source classes/methods, overload-safe owners, and mechanically parseable literal boolean/integer/string/string-array/class-literal attributes retained as opaque metadata. `@Recover` is recorded only as a direct declaration marker.

It fails closed for expressions, constants, placeholders/SpEL, wildcard/static/conflicting imports, duplicate/conflicting aliases, malformed/unsupported attributes, decoys, ambiguous owners, inherited/composed annotations and external symbols. TMF never infers retries occurring, runtime attempt counts, backoff timing/evaluation, exception matching, recovery dispatch, proxy/AOP behavior, call edges or operational semantics.

Claims use an additive `claim_retry_decl_*` namespace with annotation anchors/token hashes and ordinary freshness/deletion/reconciliation. Rollback removes this isolated resolver/deriver/ID, tests, fixture, verifier and docs; prior claims and schema readers are unchanged.
