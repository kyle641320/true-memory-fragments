# Java Spring Security `@Secured` compatibility

The bounded adapter recognizes only direct `org.springframework.security.access.annotation.Secured` declarations with one exact explicit import and literal non-empty role strings (single value or array) on unambiguous source classes or methods. Role values are opaque metadata and are never interpreted.

Wildcard, static, conflicting or local annotation declarations; constants, placeholders, mixed/dynamic arrays, duplicates, ambiguous owners, composed/meta annotations, aliases, inheritance and external symbols remain unresolved or omitted. No role hierarchy, authorization decision, proxy/AOP behavior, configuration, calls or runtime enforcement is inferred.
