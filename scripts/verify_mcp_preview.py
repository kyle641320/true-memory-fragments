"""Exercise installed TMF through the MCP Python SDK and real stdio transport."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    with tempfile.TemporaryDirectory(prefix="tmf-mcp-preview-") as td:
        repo = Path(td) / "worktree"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        source = repo / "sample.py"
        source.write_text("def price():\n    return 1\n")
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "tmf.cli", "mcp", "--repo", str(repo)],
            cwd=td,
            env={"TMF_MODEL_COMMAND": "", "PYTHONDONTWRITEBYTECODE": "1"},
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=30) as client:
                init = await client.initialize()
                tools = await client.list_tools()
                assert "tmf_explain" in {t.name for t in tools.tools}

                async def call(name, args=None):
                    response = await client.call_tool(name, args or {})
                    assert not response.is_error, response
                    return json.loads(response.content[0].text)

                status = await call("tmf_status")
                assert Path(status["repo"]).resolve() == repo.resolve()
                await call("tmf_warm")
                found = await call("tmf_retrieve", {"query": "price"})
                claim = next(c for c in found["claims"] if c.get("qualname") == "price")
                cid = claim["id"]
                assert (await call("tmf_explain", {"claim_id": cid}))["claim"]["fresh"]
                source.write_text("def price():\n    return 2\n")
                assert not (await call("tmf_explain", {"claim_id": cid}))["claim"]["fresh"]
                stale = await call("tmf_stale_slice", {"claim_id": cid})
                assert stale["stale_claim_withheld"]
                assert any(r["path"] == "sample.py" for r in stale["required_reads"])
                assert "return 2" in source.read_text()  # actual reread, before refresh
                await call("tmf_warm")
                assert (await call("tmf_explain", {"claim_id": cid}))["claim"]["fresh"]
                print(json.dumps({"status": "PASS", "protocol": init.protocol_version,
                    "transport": "stdio", "client": "MCP Python SDK", "checks":
                    ["initialize", "tools/list", "worktree binding", "fresh", "stale",
                     "required reads", "actual reread", "refresh recovery"]}))


if __name__ == "__main__":
    asyncio.run(main())
