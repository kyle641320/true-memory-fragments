# Java field-receiver call resolution

This is a source-defined, syntactic relationship graph, not a Java compiler or
a runtime DI dispatch graph. A call to an injected interface is linked to the
interface declaration, not to a guessed implementation bean.

## Direct receiver support

Java derivation `java.derive.v10` retains v9's direct lookup on a
source-defined top-level receiver type using:

- an exact fully qualified type name;
- an explicit import;
- the caller's package;
- a unique source declaration in an ordinary on-demand (`package.*`) import.

Repository and delegate names follow the same rules. `@Resource` and `@Inject`
do not disable field type collection. Source layout can span modules; this is
repository-wide source lookup, **not** proof of module/classpath accessibility.
Duplicate declarations of a FQN, including across main/test or module roots,
are ambiguous rather than first-match wins. Static on-demand imports are not
package imports. External/classpath and implicit `java.lang` collisions are not
fully modeled; source-only uniqueness is not compiler-equivalent resolution.

For a top-level parameterized receiver, such as `Delegate<Order>`, lookup uses
the outer type. This does not implement generic argument substitution or full
overload inference. Parameterized member types (`Outer<A>.Inner<B>`), arrays,
inferred `var`, lexical type variables and nested receiver types are not
promoted to unrelated top-level types. Local/parameter variable shadowing is
separate from explicit `this.field` access; nested type methods are not methods
of their enclosing receiver. Types are resolved where they were declared, not
rebound by a calling method's type parameters or local classes. Catch and
resource bindings and varargs are distinguished from same-named fields.
Flow-sensitive `instanceof` pattern-variable scopes are not resolved: from a
pattern declaration onward, a same-named bare receiver is conservatively
unknown rather than falling back to the field. Explicit `this.field` remains
separate. Qualified names tolerate Java whitespace/comments around the dots.

## Diagnosing absent edges

1. Inspect the caller declaration's `body.graph.callees` **and**
   `body.graph.unresolved_calls`, available through `retrieve_path`.
2. A resolved call creates a `calls` claim and indexed `edge_endpoints` rows.
   Unresolved calls deliberately do not create guessed endpoints.
3. Type lookup failures now retain their cause, including ambiguous wildcard,
   missing source type, unsupported receiver form, or a method not directly
   declared on the receiver. They are not all flattened into `java_method_not_found`.
4. `coverage=complete` in the warm reverse index means all files in the current
   warm manifest were indexed. It does **not** mean all semantic calls were
   resolved. Java declaration `calls_coverage` remains `partial`.

## Bounded inherited receivers

For source-defined top-level nongeneric hierarchies, bare/`this` inherited
instance fields and inherited methods on statically typed receivers can now
resolve. Parent clauses, field types and method signature types use their own
declaring file's imports. Nearer fields hide farther ones; inherited overloads
are preserved; overrides mask only the same canonical signature. A diamond
with the same original method declaration is deduplicated, not chosen by DFS
order. Method applicability requires supported known argument types.

Unknown/ambiguous parents, generic substitutions, unsupported access, cycles,
nested types, static members, and unrelated competing interface signatures
remain explicit refusals. This conservative hierarchy check also applies when
the receiver declares a method itself but has an incomplete explicit ancestry
(for example an external/JDK superclass): some v9 direct edges therefore become
unresolved. A partially inspected overload set is not presented as complete.

New hierarchy-backed edges and their caller graph declarations bind all
consulted files plus a duplicate-preserving source-symbol digest. Import-only,
field-type, intermediate-parent and overload changes invalidate that context;
new competing source symbols do too. Failed hierarchy lookups carry the same
negative-evidence dependencies so normal warm can repair them. File-level
dependencies deliberately over-invalidate unrelated changes in consulted files;
unrelated method-body changes elsewhere do not change the symbol digest.

This extension does **not** repair all earlier no-parent direct-field or
unqualified/`super` lookup/freshness limitations. The reflex's file-local
declaration projection remains separate from graph-context freshness; it does
not become a cross-file Java proposed-call gate. No claim of fixing a private
repository's particular missing chain follows from these fixtures. The historical
Guava 0/7 sample has not been re-scored by this change. Classpath/module
accessibility, runtime dispatch and DI bean choice are still outside scope.

## Validation and cache migration

`tests.test_java_field_receivers` runs production warm → declaration graph →
call-edge index → read-only retrieval. It contrasts repository/delegate names,
explicit/on-demand imports, and same/cross-module source layout, and includes
negative cases for ambiguity, lexical shadowing and unsupported shapes.
`tests.test_java_members` covers the bounded member lookup contract;
`tests.test_java_inherited_receivers` adds compiled production-path fixtures and
mutation/normal-warm repair checks for both positive and negative graph context.

The Java derivation version change makes older Java claims stale and causes
the next normal `tmf warm` to rederive the affected Java slice. It does not
silently preserve an old incomplete graph as fresh, nor require a storage
schema migration. No live-model experiment is involved.
