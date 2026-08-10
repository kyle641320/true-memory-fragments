#!/usr/bin/env python3
"""Opt-in integration gate that really compiles selected held-out Gradle fixtures.

This is deliberately separate from the fast qualification runner: it invokes Gradle
rather than treating the presence of build files as evidence that a build ran.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tools" / "java_qualification_manifest.json"
DEFAULT_TIMEOUT_SECONDS = 300


def gradle_command() -> str:
    configured = os.environ.get("TMF_GRADLE")
    command = configured or shutil.which("gradle")
    if not command:
        raise RuntimeError("Gradle is required; put gradle on PATH or set TMF_GRADLE")
    return command


def fixture_names() -> list[str]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    names = manifest.get("gradle_integration_verifiers")
    if not isinstance(names, list) or not names or not all(isinstance(name, str) for name in names):
        raise ValueError("manifest gradle_integration_verifiers must be a non-empty string list")
    if len(names) != len(set(names)):
        raise ValueError("manifest gradle_integration_verifiers contains duplicates")
    return names


def run_build(name: str, command: str, timeout: int) -> dict[str, object]:
    fixture_name = name.replace("_", "-")
    project = ROOT / "fixtures" / f"java-{fixture_name}-heldout" / "gradle"
    required = (project / "settings.gradle", project / "build.gradle")
    if not project.is_dir() or not all(path.is_file() for path in required):
        return {"name": name, "passed": False, "error": "Gradle fixture is incomplete"}
    args = [command, "--no-daemon", "--max-workers=1", "--console=plain", "clean", "build"]
    try:
        completed = subprocess.run(
            args, cwd=project, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as error:
        output = error.stdout.decode() if isinstance(error.stdout, bytes) else (error.stdout or "")
        return {"name": name, "passed": False, "error": f"timed out after {timeout}s", "output": output[-4000:]}
    output = completed.stdout or ""
    passed = completed.returncode == 0 and "BUILD SUCCESSFUL" in output
    result: dict[str, object] = {"name": name, "passed": passed, "returncode": completed.returncode}
    if not passed:
        result["output"] = output[-4000:]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="list the bounded fixture set without building")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args()
    names = fixture_names()
    if args.list:
        print("\n".join(names))
        return 0
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    try:
        command = gradle_command()
    except RuntimeError as error:
        print(json.dumps({"passed": False, "error": str(error)}, sort_keys=True, separators=(",", ":")))
        return 1
    results = [run_build(name, command, args.timeout) for name in names]
    passed = sum(bool(result["passed"]) for result in results)
    print(json.dumps({"gradle": command, "passed": passed, "total": len(results), "results": results}, sort_keys=True, separators=(",", ":")))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
