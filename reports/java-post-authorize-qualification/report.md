# Java PostAuthorize qualification: PASS

- Checks: 13/13
- Held-out declarations: 3
- Held-out unresolved: 5

## Checks

- [x] `independent_maven_fixture`
- [x] `independent_gradle_fixture`
- [x] `deterministic_repeat`
- [x] `exact_literal_metadata`
- [x] `class_and_overload_safe_declarations`
- [x] `stable_ids_under_literal_mutation`
- [x] `token_hash_changes_on_literal_mutation`
- [x] `deletion_reconciliation`
- [x] `dynamic_constant_placeholder_unresolved`
- [x] `decoy_annotation_excluded`
- [x] `import_ambiguity_excluded`
- [x] `precise_annotation_anchors`
- [x] `owner_token_hash_changes_on_annotation_mutation`

## Explicit limitations

- Declaration-only: exact explicit Spring Security PostAuthorize imports and direct annotations are recognized.
- Expression strings are retained as opaque literals; SpEL is never parsed or evaluated.
- Constants, computed expressions, placeholders, wildcard/ambiguous imports, aliases, meta-annotations, and inheritance are unresolved or excluded.
- No authorization outcome, security context, proxying, call graph, or runtime enforcement is inferred.
