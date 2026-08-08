from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tmf.derive import derive_claims_for_path
from tmf.extract import extract_functions, function_interface
from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.ids import stable_contract_claim_id
from tmf.mcp_server import McpService
from tmf.store import Store
from tmf.warm import warm_repo


class FinalContractsTests(unittest.TestCase):
    def test_python_interface_mechanical_facts(self) -> None:
        src = '''
from typing import Any

def deco(fn): return fn

@deco
async def sample(a: int, b="x", *args, **kwargs) -> str:
    if a < 0:
        raise ValueError("bad")
    yield b
'''
        fn = [f for f in extract_functions("pkg/mod.py", src) if f.qualname == "sample"][0]
        iface = function_interface(src, fn)
        self.assertTrue(iface["signature"].startswith("async def sample(a: int, b='x', *args, **kwargs)"))
        self.assertIs(iface["is_async"], True)
        self.assertIs(iface["is_generator"], True)
        self.assertEqual(iface["return"]["shape"], "annotation_only")
        self.assertEqual(iface["return"]["annotation"], "str")
        self.assertEqual(iface["raises"], ["ValueError"])
        self.assertEqual(iface["decorators"], ["deco"])
        self.assertEqual([p["name"] for p in iface["params"]], ["a", "b", "args", "kwargs"])

    def test_contract_checks_prune_unsafe_slots(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp_path = Path(d)
            (tmp_path / "m.py").write_text('''
GLOBAL = 0

def f(x: int) -> None:
    global GLOBAL
    GLOBAL = x
    if x < 0:
        raise ValueError("bad")
''', encoding="utf-8")
            repo = GitRepo(tmp_path)
            claims = derive_claims_for_path(repo, "m.py")
            by_scope = {c.scope: c for c in claims if c.scope in {"function", "contract"}}
            contract = by_scope["contract"]
            slots = contract.body["slots"]
            self.assertEqual(contract.id, stable_contract_claim_id("m.py", "f"))
            self.assertEqual(contract.bindings[0].fn_hash, by_scope["function"].bindings[0].fn_hash)
            self.assertEqual(slots["params"], [{"name": "x", "meaning": "parameter x", "confidence": 0.6, "evidence": "observed"}])
            self.assertEqual(slots["returns"]["meaning"], "declares return type None")
            self.assertEqual({r["exception"] for r in slots["raises"]}, {"ValueError"})
            self.assertTrue(slots["side_effects"])
            self.assertTrue(all(s["evidence"] == "observed" for s in slots["side_effects"]))
            checks = contract.body["_contract_checks"]
            self.assertIs(checks["accepted"], True)
            self.assertEqual(checks["mechanical_source"], "interface")

    def test_contract_stales_on_body_change(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp_path = Path(d)
            path = tmp_path / "m.py"
            path.write_text('''
def f(x):
    y = x
    if y:
        return y + 1
    return 0
''', encoding="utf-8")
            repo = GitRepo(tmp_path)
            store = Store(tmp_path)
            for claim in derive_claims_for_path(repo, "m.py"):
                store.put_claim(claim)
            contract = store.get_claim(stable_contract_claim_id("m.py", "f"))
            self.assertIsNotNone(contract)
            assert contract is not None
            self.assertTrue(check_freshness(repo, contract).fresh)
            path.write_text('''
def f(x):
    y = x + 1
    if y:
        return y
    return 0
''', encoding="utf-8")
            self.assertFalse(check_freshness(repo, contract).fresh)

    def test_tmf_context_default_is_3000_and_stubs_overflow(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp_path = Path(d)
            chunks = []
            for i in range(40):
                chunks.append(f"def function_{i}(alpha_{i}, beta_{i}):\n    if alpha_{i}:\n        return alpha_{i} + beta_{i}\n    return beta_{i}\n")
            (tmp_path / "many.py").write_text("\n".join(chunks), encoding="utf-8")
            warm_repo(tmp_path)
            service = McpService(tmp_path)
            payload = service.tmf_context("function alpha beta")
            encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            self.assertLessEqual(len(encoded), 3000)
            self.assertEqual(payload["max_chars"], 3000)
            self.assertTrue(payload["truncated"])
            self.assertTrue(payload["claims"])
            self.assertTrue(any(c.get("stub") for c in payload["claims"]))
            self.assertTrue(all("claim_id" in c for c in payload["claims"] if c.get("stub")))

    def test_java_interface_mechanical_facts_when_available(self) -> None:
        from tmf.java_extract import extract_java_methods, java_method_interface, java_status
        if not java_status().available:
            self.skipTest("tree-sitter java unavailable")
        src = """
@interface Route {}
class Demo {
  @Deprecated
  public String load(String id, int n) throws IOException, IllegalStateException {
    if (id == null) { throw new IllegalStateException(); }
    return id;
  }
}
"""
        node = [m for m in extract_java_methods("Demo.java", src) if m.qualname == "Demo.load"][0]
        iface = java_method_interface(src, node)
        self.assertEqual(iface["language"], "java")
        self.assertEqual(iface["return_type"], "String")
        self.assertEqual([p["name"] for p in iface["params"]], ["id", "n"])
        self.assertEqual([p["type"] for p in iface["params"]], ["String", "int"])
        self.assertIn("IOException", iface["throws"])
        self.assertIn("IllegalStateException", iface["throws"])
        self.assertIn("public", iface["modifiers"])
        self.assertIn("Deprecated", iface["annotations"])

    def test_tmf_context_uses_budgeted_retrieve_limit(self) -> None:
        import tmf.mcp_server as mcp
        seen = []
        orig = mcp.retrieve_text
        def fake(root, query, limit=5):
            seen.append(limit)
            return orig(root, query, limit=limit)
        with tempfile.TemporaryDirectory() as d:
            tmp_path = Path(d)
            (tmp_path / "m.py").write_text("def alpha():\n    return 1\n", encoding="utf-8")
            warm_repo(tmp_path)
            old = mcp.retrieve_text
            mcp.retrieve_text = fake
            try:
                svc = McpService(tmp_path)
                svc.tmf_context("alpha")
                svc.tmf_context("alpha", max_chars=5000)
                svc.tmf_context("alpha", max_chars=12000)
            finally:
                mcp.retrieve_text = old
        self.assertEqual(seen, [8, 12, 16])


if __name__ == "__main__":
    unittest.main()
