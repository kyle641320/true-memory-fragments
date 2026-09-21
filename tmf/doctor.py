"""Read-only inspection of the supported Claude Code reflex registration.

This is deliberately not a shell interpreter or a Claude session probe. A passing
result establishes registration and declared Python/Java file-gate capability,
not behavioral correctness or runtime firing.
"""
from __future__ import annotations

import ast
import json
import math
import os
from pathlib import Path
import re
import shutil


REQUIRED_TOOLS = ("Read", "Edit", "Write")
UNARMED_WARNING = "reflex NOT armed — operating as opt-in memory"
_HOOK_NAME = "pre_tool_use.py"
_MAX_READ = 1_048_576
_MAX_SOURCE_ENTRIES = 100_000
_MAX_SOURCE_DEPTH = 64
_SOURCE_EXCLUSIONS = frozenset({".git", ".tmf", ".venv", "venv", "__pycache__", "node_modules"})
_SOURCE_LANGUAGES = {
    ".py": "python", ".java": "java", ".js": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".go": "go", ".rs": "rust",
    ".rb": "ruby", ".c": "c", ".h": "c", ".cpp": "cpp", ".hpp": "cpp",
    ".cc": "cpp", ".hh": "cpp", ".cs": "csharp", ".swift": "swift",
    ".kt": "kotlin", ".kts": "kotlin", ".php": "php", ".scala": "scala",
    ".ex": "elixir", ".exs": "elixir", ".erl": "erlang", ".hrl": "erlang",
    ".elm": "elm",
}
_CHECKED_LANGUAGES = frozenset({"python", "java"})
_SHELL_WORD = re.compile(r'''"([^"\\]*)"|'([^']*)'|([^\s'"\\]+)''')
_PYTHON_NAME = re.compile(r"python(?:3(?:\.\d+)?)?(?:\.exe)?$")
_VARIABLE = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z_0-9]*)\}|([A-Za-z_][A-Za-z_0-9]*))")


def _read_text(path: Path) -> str:
    with path.open(encoding="utf-8") as stream:
        value = stream.read(_MAX_READ + 1)
    if len(value) > _MAX_READ:
        raise ValueError("file exceeds inspection limit")
    return value


def _repo_languages(root: Path) -> dict:
    """Bounded filename inspection only; never execute Git, a parser, or hooks.

    Nested projects are included. Metadata/dependency directories are explicitly
    excluded, not silently treated as inspected. A directory symlink is not
    followed: its uninspected contents make the result inconclusive.
    """
    languages: set[str] = set()
    problems: set[str] = set()
    pending = [(root, 0)]
    inspected = 0
    while pending:
        directory, depth = pending.pop()
        if depth > _MAX_SOURCE_DEPTH:
            problems.add("source_scan_limit")
            continue
        try:
            with os.scandir(directory) as stream:
                entries = []
                for entry in stream:
                    inspected += 1
                    if inspected > _MAX_SOURCE_ENTRIES:
                        problems.add("source_scan_limit")
                        pending.clear()
                        break
                    entries.append(entry)
            for entry in sorted(entries, key=lambda item: item.name):
                if entry.name in _SOURCE_EXCLUSIONS:
                    continue
                try:
                    if entry.is_symlink():
                        if entry.is_dir():
                            problems.add("source_scan_symlink")
                            continue
                        if not entry.is_file():
                            problems.add("source_scan_unreadable")
                            continue
                    if entry.is_dir(follow_symlinks=False):
                        if inspected <= _MAX_SOURCE_ENTRIES:
                            pending.append((Path(entry.path), depth + 1))
                    elif entry.is_file():
                        language = _SOURCE_LANGUAGES.get(Path(entry.name).suffix.lower())
                        if language:
                            languages.add(language)
                except OSError:
                    problems.add("source_scan_unreadable")
        except OSError:
            problems.add("source_scan_unreadable")
    return {
        "languages": sorted(languages),
        "required_languages": sorted(languages & _CHECKED_LANGUAGES),
        "other_source_languages": sorted(languages - _CHECKED_LANGUAGES),
        "complete": not problems,
        "inspected_entries": inspected,
        "excluded_directory_names": sorted(_SOURCE_EXCLUSIONS),
        "problems": sorted(problems),
    }


