#!/usr/bin/env python3
"""Verify the Java qualification release inputs from a source-only export.

The export is index-free and deliberately excludes VCS metadata, lock files,
reports, caches, generated state, and unrelated repository content.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
INCLUDE_FILES = (
    "CHANGES.md",
    "README.md",
    "RELEASE_EVIDENCE.md",
    "pyproject.toml",
    "tools/java_qualification_manifest.json",
    "tools/run_java_qualifications.py",
    "tests/test_java_configuration_properties.py",
    "tests/test_java_extract_structure.py",
    "tests/test_java_inherit.py",
    "tests/test_run_java_qualifications.py",
)
INCLUDE_TREES = ("fixtures", "tmf")
EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    ".tmf",
    "__pycache__",
    "build",
    "dist",
    "generated",
    "reports",
}
EXCLUDED_NAMES = {"uv.lock"}


def _ignored(relative: Path) -> bool:
    return relative.name in EXCLUDED_NAMES or any(part in EXCLUDED_PARTS for part in relative.parts)


def _copy_file(source: Path, export: Path) -> None:
    relative = source.relative_to(ROOT)
    if _ignored(relative):
        return
    target = export / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def export_sources(export: Path) -> list[str]:
    for name in INCLUDE_FILES:
        source = ROOT / name
        if not source.is_file():
            raise FileNotFoundError(f"required source input is missing: {name}")
        _copy_file(source, export)
    for name in INCLUDE_TREES:
        source_root = ROOT / name
        if not source_root.is_dir():
            raise FileNotFoundError(f"required source tree is missing: {name}")
        for source in sorted(source_root.rglob("*")):
            if source.is_file():
                _copy_file(source, export)
    for source in sorted((ROOT / "tools").glob("verify_java_*_qualification.py")):
        _copy_file(source, export)
    return sorted(path.relative_to(export).as_posix() for path in export.rglob("*") if path.is_file())


def _run(export: Path, *args: str) -> dict[str, object]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [sys.executable, *args],
        cwd=export,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    result: dict[str, object] = {
        "command": ["python3", *args],
        "returncode": completed.returncode,
    }
    if completed.stdout.strip():
        result["stdout"] = completed.stdout.strip()
    if completed.stderr.strip():
        result["stderr"] = completed.stderr.strip()
    if completed.returncode:
        raise RuntimeError(json.dumps(result, sort_keys=True))
    return result


def main() -> int:
    try:
        with tempfile.TemporaryDirectory(prefix="tmf-java-source-smoke-") as directory:
            export = Path(directory) / "source"
            export.mkdir()
            files = export_sources(export)
            forbidden = [name for name in files if _ignored(Path(name))]
            if forbidden:
                raise RuntimeError(f"source export contains excluded paths: {forbidden}")
            if not files:
                raise RuntimeError("source export is empty")
            qualifications = _run(export, "tools/run_java_qualifications.py")
            qualification_summary = json.loads(str(qualifications.get("stdout", "")))
            focused = _run(
                export,
                "-m",
                "unittest",
                "-v",
                "tests.test_java_extract_structure",
                "tests.test_java_configuration_properties",
                "tests.test_run_java_qualifications",
            )
            compileall = _run(export, "-m", "compileall", "-q", "tmf", "tests", "tools")
            summary = {
                "compileall": "passed",
                "excluded": sorted(EXCLUDED_NAMES | EXCLUDED_PARTS),
                "exported_files": len(files),
                "focused_tests": "passed",
                "qualifications": {
                    "checks_passed": sum(
                        int(result["checks_passed"])
                        for result in qualification_summary["results"]
                    ),
                    "checks_total": sum(
                        int(result["checks_total"])
                        for result in qualification_summary["results"]
                    ),
                    "failed": qualification_summary["failed"],
                    "passed": qualification_summary["passed"],
                    "total": qualification_summary["total"],
                },
                "source_only": True,
            }
            print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
            return 0
    except (FileNotFoundError, json.JSONDecodeError, KeyError, OSError, RuntimeError) as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True, separators=(",", ":")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
