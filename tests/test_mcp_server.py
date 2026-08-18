from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tmf import __version__

from tmf.ids import stable_declaration_claim_id, stable_function_claim_id, stable_java_node_claim_id
from tmf.java_extract import java_status


ROOT = Path(__file__).resolve().parents[1]


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-b", "master"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(["git", "config", "user.email", "tmf@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "tmf"], cwd=root, check=True)
    (root / "a.py").write_text("VALUE = 1\n\ndef helper():\n    return VALUE\n\ndef caller():\n    return helper()\n", encoding="utf-8")
    (root / "Child.java").write_text("class Base {}\ninterface Marker {}\nclass Child extends Base implements Marker {}\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.py", "Child.java"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(["git", "commit", "-m", "fixture"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


class McpServerTests(unittest.TestCase):
    def _rpc(self, proc, method: str, params=None, ident=1):
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": ident, "method": method, "params": params or {}}) + "\n")
        proc.stdin.flush()
        return json.loads(proc.stdout.readline())

    def test_protocol_tools_and_security(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            _init_repo(repo)
            proc = subprocess.Popen(
                [sys.executable, "-m", "tmf.cli", "mcp", "--repo", str(repo)],
                cwd=ROOT,
                text=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                init = self._rpc(proc, "initialize", {"protocolVersion": "2024-11-05"}, 1)
                self.assertEqual(init["result"]["serverInfo"]["name"], "tmf")
                self.assertEqual(init["result"]["serverInfo"]["version"], __version__)
                listed = self._rpc(proc, "tools/list", {}, 2)
                names = {tool["name"] for tool in listed["result"]["tools"]}
                expected = {"tmf_context", "tmf_fragment", "tmf_retrieve", "tmf_explain", "tmf_callers", "tmf_readers", "tmf_writers", "tmf_subtypes", "tmf_warm", "tmf_status"}
                self.assertEqual(expected, names)
                warm = self._rpc(proc, "tools/call", {"name": "tmf_warm", "arguments": {}}, 3)
                self.assertIn("content", warm["result"])
                retrieve = self._rpc(proc, "tools/call", {"name": "tmf_retrieve", "arguments": {"query": "helper caller", "limit": 3}}, 4)
                payload = json.loads(retrieve["result"]["content"][0]["text"])
                self.assertEqual(payload["view"], "thin")
                self.assertTrue(payload["claims"])
                self.assertNotIn('"body"', retrieve["result"]["content"][0]["text"])
                fn_id = stable_function_claim_id("a.py", "helper")
                decl_id = stable_declaration_claim_id("a.py", "VALUE")
                child_id = stable_java_node_claim_id("Child.java", "Child", "class")
                calls = [
                    ("tmf_explain", {"claim_id": fn_id}),
                    ("tmf_callers", {"claim_id": fn_id}),
                    ("tmf_readers", {"claim_id": decl_id}),
                    ("tmf_writers", {"claim_id": decl_id}),
                    ("tmf_status", {}),
                ]
                if java_status().available:
                    calls.insert(4, ("tmf_subtypes", {"claim_id": child_id}))
                for i, (name, args) in enumerate(calls, start=5):
                    resp = self._rpc(proc, "tools/call", {"name": name, "arguments": args}, i)
                    self.assertNotIn("error", resp)
                    text = resp["result"]["content"][0]["text"]
                    self.assertNotIn("Traceback", text)
                outside = self._rpc(proc, "tools/call", {"name": "tmf_warm", "arguments": {"path": "../outside.py"}}, 20)
                self.assertIn("error", outside)
                self.assertIn("outside repo root", outside["error"]["message"])
                proc.stdin.write("{not json}\n")
                proc.stdin.flush()
                malformed = json.loads(proc.stdout.readline())
                self.assertEqual(malformed["error"]["code"], -32700)
                ping = self._rpc(proc, "ping", {}, 21)
                self.assertEqual(ping["result"], {})
            finally:
                proc.kill()
                proc.wait(timeout=5)
                stderr = proc.stderr.read()
                self.assertNotIn("Traceback", stderr)
                proc.stdin.close()
                proc.stdout.close()
                proc.stderr.close()
                self.assertTrue(proc.stdin.closed)
                self.assertTrue(proc.stdout.closed)
                self.assertTrue(proc.stderr.closed)


if __name__ == "__main__":
    unittest.main()
