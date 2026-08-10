# Spring Security `@PreAuthorize` declaration compatibility

TMF records direct class/method declarations only when `org.springframework.security.access.prepost.PreAuthorize` is imported exactly and its sole `value` is a Java string literal. The literal expression text is retained opaquely and never parsed or evaluated.

Fail-closed: constants, placeholders, malformed/duplicate/unknown attributes, wildcard/static/conflicting imports, local decoys, qualified-only use, and ambiguous owners emit no declaration claim. Stable IDs derive from overload-safe owner IDs; annotation token hashes/anchors support mutation, deletion, freshness, and reconciliation.

No runtime authorization, expression truth, roles/role hierarchy, proxy/AOP, configuration, calls, inheritance/composition, meta-annotations, or external symbols are inferred.
