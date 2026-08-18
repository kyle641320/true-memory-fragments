from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tmf.extract import extract_classes
from tmf.ids import stable_class_claim_id, stable_contract_claim_id, stable_function_claim_id
from tmf.retrieve import refresh_path
from tmf.store import Store
from tmf.warm import warm_repo

ROOT = Path(__file__).resolve().parents[1]


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def init_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init", "-b", "master"], repo)
    run(["git", "config", "user.email", "tmf@example.com"], repo)
    run(["git", "config", "user.name", "tmf"], repo)
    for path, content in files.items():
        full = repo / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
    run(["git", "add", *files.keys()], repo)
    run(["git", "commit", "-m", "init"], repo)
    return repo


class Window1Tests(unittest.TestCase):
    def test_function_nested_classes_are_qualname_scoped(self):
        source = """
def a():
    class V:
        pass
    return V

def b():
    class V:
        pass
    return V
""".lstrip()
        names = {c.qualname for c in extract_classes("m.py", source)}
        self.assertEqual(names, {"a.V", "b.V"})

    def test_nested_class_claims_split_and_reconcile_independently(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"m.py": "def a():\n    class V:\n        x = 1\n    return V\n\ndef b():\n    class V:\n        x = 2\n    return V\n"})
            refresh_path(repo, "m.py")
            store = Store(repo)
            self.assertIsNotNone(store.get_claim(stable_class_claim_id("m.py", "a.V")))
            self.assertIsNotNone(store.get_claim(stable_class_claim_id("m.py", "b.V")))
            self.assertIsNone(store.get_claim(stable_class_claim_id("m.py", "V")))
            (repo / "m.py").write_text("def a():\n    class V:\n        x = 10\n    return V\n\ndef b():\n    class V:\n        x = 2\n    return V\n", encoding="utf-8")
            refresh_path(repo, "m.py")
            self.assertIsNotNone(store.get_claim(stable_class_claim_id("m.py", "a.V")))
            self.assertIsNotNone(store.get_claim(stable_class_claim_id("m.py", "b.V")))

    def test_self_call_resolves_unique_base_method(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"m.py": "class Base:\n    def m(self):\n        return 1\n\nclass Child(Base):\n    def run(self):\n        return self.m()\n"})
            data = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "m.py", "--refresh", "--repo", str(repo)], ROOT).stdout)
            child = [c for c in data["claims"] if c.get("qualname") == "Child.run"][0]
            self.assertEqual(child["callees"][0]["target_qualname"], "Base.m")

    def test_imported_module_func_resolves_unique_top_level(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"a.py": "import b\n\ndef main():\n    return b.helper()\n", "b.py": "def helper():\n    return 1\n"})
            data = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "a.py", "--refresh", "--repo", str(repo)], ROOT).stdout)
            main = [c for c in data["claims"] if c.get("qualname") == "main"][0]
            self.assertEqual(main["callees"][0]["target_qualname"], "helper")
            self.assertEqual(main["callees"][0]["resolution"], "import_module_direct_top_level")

    def test_mechanical_contract_slot_confidence_capped(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"m.py": "def f(x):\n    y = x + 1\n    if y:\n        return y\n    return 0\n"})
            warm_repo(repo)
            c = Store(repo).get_claim(stable_contract_claim_id("m.py", "f"))
            self.assertIsNotNone(c)
            self.assertEqual(c.body["contract_version"], "contract.v1.mechanical")
            for value in c.body["slot_confidence"].values():
                self.assertLessEqual(value, 0.6)
            for p in c.body["slots"].get("params", []):
                self.assertLessEqual(p.get("confidence", 0), 0.6)


if __name__ == "__main__":
    unittest.main()
