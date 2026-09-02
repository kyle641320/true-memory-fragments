#!/usr/bin/env python3
import hashlib
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

R = Path(__file__).resolve().parent
M = json.loads((R / "manifest.json").read_text())
only = set(sys.argv[1:])
jobs = []
for task in M["tasks"]:
    tid = task["id"]
    if only and tid not in only:
        continue
    for arm in M["arms"]:
        key = f"{tid}_{arm}"
        out = R / "raw" / f"{key}.agent.json"
        if out.exists():
            continue
        jobs.append((tid, arm, key, out))
print(f"jobs={len(jobs)}", flush=True)
for n, (tid, arm, key, out) in enumerate(jobs, 1):
    prompt = (R / "prompts" / tid / f"{arm}.txt").read_text()
    start = time.time()
    cmd = [
        "openclaw", "agent", "--agent", "main",
        "--session-id", f"java-real-stale-v3-{tid}-{arm.lower()}-{uuid.uuid4().hex[:8]}",
        "--model", M["model"]["id"], "--thinking", M["model"].get("thinking", "off"),
        "--timeout", str(M["model"]["timeout_seconds"]), "--json", "-m", prompt,
    ]
    try:
        cp = subprocess.run(cmd, text=True, capture_output=True, timeout=M["model"]["timeout_seconds"] + 45)
        stdout, stderr, exit_code, timed_out = cp.stdout, cp.stderr, cp.returncode, False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        exit_code = 124
        timed_out = True
    wall = time.time() - start
    if isinstance(stdout, bytes):
        stdout = stdout.decode(errors="replace")
    if isinstance(stderr, bytes):
        stderr = stderr.decode(errors="replace")
    json_status = None
    json_summary = None
    try:
        parsed = json.loads(stdout) if stdout.strip() else {}
        json_status = parsed.get("status") if isinstance(parsed, dict) else None
        json_summary = parsed.get("summary") if isinstance(parsed, dict) else None
    except Exception:
        pass
    valid_transport = exit_code == 0 and json_status == "ok" and json_summary == "completed"
    out.write_text(stdout)
    (R / "raw" / f"{key}.stderr").write_text(stderr)
    (R / "raw" / f"{key}.runmeta.json").write_text(json.dumps({
        "command": cmd[:-1] + ["<prompt>"],
        "exit_code": exit_code,
        "wall_seconds": wall,
        "valid_transport": valid_transport,
        "timed_out": timed_out,
        "json_status": json_status,
        "json_summary": json_summary,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
    }, indent=2) + "\n")
    print(f"{n}/{len(jobs)} {key} exit={exit_code} timeout={timed_out} wall={wall:.1f}", flush=True)
