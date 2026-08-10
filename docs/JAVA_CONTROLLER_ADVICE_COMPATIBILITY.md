# Java ControllerAdvice compatibility

TMF conservatively records direct `@ControllerAdvice` presence on class and interface declarations only when the simple name is bound by the single exact non-static import `org.springframework.web.bind.annotation.ControllerAdvice`.

Annotation arguments, wildcard/static/conflicting imports, local shadowing, local declarations, decoys, aliases, and meta-annotations fail closed. The claim records the Spring Web namespace and precise annotation token anchor/hash. It does not infer runtime scope, exception dispatch, bean discovery, advice behavior, inheritance, or application wiring.
