from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.store import Store
from tmf.warm import WARM_MANIFEST, warm_repo

from ten_repo_production_gate import SAMPLES, timed_warm


MARKER_PREFIX = "// TMF mutation/restore probe: "
EVENTUATE = {"eventuate-choreography", "eventuate-orchestration"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write_bytes(path: Path, data: bytes, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    atomic_write_bytes(path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def git_bytes(repo: Path, *args: str) -> bytes:
    process = subprocess.run(
        ["git", *args], cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
    )
    if process.returncode:
        raise RuntimeError(process.stderr.decode("utf-8", errors="replace").strip())
    return process.stdout


def tracked_diff_fingerprint(repo: Path) -> str:
    return sha256_bytes(git_bytes(repo, "diff", "--binary", "--no-ext-diff", "HEAD", "--"))


def dirty_tracked_paths(repo: Path) -> set[str]:
    raw = git_bytes(repo, "diff", "--name-only", "-z", "HEAD", "--")
    return {item.decode("utf-8", errors="surrogateescape") for item in raw.split(b"\0") if item}


def tracked_java_paths(repo: Path) -> set[str]:
    raw = git_bytes(repo, "ls-files", "-z", "--", "*.java")
    return {item.decode("utf-8", errors="surrogateescape") for item in raw.split(b"\0") if item}


def load_warmed_java_paths(repo: Path) -> set[str]:
    manifest = json.loads((repo / ".tmf" / WARM_MANIFEST).read_text(encoding="utf-8"))
    return {
        path for path in manifest.get("warmed_files", {})
        if isinstance(path, str) and path.endswith(".java")
    }


def choose_probe(repo: Path, explicit: str | None = None) -> str:
    dirty = dirty_tracked_paths(repo)
    eligible = tracked_java_paths(repo) & load_warmed_java_paths(repo)
    if explicit is not None:
        if explicit not in eligible:
            raise RuntimeError(f"explicit probe is not a tracked warmed Java file: {explicit}")
        candidates = [explicit]
    else:
        candidates = sorted(eligible, key=lambda item: ((repo / item).stat().st_size, item))
    for relpath in candidates:
        if relpath in dirty:
            continue
        data = (repo / relpath).read_bytes()
        if MARKER_PREFIX.encode("ascii") not in data:
            return relpath
    raise RuntimeError("no clean tracked warmed Java probe is available")


def mutated_bytes(original: bytes, token: str) -> bytes:
    marker = f"{MARKER_PREFIX}{token}\n".encode("ascii")
    if original.startswith(b"\xef\xbb\xbf"):
        return original[:3] + marker + original[3:]
    return marker + original


def recover_journal(journal_path: Path) -> dict[str, Any] | None:
    if not journal_path.exists():
        return None
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    if journal.get("state") in {"recovered", "complete"}:
        return journal
    target = Path(journal["repo"]) / journal["path"]
    original = base64.b64decode(journal["original_b64"])
    current = target.read_bytes()
    current_sha = sha256_bytes(current)
    if current_sha == journal["original_sha256"]:
        journal["state"] = "recovered"
        journal["recovery"] = "already_original"
    elif current_sha == journal["mutated_sha256"]:
        atomic_write_bytes(target, original, journal.get("mode"))
        journal["state"] = "recovered"
        journal["recovery"] = "restored_from_journal"
    else:
        raise RuntimeError(
            f"refusing to overwrite concurrent change in {target}; current content matches neither original nor probe"
        )
    atomic_write_json(journal_path, journal)
    return journal


def audit_claims(repo: Path, changed_path: str) -> dict[str, Any]:
    git = GitRepo(repo)
    changed_ids: set[str] = set()
    stale = 0
    unrelated_stale_count = 0
    unrelated_stale: list[str] = []
    claims = 0
    for claim in Store(repo).iter_claims():
        claims += 1
        related = any(binding.path == changed_path for binding in claim.bindings)
        if related:
            changed_ids.add(claim.id)
        if not check_freshness(git, claim).fresh:
            stale += 1
            if not related:
                unrelated_stale_count += 1
                if len(unrelated_stale) < 20:
                    unrelated_stale.append(claim.id)
    return {
        "claims": claims,
        "stale": stale,
        "unrelated_stale": unrelated_stale_count,
        "unrelated_stale_examples": unrelated_stale,
        "changed_path_claim_ids": sorted(changed_ids),
    }


def run_worker(kind: str, repo: Path, output: Path, changed_path: str | None = None) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    fd, raw_result = tempfile.mkstemp(prefix=f".{kind}-", suffix=".json", dir=output)
    os.close(fd)
    result_path = Path(raw_result)
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        kind,
        "--repo",
        str(repo),
        "--result-file",
        str(result_path),
    ]
    if changed_path is not None:
        command.extend(["--changed-path", changed_path])
    env = os.environ.copy()
    project_root = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (project_root, env.get("PYTHONPATH"))))
    try:
        process = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, env=env
        )
        if process.returncode != 0:
            stderr = process.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"{kind} worker exited {process.returncode}: {stderr or 'no stderr'}")
        try:
            value = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError(f"{kind} worker produced no valid result: {exc}") from exc
        if not isinstance(value, dict):
            raise RuntimeError(f"{kind} worker result is not an object")
        return value
    finally:
        result_path.unlink(missing_ok=True)


