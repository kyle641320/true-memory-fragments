from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ten_repo_production_gate import SAMPLES


def run_warm(repo: Path) -> dict[str, Any]:
    start = time.monotonic()
    before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result = subprocess.run(
        [sys.executable, "-c", "from pathlib import Path; import json; from tmf.warm import warm_repo; print(json.dumps(warm_repo(Path.cwd())))"],
        cwd=repo,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-4000:] or f"warm exited {result.returncode}")
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    after = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return {"result": payload, "elapsed_seconds": round(time.monotonic() - start, 3), "maxrss_kb": max(before, after)}


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Serial clean-cache warm benchmark in disposable local clones")
    parser.add_argument("--experiments-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    checkpoint_path = args.output / "checkpoint.json"
    report = json.loads(checkpoint_path.read_text()) if args.resume and checkpoint_path.exists() else {"schema": "ten-repo-clean-build-v1", "repositories": {}}
    with tempfile.TemporaryDirectory(prefix="tmf-clean-build-", dir=args.output) as staging:
        staging_path = Path(staging)
        for name, directory in SAMPLES.items():
            if name in report["repositories"] and report["repositories"][name].get("status") in {"PASS", "PARTIAL"}:
                continue
            source = (args.experiments_root / directory).resolve()
            if not (source / ".git").exists():
                report["repositories"][name] = {"status": "BLOCKED", "reason": "repository_missing"}
                atomic_write(checkpoint_path, report)
                continue
            clone = staging_path / name
            print(f"[{name}] clone", flush=True)
            clone_process = subprocess.run(
                ["git", "clone", "--local", "--no-hardlinks", "--quiet", str(source), str(clone)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            if clone_process.returncode != 0:
                if clone.exists():
                    shutil.rmtree(clone)
                shutil.copytree(source, clone, symlinks=True)
                print(f"[{name}] clone fallback=copytree reason=local_git_incomplete", flush=True)
            tmf = clone / ".tmf"
            if tmf.exists():
                shutil.rmtree(tmf)
            print(f"[{name}] clean warm 1/2", flush=True)
            first = run_warm(clone)
            print(f"[{name}] clean warm 2/2", flush=True)
            second = run_warm(clone)
            failed = first["result"].get("failed_files", {})
            clean = not failed and first["result"].get("coverage") == "complete" and second["result"].get("derived") == 0 and not second["result"].get("failed_files")
            status = "PASS" if clean else "BLOCKED"
            if status == "PASS" and name in {"eventuate-choreography", "eventuate-orchestration"}:
                status = "PARTIAL"
            report["repositories"][name] = {"status": status, "source": str(source), "warm_1": first, "warm_2": second}
            atomic_write(checkpoint_path, report)
            del clone
    report["overall"] = "PASS" if all(x["status"] == "PASS" for x in report["repositories"].values()) else ("PARTIAL" if any(x["status"] == "PARTIAL" for x in report["repositories"].values()) else "BLOCKED")
    report["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    atomic_write(args.output / "benchmark.json", report)
    digest = hashlib.sha256((args.output / "benchmark.json").read_bytes()).hexdigest()
    (args.output / "SHA256SUMS").write_text(f"{digest}  benchmark.json\n", encoding="utf-8")
    print(json.dumps({"overall": report["overall"], "output": str(args.output), "statuses": {k: v["status"] for k, v in report["repositories"].items()}}, indent=2))
    return 0 if report["overall"] != "BLOCKED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