def _matcher_tools(matcher: object) -> tuple[set[str], str | None]:
    if not isinstance(matcher, str):
        return set(), "invalid_matcher"
    if matcher in ("", "*"):
        return set(REQUIRED_TOOLS), None
    if len(matcher) > 512:
        return set(), "unsupported_matcher"
    # Claude treats these as exact names, not substring regexes.
    if re.fullmatch(r"[A-Za-z0-9_ ,|\-]+", matcher):
        names = {name.strip() for name in re.split(r"[|,]", matcher)}
        return set(REQUIRED_TOOLS) & names, None
    # Only the common Python/JavaScript regex subset is supported. In particular,
    # never interpret Python-only flags/escapes as valid JavaScript matchers.
    if (not re.fullmatch(r"[A-Za-z0-9_|.^$()*+?:\[\]\-]+", matcher)
            or re.search(r"[?*+]\+", matcher)
            or "(?" in matcher.replace("(?:", "")):
        return set(), "unsupported_matcher"
    try:
        regex = re.compile(matcher)
    except (re.error, RecursionError):
        return set(), "invalid_matcher"
    return {name for name in REQUIRED_TOOLS if regex.search(name)}, None


def _expand_word(value: str, repo: Path, *, shell: bool, quoted: bool) -> str | None:
    replacements = {"CLAUDE_PROJECT_DIR": str(repo)}
    if shell:
        replacements["HOME"] = str(Path.home())
    unknown = False

    def replace(match: re.Match) -> str:
        nonlocal unknown
        name = match.group(1) or match.group(2)
        if name not in replacements or (not shell and match.group(1) is None):
            unknown = True
            return ""
        replacement = replacements[name]
        if shell and not quoted and any(char.isspace() for char in replacement):
            unknown = True  # shell word splitting would change the argument list
        return replacement

    value = _VARIABLE.sub(replace, value)
    if unknown or "$" in value:
        return None
    if shell and value.startswith("~"):
        if quoted or not value.startswith("~/"):
            return None
        value = str(Path.home()) + value[1:]
    return value


def _command_words(handler: dict, repo: Path) -> list[str] | None:
    command = handler.get("command")
    if not isinstance(command, str) or not command:
        return None
    if "args" in handler:
        args = handler["args"]
        if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
            return None
        expanded = [_expand_word(word, repo, shell=False, quoted=True) for word in [command, *args]]
        return expanded if all(word is not None for word in expanded) else None
    if handler.get("shell", "bash") != "bash":
        return None
    # Reject shell programs, substitutions, redirects, globs, and escaped or
    # concatenated words instead of guessing whether the hook will execute.
    if re.search(r"[;&|<>`()\n\r*?\[\]\\]", command):
        return None
    words: list[str] = []
    position = 0
    while position < len(command):
        if command[position].isspace():
            position += 1
            continue
        match = _SHELL_WORD.match(command, position)
        if match is None or (match.end() < len(command) and not command[match.end()].isspace()):
            return None
        double, single, bare = match.groups()
        if single is not None:
            # Single quotes inhibit shell variable and tilde expansion.
            word = single if "$" not in single and not single.startswith("~") else None
        else:
            word = _expand_word(double if double is not None else bare, repo,
                                shell=True, quoted=double is not None)
        if word is None:
            return None
        words.append(word)
        position = match.end()
    return words


def _calls(function: ast.FunctionDef, name: str) -> bool:
    return any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
               and node.func.id == name for node in ast.walk(function))


def _function_only_filter(function: ast.FunctionDef) -> bool:
    """Detect the known inert Java gate, even with a pasted capability marker.

    This recognizes a concrete regression pattern, not arbitrary Python program
    semantics. Only the file gate is inspected, not the Python-only callee probe.
    """
    for node in ast.walk(function):
        if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
            continue
        test = node.test
        if len(test.ops) != 1 or len(test.comparators) != 1:
            continue
        left, right = test.left, test.comparators[0]
        is_scope = lambda value: isinstance(value, ast.Attribute) and value.attr == "scope"
        is_function = lambda value: isinstance(value, ast.Constant) and value.value == "function"
        if not ((is_scope(left) and is_function(right)) or (is_function(left) and is_scope(right))):
            continue
        skipped = (node.body if isinstance(test.ops[0], ast.NotEq)
                   else node.orelse if isinstance(test.ops[0], ast.Eq) else [])
        if any(isinstance(statement, ast.Continue) for statement in skipped):
            return True
    return False