def run_probe(name: str, repo: Path, output: Path, explicit: str | None = None) -> dict[str, Any]:
    journal_path = output / "journals" / f"{name}.json"
    recovered = recover_journal(journal_path)
    if recovered and recovered.get("state") == "complete":
        result = recovered.get("result")
        if isinstance(result, dict):
            return result
        raise RuntimeError("completed journal is missing its checkpoint result")

    path = choose_probe(repo, explicit)
    target = repo / path
    original = target.read_bytes()
    mode = target.stat().st_mode & 0o7777
    token = hashlib.sha256(f"{name}\0{path}\0{sha256_bytes(original)}".encode("utf-8")).hexdigest()[:16]
    mutation = mutated_bytes(original, token)
    baseline_fingerprint = tracked_diff_fingerprint(repo)
    baseline_dirty = sorted(dirty_tracked_paths(repo))
    baseline_warm = run_worker("warm", repo, output)
    baseline_audit = run_worker("audit", repo, output, path)
    journal = {
        "schema": "tmf-mutation-journal-v1", "state": "prepared", "repo": str(repo), "path": path,
        "mode": mode, "original_b64": base64.b64encode(original).decode("ascii"),
        "original_sha256": sha256_bytes(original), "mutated_sha256": sha256_bytes(mutation),
        "baseline_diff_sha256": baseline_fingerprint,
    }
    atomic_write_json(journal_path, journal)

    mutation_warm: dict[str, Any] | None = None
    mutation_audit: dict[str, Any] | None = None
    restore_warm: dict[str, Any] | None = None
    restore_audit: dict[str, Any] | None = None
    error: str | None = None
    try:
        atomic_write_bytes(target, mutation, mode)
        journal["state"] = "mutated"
        atomic_write_json(journal_path, journal)
        mutation_warm = run_worker("warm", repo, output)
        mutation_audit = run_worker("audit", repo, output, path)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            current = target.read_bytes()
            if sha256_bytes(current) == journal["mutated_sha256"]:
                atomic_write_bytes(target, original, mode)
            elif sha256_bytes(current) != journal["original_sha256"]:
                raise RuntimeError("probe file changed concurrently; refusing automatic overwrite")
            journal["state"] = "recovered"
            atomic_write_json(journal_path, journal)
        except Exception as exc:
            recovery_error = f"{type(exc).__name__}: {exc}"
            error = f"{error}; recovery: {recovery_error}" if error else f"recovery: {recovery_error}"

    if journal.get("state") == "recovered":
        try:
            restore_warm = run_worker("warm", repo, output)
            restore_audit = run_worker("audit", repo, output, path)
        except Exception as exc:
            followup = f"{type(exc).__name__}: {exc}"
            error = f"{error}; restore warm: {followup}" if error else f"restore warm: {followup}"

    final_fingerprint = tracked_diff_fingerprint(repo)
    final_dirty = sorted(dirty_tracked_paths(repo))
    baseline_ids = set(baseline_audit["changed_path_claim_ids"])
    mutation_ids = set((mutation_audit or {}).get("changed_path_claim_ids", []))
    restored_ids = set((restore_audit or {}).get("changed_path_claim_ids", []))
    checks = {
        "baseline_noop": baseline_warm["result"].get("derived") == 0 and not baseline_warm["result"].get("failed_files"),
        "baseline_valid": bool(
            baseline_warm
            and baseline_warm["result"].get("coverage") == "complete"
            and not baseline_warm["result"].get("failed_files")
            and baseline_audit["stale"] == 0
            and baseline_audit["unrelated_stale"] == 0
        ),
        "mutation_derived": bool(mutation_warm and mutation_warm["result"].get("derived", 0) >= 1),
        "mutation_complete": bool(mutation_warm and mutation_warm["result"].get("coverage") == "complete" and not mutation_warm["result"].get("failed_files")),
        "mutation_stale_zero": bool(mutation_audit and mutation_audit["stale"] == 0),
        "unrelated_stale_zero": bool(mutation_audit and mutation_audit["unrelated_stale"] == 0),
        "restore_derived": bool(restore_warm and restore_warm["result"].get("derived", 0) >= 1),
        "restore_complete": bool(restore_warm and restore_warm["result"].get("coverage") == "complete" and not restore_warm["result"].get("failed_files")),
        "restore_stale_zero": bool(restore_audit and restore_audit["stale"] == 0),
        "claim_ids_restored": restored_ids == baseline_ids,
        "tracked_diff_restored": final_fingerprint == baseline_fingerprint and final_dirty == baseline_dirty,
        "bytes_restored": target.read_bytes() == original,
    }
    required_checks = {key: value for key, value in checks.items() if key != "baseline_noop"}
    status = "PASS" if error is None and all(required_checks.values()) else "BLOCKED"
    if status == "PASS" and name in EVENTUATE:
        status = "PARTIAL"
    result = {
        "status": status, "path": path, "token": token, "error": error,
        "baseline_diff_sha256": baseline_fingerprint, "final_diff_sha256": final_fingerprint,
        "baseline_dirty_paths": baseline_dirty, "final_dirty_paths": final_dirty,
        "baseline_warm": baseline_warm, "mutation_warm": mutation_warm, "restore_warm": restore_warm,
        "baseline_audit": {key: value for key, value in baseline_audit.items() if key != "changed_path_claim_ids"},
        "mutation_audit": {key: value for key, value in (mutation_audit or {}).items() if key != "changed_path_claim_ids"},
        "restore_audit": {key: value for key, value in (restore_audit or {}).items() if key != "changed_path_claim_ids"},
        "changed_path_claim_impact": {
            "baseline": len(baseline_ids), "mutated": len(mutation_ids), "restored": len(restored_ids),
            "added_on_mutation": len(mutation_ids - baseline_ids), "removed_on_mutation": len(baseline_ids - mutation_ids),
        },
        "checks": checks,
        "runtime_boundary": "PARTIAL: static evidence does not prove broker/runtime behavior" if name in EVENTUATE else None,
    }
    journal["state"] = "complete"
    journal["result_status"] = status
    journal["result"] = result
    atomic_write_json(journal_path, journal)
    return result


