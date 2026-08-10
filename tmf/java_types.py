from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable


_PRIMITIVES = {"boolean", "byte", "short", "int", "long", "char", "float", "double", "void"}
_BOXES = {
    "boolean": "Boolean", "byte": "Byte", "short": "Short", "int": "Integer",
    "long": "Long", "char": "Character", "float": "Float", "double": "Double",
}
_UNBOXES = {boxed: primitive for primitive, boxed in _BOXES.items()}
_WIDENING = {
    "byte": ("short", "int", "long", "float", "double"),
    "short": ("int", "long", "float", "double"),
    "char": ("int", "long", "float", "double"),
    "int": ("long", "float", "double"),
    "long": ("float", "double"),
    "float": ("double",),
}
_TYPE_TOKEN_RE = re.compile(r"[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*")


@dataclass(frozen=True)
class JavaType:
    raw: str
    erased: str
    simple_name: str
    array_dims: int = 0
    varargs: bool = False
    primitive: bool = False
    type_arguments: tuple["JavaType", ...] = ()
    wildcard: str | None = None

    @property
    def canonical(self) -> str:
        suffix = "[]" * self.array_dims
        return f"{self.erased}{suffix}"


def _matching_angle(text: str, start: int) -> int | None:
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "<":
            depth += 1
        elif text[index] == ">":
            depth -= 1
            if depth == 0:
                return index
    return None