def _script_capabilities(tree: ast.Module, target: Path, file_gate: ast.FunctionDef) -> dict:
    declarations = []
    for node in tree.body:
        names = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(name, ast.Name) and name.id == "REFLEX_CAPABILITIES" for name in names):
            declarations.append(node.value)
    legacy = _function_only_filter(file_gate)
    result = {"declared_languages": [], "effective_languages": [], "usable": True,
              "evidence": "unknown", "problems": []}
    if not declarations:
        if legacy:
            result.update(declared_languages=["python"], effective_languages=["python"],
                          evidence="legacy_function_only_filter")
        else:
            result["problems"].append("missing_capabilities")
        return result
    try:
        if len(declarations) != 1:
            raise ValueError("ambiguous declaration")
        value = ast.literal_eval(declarations[0])
        if (not isinstance(value, dict) or set(value) != {"schema_version", "file_languages"}
                or value["schema_version"] != "tmf.reflex.capabilities.v1"
                or not isinstance(value["file_languages"], list)
                or not value["file_languages"]
                or not all(isinstance(language, str) and language in _CHECKED_LANGUAGES
                           for language in value["file_languages"])
                or len(value["file_languages"]) != len(set(value["file_languages"]))):
            raise ValueError("invalid capabilities")
    except (ValueError, TypeError, SyntaxError, RecursionError):
        result["problems"].append("invalid_capabilities")
        return result
    declared = set(value["file_languages"])
    effective = declared.copy()
    result.update(declared_languages=sorted(declared), evidence="literal_declaration")
    if "java" in declared:
        if legacy:
            effective.discard("java")
            result["problems"].append("java_function_only_filter")
        else:
            imports_selector = any(isinstance(node, ast.ImportFrom) and node.module == "claim_selection"
                                   and any(alias.name == "select_file_claims" and alias.asname is None
                                           for alias in node.names) for node in tree.body)
            try:
                selector = ast.parse(_read_text(target.parent.parent / "scripts" / "claim_selection.py"))
                selector_functions = {node.name for node in selector.body if isinstance(node, ast.FunctionDef)}
                selector_available = "select_file_claims" in selector_functions
            except (OSError, ValueError, SyntaxError, RecursionError):
                selector_available = False
            if not (imports_selector and _calls(file_gate, "select_file_claims") and selector_available):
                effective.discard("java")
                if imports_selector and not selector_available:
                    # The common Python/Java gate imports this module before
                    # dispatch. A missing module breaks both languages.
                    effective.clear()
                    result["usable"] = False
                result["problems"].append("unrecognized_java_selector")
    result["effective_languages"] = sorted(effective)
    return result


def _inspect_target(handler: dict, repo: Path) -> tuple[str | None, dict]:
    words = _command_words(handler, repo)
    if not words or not _PYTHON_NAME.fullmatch(Path(words[0]).name):
        return "unsupported_command", {}
    executable = words.pop(0)
    while words and words[0] in ("-u", "-B"):
        words.pop(0)
    if words and words[0] == "--":
        words.pop(0)
    if len(words) != 1 or Path(words[0]).name != _HOOK_NAME:
        return "unsupported_command", {}
    target = Path(words[0])
    # Relative script paths depend on a mutable Claude working directory.
    if not target.is_absolute():
        return "relative_script_path", {}
    if not target.is_file():
        return "missing_script", {}
    if "/" in executable or "\\" in executable:
        interpreter = Path(executable)
        if not interpreter.is_absolute():
            return "relative_interpreter_path", {}
        available = interpreter.is_file() and os.access(interpreter, os.X_OK)
    else:
        available = shutil.which(executable) is not None
    if not available:
        return "missing_interpreter", {}
    try:
        tree = ast.parse(_read_text(target))
    except (OSError, ValueError, SyntaxError, RecursionError):
        return "unreadable_script", {}
    # Do not count a same-named unrelated script, echo, or an example file. These
    # are identity checks only, not a proof that arbitrary script code is safe.
    imports_freshness = any(isinstance(node, ast.ImportFrom) and node.module == "tmf.freshness"
                            and any(alias.name == "check_freshness" for alias in node.names)
                            for node in ast.walk(tree))
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    if (not imports_freshness or not {"main", "check_file_freshness"}.issubset(functions)
            or not _calls(functions["main"], "check_file_freshness")
            or not _calls(functions["check_file_freshness"], "check_freshness")):
        return "unrecognized_script", {}
    for key in ("async", "asyncRewake"):
        if handler.get(key, False) is not False:
            return "background_hook", {}
    if "if" in handler:
        return "conditional_hook", {}
    if "enabled" in handler or "disabled" in handler:
        return "unsupported_toggle", {}
    timeout = handler.get("timeout", 600)
    if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
            or (isinstance(timeout, float) and not math.isfinite(timeout)) or timeout <= 0):
        return "invalid_timeout", {}
    return None, _script_capabilities(tree, target, functions["check_file_freshness"])