def write_report(output: Path, report: dict[str, Any]) -> None:
    statuses = [item.get("status") for item in report["repositories"].values()]
    report["overall"] = "BLOCKED" if any(value == "BLOCKED" for value in statuses) else ("PARTIAL" if any(value == "PARTIAL" for value in statuses) else "PASS")
    report["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    gate_path = output / "gate.json"
    atomic_write_json(gate_path, report)
    lines = [
        "# Ten-repo TMF mutation/restore gate", "", f"Generated: `{report['generated_at']}`", "",
        "| Repository | Probe | Mutation derived | Restore derived | Stale after mutation | Stale after restore | Diff restored | Status |",
        "|---|---|---:|---:|---:|---:|---|---|",
    ]
    for name, item in report["repositories"].items():
        mutation = (item.get("mutation_warm") or {}).get("result", {})
        restore = (item.get("restore_warm") or {}).get("result", {})
        lines.append(
            f"| {name} | `{item.get('path', '')}` | {mutation.get('derived', '')} | {restore.get('derived', '')} | "
            f"{(item.get('mutation_audit') or {}).get('stale', '')} | {(item.get('restore_audit') or {}).get('stale', '')} | "
            f"{(item.get('checks') or {}).get('tracked_diff_restored', False)} | {item.get('status')} |"
        )
    lines += [
        "", f"Overall: **{report['overall']}**.", "",
        "The gate is serial. Probe bytes are journaled before mutation and restored in `finally`; `--resume` recovers unfinished journals before continuing.",
        "Existing tracked changes are fingerprinted and preserved. Dirty Java files are never selected as probes.",
        "Eventuate repositories remain PARTIAL because static evidence does not prove broker delivery, transaction commit, runtime dispatch, payload values, or compensation execution.",
        "This gate does not authorize release. Clean-build performance evidence remains a separate release requirement.", "",
    ]
    atomic_write_bytes(output / "README.md", "\n".join(lines).encode("utf-8"))
    digest = sha256_bytes(gate_path.read_bytes())
    atomic_write_bytes(output / "SHA256SUMS", f"{digest}  gate.json\n".encode("ascii"))


def parse_probes(values: list[str]) -> dict[str, str]:
    probes: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"probe must be NAME=PATH: {value}")
        name, path = value.split("=", 1)
        probes[name] = path
    return probes


