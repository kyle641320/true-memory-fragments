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
    parser.add_argument("--require-java", action="store_true",
                        help="Fail rather than skip Java coverage when the parser extra is absent")
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
        java_available = json.loads(run(python_args + ["-c", (
            "import json; from tmf.java_extract import java_status; "
            "print(json.dumps(java_status().available))"
        )]).stdout)
        if args.require_java and not java_available:
            raise AssertionError("Java reflex acceptance requires the [java] parser extra; cannot skip")
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
        checks = ["warmed_unarmed", "mutated_unarmed", "configured_registration",
                  "fresh_hook_allow", "stale_hook_block"]

        # A matched tool with no eligible claims is not a freshness measurement.
        uncovered = repo / "Unindexed.java"
        uncovered.write_text("class Unindexed { int value() { return 1; } }\n", encoding="utf-8")
        uncovered_payload = json.dumps({"tool_name": "Read", "cwd": str(repo),
                                        "tool_input": {"file_path": str(uncovered)}})
        uncovered_result = run(python_args + [str(hook)], stdin=uncovered_payload)
        uncovered_report = json.loads(uncovered_result.stdout)
        assert uncovered_report["reason_code"] == "no_eligible_claims", uncovered_report
        assert uncovered_report.get("warning"), uncovered_report
        checks.append("uncovered_java_not_reported_fresh")

        if java_available:
            java_target = repo / "Service.java"
            java_original = ("class Service { int value() { return 1; } "
                             "int control() { return 3; } }\n")
            java_target.write_text(java_original, encoding="utf-8")
            run(["git", "add", "Service.java"])
            run(["git", "commit", "-m", "Java fixture baseline"])
            run(cli + ["warm", "--repo", str(repo)])
            # Assert actual production representation and T0 freshness, not
            # hand-built claims or a hook's self-declared capabilities.
            probe = (
                "import json; from tmf.store import Store; from tmf.git import GitRepo; "
                "from tmf.freshness import check_freshness; "
                "cs=[c for c in Store('.').iter_claims() if c.body.get('language')=='java' "
                "and c.body.get('node_kind')=='method' and c.bindings[0].path=='Service.java']; "
                "assert len(cs)==2; "
                "assert all(c.scope=='class' and c.bindings[0].role=='declaration' for c in cs); "
                "print(json.dumps({c.body['qualname']:check_freshness(GitRepo('.'),c).fresh for c in cs}))"
            )
            assert json.loads(run(python_args + ["-c", probe]).stdout) == {
                "Service.value": True, "Service.control": True}
            doctor(True)
            for tool_name in ("Read", "Edit", "Write"):
                event = json.dumps({"tool_name": tool_name, "cwd": str(repo),
                                    "tool_input": {"file_path": str(java_target)}})
                result = json.loads(run(python_args + [str(hook)], stdin=event).stdout)
                assert result["reason_code"] == "fresh", result
            java_target.write_text(java_original.replace("return 1", "return 2"), encoding="utf-8")
            assert json.loads(run(python_args + ["-c", probe]).stdout) == {
                "Service.value": False, "Service.control": True}
            for tool_name in ("Read", "Edit", "Write"):
                event = json.dumps({"tool_name": tool_name, "cwd": str(repo),
                                    "tool_input": {"file_path": str(java_target)}})
                blocked = run(python_args + [str(hook)], code=2, stdin=event)
                report = json.loads(blocked.stderr)
                assert report["decision"] == "block", report
                names = {item["qualname"] for item in report["stale_paths"]}
                assert "Service.value" in names and "Service.control" not in names, report
                assert all(item["path"] == "Service.java" for item in report["stale_paths"]), report
            warmed = json.loads(run(python_args + [str(integration / "scripts/local_warm.py"),
                                  str(repo), "Service.java"]).stdout)
            assert warmed["all_fresh_now"] is True and warmed["stale_check"], warmed
            assert any(item["qualname"] == "Service.value" for item in warmed["stale_check"]), warmed
            result = json.loads(run(python_args + [str(hook)], stdin=event).stdout)
            assert result["reason_code"] == "fresh", result

            # Model the historical function-only integration separately from
            # the installed engine; an engine upgrade cannot update this copy.
            current_script = hook.read_text(encoding="utf-8")
            legacy_script = '''from tmf.freshness import check_freshness
def check_file_freshness(repo_root, rel_path, state_root):
    from tmf.store import Store
    claim_ids = set()
    for claim in Store(repo_root).iter_claims():
        if claim.scope != "function":
            continue
        for binding in claim.bindings:
            if binding.path == rel_path:
                claim_ids.add(claim.id)
    if not claim_ids:
        return {"fresh": True, "stale_functions": [], "error": None}
    return all(check_freshness(repo_root, claim).fresh
               for claim in Store(repo_root).iter_claims() if claim.id in claim_ids)
def main():
    check_file_freshness(".", "Service.java", ".tmf")
'''
            hook.write_text(legacy_script, encoding="utf-8")
            legacy_report = doctor(False)
            assert "registration_found" in {item["code"] for item in legacy_report["findings"]}, legacy_report
            assert "java_function_only_filter" in {item["code"] for item in legacy_report["findings"]}, legacy_report
            hook.write_text(current_script, encoding="utf-8")
            doctor(True)
            checks.extend(["java_production_claims_fresh", "java_read_edit_write_fresh_allow",
                           "java_mutation_and_unchanged_control", "java_read_edit_write_stale_block",
                           "java_local_rewarm_restores_coverage", "legacy_java_blind_hook_not_armed"])
        settings["disableAllHooks"] = True
        settings_path.write_text(json.dumps(settings), encoding="utf-8")
        doctor(False)
        checks.extend(["disabled_registration", "removed_registration", "doctor_read_only"])
        settings_path.write_text("{}", encoding="utf-8")
        doctor(False)

        print(json.dumps({
            "status": "pass", "package": module,
            "installed_wheel": bool(args.python),
            "checks": checks,
            "java_behavioral_checks": "passed" if java_available else "skipped: parser extra absent",
            "claude_host_dispatch_verified": False,
            "autonomous_agent_experiment": False,
        }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
