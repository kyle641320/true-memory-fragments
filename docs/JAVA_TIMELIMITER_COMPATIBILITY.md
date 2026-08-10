# Java Resilience4j TimeLimiter compatibility

TMF recognizes only direct source class and method declarations using the exact explicit import
`io.github.resilience4j.timelimiter.annotation.TimeLimiter`. `name` is required and
`fallbackMethod` is optional; both must be non-dynamic string literals retained as opaque metadata.

Stable claims use overload-safe declaration owners and bind to the exact annotation line range and
Java token hash. Normal freshness and path reconciliation stale mutations and remove deletions.

Wildcard/static/conflicting imports, local decoys, aliases/composed annotations, constants,
placeholders/expressions, duplicate, malformed, unnamed or unknown attributes, missing/empty names,
and ambiguous owners fail closed. TMF does not infer timeout or cancellation behavior, future or
reactive semantics, configuration activation, fallback resolution/dispatch, proxy/AOP behavior,
calls, inheritance, composition, or any runtime behavior.

Qualification: `python3 tools/verify_java_time_limiter_qualification.py`.
