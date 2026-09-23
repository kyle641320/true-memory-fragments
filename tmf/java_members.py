"""Bounded, source-only lookup for inherited Java instance members.

This is deliberately not a Java compiler.  An incomplete hierarchy, generic
substitution, lexical type ambiguity, or unsupported invocation conversion is a
refusal, not permission to select the first declaration.  The dependency list
includes inspected source files on *both* successful and unsuccessful lookups;
the caller is responsible for binding those files and the source-symbol universe
to freshness.  Resolver instances belong to one immutable derivation snapshot.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .extract import ClassNode
from .java_index import JavaSymbol, java_package, java_project_index
from .java_types import unique_applicable_signature


_TYPE_KINDS = {"class_declaration", "interface_declaration"}
_LEXICAL_TYPE_KINDS = _TYPE_KINDS | {
    "enum_declaration", "record_declaration", "annotation_type_declaration",
}
_IDENTIFIER = re.compile(r"[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*\Z")
_PRIMITIVES = {"boolean", "byte", "short", "char", "int", "long", "float", "double"}
_JAVA_LANG = {
    "Object", "String", "Boolean", "Byte", "Short", "Character", "Integer",
    "Long", "Float", "Double", "Number", "Throwable", "Exception",
    "RuntimeException", "Error", "Class", "Void",
}
_BOXES = {
    "boolean": "java.lang.Boolean", "byte": "java.lang.Byte",
    "short": "java.lang.Short", "char": "java.lang.Character",
    "int": "java.lang.Integer", "long": "java.lang.Long",
    "float": "java.lang.Float", "double": "java.lang.Double",
}
_UNBOXES = {value: key for key, value in _BOXES.items()}
_MAX_TYPES = 128


@dataclass(frozen=True)
class FieldLookup:
    target_path: str | None = None
    target_qualname: str | None = None
    dependency_paths: tuple[str, ...] = ()
    reason: str | None = None


@dataclass(frozen=True)
class MethodLookup:
    method: ClassNode | None = None
    dependency_paths: tuple[str, ...] = ()
    reason: str | None = None


class _Refusal(Exception):
    pass


@dataclass
class _Source:
    path: str
    text: str
    data: bytes
    root: Any
    package: str
    imports: dict[str, str]
    wildcard_imports: set[str]
    conflicting_imports: set[str]
    types: dict[str, list[Any]]
    methods: list[ClassNode]


@dataclass
class _Type:
    source: _Source
    name: str
    node: Any

    @property
    def key(self) -> tuple[str, str]:
        return self.source.path, self.name

    @property
    def interface(self) -> bool:
        return self.node.type == "interface_declaration"


@dataclass
class _Hierarchy:
    root: _Type
    types: dict[tuple[str, str], _Type]
    parents: dict[tuple[str, str], tuple[tuple[str, str], ...]]

    def ancestors(self, key: tuple[str, str]) -> set[tuple[str, str]]:
        found: set[tuple[str, str]] = set()
        pending = list(self.parents[key])
        while pending:
            parent = pending.pop()
            if parent not in found:
                found.add(parent)
                pending.extend(self.parents[parent])
        return found

    def wholly_same_package(self, owner: _Type) -> bool:
        # A package-private member is not inherited back into its package after
        # an intervening subclass outside that package.
        for key, item in self.types.items():
            if key == owner.key or owner.key in self.ancestors(key):
                if item.source.package != owner.source.package:
                    return False
        return True


@dataclass
class _Method:
    owner: _Type
    node: Any
    declaration: ClassNode
    signature: tuple[str, ...]


def _text(data: bytes, node: Any) -> str:
    return data[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _name(data: bytes, node: Any) -> str | None:
    named = node.child_by_field_name("name")
    return _text(data, named) if named is not None else None


def _modifiers(node: Any) -> set[str]:
    modifiers = next((child for child in node.named_children if child.type == "modifiers"), None)
    return {child.type for child in modifiers.children if not child.is_named} if modifiers is not None else set()


def _body(node: Any) -> list[Any]:
    body = node.child_by_field_name("body")
    return list(body.named_children) if body is not None else []


def _type_parameters(node: Any) -> set[str]:
    parameters = node.child_by_field_name("type_parameters")
    if parameters is None:
        parameters = next((child for child in node.named_children if child.type == "type_parameters"), None)
    if parameters is None:
        return set()
    # The presence (rather than the spelling) controls hierarchy rejection.
    return {"<type-parameters>"}


def _parent_expressions(item: _Type) -> list[str]:
    found: list[str] = []
    for child in item.node.named_children:
        if child.type not in {"superclass", "super_interfaces", "extends_interfaces"}:
            continue
        entries = list(child.named_children)
        if len(entries) == 1 and entries[0].type == "type_list":
            entries = list(entries[0].named_children)
        found.extend(_text(item.source.data, entry) for entry in entries
                     if entry.type not in {"line_comment", "block_comment"})
    return found


class JavaMemberResolver:
    def __init__(self, repo: Any):
        self.repo = repo
        self.index = java_project_index(repo)
        self._sources: dict[str, _Source] = {}

    def _source(self, path: str, dependencies: set[str]) -> _Source:
        dependencies.add(path)
        if path in self._sources:
            return self._sources[path]
        try:
            from .java_extract import _java_imports, _language_and_parser, extract_java_methods
            text = self.repo.read_file(path)
            data = text.encode("utf-8")
            _, parser = _language_and_parser()
            root = parser.parse(data).root_node
            if root.has_error:
                raise _Refusal("java_inherited_parse_error")
            imports, wildcard_imports, _ = _java_imports(data, root)
            conflicting: set[str] = set()
            import_targets: dict[str, set[str]] = {}
            for child in root.named_children:
                if child.type != "import_declaration":
                    continue
                expression = _text(data, child).strip()[len("import"):].strip().rstrip(";").strip()
                if not expression.startswith("static ") and not expression.endswith(".*"):
                    simple = expression.rsplit(".", 1)[-1]
                    import_targets.setdefault(simple, set()).add(expression)
            conflicting.update(name for name, targets in import_targets.items() if len(targets) > 1)
            types: dict[str, list[Any]] = {}
            for child in root.named_children:
                if child.type in _LEXICAL_TYPE_KINDS:
                    name = _name(data, child)
                    if name:
                        types.setdefault(name, []).append(child)
            source = _Source(path, text, data, root, java_package(text), imports,
                             wildcard_imports, conflicting, types, extract_java_methods(path, text))
        except (OSError, UnicodeError, ImportError) as error:
            raise _Refusal("java_inherited_source_unavailable") from error
        self._sources[path] = source
        return source

    def _type(self, path: str, qualname: str, dependencies: set[str]) -> _Type:
        source = self._source(path, dependencies)
        if "." in qualname:
            raise _Refusal("java_inherited_nested_type_unsupported")
        matches = source.types.get(qualname, [])
        if len(matches) != 1 or matches[0].type not in _TYPE_KINDS:
            raise _Refusal("java_inherited_type_not_unique_or_supported")
        fqn = f"{source.package}.{qualname}" if source.package else qualname
        candidates = [symbol for symbol in self.index.candidates(qualname) if symbol.fqn == fqn]
        dependencies.update(symbol.path for symbol in candidates)
        if len(candidates) != 1 or candidates[0].path != path:
            raise _Refusal("java_inherited_duplicate_type")
        return _Type(source, qualname, matches[0])

    def has_parents(self, path: str, qualname: str) -> bool:
        """Whether the exact top-level declaration has explicit ancestry.

        An uninspectable declaration returns True so callers route it through
        the refusing hierarchy path, not a permissive direct-method fallback.
        """
        try:
            return bool(_parent_expressions(self._type(path, qualname, set())))
        except _Refusal:
            return True

    def check_receiver_type_context(self, path: str, owner_qualname: str,
                                    type_expr: str) -> tuple[tuple[str, ...], str | None]:
        """Do not promote inherited member type names to caller imports.

        This checks the receiver declaration's enclosing type, independently of
        argument types. No explicit parents means existing lexical validation
        suffices. Unknown ancestry cannot prove absence of a shadowing type.
        """
        dependencies: set[str] = set()
        try:
            owner = self._type(path, owner_qualname, dependencies)
            if not _parent_expressions(owner):
                return tuple(sorted(dependencies)), None
            hierarchy = self._hierarchy(path, owner_qualname, dependencies)
            from .java_types import parse_java_type
            leading = parse_java_type(type_expr).erased.split(".", 1)[0]
            for key in hierarchy.ancestors(owner.key):
                ancestor = hierarchy.types[key]
                if any(child.type in _LEXICAL_TYPE_KINDS and _name(ancestor.source.data, child) == leading
                       for child in _body(ancestor.node)):
                    raise _Refusal("java_inherited_receiver_member_type_unsupported")
            return tuple(sorted(dependencies)), None
        except _Refusal as error:
            return tuple(sorted(dependencies)), str(error)

    @staticmethod
    def _shadows(item: _Type, *, method_name: str | None = None) -> set[str]:
        shadows: set[str] = set()
        data = item.source.data

        def variables(node: Any) -> None:
            for child in node.named_children:
                if child.type == "type_parameters":
                    for parameter in child.named_children:
                        name = next((nested for nested in parameter.named_children
                                     if nested.type == "type_identifier"), None)
                        if name is not None:
                            shadows.add(_text(data, name))

        variables(item.node)
        for child in _body(item.node):
            if child.type in _LEXICAL_TYPE_KINDS:
                name = _name(data, child)
                if name:
                    shadows.add(name)
            elif child.type in {"method_declaration", "constructor_declaration"}:
                if method_name is not None and _name(data, child) != method_name:
                    continue
                # With no source position in this API, local type declarations
                # are conservatively considered possible shadows for this
                # method (or all methods when only the caller type is known).
                variables(child)
                pending = list(child.named_children)
                while pending:
                    local = pending.pop()
                    if local.type in _LEXICAL_TYPE_KINDS:
                        name = _name(data, local)
                        if name:
                            shadows.add(name)
                    else:
                        pending.extend(local.named_children)
        return shadows

    def _resolve(self, item: _Type, raw: str, dependencies: set[str], *,
                 shadows: set[str] | None = None) -> JavaSymbol:
        clean = re.sub(r"/\*.*?\*/|//[^\n]*", " ", raw, flags=re.S)
        clean = re.sub(r"\s*\.\s*", ".", clean.strip())
        if not _IDENTIFIER.fullmatch(clean) or clean in _PRIMITIVES | {"void", "var"}:
            raise _Refusal("java_inherited_type_shape_unsupported")
        leading = clean.split(".", 1)[0]
        if leading in (self._shadows(item) if shadows is None else shadows):
            raise _Refusal("java_inherited_lexical_type_unsupported")
        if leading in item.source.conflicting_imports:
            raise _Refusal("java_inherited_ambiguous_import")
        if "." in clean:
            # A source type prefix means a member type, not a package.  Never
            # resolve it as an unrelated top-level type under a same-named path.
            prefixes = clean.split(".")
            for length in range(1, len(prefixes)):
                prefix = ".".join(prefixes[:length])
                enclosing, reason = self.index.resolve(
                    prefix, package=item.source.package, imports=item.source.imports,
                    wildcard_imports=item.source.wildcard_imports,
                )
                if enclosing is not None or "ambiguous" in reason or (length == 1 and prefix in item.source.imports):
                    if enclosing is not None:
                        dependencies.add(enclosing.path)
                    raise _Refusal("java_inherited_nested_type_unsupported")
        symbol, reason = self.index.resolve(clean, package=item.source.package,
                                            imports=item.source.imports,
                                            wildcard_imports=item.source.wildcard_imports)
        if symbol is None:
            if "ambiguous" in reason:
                dependencies.update(candidate.path for candidate in self.index.candidates(clean.rsplit(".", 1)[-1]))
            raise _Refusal("java_inherited_" + reason)
        dependencies.add(symbol.path)
        return symbol

    def _hierarchy(self, path: str, qualname: str, dependencies: set[str]) -> _Hierarchy:
        types: dict[tuple[str, str], _Type] = {}
        parents: dict[tuple[str, str], tuple[tuple[str, str], ...]] = {}
        active: set[tuple[str, str]] = set()

        def visit(item: _Type) -> None:
            if item.key in active:
                raise _Refusal("java_inherited_cycle")
            if item.key in types:
                return
            if len(types) >= _MAX_TYPES:
                raise _Refusal("java_inherited_hierarchy_limit")
            types[item.key] = item
            active.add(item.key)
            if _type_parameters(item.node):
                raise _Refusal("java_inherited_generic_hierarchy_unsupported")
            ancestors: list[tuple[str, str]] = []
            for raw in _parent_expressions(item):
                if "<" in raw or ">" in raw:
                    raise _Refusal("java_inherited_generic_hierarchy_unsupported")
                symbol = self._resolve(item, raw, dependencies)
                parent = self._type(symbol.path, symbol.simple_name, dependencies)
                if "public" not in _modifiers(parent.node) and parent.source.package != item.source.package:
                    raise _Refusal("java_inherited_parent_inaccessible")
                if parent.key in ancestors:
                    raise _Refusal("java_inherited_duplicate_parent")
                ancestors.append(parent.key)
                visit(parent)
            parents[item.key] = tuple(ancestors)
            active.remove(item.key)

        root = self._type(path, qualname, dependencies)
        visit(root)
        hierarchy = _Hierarchy(root, types, parents)
        for item in types.values():
            inherited_shadows: set[str] = set()
            for key in hierarchy.ancestors(item.key):
                inherited_shadows.update(self._shadows(types[key]))
            if any(raw.strip().split(".", 1)[0] in inherited_shadows for raw in _parent_expressions(item)):
                raise _Refusal("java_inherited_lexical_type_unsupported")
        return hierarchy

    def lookup_field(self, path: str, qualname: str, name: str) -> FieldLookup:
        dependencies: set[str] = set()
        try:
            hierarchy = self._hierarchy(path, qualname, dependencies)
            fields: list[tuple[_Type, Any, Any]] = []
            for owner in hierarchy.types.values():
                for node in _body(owner.node):
                    if node.type not in {"field_declaration", "constant_declaration"}:
                        continue
                    for variable in node.named_children:
                        if variable.type == "variable_declarator" and _name(owner.source.data, variable) == name:
                            fields.append((owner, node, variable))
            # A declaration in a subtype hides a same-named ancestor field even
            # when it is private or otherwise unusable from the caller.
            visible = [entry for entry in fields if not any(
                entry[0].key in hierarchy.ancestors(other[0].key)
                for other in fields if other is not entry
            )]
            if not visible:
                raise _Refusal("java_inherited_field_not_found")
            if len(visible) != 1:
                raise _Refusal("java_inherited_field_ambiguous")
            owner, node, variable = visible[0]
            modifiers = _modifiers(node)
            if owner.interface or "static" in modifiers:
                raise _Refusal("java_inherited_static_field_unsupported")
            if owner.key != hierarchy.root.key:
                if "private" in modifiers:
                    raise _Refusal("java_inherited_field_inaccessible")
                if not modifiers & {"public", "protected"} and not hierarchy.wholly_same_package(owner):
                    raise _Refusal("java_inherited_field_inaccessible")
            type_node = node.child_by_field_name("type")
            if type_node is None or any(child.type == "dimensions" for child in variable.named_children):
                raise _Refusal("java_inherited_type_shape_unsupported")
            shadows = self._shadows(owner)
            for key in hierarchy.ancestors(owner.key):
                shadows.update(self._shadows(hierarchy.types[key]))
            symbol = self._resolve(owner, _text(owner.source.data, type_node), dependencies, shadows=shadows)
            target = self._type(symbol.path, symbol.simple_name, dependencies)
            if "public" not in _modifiers(target.node) and target.source.package != owner.source.package:
                raise _Refusal("java_inherited_receiver_type_inaccessible")
            if _type_parameters(target.node):
                raise _Refusal("java_inherited_generic_receiver_unsupported")
            return FieldLookup(symbol.path, symbol.simple_name, tuple(sorted(dependencies)))
        except _Refusal as error:
            return FieldLookup(dependency_paths=tuple(sorted(dependencies)), reason=str(error))

    def _canonical(self, item: _Type, raw: str, dependencies: set[str], shadows: set[str]) -> str:
        clean = re.sub(r"/\*.*?\*/|//[^\n]*", " ", raw, flags=re.S)
        clean = re.sub(r"\s*\.\s*", ".", clean.strip())
        if clean in _PRIMITIVES:
            return clean
        if not _IDENTIFIER.fullmatch(clean) or clean in {"void", "var", "null"}:
            raise _Refusal("java_inherited_signature_type_unsupported")
        if clean.split(".", 1)[0] in shadows:
            raise _Refusal("java_inherited_lexical_type_unsupported")
        if clean.startswith("java.lang.") and clean[len("java.lang."):] in _JAVA_LANG:
            # Do not assume JDK meaning when the source tree itself declares the
            # same fully qualified name.
            if self.index.candidates(clean.rsplit(".", 1)[-1], package="java.lang"):
                raise _Refusal("java_inherited_jdk_name_conflict")
            return clean
        if clean in _JAVA_LANG and clean not in item.source.imports:
            same_package = self.index.candidates(clean, package=item.source.package)
            wildcard = [symbol for symbol in self.index.candidates(clean)
                        if symbol.package in item.source.wildcard_imports]
            if not same_package:
                if wildcard:
                    raise _Refusal("java_inherited_jdk_name_conflict")
                return "java.lang." + clean
        imported = item.source.imports.get(clean)
        if imported and imported[:-5].replace("/", ".") in {"java.lang." + name for name in _JAVA_LANG}:
            if clean in item.source.conflicting_imports:
                raise _Refusal("java_inherited_ambiguous_import")
            return imported[:-5].replace("/", ".")
        symbol = self._resolve(item, clean, dependencies, shadows=shadows)
        target = self._type(symbol.path, symbol.simple_name, dependencies)
        if "public" not in _modifiers(target.node) and target.source.package != item.source.package:
            raise _Refusal("java_inherited_signature_type_inaccessible")
        return symbol.fqn

    def _methods(self, hierarchy: _Hierarchy, name: str, caller: _Type,
                 dependencies: set[str]) -> list[_Method]:
        candidates: list[_Method] = []
        for owner in hierarchy.types.values():
            shadows = self._shadows(owner)
            for key in hierarchy.ancestors(owner.key):
                shadows.update(self._shadows(hierarchy.types[key]))
            for node in _body(owner.node):
                if node.type != "method_declaration" or _name(owner.source.data, node) != name:
                    continue
                modifiers = _modifiers(node)
                if "static" in modifiers or "private" in modifiers:
                    raise _Refusal("java_inherited_method_access_unsupported")
                if "public" not in modifiers and not owner.interface:
                    if caller.source.package != owner.source.package or not hierarchy.wholly_same_package(owner):
                        raise _Refusal("java_inherited_method_inaccessible")
                if _type_parameters(node):
                    raise _Refusal("java_inherited_generic_method_unsupported")
                parameters = node.child_by_field_name("parameters")
                signature: list[str] = []
                for parameter in parameters.named_children if parameters is not None else ():
                    if parameter.type in {"line_comment", "block_comment"}:
                        continue
                    if parameter.type != "formal_parameter":
                        raise _Refusal("java_inherited_signature_type_unsupported")
                    type_node = parameter.child_by_field_name("type")
                    if type_node is None or any(child.type == "dimensions" for child in parameter.named_children):
                        raise _Refusal("java_inherited_signature_type_unsupported")
                    signature.append(self._canonical(owner, _text(owner.source.data, type_node), dependencies, shadows))
                # Match by hash as well as line: several overloads may be on a
                # single line, and each retains the production identity key.
                from .java_extract import java_hash_for_node
                digest = java_hash_for_node(owner.source.text, node)
                matches = [method for method in owner.source.methods
                           if method.qualname == owner.name + "." + name
                           and method.node_kind == "method"
                           and method.class_hash == digest
                           and method.line_start == node.start_point[0] + 1]
                if len(matches) != 1:
                    raise _Refusal("java_inherited_method_identity_ambiguous")
                candidates.append(_Method(owner, node, matches[0], tuple(signature)))
        # Override by normalized declaration-context signature, never name or
        # mere arity.  Unrelated interfaces with the same signature stay
        # ambiguous even if Java could legally merge their abstract contracts.
        selected = [candidate for candidate in candidates if not any(
            candidate.signature == other.signature
            and candidate.owner.key in hierarchy.ancestors(other.owner.key)
            for other in candidates if other is not candidate
        )]
        seen: set[tuple[str, ...]] = set()
        for candidate in selected:
            if candidate.signature in seen:
                raise _Refusal("java_inherited_method_ambiguous")
            seen.add(candidate.signature)
        return selected

    def lookup_method(self, path: str, qualname: str, name: str,
                      argument_types: tuple[str, ...] | list[str] | None, *,
                      caller_path: str, caller_qualname: str) -> MethodLookup:
        dependencies: set[str] = set()
        try:
            hierarchy = self._hierarchy(path, qualname, dependencies)
            caller_parts = caller_qualname.split(".")
            if len(caller_parts) > 2:
                raise _Refusal("java_inherited_nested_caller_unsupported")
            caller = self._type(caller_path, caller_parts[0], dependencies)
            if "public" not in _modifiers(hierarchy.root.node) and hierarchy.root.source.package != caller.source.package:
                raise _Refusal("java_inherited_receiver_type_inaccessible")
            shadows = self._shadows(caller, method_name=caller_parts[1] if len(caller_parts) == 2 else None)
            if argument_types is None or any(not isinstance(argument, str) or not argument for argument in argument_types):
                raise _Refusal("java_inherited_argument_types_unknown")
            if any(argument.strip() not in _PRIMITIVES for argument in argument_types):
                caller_hierarchy = self._hierarchy(caller_path, caller.name, dependencies)
                for key in caller_hierarchy.ancestors(caller.key):
                    shadows.update(self._shadows(caller_hierarchy.types[key]))
            arguments = tuple(self._canonical(caller, argument, dependencies, shadows) for argument in argument_types)
            candidates = self._methods(hierarchy, name, caller, dependencies)
            if not candidates:
                raise _Refusal("java_inherited_method_not_found")
            # All supported methods are nongeneric and fixed-arity, and the
            # override pass rejected duplicate canonical signatures.  An exact
            # full signature therefore strictly dominates every other possible
            # invocation conversion, including an unsupported reference upcast.
            # Do not let an unrelated overload erase this proven match.
            exact = [candidate for candidate in candidates if candidate.signature == arguments]
            if len(exact) == 1:
                return MethodLookup(exact[0].declaration, tuple(sorted(dependencies)))
            signatures: list[tuple[str, ...] | None] = []
            for candidate in candidates:
                signature = candidate.signature
                if len(signature) != len(arguments):
                    signatures.append(None)
                    continue
                incompatible = False
                unsupported = False
                for argument, target in zip(arguments, signature):
                    if argument == target or (argument in _PRIMITIVES and target in _PRIMITIVES):
                        continue
                    if argument in _PRIMITIVES and target == _BOXES[argument]:
                        continue
                    if target in _PRIMITIVES and argument in _UNBOXES:
                        continue
                    if target in _PRIMITIVES:
                        # A known reference other than a JDK wrapper cannot
                        # unbox.  In particular String -> int is impossible.
                        incompatible = True
                        continue
                    if argument in _PRIMITIVES:
                        if target in {"java.lang.Object", "java.lang.Number"}:
                            # Boxing followed by reference widening is outside
                            # the helper's invocation conversion contract.
                            unsupported = True
                        else:
                            # The JDK wrapper cannot acquire a source-defined
                            # superclass/interface.  Neither String nor another
                            # wrapper can accept this primitive by invocation
                            # conversion.  No simple-name boxing shortcut.
                            incompatible = True
                        continue
                    # Unknown reference upcasts must not be silently removed
                    # from the overload set and thereby improve another match.
                    unsupported = True
                if incompatible:
                    signatures.append(None)
                elif unsupported:
                    raise _Refusal("java_inherited_argument_conversion_unsupported")
                else:
                    signatures.append(signature)
            index = unique_applicable_signature(arguments, signatures)
            if index is None:
                raise _Refusal("java_inherited_method_not_uniquely_applicable")
            return MethodLookup(candidates[index].declaration, tuple(sorted(dependencies)))
        except _Refusal as error:
            return MethodLookup(dependency_paths=tuple(sorted(dependencies)), reason=str(error))