_PROBLEM_MESSAGES = {
    "unsupported_command": "TMF candidate is not a supported direct Python-script command; inspect it in Claude /hooks.",
    "relative_script_path": "TMF script path depends on the working directory; use an absolute path or quoted $CLAUDE_PROJECT_DIR path.",
    "relative_interpreter_path": "Python interpreter path depends on the working directory; use an absolute path or a Python executable on PATH.",
    "missing_script": "Configured TMF hook script is missing or is not a regular file; install/link the reflex integration and correct its path.",
    "missing_interpreter": "Configured Python interpreter is unavailable in this environment; correct its path and verify Claude's environment.",
    "unreadable_script": "Configured TMF hook script cannot be read or parsed as Python.",
    "unrecognized_script": "Configured script does not have the supported TMF reflex entrypoint; a filename alone is not registration evidence.",
    "background_hook": "Background hooks cannot provide a synchronous pre-tool reflex gate.",
    "conditional_hook": "A conditional hook does not establish unconditional Read/Edit/Write coverage.",
    "unsupported_toggle": "Per-handler enabled/disabled fields are unsupported; inspect the configuration in Claude /hooks.",
    "invalid_timeout": "TMF hook timeout must be a positive number.",
    "invalid_matcher": "Hook matcher is invalid; use Read|Edit|Write or another supported matcher.",
    "unsupported_matcher": "Hook matcher is outside the statically supported regex subset; use Read|Edit|Write or verify it in Claude /hooks.",
    "missing_capabilities": "Registered hook has no recognized file-language capability declaration; update/link the reflex integration and rerun doctor.",
    "invalid_capabilities": "Registered hook has an invalid or non-literal REFLEX_CAPABILITIES declaration; install the complete current reflex integration, not a copied capability header.",
    "java_function_only_filter": "Registered hook's file gate filters scope='function', which omits production Java declaration claims; update/link the complete reflex integration before relying on Java gating.",
    "unrecognized_java_selector": "Declared Java support has no recognized, readable shared file selector linked from the hook; install/link the complete reflex integration and verify its Java stale-block smoke.",
    "source_scan_limit": "Repository filename inspection exceeded its entry/depth bound; source-language capability is inconclusive.",
    "source_scan_unreadable": "Part of the repository source tree is unreadable or has a broken symlink; source-language capability is inconclusive.",
    "source_scan_symlink": "A source-tree directory symlink was not followed; source-language capability is inconclusive until that scope is inspected separately.",
}


