#!/usr/bin/env python3
"""Run every deterministic Java held-out qualification verifier."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
PATTERN = "verify_java_*_qualification.py"
MANIFEST = TOOLS / "java_qualification_manifest.json"
FIXTURE_SUFFIX = "-heldout"
OUTPUT_CONTRACT = "tmf.java-qualification-output.v1"
VERIFIER_TIMEOUT_SECONDS = 300


def verifier_paths() -> list[Path]:
    return sorted(TOOLS.glob(PATTERN), key=lambda path: path.name)


def _fixture_corpora(path: Path) -> set[str]:
    """Return held-out corpus names referenced by a verifier's string literals."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    corpora: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        for part in node.value.replace("\\", "/").split("/"):
            if part.startswith("java-") and part.endswith(FIXTURE_SUFFIX):
                corpora.add(part)
    return corpora


def validate_fixture_corpora(paths: list[Path], manifest: dict[str, object]) -> None:
    shared = manifest.get("shared_fixture_corpora", {})
    if not isinstance(shared, dict):
        raise ValueError("Java qualification manifest shared_fixture_corpora must be an object")
    actual_names = {path.stem.removeprefix("verify_java_").removesuffix("_qualification") for path in paths}
    for name, declaration in shared.items():
        if name not in actual_names or not isinstance(declaration, dict):
            raise ValueError(f"invalid shared fixture declaration for {name!r}")
        corpus = declaration.get("corpus")
        reason = declaration.get("reason")
        if not isinstance(corpus, str) or not corpus.endswith(FIXTURE_SUFFIX):
            raise ValueError(f"shared fixture declaration for {name!r} needs a held-out corpus")
        if not isinstance(reason, str) or len(reason.strip()) < 20:
            raise ValueError(f"shared fixture declaration for {name!r} needs an auditable reason")
    fingerprints: dict[str, str] = {}
    for path in paths:
        name = path.stem.removeprefix("verify_java_").removesuffix("_qualification")
        corpora = _fixture_corpora(path)
        expected = f"java-{name.replace('_', '-')}{FIXTURE_SUFFIX}"
        declaration = shared.get(name)
        allowed = declaration["corpus"] if isinstance(declaration, dict) else expected
        if corpora != {allowed}:
            raise ValueError(
                f"Java qualification fixture mismatch for {name}: expected={[allowed]}, actual={sorted(corpora)}"
            )
        corpus_root = ROOT / "fixtures" / allowed
        split_layout = all((corpus_root / build_file).is_file() for build_file in ("maven/pom.xml", "gradle/build.gradle"))
        root_layout = all((corpus_root / build_file).is_file() for build_file in ("pom.xml", "build.gradle"))
        if not split_layout and not root_layout:
            raise ValueError(f"Java qualification fixture {allowed} needs complete Maven and Gradle builds")
        source_hashes = sorted({
            hashlib.sha256(source.read_bytes()).hexdigest()
            for source in corpus_root.rglob("*.java")
        })
        if not source_hashes:
            raise ValueError(f"Java qualification fixture {allowed} has no Java evidence")
        fingerprint = hashlib.sha256("\n".join(source_hashes).encode("ascii")).hexdigest()
        previous = fingerprints.get(fingerprint)
        if previous is not None and previous != allowed:
            raise ValueError(f"Java qualification fixtures {previous} and {allowed} have identical evidence")
        fingerprints[fingerprint] = allowed


def validate_manifest(paths: list[Path]) -> dict[str, object]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("format") != "tmf.java-qualification-manifest.v3":
        raise ValueError("Java qualification manifest format must be 'tmf.java-qualification-manifest.v3'")
    if manifest.get("release_status") != "unreleased":
        raise ValueError("Java qualification manifest release_status must be 'unreleased'")
    if manifest.get("output_contract") != OUTPUT_CONTRACT:
        raise ValueError(f"Java qualification manifest output_contract must be {OUTPUT_CONTRACT!r}")
    if manifest.get("verifier_timeout_seconds") != VERIFIER_TIMEOUT_SECONDS:
        raise ValueError(
            "Java qualification manifest verifier_timeout_seconds must be "
            f"{VERIFIER_TIMEOUT_SECONDS}"
        )
    expected = manifest.get("verifiers")
    expected_count = manifest.get("expected_count")
    expected_checks = manifest.get("expected_checks")
    full_unittest_count = manifest.get("full_unittest_count")
    if not isinstance(expected, list) or not all(isinstance(name, str) for name in expected):
        raise ValueError("Java qualification manifest verifiers must be a list of strings")
    if len(expected) != len(set(expected)):
        raise ValueError("Java qualification manifest verifiers must be unique")
    if expected_count != len(expected):
        raise ValueError("Java qualification manifest expected_count does not match verifiers")
    if not isinstance(expected_checks, int) or isinstance(expected_checks, bool) or expected_checks < expected_count:
        raise ValueError("Java qualification manifest expected_checks must be an integer >= expected_count")
    if not isinstance(full_unittest_count, int) or isinstance(full_unittest_count, bool) or full_unittest_count < 1:
        raise ValueError("Java qualification manifest full_unittest_count must be a positive integer")
    actual = [path.stem.removeprefix("verify_java_").removesuffix("_qualification") for path in paths]
    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        unexpected = sorted(set(actual) - set(expected))
        raise ValueError(f"Java qualification manifest mismatch: missing={missing}, unexpected={unexpected}")
    validate_fixture_corpora(paths, manifest)
    return manifest