def _split_arguments(text: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    for index, char in enumerate(text):
        if char == "<":
            depth += 1
        elif char == ">":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(text[start:index].strip())
            start = index + 1
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def parse_java_type(type_text: str) -> JavaType:
    raw = " ".join(type_text.strip().split())
    text = re.sub(r"@(?:[A-Za-z_$][\w$]*\.)*[A-Za-z_$][\w$]*(?:\([^)]*\))?\s*", "", raw).strip()
    varargs = text.endswith("...")
    if varargs:
        text = text[:-3].strip()
    array_dims = 0
    while re.search(r"\[\s*\]\s*$", text):
        array_dims += 1
        text = re.sub(r"\[\s*\]\s*$", "", text).strip()
    wildcard = None
    if text == "?":
        return JavaType(raw, "java.lang.Object", "Object", array_dims, varargs, False, (), "unbounded")
    wildcard_match = re.match(r"^\?\s+(extends|super)\s+(.+)$", text)
    if wildcard_match:
        wildcard = wildcard_match.group(1)
        bound = parse_java_type(wildcard_match.group(2))
        return JavaType(raw, bound.erased, bound.simple_name, array_dims + bound.array_dims, varargs, bound.primitive, bound.type_arguments, wildcard)
    arguments: tuple[JavaType, ...] = ()
    angle = text.find("<")
    if angle >= 0:
        end = _matching_angle(text, angle)
        if end is not None:
            arguments = tuple(parse_java_type(part) for part in _split_arguments(text[angle + 1:end]))
            text = (text[:angle] + text[end + 1:]).strip()
    tokens = _TYPE_TOKEN_RE.findall(text)
    erased = tokens[-1] if tokens else text
    simple = erased.rsplit(".", 1)[-1].rsplit("$", 1)[-1]
    return JavaType(raw, erased, simple, array_dims, varargs, erased in _PRIMITIVES, arguments, wildcard)


def java_type_references(type_text: str) -> tuple[JavaType, ...]:
    root = parse_java_type(type_text)
    found: list[JavaType] = []

    def visit(item: JavaType) -> None:
        if not item.primitive and item.wildcard != "unbounded":
            found.append(item)
        for argument in item.type_arguments:
            visit(argument)

    visit(root)
    return tuple(found)


def _conversion_cost(
    source: str,
    target: str,
    reference_distance: Callable[[str, str], int | None] | None = None,
) -> tuple[int, int] | None:
    """Return a conservative Java invocation-conversion cost.

    Categories are exact, primitive widening, boxing/unboxing, then
    unboxing+widening. Reference hierarchy conversions require symbols and are
    deliberately outside this source-only helper.
    """
    source_type, target_type = parse_java_type(source), parse_java_type(target)
    if source_type.canonical == target_type.canonical:
        return (0, 0)
    if source_type.array_dims or target_type.array_dims:
        return None
    source_name = source_type.simple_name
    target_name = target_type.simple_name
    if source_type.primitive and target_type.primitive:
        widened = _WIDENING.get(source_name, ())
        return (1, widened.index(target_name) + 1) if target_name in widened else None
    if source_type.primitive and _BOXES.get(source_name) == target_name:
        return (2, 0)
    if target_type.primitive and source_name in _UNBOXES:
        unboxed = _UNBOXES[source_name]
        if unboxed == target_name:
            return (2, 0)
        widened = _WIDENING.get(unboxed, ())
        return (3, widened.index(target_name) + 1) if target_name in widened else None
    if not source_type.primitive and not target_type.primitive and reference_distance is not None:
        distance = reference_distance(source, target)
        return (1, distance) if distance is not None and distance > 0 else None
    return None


def unique_applicable_signature(
    argument_types: tuple[str, ...],
    signatures: list[tuple[str, ...] | None],
    reference_distance: Callable[[str, str], int | None] | None = None,
    method_type_parameters: list[dict[str, str | None] | None] | None = None,
) -> int | None:
    """Return the uniquely best applicable signature index, otherwise None.

    Selection uses per-argument Pareto dominance rather than summing unrelated
    conversions. Thus crossing preferences and equal costs remain ambiguous.
    Unknown signatures are never ranked.
    """
    def instantiate(index: int, signature: tuple[str, ...]) -> tuple[tuple[str, ...], bool] | None:
        specs = method_type_parameters[index] if method_type_parameters else None
        if not specs:
            return signature, False
        # This intentionally supports only a single, source-declared method
        # variable occurring as a whole parameter type. Nested shapes and
        # generic varargs require Java's constraint solver and are not guessed.
        if len(specs) != 1:
            return None
        name, bound = next(iter(specs.items()))
        positions = [i for i, target in enumerate(signature) if target == name]
        if not positions or any("<" in target or target.endswith("...") for target in signature):
            return None
        inferred = {argument_types[i] for i in positions}
        if len(inferred) != 1:
            return None
        replacement = next(iter(inferred))
        replacement_type = parse_java_type(replacement)
        if (replacement_type.primitive or replacement_type.type_arguments
                or replacement_type.wildcard or replacement_type.array_dims):
            return None
        if bound:
            bound_type = parse_java_type(bound)
            if (bound_type.type_arguments or bound_type.wildcard or bound_type.array_dims
                    or bound_type.primitive):
                return None
            if replacement_type.canonical != bound_type.canonical:
                if reference_distance is None or reference_distance(replacement, bound) is None:
                    return None
        return tuple(replacement if target == name else target for target in signature), True

    def applicable(variable_phase: bool) -> list[tuple[int, tuple[tuple[int, int], ...], bool]]:
        ranked: list[tuple[int, tuple[tuple[int, int], ...], bool]] = []
        for index, signature in enumerate(signatures):
            if signature is None:
                continue
            instantiated = instantiate(index, signature)
            if instantiated is None:
                continue
            signature, generic = instantiated
            variable = bool(signature and signature[-1].endswith("..."))
            targets = signature
            if variable:
                fixed = signature[:-1]
                component = signature[-1][:-3]
                # Generic varargs need substitution/reifiability knowledge which
                # this source-only slice deliberately does not guess.
                if not component or "<" in component:
                    continue
                if variable_phase:
                    if len(argument_types) < len(fixed):
                        continue
                    targets = fixed + (component,) * (len(argument_types) - len(fixed))
                else:
                    # A varargs declaration is also applicable as fixed arity
                    # when its final actual is the exact declared array type.
                    # _conversion_cost deliberately permits only exact array
                    # shapes, avoiding covariance and classpath guesses.
                    if len(argument_types) != len(signature):
                        continue
                    targets = fixed + (component + "[]",)
            elif variable_phase:
                continue
            elif len(signature) != len(argument_types):
                continue
            costs = tuple(_conversion_cost(source, target, reference_distance)
                          for source, target in zip(argument_types, targets))
            if all(cost is not None for cost in costs):
                ranked.append((index, costs, generic))  # type: ignore[arg-type]
        return ranked

    # Java considers fixed arity (including exact-array use of a varargs
    # declaration) before variable-arity expansion.
    ranked = applicable(False)
    if not ranked:
        ranked = applicable(True)
    winners: list[int] = []
    for index, costs, generic in ranked:
        dominated = any(
            all(other <= cost for other, cost in zip(other_costs, costs))
            and (any(other < cost for other, cost in zip(other_costs, costs))
                 or (other_costs == costs and generic and not other_generic))
            for other_index, other_costs, other_generic in ranked if other_index != index
        )
        if not dominated:
            winners.append(index)
    return winners[0] if len(winners) == 1 else None
