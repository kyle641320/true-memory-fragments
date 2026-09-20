"""Read-only inspection of the supported Claude Code reflex registration.

This is deliberately not a shell interpreter or a Claude session probe. A passing
result establishes a registration in the inspected settings, not runtime firing.
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
_SHELL_WORD = re.compile(r'''"([^"\\]*)"|'([^']*)'|([^\s'"\\]+)''')
_PYTHON_NAME = re.compile(r"python(?:3(?:\.\d+)?)?(?:\.exe)?$")
_VARIABLE = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z_0-9]*)\}|([A-Za-z_][A-Za-z_0-9]*))")


def _read_text(path: Path) -> str:
    with path.open(encoding="utf-8") as stream:
        value = stream.read(_MAX_READ + 1)
    if len(value) > _MAX_READ:
        raise ValueError("file exceeds inspection limit")
    return value


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


def _target_problem(handler: dict, repo: Path) -> str | None:
    words = _command_words(handler, repo)
    if not words or not _PYTHON_NAME.fullmatch(Path(words[0]).name):
        return "unsupported_command"
    executable = words.pop(0)
    while words and words[0] in ("-u", "-B"):
        words.pop(0)
    if words and words[0] == "--":
        words.pop(0)
    if len(words) != 1 or Path(words[0]).name != _HOOK_NAME:
        return "unsupported_command"
    target = Path(words[0])
    # Relative script paths depend on a mutable Claude working directory.
    if not target.is_absolute():
        return "relative_script_path"
    if not target.is_file():
        return "missing_script"
    if "/" in executable or "\\" in executable:
        interpreter = Path(executable)
        if not interpreter.is_absolute():
            return "relative_interpreter_path"
        available = interpreter.is_file() and os.access(interpreter, os.X_OK)
    else:
        available = shutil.which(executable) is not None
    if not available:
        return "missing_interpreter"
    try:
        tree = ast.parse(_read_text(target))
    except (OSError, ValueError, SyntaxError, RecursionError):
        return "unreadable_script"
    # Do not count a same-named unrelated script, echo, or an example file. These
    # are identity checks only, not a proof that arbitrary script code is safe.
    imports_freshness = any(isinstance(node, ast.ImportFrom) and node.module == "tmf.freshness"
                            and any(alias.name == "check_freshness" for alias in node.names)
                            for node in ast.walk(tree))
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    if not imports_freshness or not {"main", "check_file_freshness"}.issubset(functions):
        return "unrecognized_script"
    for key in ("async", "asyncRewake"):
        if handler.get(key, False) is not False:
            return "background_hook"
    if "if" in handler:
        return "conditional_hook"
    if "enabled" in handler or "disabled" in handler:
        return "unsupported_toggle"
    timeout = handler.get("timeout", 600)
    if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
            or (isinstance(timeout, float) and not math.isfinite(timeout)) or timeout <= 0):
        return "invalid_timeout"
    return None


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
    matched: set[str] = set()
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
                    problem = _target_problem(handler, root)
                    if problem:
                        finding(problem, _PROBLEM_MESSAGES[problem], scope)
                        unknown |= problem in {"unsupported_command", "relative_script_path", "relative_interpreter_path", "conditional_hook", "unsupported_toggle"}
                        continue
                    matched.update(coverage)
                    finding("registration_found", "Supported synchronous TMF PreToolUse registration found (static inspection only).", scope)
    if disabled:
        finding("hooks_disabled", "Effective disableAllHooks is true after global < project < local precedence.", disabled_scope)
    missing = [tool for tool in REQUIRED_TOOLS if tool not in matched]
    if missing:
        finding("missing_coverage", "No verified registration for: " + ", ".join(missing) + ".", "effective")
    if invalid:
        status = "invalid"
    elif disabled:
        status = "disabled"
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
        "warning": None if armed else UNARMED_WARNING,
        "required_tools": list(REQUIRED_TOOLS),
        "matched_tools": [tool for tool in REQUIRED_TOOLS if tool in matched],
        "checked_locations": checked,
        "findings": findings,
        "guidance": [
            "Install/link integrations/reflex and adapt integrations/reflex/examples/claude-settings.example.json into a checked Claude settings file; package installation and tmf warm do not register hooks.",
            "Use a synchronous PreToolUse command matching Read|Edit|Write, with an existing Python interpreter and the TMF hooks/pre_tool_use.py script; preserve unrelated settings.",
            "Restart/reload Claude settings as needed, inspect /hooks, and verify an actual tool event before relying on enforcement; rerun tmf doctor --repo <project>.",
        ],
        "limitations": [
            "Static registration inspection only: no hook, interpreter, Claude session, or freshness check was executed.",
            "Managed policy, plugins, extra --settings/--setting-sources, session overrides, trust, and host reload/dispatch are not inspected; runtime firing is NOT verified.",
            "Only direct Python launches and a common regex subset are recognized; wrappers, complex shell commands, arbitrary environment expansion, and relative script paths require manual verification.",
            "Read/Edit/Write are required by the Claude example; apply_patch and shell-based edits are outside this coverage check.",
        ],
    }


def render_doctor_text(result: dict) -> str:
    headline = ("reflex registration detected — runtime firing NOT verified"
                if result["armed"] else "WARNING: " + UNARMED_WARNING)
    lines = [headline, f"Status: {result['status']} (read-only static check)", "Checked settings:"]
    lines.extend(f"  {item['scope']}: {item['path']} [{item['status']}]" for item in result["checked_locations"])
    lines.extend(f"  [{item['code']}] {item['message']}" for item in result["findings"])
    lines.append("Next steps:")
    lines.extend("  " + item for item in result["guidance"])
    lines.append("Limits:")
    lines.extend("  " + item for item in result["limitations"])
    return "\n".join(lines)
