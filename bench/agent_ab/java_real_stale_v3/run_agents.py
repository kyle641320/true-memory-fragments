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
    cp = subprocess.run(cmd, text=True, capture_output=True, timeout=M["model"]["timeout_seconds"] + 45)
    wall = time.time() - start
    out.write_text(cp.stdout)
    (R / "raw" / f"{key}.stderr").write_text(cp.stderr)
    (R / "raw" / f"{key}.runmeta.json").write_text(json.dumps({
        "command": cmd[:-1] + ["<prompt>"],
        "exit_code": cp.returncode,
        "wall_seconds": wall,
        "valid_transport": cp.returncode == 0,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
    }, indent=2) + "\n")
    print(f"{n}/{len(jobs)} {key} exit={cp.returncode} wall={wall:.1f}", flush=True)
