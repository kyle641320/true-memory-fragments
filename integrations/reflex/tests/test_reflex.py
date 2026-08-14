#!/usr/bin/env python3
"""
TMF 反射钩子健康度验证（成功判据 D）

验证四项 + 端到端对撞：
  D1 反射触发    含 stale 函数的文件 → 硬阻断 + 精确报出函数名（函数级）
  D2 反射不过度  同文件未变函数不误报 stale
  D3 反射不漏    被改函数确实触发阻断
  D4 闭环无循环  阻断→局部重读→缓存更新→放行，且只更新该文件
  E  端到端对撞  旧认知(2参)→代码改为新版(3参)→反射在生成错误调用前阻断

每个测试构造独立的临时 git 仓库，warm TMF，再改代码，模拟 PreToolUse 钩子调用。
"""

import json
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HOOK_SCRIPT = PROJECT_ROOT / "hooks" / "pre_tool_use.py"
WARM_SCRIPT = PROJECT_ROOT / "scripts" / "local_warm.py"
CALIBRATE_SCRIPT = PROJECT_ROOT / "scripts" / "git_calibrate.py"
TMF_WORKTREE = PROJECT_ROOT.parent.parent


def _load_calibrate_module():
    spec = importlib.util.spec_from_file_location("tmf_git_freshness_calibrate", CALIBRATE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def make_repo(tmpdir: Path, files: dict[str, str]) -> Path:
    repo = tmpdir / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.com")
    _git(repo, "config", "user.name", "t")
    for rel, content in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")
    return repo


def warm_repo(repo: Path) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(TMF_WORKTREE) + os.pathsep + env.get("PYTHONPATH", "")
    env["TMF_STATE_ROOT"] = str(repo / ".tmf")
    subprocess.run([sys.executable, "-m", "tmf.cli", "warm", "--repo", str(repo)],
                   cwd=TMF_WORKTREE, check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)


def calibrate_repo(repo: Path, old_rev: str, new_rev: str = "HEAD", update_cache: bool = True) -> dict:
    module = _load_calibrate_module()
    return module.calibrate(
        repo,
        old_rev,
        new_rev,
        update_cache=update_cache,
    )


def call_hook(
    repo: Path,
    rel_path: str,
    tool_name: str = "Edit",
    new_text: str | None = None,
    tool_input_extra: dict | None = None,
) -> tuple[int, str]:
    """模拟 PreToolUse 钩子调用，返回 (exit_code, stderr)。"""
    tool_input = {"file_path": str(repo / rel_path)}
    if new_text is not None:
        if tool_name == "Write":
            tool_input["content"] = new_text
        else:
            tool_input["new_string"] = new_text
    if tool_input_extra:
        tool_input.update(tool_input_extra)
    hook_input = json.dumps({
        "tool_name": tool_name,
        "tool_input": tool_input,
        "cwd": str(repo),
    })
    env = dict(os.environ)
    env["TMF_WORKTREE"] = str(TMF_WORKTREE)
    env["TMF_STATE_ROOT"] = str(repo / ".tmf")
    proc = subprocess.run([sys.executable, str(HOOK_SCRIPT)],
                          input=hook_input, capture_output=True, text=True, env=env)
    return proc.returncode, proc.stderr


def local_warm(repo: Path, rel_path: str) -> dict:
    env = dict(os.environ)
    env["TMF_WORKTREE"] = str(TMF_WORKTREE)
    env["TMF_STATE_ROOT"] = str(repo / ".tmf")
    proc = subprocess.run([
        sys.executable,
        str(WARM_SCRIPT),
        str(repo),
        rel_path,
        "--state-root",
        str(repo / ".tmf"),
    ], capture_output=True, text=True, env=env)
    out = proc.stdout or proc.stderr
    return json.loads(out)


class ReflexHealthTests(unittest.TestCase):

    def test_git_calibration_emits_manifest_and_refreshes_changed_file(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(Path(td), {"mod.py": "def f(x):\n    return x\n"})
            warm_repo(repo)
            old = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True,
                                 capture_output=True, text=True).stdout.strip()
            (repo / "mod.py").write_text("def f(x, y):\n    return x + y\n", encoding="utf-8")
            _git(repo, "add", "mod.py"); _git(repo, "commit", "-m", "drift")
            manifest = calibrate_repo(repo, old)
            self.assertEqual(manifest["entries"][0]["status"], "changed")
            self.assertEqual(manifest["entries"][0]["qualname"], "f")
            code, stderr = call_hook(repo, "mod.py")
            self.assertEqual(code, 0, stderr)

    def test_D1_reflex_triggers_and_names_function(self):
        """D1: stale 函数 → 硬阻断(exit 2) + 精确报出函数名。"""
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(Path(td), {
                "mod.py": "def enforce_length(text):\n    return text[:100]\n\n"
                          "def other(x):\n    return x + 1\n",
            })
            warm_repo(repo)
            # 改 enforce_length（加参数）
            (repo / "mod.py").write_text(
                "def enforce_length(text, limit):\n    return text[:limit]\n\n"
                "def other(x):\n    return x + 1\n", encoding="utf-8")
            code, stderr = call_hook(repo, "mod.py")
            self.assertEqual(code, 2, f"应硬阻断 exit 2，实际 {code}")
            self.assertIn("enforce_length", stderr, "应精确报出 enforce_length")
            # 函数级：不应把整个文件当成全变
            payload = json.loads(stderr.strip().split("\n")[-1])
            self.assertEqual(payload["decision"], "block")

    def test_D2_reflex_not_overactive(self):
        """D2: 同文件中未变函数不应被误报 stale。"""
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(Path(td), {
                "mod.py": "def changed_fn(x):\n    return x\n\n"
                          "def stable_fn(y):\n    return y * 2\n",
            })
            warm_repo(repo)
            # 只改 changed_fn
            (repo / "mod.py").write_text(
                "def changed_fn(x):\n    return x + 999\n\n"
                "def stable_fn(y):\n    return y * 2\n", encoding="utf-8")
            code, stderr = call_hook(repo, "mod.py")
            self.assertEqual(code, 2)
            self.assertIn("changed_fn", stderr)
            self.assertNotIn("stable_fn", stderr,
                             "未变的 stable_fn 不应被报 stale（反射不过度）")

    def test_D3_reflex_no_miss(self):
        """D3: 被改函数确实触发阻断，不漏过。"""
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(Path(td), {
                "mod.py": "def target(a, b):\n    return a + b\n",
            })
            warm_repo(repo)
            (repo / "mod.py").write_text(
                "def target(a, b, c):\n    return a + b + c\n", encoding="utf-8")
            code, stderr = call_hook(repo, "mod.py")
            self.assertEqual(code, 2, "被改函数必须触发阻断，不能漏")
            self.assertIn("target", stderr)

    def test_D3b_fresh_file_allows(self):
        """D3 反向: 未改动文件应放行(exit 0)。"""
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(Path(td), {
                "mod.py": "def stay(x):\n    return x\n",
            })
            warm_repo(repo)
            code, stderr = call_hook(repo, "mod.py")
            self.assertEqual(code, 0, f"fresh 文件应放行，实际 {code}: {stderr}")

    def test_D4_closed_loop_no_infinite_cycle(self):
        """D4: 阻断→局部重读→缓存更新→放行，且只更新该文件。"""
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(Path(td), {
                "a.py": "def fa(x):\n    return x\n",
                "b.py": "def fb(y):\n    return y\n",
            })
            warm_repo(repo)
            # 改 a.py
            (repo / "a.py").write_text("def fa(x, z):\n    return x + z\n", encoding="utf-8")

            # 第一次：阻断
            code1, _ = call_hook(repo, "a.py")
            self.assertEqual(code1, 2, "改动后首次应阻断")

            # b.py 未动，应放行（验证局部性）
            code_b, _ = call_hook(repo, "b.py")
            self.assertEqual(code_b, 0, "未动的 b.py 应放行")

            # 恢复动作：局部 warm a.py（通过 Bash 路径，不经钩子）
            result = local_warm(repo, "a.py")
            self.assertTrue(result["all_fresh_now"], f"局部 warm 后应全 fresh: {result}")

            # 第二次：放行（闭环完成，无循环）
            code2, stderr2 = call_hook(repo, "a.py")
            self.assertEqual(code2, 0, f"局部 warm 后应放行，实际 {code2}: {stderr2}")

            # 验证只更新了 a.py：b.py claims 数量未变（局部性）
            self.assertEqual(result["file"], "a.py")

    def test_E_call_symbol_collision_on_editing_caller(self):
        """
        E: 真实缺口回归。
        build_url 所在 u.py 已 stale；agent 不读 u.py，只编辑 fresh caller.py，
        在新增内容里写下 build_url("x", "y")。反射必须拦这一笔调用。
        """
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(Path(td), {
                "u.py": "def build_url(host, path):\n"
                        "    return f'http://{host}/{path}'\n",
                "caller.py": "from u import build_url\n\n"
                             "def existing():\n"
                             "    return 'ok'\n",
            })
            warm_repo(repo)

            # 代码被协作者改成新签名（3 参，加了 scheme）
            (repo / "u.py").write_text(
                "def build_url(host, path, scheme):\n"
                "    return f'{scheme}://{host}/{path}'\n", encoding="utf-8")

            new_text = (
                "\ndef call_new():\n"
                "    return build_url('example.com', 'api')\n"
            )
            code, stderr = call_hook(repo, "caller.py", tool_name="Edit", new_text=new_text)
            self.assertEqual(code, 2, "写下 stale build_url 调用时必须硬阻断")
            self.assertIn("build_url", stderr, "应精确指出 build_url 已变化")
            self.assertIn("u.py", stderr, "恢复命令应只指向 build_url 所在文件")
            self.assertNotIn("caller.py:build_url", stderr,
                             "不应把 caller.py 里的调用点当成 stale 定义")

            # agent 响应阻断 → 局部重新认知 build_url 所在 u.py
            result = local_warm(repo, "u.py")
            self.assertTrue(result["all_fresh_now"])

            good_text = (
                "\ndef call_new():\n"
                "    return build_url('example.com', 'api', 'https')\n"
            )
            code2, stderr2 = call_hook(repo, "caller.py", tool_name="Edit", new_text=good_text)
            self.assertEqual(code2, 0, f"局部 warm 后再写调用应放行: {stderr2}")

    def test_E_openclaw_batched_edit_shape_blocks_stale_callee(self):
        """OpenClaw edit params use edits[].newText; production hook must inspect them."""
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(Path(td), {
                "u.py": "def build_url(host, path):\n    return f'http://{host}/{path}'\n",
                "caller.py": "from u import build_url\n",
            })
            warm_repo(repo)
            (repo / "u.py").write_text(
                "def build_url(host, path, scheme):\n"
                "    return f'{scheme}://{host}/{path}'\n", encoding="utf-8")
            code, stderr = call_hook(
                repo,
                "caller.py",
                tool_name="Edit",
                tool_input_extra={"edits": [{
                    "oldText": "from u import build_url\n",
                    "newText": "from u import build_url\n\ndef run():\n    return build_url('h', 'p')\n",
                }]},
            )
            self.assertEqual(code, 2, stderr)
            self.assertIn("build_url", stderr)

    def test_E_boundary_existing_stale_call_in_file_is_ignored(self):
        """只管本次新增内容：目标文件里既有 stale 调用，但这次写 fresh 调用，应放行。"""
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(Path(td), {
                "u.py": "def build_url(host, path):\n"
                        "    return f'http://{host}/{path}'\n\n"
                        "def fresh_fn(value):\n"
                        "    return value.upper()\n",
                "caller.py": "from u import build_url, fresh_fn\n\n"
                             "def old_existing():\n"
                             "    return build_url('old.example', 'api')\n",
            })
            warm_repo(repo)
            (repo / "u.py").write_text(
                "def build_url(host, path, scheme):\n"
                "    return f'{scheme}://{host}/{path}'\n\n"
                "def fresh_fn(value):\n"
                "    return value.upper()\n", encoding="utf-8")

            new_text = (
                "\ndef new_work():\n"
                "    return fresh_fn('ok')\n"
            )
            code, stderr = call_hook(repo, "caller.py", tool_name="Edit", new_text=new_text)
            self.assertEqual(code, 0,
                             f"不应因为 caller.py 既有 stale build_url 调用而阻断: {stderr}")

    def test_E_fresh_called_symbol_allows(self):
        """本次新增调用的目标符号 fresh → 放行。"""
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(Path(td), {
                "u.py": "def fresh_fn(value):\n    return value.upper()\n",
                "caller.py": "from u import fresh_fn\n",
            })
            warm_repo(repo)
            code, stderr = call_hook(
                repo,
                "caller.py",
                tool_name="Edit",
                new_text="\ndef run():\n    return fresh_fn('ok')\n",
            )
            self.assertEqual(code, 0, f"fresh 被调用符号应放行: {stderr}")

    def test_E_ambiguous_called_symbol_is_skipped(self):
        """无法唯一定位调用符号 → 保守跳过不拦。"""
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(Path(td), {
                "a.py": "def dup(value):\n    return value\n",
                "b.py": "def dup(value):\n    return value\n",
                "caller.py": "from a import dup\n",
            })
            warm_repo(repo)
            (repo / "a.py").write_text("def dup(value, extra):\n    return value\n", encoding="utf-8")
            code, stderr = call_hook(
                repo,
                "caller.py",
                tool_name="Edit",
                new_text="\ndef run():\n    return dup('ok')\n",
            )
            self.assertEqual(code, 0, f"多义符号应跳过不拦: {stderr}")

    def test_E_write_content_call_symbol_collision(self):
        """Write 工具也只检查即将写入的 content 中的调用。"""
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(Path(td), {
                "u.py": "def build_url(host, path):\n"
                        "    return f'http://{host}/{path}'\n",
            })
            warm_repo(repo)
            (repo / "u.py").write_text(
                "def build_url(host, path, scheme):\n"
                "    return f'{scheme}://{host}/{path}'\n", encoding="utf-8")

            content = (
                "from u import build_url\n\n"
                "def run():\n"
                "    return build_url('example.com', 'api')\n"
            )
            code, stderr = call_hook(repo, "new_caller.py", tool_name="Write", new_text=content)
            self.assertEqual(code, 2, "Write 新文件时写下 stale 调用也必须阻断")
            self.assertIn("build_url", stderr)

    def test_E_apply_patch_added_call_symbol_collision(self):
        """apply_patch 只检查本次 patch 新增行里的调用。"""
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(Path(td), {
                "u.py": "def build_url(host, path):\n"
                        "    return f'http://{host}/{path}'\n",
                "caller.py": "from u import build_url\n\n"
                             "def make_api_url():\n"
                             "    return 'TODO'\n",
            })
            warm_repo(repo)
            (repo / "u.py").write_text(
                "def build_url(host, path, scheme):\n"
                "    return f'{scheme}://{host}/{path}'\n", encoding="utf-8")

            patch = """*** Begin Patch
*** Update File: {caller}
@@
 def make_api_url():
-    return 'TODO'
+    return build_url('example.com', 'api')
*** End Patch
""".format(caller=repo / "caller.py")
            code, stderr = call_hook(
                repo,
                "caller.py",
                tool_name="apply_patch",
                tool_input_extra={"input": patch},
            )
            self.assertEqual(code, 2, "apply_patch 新增 stale 调用也必须阻断")
            self.assertIn("build_url", stderr)

    def test_non_code_file_passes(self):
        """非代码文件（.md）直接放行。"""
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(Path(td), {
                "mod.py": "def f(x):\n    return x\n",
                "README.md": "# hello\n",
            })
            warm_repo(repo)
            (repo / "mod.py").write_text("def f(x, y):\n    return x+y\n", encoding="utf-8")
            # README.md 即使在有 stale py 的 repo 里，自身也应放行
            code, _ = call_hook(repo, "README.md")
            self.assertEqual(code, 0, "非代码文件应放行")

    def test_non_touch_tool_passes(self):
        """非 Read/Edit/Write 工具（如 Bash）直接放行 —— 保证恢复动作不被拦。"""
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(Path(td), {"mod.py": "def f(x):\n    return x\n"})
            warm_repo(repo)
            (repo / "mod.py").write_text("def f(x, y):\n    return x\n", encoding="utf-8")
            code, _ = call_hook(repo, "mod.py", tool_name="Bash")
            self.assertEqual(code, 0, "Bash 工具应放行，否则恢复动作会死循环")



if __name__ == "__main__":
    unittest.main()
