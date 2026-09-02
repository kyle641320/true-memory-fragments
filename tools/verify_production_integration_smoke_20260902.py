#!/usr/bin/env python3
"""Production integration smoke for TMF CLI + MCP surfaces.

This evidence script exercises the user-facing integration path without changing
engine code: CLI warm/retrieve/explain/callers, stale labeling after source
mutation, include-source fallback, MCP initialize/list/warm/retrieve/status, and
MCP path traversal rejection.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tmf.ids import stable_function_claim_id

OUT_JSON = ROOT / "reports" / "production-integration-smoke-20260902.json"
OUT_MD = ROOT / "TMF_PRODUCTION_INTEGRATION_SMOKE_20260902.md"


def run(cmd: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def py_tmf(args: list[str], repo: Path | None = None, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    full = [sys.executable, "-m", "tmf.cli", *args]
    if repo is not None and "--repo" not in args:
        full += ["--repo", str(repo)]
    return run(full, ROOT, check=check)


def init_repo(repo: Path) -> None:
    run(["git", "init", "-q", "-b", "main"], repo)
    run(["git", "config", "user.email", "tmf@example.invalid"], repo)
    run(["git", "config", "user.name", "TMF Smoke"], repo)
    (repo / "b.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
    (repo / "a.py").write_text("from b import helper\n\ndef main():\n    return helper()\n", encoding="utf-8")
    run(["git", "add", "a.py", "b.py"], repo)
    run(["git", "commit", "-q", "-m", "initial"], repo)


def rpc(proc: subprocess.Popen[str], method: str, params: dict[str, Any] | None = None, ident: int = 1) -> dict[str, Any]:
    assert proc.stdin is not None and proc.stdout is not None
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": ident, "method": method, "params": params or {}}) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError("MCP server returned no response")
    return json.loads(line)


def ok(name: str, passed: bool, details: Any = None) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "details": details}


def main() -> None:
    checks: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="tmf-prod-smoke-") as td:
        repo = Path(td)
        init_repo(repo)
        helper_id = stable_function_claim_id("b.py", "helper")

        warm = py_tmf(["warm"], repo)
        warm_payload = json.loads(warm.stdout)
        checks.append(ok("cli_warm_exports_claims", warm_payload.get("derived", 0) >= 2 and warm_payload.get("coverage") == "complete", warm_payload))

        retrieve = py_tmf(["retrieve", "helper caller", "--limit", "5"], repo)
        retrieve_payload = json.loads(retrieve.stdout)
        checks.append(ok("cli_retrieve_thin_claims", retrieve_payload.get("view") == "thin" and bool(retrieve_payload.get("claims")), {"claims": len(retrieve_payload.get("claims", [])), "gaps": retrieve_payload.get("gaps")}))
        checks.append(ok("cli_retrieve_omits_thick_body", '"body"' not in retrieve.stdout, None))

        explain = py_tmf(["explain", helper_id, "--json"], repo)
        explain_payload = json.loads(explain.stdout)
        checks.append(ok("cli_explain_json_fresh", explain_payload.get("fresh") is True and explain_payload.get("id") == helper_id, explain_payload))

        callers = py_tmf(["callers", helper_id], repo)
        callers_payload = json.loads(callers.stdout)
        checks.append(ok("cli_callers_has_main", any("a.py" == item.get("caller_path") for item in callers_payload.get("callers", [])), callers_payload))

        # Mutate source after claim derivation, commit, then verify existing claim is marked stale and source fallback is available.
        (repo / "b.py").write_text("def helper():\n    return 2\n", encoding="utf-8")
        run(["git", "add", "b.py"], repo)
        run(["git", "commit", "-q", "-m", "mutate helper"], repo)
        stale = py_tmf(["explain", helper_id, "--json"], repo)
        stale_payload = json.loads(stale.stdout)
        checks.append(ok("cli_explain_marks_stale_after_source_change", stale_payload.get("fresh") is False and stale_payload.get("stale_reasons"), stale_payload))

        path_view = py_tmf(["retrieve", "--path", "b.py", "--include-source"], repo)
        path_payload = json.loads(path_view.stdout)
        checks.append(ok("cli_retrieve_source_fallback_after_stale", "b.py" in path_payload.get("source_fallback_paths", []) and "source_fallback" in path_payload, {"paths": path_payload.get("source_fallback_paths")}))

        proc = subprocess.Popen(
            [sys.executable, "-m", "tmf.cli", "mcp", "--repo", str(repo)],
            cwd=ROOT,
            text=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            init = rpc(proc, "initialize", {"protocolVersion": "2024-11-05"}, 1)
            checks.append(ok("mcp_initialize", init.get("result", {}).get("serverInfo", {}).get("name") == "tmf", init))
            tools = rpc(proc, "tools/list", {}, 2)
            names = {t.get("name") for t in tools.get("result", {}).get("tools", [])}
            required = {"tmf_context", "tmf_retrieve", "tmf_explain", "tmf_callers", "tmf_warm", "tmf_status"}
            checks.append(ok("mcp_tools_list_required", required <= names, sorted(names)))
            warm_mcp = rpc(proc, "tools/call", {"name": "tmf_warm", "arguments": {}}, 3)
            checks.append(ok("mcp_warm_content", "content" in warm_mcp.get("result", {}), warm_mcp))
            retrieve_mcp = rpc(proc, "tools/call", {"name": "tmf_retrieve", "arguments": {"query": "helper caller", "limit": 3}}, 4)
            txt = retrieve_mcp.get("result", {}).get("content", [{}])[0].get("text", "")
            payload = json.loads(txt)
            checks.append(ok("mcp_retrieve_thin_no_body", payload.get("view") == "thin" and '"body"' not in txt, {"claims": len(payload.get("claims", []))}))
            status = rpc(proc, "tools/call", {"name": "tmf_status", "arguments": {}}, 5)
            checks.append(ok("mcp_status_content", "content" in status.get("result", {}), status))
            outside = rpc(proc, "tools/call", {"name": "tmf_warm", "arguments": {"path": "../outside.py"}}, 6)
            checks.append(ok("mcp_rejects_path_traversal", "error" in outside and "outside repo root" in outside.get("error", {}).get("message", ""), outside))
            malformed_line = "{not json}\n"
            assert proc.stdin is not None and proc.stdout is not None
            proc.stdin.write(malformed_line)
            proc.stdin.flush()
            malformed = json.loads(proc.stdout.readline())
            checks.append(ok("mcp_malformed_json_fails_closed", malformed.get("error", {}).get("code") == -32700, malformed))
        finally:
            proc.kill()
            proc.wait(timeout=5)
            stderr = proc.stderr.read() if proc.stderr else ""
            checks.append(ok("mcp_no_traceback_stderr", "Traceback" not in stderr, stderr[-1000:]))

    summary = {
        "checks": len(checks),
        "passed": sum(1 for c in checks if c["passed"]),
        "failed": sum(1 for c in checks if not c["passed"]),
    }
    summary["verdict"] = "PASS" if summary["failed"] == 0 else "FAIL"
    result = {"schema": "tmf.production_integration_smoke.v1", "summary": summary, "checks": checks}
    OUT_JSON.parent.mkdir(exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    lines = [
        "# TMF Production Integration Smoke — 2026-09-02",
        "",
        f"Verdict: **{summary['verdict']}**.",
        "",
        "Scope: user-facing CLI and MCP integration smoke. This validates local operational surfaces, stale labeling, source fallback, thin retrieval, reverse callers, MCP tool listing/status, and fail-closed path/malformed-json behavior. It does not publish a package, create a release tag, or certify runtime framework behavior.",
        "",
        "## Summary",
        "",
        f"- Checks: {summary['passed']}/{summary['checks']} pass.",
        "",
        "## Checks",
        "",
    ]
    for c in checks:
        lines.append(f"- {c['name']}: {'PASS' if c['passed'] else 'FAIL'}.")
    OUT_MD.write_text("\n".join(lines) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
