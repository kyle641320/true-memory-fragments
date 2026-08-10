# Java Resilience4j Retry compatibility

TMF recognizes only direct class/method `@Retry` declarations with the exact explicit import `io.github.resilience4j.retry.annotation.Retry`. A non-empty literal `name` is required; literal `fallbackMethod` is optional and opaque. This declaration kind is deterministic and distinct from Spring Retry `org.springframework.retry.annotation.Retryable`.

Dynamic values, constants, placeholders/expressions, unnamed/duplicate/unknown attributes, malformed annotations, wildcard/static/conflicting imports, local decoys, qualified forms, and ambiguous owners fail closed. Runtime retries/backoff, exception matching, configuration, fallback dispatch, proxies/AOP, calls, inheritance/composition, and external symbols are not inferred.

Qualification: `uv run --offline python tools/verify_java_resilience4j_retry_qualification.py`.
