from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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


class Window1D1Tests(unittest.TestCase):
    def test_nested_class_qualname_is_function_scoped(self) -> None:
        from tmf.extract import extract_classes
        src = "def outer():\n    class Inner:\n        pass\n    return Inner\n"
        classes = extract_classes("m.py", src)
        self.assertEqual([c.qualname for c in classes], ["outer.Inner"])

    def test_mechanical_contract_confidence_is_capped_at_point_six(self) -> None:
        from tmf.derive import derive_claims_for_path
        from tmf.git import GitRepo
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"m.py": "def f(x: int) -> int:\n    y = x\n    if y < 0:\n        raise ValueError()\n    return y + 1\n"})
            contracts = [c for c in derive_claims_for_path(GitRepo(repo), "m.py") if c.scope == "contract"]
            self.assertEqual(len(contracts), 1)
            slots = contracts[0].body["slots"]
            self.assertLessEqual(slots["params"][0]["confidence"], 0.6)
            self.assertLessEqual(contracts[0].body["slot_confidence"]["params"], 0.6)
            self.assertIn("capped at 0.6", " ".join(contracts[0].body["notes"]))

    def test_self_method_resolves_unique_inherited_base_method(self) -> None:
        repo_src = "class Base:\n    def m(self):\n        return 1\n\nclass Child(Base):\n    def call(self):\n        return self.m()\n"
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"m.py": repo_src})
            data = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "m.py", "--repo", str(repo)], ROOT).stdout)
            by_name = {c.get("qualname"): c for c in data["claims"] if c["scope"] == "function"}
            self.assertEqual(by_name["Child.call"]["callees"][0]["target_qualname"], "Base.m")
            self.assertFalse(by_name["Child.call"].get("unresolved_calls"))

    def test_imported_module_function_resolves_unique_top_level(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "a.py": "import b\n\ndef main():\n    return b.helper()\n",
                "b.py": "def helper():\n    return 1\n",
            })
            data = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "a.py", "--repo", str(repo)], ROOT).stdout)
            main = [c for c in data["claims"] if c.get("qualname") == "main"][0]
            self.assertEqual(main["callees"][0]["target_qualname"], "helper")
            self.assertEqual(main["callees"][0]["target_path"], "b.py")
            self.assertEqual(main["callees"][0]["resolution"], "import_module_direct_top_level")


if __name__ == "__main__":
    unittest.main()
