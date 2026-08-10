# Java RPC declaration compatibility

| Source construct | Status | Evidence boundary |
|---|---|---|
| Spring Cloud OpenFeign `@FeignClient` on an interface | Supported (bounded) | Exact explicit import; literal `name`/`value`; optional literal `url` and `path` |
| Spring mapping on a declared client method | Supported (bounded) | Exact explicit import; one literal HTTP method and literal path(s); unique non-overloaded source method |
| Annotated Spring MVC/WebFlux server endpoint | Reused | Existing conservative annotated endpoint adapter; no client/server equivalence edge is asserted |
| placeholders/SpEL, composed annotations, inheritance, ambiguous/unsupported overloads | Fail closed | No RPC API relationship emitted |
| discovery, networking, balancing, serialization, auth, retry, fallback | Unsupported | Runtime semantics are never inferred |

The Feign client annotation and method declaration are two role-typed v2 bindings with independent hashes, anchors, freshness and deletion reconciliation. IDs use the existing stable API relationship namespace, preserving legacy compatibility.