def inspect_reflex(repo: str | Path = ".") -> dict:
    """Inspect settings and target files without invoking hooks or modifying state."""
    root = Path(repo).expanduser().resolve()
    config_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude").expanduser().resolve()
    locations = [
        ("global", config_dir / "settings.json"),
        ("project", root / ".claude" / "settings.json"),
        ("local", root / ".claude" / "settings.local.json"),
    ]
    checked: list[dict] = []
    findings: list[dict] = []
    registered: set[str] = set()
    usable_registered: set[str] = set()
    registrations: list[dict] = []
    source_languages = _repo_languages(root)
    required_languages = source_languages["required_languages"]
    language_tools = {language: set() for language in required_languages}
    disabled = False
    disabled_scope = None
    invalid = False
    unknown = False

    def finding(code: str, message: str, scope: str) -> None:
        findings.append({"code": code, "message": message, "scope": scope})

    def reject_constant(value: str) -> None:
        raise ValueError("non-finite values are not JSON")

    if not root.is_dir():
        invalid = True
        finding("invalid_repo", "--repo must name an existing project directory.", "repo")
    for problem in source_languages["problems"]:
        finding(problem, _PROBLEM_MESSAGES[problem], "repo")
    if not source_languages["complete"]:
        unknown = True
    if source_languages["other_source_languages"]:
        finding("other_languages_unverified", "This check covers Python/Java direct file declarations only; other detected source languages are NOT verified: "
                + ", ".join(source_languages["other_source_languages"]) + ".", "repo")
    for scope, path in locations:
        item = {"scope": scope, "path": str(path), "status": "missing"}
        checked.append(item)
        try:
            settings = json.loads(_read_text(path), parse_constant=reject_constant)
            if not isinstance(settings, dict):
                raise ValueError("settings must be an object")
        except FileNotFoundError:
            continue
        except (OSError, ValueError, RecursionError):
            invalid = True
            item["status"] = "invalid"
            finding("invalid_settings", "Settings cannot be read as a JSON object; fix this file before relying on hook registration.", scope)
            continue
        item["status"] = "loaded"
        if "disableAllHooks" in settings:
            if not isinstance(settings["disableAllHooks"], bool):
                invalid = True
                finding("invalid_disable_all_hooks", "disableAllHooks must be a boolean.", scope)
            else:
                disabled = settings["disableAllHooks"]
                disabled_scope = scope
        hooks = settings.get("hooks", {})
        if not isinstance(hooks, dict):
            invalid = True
            finding("invalid_hooks", "hooks must be an object keyed by hook event.", scope)
            continue
        for event, groups in hooks.items():
            if not isinstance(groups, list):
                invalid = True
                finding("invalid_hook_groups", "Hook event entries must be arrays of matcher groups.", scope)
                continue
            for group in groups:
                if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                    invalid = True
                    finding("invalid_hook_group", "Hook matcher groups must contain a hooks array.", scope)
                    continue
                for handler in group["hooks"]:
                    if not isinstance(handler, dict):
                        invalid = True
                        finding("invalid_handler", "Each hook handler must be an object.", scope)
                        continue
                    # Other tools' hooks, prompts, comments, and example files
                    # are not TMF registration evidence and are never executed.
                    command = handler.get("command", "")
                    args = handler.get("args", [])
                    candidate = isinstance(command, str) and _HOOK_NAME in command
                    candidate |= isinstance(args, list) and any(isinstance(arg, str) and _HOOK_NAME in arg for arg in args)
                    if not candidate or handler.get("type") != "command":
                        continue
                    if event != "PreToolUse":
                        finding("wrong_event", "A TMF command exists outside PreToolUse and does not arm the pre-tool reflex.", scope)
                        continue
                    coverage, problem = _matcher_tools(group.get("matcher", ""))
                    if problem:
                        finding(problem, _PROBLEM_MESSAGES[problem], scope)
                        invalid |= problem == "invalid_matcher"
                        unknown |= problem == "unsupported_matcher"
                        continue
                    if not coverage:
                        finding("wrong_matcher", "TMF PreToolUse matcher does not cover any of Read/Edit/Write.", scope)
                        continue
                    problem, capabilities = _inspect_target(handler, root)
                    if problem:
                        finding(problem, _PROBLEM_MESSAGES[problem], scope)
                        unknown |= problem in {"unsupported_command", "relative_script_path", "relative_interpreter_path", "conditional_hook", "unsupported_toggle"}
                        continue
                    registered.update(coverage)
                    if capabilities["usable"]:
                        usable_registered.update(coverage)
                    finding("registration_found", "Supported synchronous TMF PreToolUse registration found (static inspection only).", scope)
                    registrations.append({"scope": scope, "tools": sorted(coverage), **capabilities})
                    for problem in capabilities["problems"]:
                        finding(problem, _PROBLEM_MESSAGES[problem], scope)
                    if "java" in required_languages and capabilities["evidence"] == "legacy_function_only_filter":
                        finding("java_function_only_filter", _PROBLEM_MESSAGES["java_function_only_filter"], scope)
                    for language in required_languages:
                        if language in capabilities["effective_languages"]:
                            language_tools[language].update(coverage)
    matched = {tool for tool in usable_registered
               if all(tool in language_tools[language] for language in required_languages)}
    if disabled:
        finding("hooks_disabled", "Effective disableAllHooks is true after global < project < local precedence.", disabled_scope)
    missing = [tool for tool in REQUIRED_TOOLS if tool not in matched]
    if missing:
        finding("missing_coverage", "No compatible registration for: " + ", ".join(missing) + ".", "effective")
    for language, coverage in language_tools.items():
        uncovered = [tool for tool in REQUIRED_TOOLS if tool not in coverage]
        if uncovered and registered:
            finding("missing_language_coverage", "No registered hook with recognized declared " + language
                    + " file-gate support for: " + ", ".join(uncovered) + ".", "effective")
    if invalid:
        status = "invalid"
    elif disabled:
        status = "disabled"
    elif not source_languages["complete"]:
        status = "unknown"
    elif not missing:
        status = "armed"
    elif unknown:
        status = "unknown"
    else:
        status = "unarmed"
    armed = status == "armed"
    return {
        "schema_version": "tmf.doctor.v1",
        "repo": str(root),
        "status": status,
        "armed": armed,
        "runtime_verified": False,
        "behavior_verified": False,
        "warning": None if armed else UNARMED_WARNING,
        "required_tools": list(REQUIRED_TOOLS),
        "matched_tools": [tool for tool in REQUIRED_TOOLS if tool in matched],
        "registered_tools": [tool for tool in REQUIRED_TOOLS if tool in registered],
        "language_capability": {
            "scope": "python_and_java_file_declarations",
            "evidence": "static_declaration_and_known_regression_checks_only",
            "source_scan": source_languages,
            "matched_tools_by_language": {language: [tool for tool in REQUIRED_TOOLS if tool in coverage]
                                          for language, coverage in language_tools.items()},
            "registrations": registrations,
        },
        "checked_locations": checked,
        "findings": findings,
        "guidance": [
            "Install/link integrations/reflex and adapt integrations/reflex/examples/claude-settings.example.json into a checked Claude settings file; package installation and tmf warm do not register hooks.",
            "Use a synchronous PreToolUse command matching Read|Edit|Write, with an existing Python interpreter and the TMF hooks/pre_tool_use.py script; preserve unrelated settings.",
            "For Java projects, install/link the complete current reflex integration, including scripts/claim_selection.py; older function-only hooks do not check Java declaration claims. Run the Java stale-block smoke after installation.",
            "Restart/reload Claude settings as needed, inspect /hooks, and verify an actual tool event before relying on enforcement; rerun tmf doctor --repo <project>.",
        ],
        "limitations": [
            "Static registration/capability inspection only: no hook, interpreter, Claude session, or freshness check was executed. Capability declarations and recognized AST shapes are not behavioral proof.",
            "Language discovery uses bounded source filenames, includes nested projects, and excludes only the listed metadata/dependency directory names. Other source languages are not covered by the Python/Java capability check.",
            "This check does not verify extraction dependencies, warmed claim coverage, source freshness, Java cross-file callees, or arbitrary custom hook semantics; verify real fresh/stale tool events separately.",
            "Managed policy, plugins, extra --settings/--setting-sources, session overrides, trust, and host reload/dispatch are not inspected; runtime firing is NOT verified.",
            "Only direct Python launches and a common regex subset are recognized; wrappers, complex shell commands, arbitrary environment expansion, and relative script paths require manual verification.",
            "Read/Edit/Write are required by the Claude example; apply_patch and shell-based edits are outside this coverage check.",
        ],
    }


def render_doctor_text(result: dict) -> str:
    headline = ("reflex registration and declared file capability detected — runtime firing NOT verified"
                if result["armed"] else "WARNING: " + UNARMED_WARNING)
    lines = [headline, f"Status: {result['status']} (read-only static check)", "Checked settings:"]
    lines.extend(f"  {item['scope']}: {item['path']} [{item['status']}]" for item in result["checked_locations"])
    lines.extend(f"  [{item['code']}] {item['message']}" for item in result["findings"])
    lines.append("Next steps:")
    lines.extend("  " + item for item in result["guidance"])
    lines.append("Limits:")
    lines.extend("  " + item for item in result["limitations"])
    return "\n".join(lines)
