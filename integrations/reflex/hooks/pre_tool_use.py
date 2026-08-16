#!/usr/bin/env python3
"""
TMF 函数级一致性反射钩子
TMF Function-Level Consistency Reflex Hook

在 agent 即将触碰代码文件时，检查 TMF 缓存中该文件的函数是否 stale。
若 stale → 硬阻断（exit 2），精确报出变化函数名。
若 fresh → 放行（exit 0）。

仿生学三组件：
  感觉器官  Sensory organ    TMF per-function fn_hash freshness (2ms-level)
  反射弧    Reflex arc        Claude Code / Codex PreToolUse hook
  反射动作  Reflex action     exit 2 hard block + localized single-file re-warm

关键设计约束：
  1. 函数级精度 — 报出具体哪个函数变了，不是"该文件有变化"
  2. 硬阻断 exit 2 — 不在内容里塞警告然后放行
  3. 一视同仁 — 不预判文件"重要性"；agent 正要碰的就是当下重要的
  4. 严格局部 — 只查目标文件的函数，不触发全量 re-warm
  5. 只用 TMF fn_hash — 不做语义检索、不猜意图

恢复闭环：
  阻断 → agent 收到"函数 X 已变化" → 运行 tmf-local-warm <该文件> →
  TMF 缓存更新 → stale 消失 → 再次操作时放行。
  tmf-local-warm 通过 Bash 工具执行，不经过 Read/Edit/Write 路径，闭环自然无循环。
"""

import ast
import hashlib
import json
import sys
import os
import textwrap
import shlex
from pathlib import Path

# ── 配置 ──────────────────────────────────────────────────────────
# 代码文件后缀（我们追踪的文件类型）
CODE_SUFFIXES: set[str] = {
    ".py", ".java", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".rb",
    ".c", ".h", ".cpp", ".hpp", ".cc", ".hh", ".cs", ".swift", ".kt", ".kts",
    ".php", ".scala", ".ex", ".exs", ".erl", ".hrl", ".elm",
}

# 会触碰代码文件的工具（需要拦截）
CODE_TOUCH_TOOLS: set[str] = {"read", "edit", "write", "apply_patch"}

# TMF 模块路径（可通过环境变量 TMF_WORKTREE 覆盖）
_TMF_WORKTREE = os.environ.get(
    "TMF_WORKTREE",
    str(Path(__file__).resolve().parents[3]),
)

# 退出码（对应 Claude Code PreToolUse 规范）
EXIT_ALLOW = 0   # 放行
EXIT_BLOCK = 2   # 硬阻断


def _ensure_tmf_importable() -> None:
    """确保 TMF 模块在 sys.path 中。"""
    if _TMF_WORKTREE not in sys.path and Path(_TMF_WORKTREE).exists():
        sys.path.insert(0, _TMF_WORKTREE)


def find_repo_root(path: str) -> str | None:
    """从给定路径向上查找 git 仓库根目录。"""
    d = Path(path).resolve()
    while d != d.parent:
        if (d / ".git").exists():
            return str(d)
        d = d.parent
    return None


def resolve_file_path(tool_input: dict, cwd: str) -> str | None:
    """从工具输入中提取并解析文件路径。"""
    file_path = tool_input.get("file_path") or tool_input.get("path") or tool_input.get("file")
    if not file_path:
        file_path = tool_input.get("filePath") or tool_input.get("filepath")
    if not file_path:
        return None
    if Path(file_path).is_absolute():
        return str(Path(file_path).resolve())
    return str((Path(cwd) / file_path).resolve())


def resolve_state_root(repo_root: str) -> Path:
    """Use TMF_STATE_ROOT when set, otherwise the repository-local .tmf."""
    configured = os.environ.get("TMF_STATE_ROOT")
    return Path(configured).expanduser().resolve() if configured else Path(repo_root) / ".tmf"


def is_callable_claim(claim: object) -> bool:
    """Select claims whose source node can be checked as a callable."""
    if getattr(claim, "scope", None) == "function":
        return True
    body = getattr(claim, "body", None)
    return (
        getattr(claim, "scope", None) == "class"
        and isinstance(body, dict)
        and body.get("language") == "java"
        and body.get("node_kind") in {"method", "constructor"}
    )


