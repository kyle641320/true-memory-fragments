# Java PreFilter qualification: PASS

- Checks: 18/18
- Held-out declarations: 2
- Held-out unresolved: 13

## Checks

- [x] `independent_maven_fixture`
- [x] `independent_gradle_fixture`
- [x] `deterministic_repeat`
- [x] `exact_literal_metadata`
- [x] `optional_filter_target_retained_opaquely`
- [x] `method_only_and_overload_safe_declarations`
- [x] `stable_ids_under_literal_mutation`
- [x] `token_hash_changes_on_literal_mutation`
- [x] `deletion_reconciliation`
- [x] `dynamic_constant_placeholder_unresolved`
- [x] `filter_target_constant_placeholder_unresolved`
- [x] `unknown_and_duplicate_attributes_unresolved`
- [x] `class_target_rejected`
- [x] `wildcard_and_static_imports_rejected`
- [x] `decoy_annotation_excluded`
- [x] `import_ambiguity_excluded`
- [x] `precise_annotation_anchors`
- [x] `owner_token_hash_changes_on_annotation_mutation`

## Explicit limitations

- Declaration-only: exact explicit Spring Security PreFilter imports and direct annotations are recognized.
- Expression strings are retained as opaque literals; SpEL is never parsed or evaluated.
- Constants, computed expressions, placeholders, wildcard/ambiguous imports, aliases, meta-annotations, and inheritance are unresolved or excluded.
- No authorization outcome, security context, proxying, call graph, or runtime enforcement is inferred.
