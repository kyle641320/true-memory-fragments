"""Post-processing oracle for the *bounded* M10 successor insertion task.

This is not a general Java semantic equivalence checker.  The caller supplies
the sealed, unedited T1 source as ``reference_source``.  A candidate may add one
call to the existing no-op hook, plus comments/whitespace, and nothing else.
Removing hook expression statements must recover the entire reference AST.
That restriction makes placement assessment possible without pretending to
prove reachability of arbitrary newly written Java.  Compilation is a separate
measurement; no compilation/model execution occurs here.

Oracle details and diagnostics belong to post-processing only, never model
messages or model-visible tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from tmf.java_extract import _language_and_parser


PACKAGE = "com.google.common.eventbus"
OWNER = f"{PACKAGE}.Dispatcher.PerThreadQueuedDispatcher"
CURRENT_METHOD = f"{OWNER}.dispatchPreparedSubscriber(EventWithPreparedSubscriber):void"
OBSOLETE_METHOD = f"{OWNER}.dispatch(Object,Iterator<Subscriber>):void"
HOOK_METHOD = f"{OWNER}.hook():void"
COMMENTS = frozenset({"line_comment", "block_comment"})
CLASS_DECLARATIONS = frozenset(
    {"class_declaration", "interface_declaration", "enum_declaration", "record_declaration"}
)


@dataclass(frozen=True)
class PlacementScore:
    # The original fields remain available to existing result consumers.
    parse_ok: bool
    syntax_error: bool
    hook_definition_count: int
    hook_call_count: int
    correct_current_boundary: bool
    obsolete_queue_loop: bool
    other_incorrect_placement: bool
    enclosing_methods: tuple[str, ...]
    # Kept for schema compatibility only; placement no longer uses regex.
    diagnostic_regex_wrong_inline: bool
    outcome: str = "unclassified"
    constraint_violations: tuple[str, ...] = ()

    @property
    def semantic_pass(self) -> bool:
        return (
            self.parse_ok
            and not self.constraint_violations
            and self.hook_definition_count == 1
            and self.hook_call_count == 1
            and self.correct_current_boundary
            and not self.obsolete_queue_loop
            and not self.other_incorrect_placement
        )


def _walk(node: Any) -> Iterable[Any]:
    yield node
    for child in node.children:
        yield from _walk(child)


def _has_java_unicode_escape(source: str) -> bool:
    """Fail closed on Java's pre-lexing escapes rather than trust a split parse.

    javac expands eligible Unicode escapes *before* recognizing comments.  A
    tree-sitter comment can therefore hide live Java statements after an
    escaped newline.  This bounded fixture contains no such escapes; accepting
    them would require a separately validated Java Unicode translation pass.
    Conservatively reject even ineligible/escaped occurrences in strings.
    """
    for index, char in enumerate(source):
        if char != "\\" or index + 1 == len(source) or source[index + 1] != "u":
            continue
        end = index + 1
        while end < len(source) and source[end] == "u":
            end += 1
        digits = source[end : end + 4]
        if len(digits) == 4 and all(char in "0123456789abcdefABCDEF" for char in digits):
            return True
    return False


def _text(data: bytes, node: Any | None) -> str:
    if node is None:
        return ""
    return data[node.start_byte : node.end_byte].decode("utf-8")


def _named(node: Any) -> list[Any]:
    return [child for child in node.named_children if child.type not in COMMENTS]


def _tokens(data: bytes, node: Any | None) -> str:
    """Token text without trivia, for signatures/identifiers, not scoring code."""
    if node is None or node.type in COMMENTS:
        return ""
    if not node.children:
        return _text(data, node)
    return "".join(_tokens(data, child) for child in node.children)


def _ast(data: bytes, node: Any, excluded: frozenset[int] = frozenset()) -> Any:
    """Full CST/AST shape with token values, ignoring only trivia/removals."""
    if node.type in COMMENTS or node.id in excluded:
        return None
    if not node.children:
        return (node.type, _text(data, node))
    children = []
    for index, child in enumerate(node.children):
        value = _ast(data, child, excluded)
        if value is not None:
            children.append((node.field_name_for_child(index), value))
    return (node.type, tuple(children))


def _name(data: bytes, node: Any) -> str:
    return _text(data, node.child_by_field_name("name"))


def _package(data: bytes, root: Any) -> str:
    declarations = [child for child in _named(root) if child.type == "package_declaration"]
    if len(declarations) != 1:
        return "<missing-or-ambiguous-package>"
    identifiers = [child for child in _named(declarations[0]) if child.type in {"identifier", "scoped_identifier"}]
    return _tokens(data, identifiers[0]) if len(identifiers) == 1 else "<unknown-package>"


def _method_identity(data: bytes, method: Any, package: str) -> str:
    owners: list[str] = []
    current = method.parent
    while current is not None:
        if current.type in CLASS_DECLARATIONS:
            owners.append(_name(data, current))
        elif current.type == "class_body" and current.parent is not None and current.parent.type == "object_creation_expression":
            owners.append("<anonymous>")
        current = current.parent
    parameters = method.child_by_field_name("parameters")
    types = []
    if parameters is not None:
        for parameter in _named(parameters):
            parameter_type = _tokens(data, parameter.child_by_field_name("type"))
            dimensions = _tokens(data, parameter.child_by_field_name("dimensions"))
            suffix = "..." if parameter.type == "spread_parameter" else ""
            types.append(parameter_type + dimensions + suffix)
    owner = ".".join([package, *reversed(owners)])
    return f"{owner}.{_name(data, method)}({','.join(types)}):{_tokens(data, method.child_by_field_name('type'))}"


def _enclosing_method(data: bytes, node: Any, package: str) -> str:
    current = node.parent
    while current is not None:
        if current.type == "method_declaration":
            return _method_identity(data, current, package)
        current = current.parent
    return "<none>"


def _identifier(data: bytes, node: Any | None, value: str) -> bool:
    return node is not None and node.type == "identifier" and _text(data, node) == value


def _field(data: bytes, node: Any | None, receiver: str, field: str) -> bool:
    return (
        node is not None
        and node.type == "field_access"
        and _identifier(data, node.child_by_field_name("object"), receiver)
        and _identifier(data, node.child_by_field_name("field"), field)
    )


def _arguments(invocation: Any) -> list[Any]:
    arguments = invocation.child_by_field_name("arguments")
    return _named(arguments) if arguments is not None else []


def _direct_invocation(statement: Any | None) -> Any | None:
    if statement is None or statement.type != "expression_statement":
        return None
    children = _named(statement)
    return children[0] if len(children) == 1 and children[0].type == "method_invocation" else None


def _current_handoff(data: bytes, statement: Any) -> bool:
    invocation = _direct_invocation(statement)
    if invocation is None:
        return False
    args = _arguments(invocation)
    return (
        _name(data, invocation) == "dispatchEvent"
        and _field(data, invocation.child_by_field_name("object"), "prepared", "subscriber")
        and len(args) == 1
        and _field(data, args[0], "prepared", "event")
    )


def _queue_handoff(data: bytes, statement: Any) -> bool:
    invocation = _direct_invocation(statement)
    if invocation is None:
        return False
    args = _arguments(invocation)
    return (
        _name(data, invocation) == "dispatchQueuedSubscriber"
        and invocation.child_by_field_name("object") is None
        and len(args) == 2
        and _field(data, args[0], "nextEvent", "event")
        and _identifier(data, args[1], "nextSubscriber")
    )


def _queue_loop_body(data: bytes, method: Any) -> Any | None:
    """Identify the particular inner subscriber loop, not any dispatch method."""
    bodies = []
    for node in _walk(method):
        if node.type != "while_statement":
            continue
        condition = node.child_by_field_name("condition")
        if condition is None or condition.type != "parenthesized_expression":
            continue
        children = _named(condition)
        if len(children) != 1 or children[0].type != "method_invocation":
            continue
        invocation = children[0]
        body = node.child_by_field_name("body")
        if (
            _name(data, invocation) == "hasNext"
            and _field(data, invocation.child_by_field_name("object"), "nextEvent", "subscribers")
            and not _arguments(invocation)
            and body is not None
            and body.type == "block"
            and sum(_queue_handoff(data, item) for item in _named(body)) == 1
            and node.parent is not None
            and node.parent.type == "block"
            and node.parent.parent is not None
            and node.parent.parent.type == "while_statement"
        ):
            bodies.append(body)
    return bodies[0] if len(bodies) == 1 else None


def _hook_receiver_allowed(data: bytes, invocation: Any) -> bool:
    receiver = invocation.child_by_field_name("object")
    if receiver is None:
        return True
    if receiver.type == "this":
        return True
    # Qualified this names the same lexically enclosing instance; an arbitrary
    # object named e.g. `prepared` must not count as the existing hook.
    if receiver.type != "field_access":
        return False
    field = receiver.child_by_field_name("field")
    qualifier = _tokens(data, receiver.child_by_field_name("object"))
    return field is not None and field.type == "this" and qualifier in {
        "PerThreadQueuedDispatcher", "Dispatcher.PerThreadQueuedDispatcher", OWNER,
    }


def _reference_error(data: bytes, root: Any) -> str | None:
    package = _package(data, root)
    methods = [node for node in _walk(root) if node.type == "method_declaration"]
    by_identity: dict[str, list[Any]] = {}
    for method in methods:
        by_identity.setdefault(_method_identity(data, method, package), []).append(method)
    if any(len(by_identity.get(identity, [])) != 1 for identity in (CURRENT_METHOD, OBSOLETE_METHOD, HOOK_METHOD)):
        return "reference_missing_or_ambiguous_required_method_signature"
    if sum(_name(data, method) == "hook" for method in methods) != 1:
        return "reference_hook_definition_count"
    if any(node.type == "method_invocation" and _name(data, node) == "hook" for node in _walk(root)):
        return "reference_already_contains_hook_call"
    hook_body = by_identity[HOOK_METHOD][0].child_by_field_name("body")
    if hook_body is None or _named(hook_body):
        return "reference_hook_is_not_noop"
    current_body = by_identity[CURRENT_METHOD][0].child_by_field_name("body")
    if current_body is None or len(_named(current_body)) != 1 or not _current_handoff(data, _named(current_body)[0]):
        return "reference_current_handoff_shape"
    if _queue_loop_body(data, by_identity[OBSOLETE_METHOD][0]) is None:
        return "reference_obsolete_loop_shape"
    return None


def score_placement_ast(source: str, *, reference_source: str) -> PlacementScore:
    """Score against a caller-sealed T1 fixture, without running Java or models.

    ``outcome`` is exhaustive.  ``constraint_violations`` records disallowed
    program edits separately from placement.  With multiple calls, old flags
    can describe both real sites, but ``semantic_pass`` is necessarily false.
    """
    data, reference_data = source.encode("utf-8"), reference_source.encode("utf-8")
    try:
        _, parser = _language_and_parser()
        root = parser.parse(data).root_node
        reference_root = parser.parse(reference_data).root_node
    except Exception:
        return PlacementScore(False, False, 0, 0, False, False, False, (), False,
                              "parser_unavailable", ("java_parser_unavailable",))

    package = _package(data, root)
    methods = [node for node in _walk(root) if node.type == "method_declaration"]
    definitions = [node for node in methods if _name(data, node) == "hook"]
    calls = [node for node in _walk(root) if node.type == "method_invocation" and _name(data, node) == "hook"]
    enclosing = tuple(_enclosing_method(data, call, package) for call in calls)
    violations: list[str] = []
    parse_ok = not root.has_error
    if not parse_ok:
        violations.append("candidate_syntax_error")
    reference_error = "reference_syntax_error" if reference_root.has_error else _reference_error(reference_data, reference_root)
    if _has_java_unicode_escape(reference_source):
        reference_error = "reference_java_unicode_escape_not_supported"
    if reference_error:
        violations.append(reference_error)
    unicode_escape = _has_java_unicode_escape(source)
    if unicode_escape:
        violations.append("java_unicode_escape_not_supported")
    if len(definitions) != 1:
        violations.append("expected_exactly_one_hook_definition")
    if len(calls) != 1:
        violations.append("expected_exactly_one_hook_call")

    removable = [call.parent for call in calls if _direct_invocation(call.parent) == call]
    if len(removable) != len(calls):
        violations.append("hook_must_be_a_standalone_expression_statement")
    if any(_arguments(call) for call in calls):
        violations.append("hook_must_have_no_arguments")
    if any(not _hook_receiver_allowed(data, call) for call in calls):
        violations.append("hook_must_target_existing_lexical_instance")
    unchanged = (
        parse_ok
        and not reference_error
        and not unicode_escape
        and _ast(data, root, frozenset(node.id for node in removable)) == _ast(reference_data, reference_root)
    )
    if not unchanged:
        violations.append("program_changed_beyond_hook_insertion")

    placements: list[str] = []
    method_by_identity = {_method_identity(data, method, package): method for method in methods}
    obsolete_method = method_by_identity.get(OBSOLETE_METHOD)
    obsolete_body = _queue_loop_body(data, obsolete_method) if obsolete_method is not None else None
    current_method = method_by_identity.get(CURRENT_METHOD)
    current_body = current_method.child_by_field_name("body") if current_method is not None else None
    for call, identity in zip(calls, enclosing):
        statement = call.parent
        placement = "other"
        if unchanged and not _arguments(call) and _hook_receiver_allowed(data, call) and _direct_invocation(statement) == call:
            if identity == CURRENT_METHOD and statement.parent == current_body:
                siblings = _named(current_body)
                index = siblings.index(statement)
                if index + 1 < len(siblings) and _current_handoff(data, siblings[index + 1]):
                    placement = "current"
            elif identity == OBSOLETE_METHOD and statement.parent == obsolete_body:
                placement = "obsolete"
        placements.append(placement)

    correct = "current" in placements
    obsolete = "obsolete" in placements
    other = "other" in placements
    if not parse_ok:
        outcome = "parse_error"
    elif reference_error:
        outcome = "invalid_reference"
    elif any(value != "expected_exactly_one_hook_call" for value in violations):
        outcome = "constraint_violation"
    elif not calls:
        outcome = "missing_hook"
    elif len(calls) != 1:
        outcome = "multiple_hooks"
    elif correct:
        outcome = "correct_current_boundary"
    elif obsolete:
        outcome = "obsolete_queue_loop"
    else:
        outcome = "other_incorrect_placement"
    return PlacementScore(
        parse_ok, not parse_ok, len(definitions), len(calls), correct, obsolete,
        other, enclosing, False, outcome, tuple(violations),
    )