def main() -> int:
    parser = argparse.ArgumentParser(description="Serial, journaled ten-repository mutation/restore gate")
    parser.add_argument("--experiments-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--probe", action="append", default=[], metavar="NAME=PATH")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--worker", choices=("warm", "audit"))
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--changed-path")
    parser.add_argument("--result-file", type=Path)
    args = parser.parse_args()
    if args.worker:
        if args.repo is None or args.result_file is None:
            parser.error("--worker requires --repo and --result-file")
        if args.worker == "audit" and args.changed_path is None:
            parser.error("audit worker requires --changed-path")
        value = timed_warm(args.repo.resolve()) if args.worker == "warm" else audit_claims(
            args.repo.resolve(), args.changed_path
        )
        atomic_write_json(args.result_file.resolve(), value)
        return 0
    if args.experiments_root is None or args.output is None:
        parser.error("gate mode requires --experiments-root and --output")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "journals").mkdir(exist_ok=True)
    probes = parse_probes(args.probe)

    for journal_path in sorted((output / "journals").glob("*.json")):
        recover_journal(journal_path)

    gate_path = output / "gate.json"
    if args.resume and gate_path.exists():
        report = json.loads(gate_path.read_text(encoding="utf-8"))
    else:
        report = {"schema": "ten-repo-mutation-gate-v1", "mode": "serial-mutation-restore", "repositories": {}}
    for name, directory in SAMPLES.items():
        if args.resume and report["repositories"].get(name, {}).get("status") in {"PASS", "PARTIAL"}:
            print(f"[{name}] checkpoint complete; skipping", flush=True)
            continue
        repo = (args.experiments_root / directory).resolve()
        print(f"[{name}] mutation/restore", flush=True)
        try:
            report["repositories"][name] = run_probe(name, repo, output, probes.get(name))
        except Exception as exc:
            report["repositories"][name] = {"status": "BLOCKED", "path": probes.get(name), "error": f"{type(exc).__name__}: {exc}"}
        write_report(output, report)
    write_report(output, report)
    print(json.dumps({"overall": report["overall"], "output": str(output), "statuses": {name: value["status"] for name, value in report["repositories"].items()}}, indent=2))
    return 2 if report["overall"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