def _claim_anchor(claim: object, binding: object, rel_path: str) -> tuple[int | None, int | None]:
    """Prefer binding anchors, falling back to Java's existing body anchors."""
    line_start = getattr(binding, "line_start", None)
    line_end = getattr(binding, "line_end", None)
    if isinstance(line_start, int) and isinstance(line_end, int):
        return line_start, line_end
    body = getattr(claim, "body", None)
    if isinstance(body, dict):
        for anchor in body.get("anchors") or []:
            if isinstance(anchor, dict) and anchor.get("path") == rel_path:
                start, end = anchor.get("line_start"), anchor.get("line_end")
                if isinstance(start, int) and isinstance(end, int):
                    return start, end
    return None, None


def check_file_freshness(repo_root: str, rel_path: str, state_root: Path) -> dict:
    """
    检查指定文件中所有 Python function 和 Java method/constructor claims。

    返回:
        {"fresh": bool, "stale_functions": [str], "error": str | None}
    """
    _ensure_tmf_importable()

    from tmf.git import GitRepo
    from tmf.store import Store
    from tmf.freshness import check_freshness

    repo = GitRepo(repo_root)
    store = Store(state_root.parent if state_root.name == ".tmf" else repo_root)

    # 收集该文件的所有 callable claim IDs。Java callable claims intentionally
    # retain their existing scope=class schema.
    claim_ids: set[str] = set()
    for claim in store.iter_claims():
        if not is_callable_claim(claim):
            continue
        for binding in claim.bindings:
            if binding.path == rel_path:
                claim_ids.add(claim.id)
                break

    if not claim_ids:
        return {"fresh": True, "stale_functions": [], "error": None}

    stale_functions: list[str] = []
    stale_items: list[dict] = []
    for claim_id in sorted(claim_ids):
        claim = store.get_claim(claim_id)
        if claim is None:
            continue
        freshness = check_freshness(repo, claim)
        if not freshness.fresh:
            for stale_binding in freshness.stale_bindings:
                # 解析 stale binding: "path:qualname: reason"
                parts = stale_binding.split(":", 2)
                func_name = parts[1] if len(parts) > 1 else stale_binding
                detail = parts[2].strip() if len(parts) > 2 else "changed"
                stale_functions.append(f"{func_name} — {detail}")
                binding = next((b for b in claim.bindings if b.path == rel_path), None)
                line_start, line_end = _claim_anchor(claim, binding, rel_path)
                stale_items.append({
                    "path": rel_path,
                    "symbol": func_name,
                    "qualname": getattr(binding, "qualname", None) or func_name,
                    "line_start": line_start,
                    "line_end": line_end,
                    "stored_blob": getattr(binding, "file_blob", None),
                    "detail": detail,
                })

    return {
        "fresh": len(stale_functions) == 0,
        "stale_functions": stale_functions,
        "stale_items": stale_items,
        "error": None,
    }


def extract_new_written_text(tool_name: str, tool_input: dict) -> str:
    """Return only the content this Edit/Write operation is about to add/write."""
    if tool_name == "edit":
        for key in ("new_string", "newText", "replacement", "new_text"):
            value = tool_input.get(key)
            if isinstance(value, str):
                return value
        # OpenClaw's current edit tool batches exact replacements under
        # params.edits[].newText. Inspect every newly written fragment so the
        # native before_tool_call adapter cannot miss stale callees.
        edits = tool_input.get("edits")
        if isinstance(edits, list):
            fragments = []
            for item in edits:
                if not isinstance(item, dict):
                    continue
                value = item.get("newText") or item.get("new_string") or item.get("new_text")
                if isinstance(value, str):
                    fragments.append(value)
            return "\n".join(fragments)
        return ""
    if tool_name == "write":
        for key in ("content", "text", "data"):
            value = tool_input.get(key)
            if isinstance(value, str):
                return value
    if tool_name == "apply_patch":
        patch = tool_input.get("input")
        if not isinstance(patch, str):
            return ""
        added_lines: list[str] = []
        for line in patch.splitlines():
            if line.startswith("+++"):
                continue
            if line.startswith("+"):
                added_lines.append(line[1:])
        return "\n".join(added_lines)
    return ""


