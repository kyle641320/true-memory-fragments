import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ExplicitGitInitialBranchTests(unittest.TestCase):
    def test_test_and_tool_fixtures_never_use_bare_git_init(self):
        violations = []
        for directory in (ROOT / "tests", ROOT / "tools"):
            for path in directory.rglob("*.py"):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                for node in ast.walk(tree):
                    if not isinstance(node, (ast.List, ast.Tuple)):
                        continue
                    values = []
                    for item in node.elts:
                        if isinstance(item, ast.Constant) and isinstance(item.value, str):
                            values.append(item.value)
                        else:
                            values.append(None)
                    if values[:2] != "git init".split():
                        continue
                    if "-b" not in values[2:] and "--initial-branch" not in values[2:]:
                        violations.append(f"{path.relative_to(ROOT)}:{node.lineno}")
        self.assertEqual([], violations, "bare git init commands: " + ", ".join(violations))


if __name__ == "__main__":
    unittest.main()
