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


def run_hook(
    repo: Path,
    rel_path: str,
    tool_name: str = "Edit",
    new_text: str | None = None,
    tool_input_extra: dict | None = None,
) -> subprocess.CompletedProcess:
    """Run the real hook so both allow receipts and collisions are observable."""
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
    return subprocess.run([sys.executable, str(HOOK_SCRIPT)],
                          input=hook_input, capture_output=True, text=True, env=env)


def call_hook(*args, **kwargs) -> tuple[int, str]:
    """Compatibility helper for the Python collision tests."""
    proc = run_hook(*args, **kwargs)
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

    def test_unwarmed_file_is_allowed_without_freshness_claim(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(Path(td), {"mod.py": "def f():\n    return 1\n"})
            proc = run_hook(repo, "mod.py")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            receipt = json.loads(proc.stdout)
            self.assertEqual(receipt["reason_code"], "not_warmed")
            self.assertEqual(receipt["checked_claims"], 0)
            self.assertIn("without a freshness determination", receipt["warning"])

    def test_no_eligible_nodes_do_not_report_fresh_after_warm(self):
        for path, source, expected_reason in [
            ("empty.py", "# nothing to bind\n", "no_eligible_claims"),
            ("mod.js", "function f() { return 1; }\n", "unsupported_language"),
        ]:
            with self.subTest(path=path), tempfile.TemporaryDirectory() as td:
                repo = make_repo(Path(td), {path: source})
                warm_repo(repo)
                proc = run_hook(repo, path)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                receipt = json.loads(proc.stdout)
                self.assertEqual(receipt["reason_code"], expected_reason)
                self.assertEqual(receipt["checked_claims"], 0)
                self.assertTrue(receipt["warning"])
                result = local_warm(repo, path)
                self.assertFalse(result["all_fresh_now"], result)
                self.assertEqual(result["checked_claims"], 0)
                self.assertEqual(result["reason_code"], expected_reason)
                self.assertTrue(result["warning"])

    def test_java_without_parser_is_allowed_with_coverage_warning(self):
        # -S excludes optional site packages even on the mandatory Java CI job.
        # Exercise degraded production warm and the actual hook/local recovery,
        # not fabricated Java claim dictionaries.
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(Path(td), {"Service.java": "class Service { int f() { return 1; } }\n"})
            env = dict(os.environ, PYTHONPATH=str(TMF_WORKTREE),
                       TMF_WORKTREE=str(TMF_WORKTREE), TMF_STATE_ROOT=str(repo / ".tmf"))
            subprocess.run([sys.executable, "-S", "-c",
                            "from tmf.java_extract import java_status; assert not java_status().available"],
                           cwd=TMF_WORKTREE, env=env, capture_output=True, text=True, check=True)
            subprocess.run([sys.executable, "-S", "-m", "tmf.cli", "warm", "--repo", str(repo)],
                           cwd=TMF_WORKTREE, env=env, capture_output=True, text=True, check=True)
            proc = subprocess.run([sys.executable, "-S", str(HOOK_SCRIPT)],
                                  input=json.dumps({"tool_name": "Read", "cwd": str(repo),
                                                    "tool_input": {"file_path": str(repo / "Service.java")}}),
                                  env=env, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            receipt = json.loads(proc.stdout)
            self.assertEqual(receipt["reason_code"], "no_eligible_claims")
            self.assertEqual(receipt["checked_claims"], 0)
            self.assertIn("dependencies", receipt["warning"])
            warmed = subprocess.run([sys.executable, "-S", str(WARM_SCRIPT), str(repo), "Service.java"],
                                    env=env, capture_output=True, text=True, check=True)
            result = json.loads(warmed.stdout)
            self.assertFalse(result["all_fresh_now"], result)
            self.assertEqual(result["checked_claims"], 0)
            self.assertTrue(result["warning"])

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

@unittest.skipUnless(
    importlib.util.find_spec("tree_sitter") and importlib.util.find_spec("tree_sitter_java"),
    "Java extraction dependencies are not installed",
)
class JavaReflexHealthTests(unittest.TestCase):
    SOURCE = (
        "class Service {\n"
        "    int count = 1;\n"
        "    Service() { count = 2; }\n"
        "    int changed() { return count; }\n"
        "    int stable() { return 7; }\n"
        "}\n"
    )

    def test_java_production_method_claim_blocks_read_edit_and_write(self):
        from tmf.freshness import check_freshness
        from tmf.git import GitRepo
        from tmf.store import Store

        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(Path(td), {"Service.java": self.SOURCE})
            warm_repo(repo)
            method = next(c for c in Store(repo).iter_claims()
                          if c.body.get("qualname") == "Service.changed"
                          and c.body.get("extraction_tier") == "java-treesitter-syntactic")
            self.assertEqual(method.scope, "class")
            self.assertEqual(method.bindings[0].role, "declaration")
            self.assertTrue(check_freshness(GitRepo(repo), method).fresh)
            before = run_hook(repo, "Service.java", tool_name="Read")
            self.assertEqual(before.returncode, 0, before.stderr)
            self.assertEqual(json.loads(before.stdout)["reason_code"], "fresh")
            (repo / "Service.java").write_text(
                self.SOURCE.replace("return count;", "return count + 1;"), encoding="utf-8")
            freshness = check_freshness(GitRepo(repo), method)
            self.assertFalse(freshness.fresh)
            self.assertEqual(freshness.stale_bindings,
                             ["Service.java:Service.changed: java_hash mismatch"])
            for tool in ("Read", "Edit", "Write"):
                with self.subTest(tool=tool):
                    proc = run_hook(repo, "Service.java", tool_name=tool)
                    self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
                    receipt = json.loads(proc.stderr)
                    self.assertEqual(receipt["reason_code"], "stale_collision")
                    names = {item["qualname"] for item in receipt["stale_paths"]}
                    self.assertIn("Service.changed", names)
                    self.assertNotIn("Service.stable", names)
                    self.assertNotIn("Service.Service", names)
                    for item in receipt["stale_paths"]:
                        self.assertEqual(item["path"], "Service.java")
                        self.assertTrue(item["anchor"]["reliable"])

    def test_java_constructor_field_and_type_changes_block(self):
        cases = [
            ("count = 2;", "count = 3;", "Service.Service"),
            ("count = 1;", "count = 9;", "Service.count"),
            ("class Service", "final class Service", "Service"),
        ]
        for old, new, name in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as td:
                repo = make_repo(Path(td), {"Service.java": self.SOURCE})
                warm_repo(repo)
                (repo / "Service.java").write_text(self.SOURCE.replace(old, new), encoding="utf-8")
                proc = run_hook(repo, "Service.java")
                self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
                names = {item["qualname"] for item in json.loads(proc.stderr)["stale_paths"]}
                self.assertIn(name, names)
                self.assertNotIn("Service.stable", names)

    def test_java_renamed_and_deleted_methods_block(self):
        for replacement in ("    int renamed() { return count; }\n", ""):
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as td:
                repo = make_repo(Path(td), {"Service.java": self.SOURCE})
                warm_repo(repo)
                (repo / "Service.java").write_text(
                    self.SOURCE.replace("    int changed() { return count; }\n", replacement),
                    encoding="utf-8")
                proc = run_hook(repo, "Service.java")
                self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
                missing = [item for item in json.loads(proc.stderr)["stale_paths"]
                           if item["qualname"] == "Service.changed"]
                self.assertEqual(len(missing), 1)
                self.assertEqual(missing[0]["detail"], "java node missing")

    def test_java_overload_mutation_keeps_changed_declaration_anchor(self):
        source = (
            "class Service {\n"
            "    int size(int value) { return value; }\n"
            "    int size(String value) { return value.length(); }\n"
            "}\n"
        )
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(Path(td), {"Service.java": source})
            warm_repo(repo)
            (repo / "Service.java").write_text(
                source.replace("return value;", "return value + 1;"), encoding="utf-8")
            proc = run_hook(repo, "Service.java")
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            overloads = [item for item in json.loads(proc.stderr)["stale_paths"]
                         if item["qualname"] == "Service.size"]
            self.assertEqual(len(overloads), 1)
            self.assertEqual(overloads[0]["anchor"]["line_start"], 2)

    def test_java_unchanged_target_does_not_check_relationship_endpoint(self):
        from tmf.freshness import check_freshness
        from tmf.git import GitRepo
        from tmf.store import Store

        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(Path(td), {
                "Child.java": "class Child extends Parent { int own() { return 2; } }\n",
                "Parent.java": "class Parent { int base() { return 1; } }\n",
            })
            warm_repo(repo)
            edges = [c for c in Store(repo).iter_claims() if c.body.get("edge_kind") == "inherits"]
            self.assertTrue(edges, "fixture must contain a production relationship")
            (repo / "Parent.java").write_text(
                "class Parent { int base() { return 9; } }\n", encoding="utf-8")
            self.assertTrue(any(not check_freshness(GitRepo(repo), c).fresh for c in edges))
            proc = run_hook(repo, "Child.java")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["reason_code"], "fresh")
            self.assertEqual(run_hook(repo, "Parent.java").returncode, 2)

    def test_java_local_warm_verifies_same_nodes_and_is_file_local(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(Path(td), {
                "Service.java": self.SOURCE,
                "Other.java": "class Other { int value() { return 1; } }\n",
            })
            warm_repo(repo)
            (repo / "Service.java").write_text(
                self.SOURCE.replace("return count;", "return count + 1;"), encoding="utf-8")
            (repo / "Other.java").write_text(
                "class Other { int value() { return 2; } }\n", encoding="utf-8")
            self.assertEqual(run_hook(repo, "Service.java").returncode, 2)
            result = local_warm(repo, "Service.java")
            self.assertEqual(result["function_claims"], 0)
            self.assertGreater(result["checked_claims"], 0)
            self.assertEqual(result["checked_claims"], len(result["stale_check"]))
            self.assertTrue(result["all_fresh_now"], result)
            self.assertIn("Service.changed", result["functions"])
            self.assertIn("Service.Service", result["functions"])
            self.assertIn("Service.count", result["functions"])
            after = run_hook(repo, "Service.java")
            self.assertEqual(after.returncode, 0, after.stderr)
            self.assertEqual(json.loads(after.stdout)["checked_claims"], result["checked_claims"])
            self.assertEqual(run_hook(repo, "Other.java").returncode, 2)

    def test_enriched_java_declaration_checks_own_binding_without_mutating_store(self):
        from tmf.freshness import check_freshness
        from tmf.git import GitRepo
        from tmf.store import Store

        owner = ("package app;\nimport jakarta.persistence.Entity;\n"
                 "@Entity class Owner { Long id; }\n")
        repository = (
            "package app;\n"
            "import org.springframework.data.jpa.repository.JpaRepository;\n"
            "public interface OwnerRepo extends JpaRepository<Owner, Long> {\n"
            "    int VERSION = 1;\n"
            "    Owner findById(Long id);\n"
            "}\n"
        )
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(Path(td), {"Owner.java": owner, "OwnerRepo.java": repository})
            warm_repo(repo)
            store = Store(repo)
            declaration = next(c for c in store.iter_claims()
                               if c.body.get("extraction_tier") == "java-treesitter-syntactic"
                               and c.body.get("node_kind") == "interface"
                               and any(b.path == "OwnerRepo.java" for b in c.bindings))
            self.assertTrue(any(b.role == "repository_domain_entity" for b in declaration.bindings),
                            declaration.to_dict())
            original = declaration.to_dict()
            self.assertTrue(check_freshness(GitRepo(repo), declaration).fresh)

            # An external entity change stales the enriched claim, not this
            # unchanged local declaration. The file gate must remain local.
            (repo / "Owner.java").write_text(owner.replace("Long id", "Integer id"), encoding="utf-8")
            self.assertFalse(check_freshness(GitRepo(repo), declaration).fresh)
            result = run_hook(repo, "OwnerRepo.java")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["reason_code"], "fresh")
            self.assertEqual(store.get_claim(declaration.id).to_dict(), original)

            (repo / "Owner.java").write_text(owner, encoding="utf-8")
            (repo / "OwnerRepo.java").write_text(
                repository.replace("JpaRepository<Owner, Long>", "JpaRepository<Owner, Integer>"),
                encoding="utf-8")
            self.assertFalse(check_freshness(GitRepo(repo), declaration).fresh)
            result = run_hook(repo, "OwnerRepo.java")
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            receipt = json.loads(result.stderr)
            names = {item["qualname"] for item in receipt["stale_paths"]}
            self.assertIn(declaration.body["qualname"], names)
            self.assertFalse(any(name.endswith("findById") for name in names), names)
            self.assertTrue(all(item["path"] == "OwnerRepo.java" for item in receipt["stale_paths"]))
            self.assertEqual(store.get_claim(declaration.id).to_dict(), original)
            recovered = local_warm(repo, "OwnerRepo.java")
            self.assertTrue(recovered["all_fresh_now"], recovered)
            self.assertIn(declaration.body["qualname"], recovered["functions"])
            self.assertEqual(run_hook(repo, "OwnerRepo.java").returncode, 0)

    def test_java_empty_file_is_not_fresh(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(Path(td), {"Empty.java": "// no declarations\n"})
            warm_repo(repo)
            proc = run_hook(repo, "Empty.java")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["reason_code"], "no_eligible_claims")
            result = local_warm(repo, "Empty.java")
            self.assertFalse(result["all_fresh_now"], result)
            self.assertEqual(result["checked_claims"], 0)


if __name__ == "__main__":
    unittest.main()