def extract_called_symbols_from_new_text(text: str) -> set[str]:
    """
    Extract called symbol names from newly written Python-ish text.

    This deliberately inspects only the new text for the current tool call.
    If the snippet cannot be parsed conservatively, return an empty set.
    """
    if not text.strip():
        return set()

    candidates = [textwrap.dedent(text)]
    candidates.append("def __tmf_reflex_probe__():\n" + textwrap.indent(textwrap.dedent(text), "    "))

    tree = None
    for candidate in candidates:
        try:
            tree = ast.parse(candidate)
            break
        except SyntaxError:
            continue
    if tree is None:
        return set()

    symbols: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            symbols.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            symbols.add(node.func.attr)
    return symbols


def resolve_unique_function_claim(repo_root: str, symbol: str, state_root: Path):
    """Resolve a call symbol to exactly one function claim, or None if ambiguous/unknown."""
    _ensure_tmf_importable()

    from tmf.store import Store

    store = Store(state_root.parent if state_root.name == ".tmf" else repo_root)
    matches = []
    for claim in store.iter_claims():
        if claim.scope != "function":
            continue
        qualname = claim.body.get("qualname") if isinstance(claim.body, dict) else None
        if not qualname and claim.bindings:
            qualname = claim.bindings[0].qualname
        if not isinstance(qualname, str):
            continue
        if qualname == symbol or qualname.endswith(f".{symbol}"):
            matches.append(claim)

    unique: dict[str, object] = {claim.id: claim for claim in matches}
    if len(unique) != 1:
        return None
    return next(iter(unique.values()))


def check_called_symbol_freshness(repo_root: str, new_text: str, state_root: Path) -> dict:
    """
    Check freshness of uniquely resolvable function symbols called in new_text.

    Unknown or ambiguous symbols are intentionally skipped to avoid false blocks.
    """
    _ensure_tmf_importable()

    from tmf.git import GitRepo
    from tmf.freshness import check_freshness

    repo = GitRepo(repo_root)
    stale_calls: list[dict] = []

    for symbol in sorted(extract_called_symbols_from_new_text(new_text)):
        claim = resolve_unique_function_claim(repo_root, symbol, state_root)
        if claim is None:
            continue
        freshness = check_freshness(repo, claim)
        if freshness.fresh:
            continue
        binding = claim.bindings[0] if claim.bindings else None
        qualname = claim.body.get("qualname") if isinstance(claim.body, dict) else symbol
        stale_calls.append({
            "symbol": symbol,
            "qualname": qualname or symbol,
            "path": binding.path if binding else "",
            "details": freshness.stale_bindings,
            "line_start": getattr(binding, "line_start", None),
            "line_end": getattr(binding, "line_end", None),
            "stored_blob": getattr(binding, "file_blob", None),
        })

    return {
        "fresh": len(stale_calls) == 0,
        "stale_calls": stale_calls,
        "error": None,
    }


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def action_fingerprint(tool_name: str, tool_input: dict, rel_path: str) -> str:
    payload = {"tool_name": tool_name, "path": rel_path, "input": tool_input}
    return hashlib.sha256(_stable_json(payload).encode()).hexdigest()


def source_blob(repo_root: str, rel_path: str) -> str | None:
    _ensure_tmf_importable()
    from tmf.git import GitRepo
    return GitRepo(repo_root).blob_sha(rel_path)


