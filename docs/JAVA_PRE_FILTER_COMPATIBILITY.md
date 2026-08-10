# Spring Security `@PreFilter` declaration compatibility

TMF records direct method declarations only when `org.springframework.security.access.prepost.PreFilter` is imported exactly and the required `value` is a Java string literal. Optional literal `filterTarget` is retained opaquely. Neither value is parsed, resolved, or evaluated.

Fail-closed: class targets (not allowed by the annotation), constants, computed values, placeholders, malformed/duplicate/unknown attributes, wildcard/static/conflicting imports, local decoys, qualified-only use, aliases/meta-annotations, and ambiguous owners emit no declaration claim. Stable distinct IDs derive from overload-safe method owner IDs; exact annotation anchors and Java token hashes support mutation, deletion, freshness, and reconciliation.

No SpEL meaning, filtering, collection/parameter target resolution, authorization outcome, security context, proxy/AOP, configuration, calls, inheritance/composition, or runtime behavior is inferred.
