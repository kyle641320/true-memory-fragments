# Java field-receiver call resolution

This is a source-defined, syntactic relationship graph, not a Java compiler or
a runtime DI dispatch graph. A call to an injected interface is linked to the
interface declaration, not to a guessed implementation bean.

## Direct receiver support

Java derivation `java.derive.v9` resolves directly declared methods on a
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

Inherited injected fields and methods inherited by a typed receiver are still
separate unresolved boundaries. No claim of fixing a private repository's
particular missing chain follows from these synthetic fixtures. The historical
Guava 0/7 field-receiver sample has not been re-scored by this change.

## Validation and cache migration

`tests.test_java_field_receivers` runs production warm → declaration graph →
call-edge index → read-only retrieval. It contrasts repository/delegate names,
explicit/on-demand imports, and same/cross-module source layout, and includes
negative cases for ambiguity, lexical shadowing and unsupported shapes.

The Java derivation version change makes older Java claims stale and causes
the next normal `tmf warm` to rederive the affected Java slice. It does not
silently preserve an old incomplete graph as fresh, nor require a storage
schema migration. No live-model experiment is involved.