def collision_payload(repo_root: str, state_root: Path, rel_path: str, tool_name: str,
                      tool_input: dict, stale_items: list[dict], reason_code: str) -> dict:
    repo = str(Path(repo_root).resolve())
    state = str(state_root.resolve())
    paths: list[dict] = []
    for item in stale_items:
        stale_path = str(item.get("path") or rel_path)
        current = source_blob(repo, stale_path)
        paths.append({
            "path": stale_path,
            "symbol": item.get("symbol"),
            "qualname": item.get("qualname"),
            "anchor": {
                "line_start": item.get("line_start"),
                "line_end": item.get("line_end"),
                "reliable": isinstance(item.get("line_start"), int) and isinstance(item.get("line_end"), int),
            },
            "stored_blob": item.get("stored_blob"),
            "current_source_blob": current,
            "detail": item.get("detail") or "; ".join(item.get("details") or []),
        })
    paths = sorted(paths, key=lambda x: (x["path"], str(x.get("qualname"))))
    warm_script = Path(__file__).resolve().parent.parent / "scripts" / "local_warm.py"
    commands = [
        f"python3 {shlex.quote(str(warm_script))} {shlex.quote(repo)} {shlex.quote(p['path'])} --state-root {shlex.quote(state)}"
        for p in {p["path"]: p for p in paths}.values()
    ]
    identity = {
        "repo_root": repo, "state_root": state, "blocked_action_fingerprint": action_fingerprint(tool_name, tool_input, rel_path),
        "paths": [{"path": p["path"], "blob": p["current_source_blob"], "qualname": p.get("qualname")} for p in paths],
    }
    return {
        "schema_version": "tmf.reflex.collision.v1",
        "decision": "block",
        "reason_code": reason_code,
        "collision_id": hashlib.sha256(_stable_json(identity).encode()).hexdigest()[:24],
        "canonical_repo_root": repo,
        "canonical_state_root": state,
        "session_identity": None,
        "run_identity": None,
        "blocked_action_fingerprint": identity["blocked_action_fingerprint"],
        "blocked_tool": tool_name,
        "blocked_target_path": rel_path,
        "stale_paths": paths,
        "recovery_commands": commands,
        "recovery_command": commands[0] if len(commands) == 1 else None,
    }


def emit_block(payload: dict, human_reason: str) -> None:
    payload["reason"] = human_reason
    sys.stderr.write(json.dumps(payload, ensure_ascii=False) + "\n")
    raise SystemExit(EXIT_BLOCK)


