# Spring Security `@PostFilter` declaration compatibility

TMF records direct method declarations only when `org.springframework.security.access.prepost.PostFilter` is imported exactly and its sole `value` is a Java string literal. The expression is retained opaquely and never parsed or evaluated.

The Spring Security source contract defines only `String value()` (and permits METHOD and TYPE targets); unlike `PreFilter`, it has no `filterTarget`. This deliberately conservative adapter accepts methods only and rejects type annotations, `filterTarget`, constants/computed values/placeholders, malformed/duplicate/unknown attributes, wildcard/static/conflicting imports, local decoys, and ambiguous owners.

It does not infer filtering, authorization, security context, proxy/AOP or configuration, calls, inheritance/composition, aliases/meta-annotations, or runtime enforcement. IDs derive from overload-safe owner IDs; bindings anchor the exact annotation with `java_token_sha256`. Mutation changes evidence hashes without changing owner-based identity; deletion removes the declaration on re-derivation.

Contract verified against Spring Security's `core/.../access/prepost/PostFilter.java`: `@Target({ METHOD, TYPE })`, required `String value()`, no other members.