def validate_result_baseline(results: list[dict[str, object]], manifest: dict[str, object]) -> None:
    """Fail closed when successful verifier outputs drift from the manifest check baseline."""
    if not results or not all(result.get("passed") is True for result in results):
        return
    actual_checks = sum(int(result["checks_total"]) for result in results)
    expected_checks = int(manifest["expected_checks"])
    if actual_checks != expected_checks:
        raise ValueError(
            "Java qualification check baseline mismatch: "
            f"expected={expected_checks}, actual={actual_checks}"
        )


def _validated_output(stdout: str) -> tuple[dict[str, object] | None, str | None]:
    if not stdout:
        return None, "verifier stdout is empty"
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return None, f"verifier stdout is not one JSON object: {exc.msg}"
    if not isinstance(parsed, dict):
        return None, "verifier stdout JSON must be an object"
    checks = parsed.get("checks")
    passed = parsed.get("passed")
    total = parsed.get("total")
    if not isinstance(checks, dict) or not checks:
        return None, "verifier output checks must be a non-empty object"
    if not all(isinstance(name, str) and isinstance(value, bool) for name, value in checks.items()):
        return None, "verifier output checks must map string names to booleans"
    if not isinstance(passed, int) or isinstance(passed, bool):
        return None, "verifier output passed must be an integer"
    if not isinstance(total, int) or isinstance(total, bool):
        return None, "verifier output total must be an integer"
    actual_passed = sum(checks.values())
    if (passed, total) != (actual_passed, len(checks)):
        return None, (
            "verifier output counts do not match checks: "
            f"reported={passed}/{total}, actual={actual_passed}/{len(checks)}"
        )
    return parsed, None


def _duration_ms(start_ns: int) -> int:
    return (time.perf_counter_ns() - start_ns) // 1_000_000


def run_all(paths: list[Path], *, include_timings: bool = False) -> tuple[list[dict[str, object]], int]:
    results: list[dict[str, object]] = []
    failures = 0
    for path in paths:
        start_ns = time.perf_counter_ns()
        try:
            completed = subprocess.run(
                [sys.executable, str(path)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
                timeout=VERIFIER_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            def text(value: str | bytes | None) -> str:
                if isinstance(value, bytes):
                    return value.decode(errors="replace").strip()
                return value.strip() if value else ""

            failures += 1
            result: dict[str, object] = {
                "name": path.stem.removeprefix("verify_java_").removesuffix("_qualification"),
                "passed": False,
                "returncode": None,
                "contract_error": f"verifier timed out after {VERIFIER_TIMEOUT_SECONDS} seconds",
                "stdout": text(exc.stdout),
                "stderr": text(exc.stderr),
            }
            if include_timings:
                result["duration_ms"] = _duration_ms(start_ns)
            results.append(result)
            continue
        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        parsed, contract_error = _validated_output(stdout)
        if (
            contract_error is None
            and completed.returncode == 0
            and parsed is not None
            and parsed["passed"] != parsed["total"]
        ):
            contract_error = "verifier exited zero with failed checks"
        passed = completed.returncode == 0 and contract_error is None
        failures += not passed
        result: dict[str, object] = {
            "name": path.stem.removeprefix("verify_java_").removesuffix("_qualification"),
            "passed": passed,
            "returncode": completed.returncode,
        }
        if include_timings:
            result["duration_ms"] = _duration_ms(start_ns)
        if parsed is not None:
            result["checks_passed"] = parsed["passed"]
            result["checks_total"] = parsed["total"]
        if contract_error is not None:
            result["contract_error"] = contract_error
        if not passed:
            result["stdout"] = stdout
            result["stderr"] = stderr
        results.append(result)
    return results, failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="list verifiers without running them")
    parser.add_argument(
        "--timings",
        action="store_true",
        help="include non-deterministic wall-clock duration_ms for each verifier",
    )
    args = parser.parse_args()
    manifest: dict[str, object] | None = None
    try:
        paths = verifier_paths()
        if all(path.parent.resolve() == TOOLS.resolve() for path in paths):
            manifest = validate_manifest(paths)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True))
        return 2
    if args.list:
        print("\n".join(path.name for path in paths))
        return 0
    if not paths:
        print(json.dumps({"error": "no Java qualification verifiers found"}, sort_keys=True))
        return 2
    results, failures = run_all(paths, include_timings=args.timings)
    if manifest is not None:
        try:
            validate_result_baseline(results, manifest)
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}, sort_keys=True))
            return 2
    summary: dict[str, object] = {
        "failed": failures,
        "passed": len(results) - failures,
        "results": results,
        "total": len(results),
    }
    if args.timings:
        summary["duration_ms"] = sum(int(result["duration_ms"]) for result in results)
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
