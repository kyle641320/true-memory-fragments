from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path
import unittest


class JavaExtractStructureTests(unittest.TestCase):
    def test_top_level_symbols_are_unique(self) -> None:
        path = Path(__file__).parents[1] / "tmf" / "java_extract.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        names = [
            node.name
            for node in tree.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
        self.assertEqual([], duplicates, "top-level definitions shadow earlier code")


if __name__ == "__main__":
    unittest.main()
