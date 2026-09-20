"""Offline installed-but-unarmed regression; never changes live client settings.

Use --python to exercise an installed wheel from outside its source checkout.
The hook invocation is a deterministic fixture, not a Claude host-dispatch test
or an autonomous-agent A/B experiment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile


WARNING = "reflex NOT armed — operating as opt-in memory"


def snapshot(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*") if path.is_file()
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", help="Python in a wheel installation venv")
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    # Resolving a venv's Python symlink would select the system interpreter.
    python = os.path.abspath(args.python or sys.executable)
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("TMF_", "PYTHON", "CLAUDE_", "GIT_"))}
    env.update(PYTHONDONTWRITEBYTECODE="1", GIT_CONFIG_NOSYSTEM="1",
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_COUNT="0")
    if not args.python:
        env["PYTHONPATH"] = str(source)
    python_args = [python, "-I", "-B"] if args.python else [python, "-B"]

    with tempfile.TemporaryDirectory(prefix="tmf-reflex-arming-") as directory:
        root = Path(directory)
        repo = root / "target repo"
        repo.mkdir()
        config = root / "claude-config"
        config.mkdir()
        env["CLAUDE_CONFIG_DIR"] = str(config)

        def run(argv: list[str], *, code: int = 0, stdin: str | None = None):
            result = subprocess.run(argv, cwd=repo, env=env, input=stdin,
                                    capture_output=True, text=True, timeout=60)
            if result.returncode != code:
                raise AssertionError(
                    f"{argv!r}: expected exit {code}, got {result.returncode}\n"
                    f"{result.stdout}\n{result.stderr}")
            return result

        module = run(python_args + ["-c", "import tmf; print(tmf.__file__)"]).stdout.strip()
        if args.python:
            run(python_args + ["-c", (
                "import pathlib, sys, tmf; "
                "p=pathlib.Path(tmf.__file__).resolve(); "
                "assert p.is_relative_to(pathlib.Path(sys.prefix).resolve()), p; "
                "assert 'site-packages' in p.parts, p"
            )])
        for git_args in (("init",), ("config", "user.name", "TMF smoke"),
                         ("config", "user.email", "smoke@example.invalid"),
                         ("config", "maintenance.auto", "false"),
                         ("config", "gc.auto", "0")):
            run(["git", *git_args])
        target = repo / "service.py"
        original = "def calculate(value):\n    return value + 1\n"
        target.write_text(original, encoding="utf-8")
        run(["git", "add", "service.py"])
        run(["git", "commit", "-m", "fixture baseline"])
        cli = python_args + ["-m", "tmf.cli"]
        run(cli + ["warm", "--repo", str(repo)])
        assert (repo / ".tmf").is_dir(), "fixture must have a warmed engine"

        def doctor(armed: bool) -> dict:
            before = snapshot(root)
            result = run(cli + ["doctor", "--repo", str(repo), "--json"],
                         code=0 if armed else 1)
            report = json.loads(result.stdout)
            assert report["armed"] is armed, report
            assert report["runtime_verified"] is False, report
            assert snapshot(root) == before, "doctor must not mutate the fixture"
            if not armed:
                text_result = run(cli + ["doctor", "--repo", str(repo)], code=1)
                assert WARNING in text_result.stdout + text_result.stderr
                assert snapshot(root) == before, "text doctor must also be read-only"
            return report

        doctor(False)
        target.write_text("def calculate(value, offset):\n    return value + offset\n", encoding="utf-8")
        doctor(False)
        target.write_text(original, encoding="utf-8")

        integration = repo / "integrations" / "reflex"
        for name in ("hooks", "scripts"):
            shutil.copytree(source / "integrations" / "reflex" / name,
                            integration / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        hook = integration / "hooks" / "pre_tool_use.py"
        settings_path = repo / ".claude" / "settings.json"
        settings_path.parent.mkdir()
        settings = {"hooks": {"PreToolUse": [{
            "matcher": "Read|Edit|Write", "hooks": [{
                "type": "command", "command": shlex.join([python, str(hook)]), "timeout": 5,
            }],
        }]}}
        settings_path.write_text(json.dumps(settings), encoding="utf-8")
        doctor(True)
        payload = json.dumps({"tool_name": "Edit", "cwd": str(repo),
                              "tool_input": {"file_path": str(target)}})
        run(python_args + [str(hook)], stdin=payload)
        target.write_text("def calculate(value, offset):\n    return value + offset\n", encoding="utf-8")
        blocked = run(python_args + [str(hook)], code=2, stdin=payload)
        assert "calculate" in blocked.stderr, blocked.stderr
        settings["disableAllHooks"] = True
        settings_path.write_text(json.dumps(settings), encoding="utf-8")
        doctor(False)
        settings_path.write_text("{}", encoding="utf-8")
        doctor(False)

        print(json.dumps({
            "status": "pass", "package": module,
            "installed_wheel": bool(args.python),
            "checks": ["warmed_unarmed", "mutated_unarmed", "configured_registration",
                       "fresh_hook_allow", "stale_hook_block", "disabled_registration",
                       "removed_registration", "doctor_read_only"],
            "claude_host_dispatch_verified": False,
            "autonomous_agent_experiment": False,
        }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