def emit_allow(repo_root: str | None = None, state_root: Path | None = None,
               rel_path: str | None = None, reason_code: str = "fresh") -> None:
    payload = {"schema_version": "tmf.reflex.decision.v1", "decision": "allow", "reason_code": reason_code}
    if repo_root and state_root and rel_path:
        payload.update({"canonical_repo_root": str(Path(repo_root).resolve()),
                        "canonical_state_root": str(state_root.resolve()),
                        "target_path": rel_path, "current_source_blob": source_blob(repo_root, rel_path)})
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    raise SystemExit(EXIT_ALLOW)


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            sys.exit(EXIT_ALLOW)
        hook_input = json.loads(raw)
    except (json.JSONDecodeError, EOFError, IOError):
        sys.exit(EXIT_ALLOW)

    tool_name = str(hook_input.get("tool_name", "")).lower()
    tool_input = hook_input.get("tool_input", {})
    cwd = hook_input.get("cwd", os.getcwd())

    # 1. 只拦截代码触碰工具
    if tool_name not in CODE_TOUCH_TOOLS:
        sys.exit(EXIT_ALLOW)

    # 2. 提取文件路径
    file_path = resolve_file_path(tool_input, cwd)
    if file_path is None:
        sys.exit(EXIT_ALLOW)

    # 3. 只拦截代码文件
    suffix = Path(file_path).suffix
    if suffix not in CODE_SUFFIXES:
        sys.exit(EXIT_ALLOW)

    # 4. 找到 git repo 根目录
    repo_root = find_repo_root(file_path)
    if repo_root is None:
        # 不在 git 仓库中 — 放行
        sys.exit(EXIT_ALLOW)

    # 5. 检查 TMF 是否已初始化
    state_root = resolve_state_root(repo_root)
    tmf_dir = state_root / "claims"
    if not tmf_dir.exists():
        # TMF 未 warm — 放行（这是初始状态，无可比对）
        sys.exit(EXIT_ALLOW)

    # 6. 计算相对路径
    try:
        rel_path = str(Path(file_path).resolve().relative_to(Path(repo_root).resolve()))
    except ValueError:
        sys.exit(EXIT_ALLOW)

    # 7. 检查目标文件自身 freshness
    try:
        result = check_file_freshness(repo_root, rel_path, state_root)
    except Exception as exc:
        sys.stderr.write(
            json.dumps(
                {"decision": "allow", "warning": f"TMF reflex hook error: {exc}"},
                ensure_ascii=False,
            )
            + "\n"
        )
        sys.exit(EXIT_ALLOW)

    if result["error"]:
        # 检查出错 — 保守放行（不因工具异常阻断 agent）
        sys.stderr.write(
            json.dumps(
                {"decision": "allow", "warning": f"TMF reflex hook error: {result['error']}"},
                ensure_ascii=False,
            )
            + "\n"
        )
        sys.exit(EXIT_ALLOW)

    if result["fresh"]:
        # 目标文件 fresh；Edit/Write 还要检查这次新写下的调用符号。
        if tool_name in {"edit", "write", "apply_patch"}:
            new_text = extract_new_written_text(tool_name, tool_input)
            try:
                call_result = check_called_symbol_freshness(repo_root, new_text, state_root)
            except Exception as exc:
                sys.stderr.write(
                    json.dumps(
                        {"decision": "allow", "warning": f"TMF reflex hook call-symbol error: {exc}"},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                sys.exit(EXIT_ALLOW)

            if not call_result["fresh"]:
                script_dir = Path(__file__).resolve().parent.parent
                warm_script = script_dir / "scripts" / "local_warm.py"
                stale_items = []
                warm_paths = []
                for item in call_result["stale_calls"]:
                    details = "; ".join(item["details"]) if item["details"] else "fn_hash mismatch"
                    stale_items.append(f"  • {item['qualname']} — {details}")
                    if item["path"]:
                        warm_paths.append(item["path"])
                stale_list = "\n".join(stale_items)
                commands = "\n".join(
                    f"  python3 {warm_script} {repo_root} {path} --state-root {state_root}"
                    for path in sorted(set(warm_paths))
                )
                message = (
                    f"═══ TMF 一致性反射阻断 ═══\n\n"
                    f"你正要写下的代码调用了相对于 TMF 缓存已变化的符号：\n\n"
                    f"{stale_list}\n\n"
                    f"这些被调用符号的旧认知已不可靠。请先局部重新认知对应文件：\n\n"
                    f"{commands}\n\n"
                    f"执行上条命令后 TMF 缓存即更新到当前版本，再次写这个调用时会自动放行。\n\n"
                    f"正在执行的操作：{tool_name} → {rel_path}"
                )
                items = [{**item, "detail": "; ".join(item["details"]) if item["details"] else "fn_hash mismatch"}
                         for item in call_result["stale_calls"]]
                emit_block(collision_payload(repo_root, state_root, rel_path, tool_name, tool_input,
                                             items, "stale_collision"), message)

        # 文件 fresh 且本次新写调用的符号 fresh/未知/多义 — 放行
        emit_allow(repo_root, state_root, rel_path)

    # 8. 有 stale 函数 — 硬阻断
    stale_list = "\n".join(f"  • {fn}" for fn in result["stale_functions"])
    # 推测 tmf-local-warm 脚本的位置
    script_dir = Path(__file__).resolve().parent.parent
    warm_script = script_dir / "scripts" / "local_warm.py"

    message = (
        f"═══ TMF 一致性反射阻断 ═══\n\n"
        f"你正要触碰的代码相对于 TMF 缓存已发生变化：\n\n"
        f"{stale_list}\n\n"
        f"这些函数的旧认知已不可靠。请先重新认知这一部分代码：\n\n"
        f"  python3 {warm_script} {repo_root} {rel_path} --state-root {state_root}\n\n"
        f"执行上条命令后 TMF 缓存即更新到当前版本，再次操作时会自动放行。\n\n"
        f"正在执行的操作：{tool_name} → {rel_path}"
    )

    # Claude Code PreToolUse 阻断格式
    emit_block(collision_payload(repo_root, state_root, rel_path, tool_name, tool_input,
                                 result["stale_items"], "stale_collision"), message)


if __name__ == "__main__":
    main()
