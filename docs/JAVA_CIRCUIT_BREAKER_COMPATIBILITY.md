# Java Resilience4j CircuitBreaker compatibility

TMF recognizes only direct source declarations using the exact explicit import
`io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker`. `name` is
required and `fallbackMethod` is optional; both must be non-dynamic string
literals and are retained as opaque metadata.

Stable claims are owned by overload-safe source declaration IDs and bind to the
exact annotation line range and Java token hash. Normal source freshness and
path reconciliation therefore stale mutated annotations and remove deleted
declarations.

Wildcard/static/conflicting imports, local decoys, aliases/composed annotations,
constants, placeholders/expressions, duplicate/unknown attributes, missing or
empty names, and ambiguous owners fail closed. TMF does not resolve the fallback
method or infer circuit state, thresholds, failures, configuration activation,
runtime dispatch, calls, proxy/AOP, inheritance, or composition.

Qualification: `python3 tools/verify_java_circuit_breaker_qualification.py`.
