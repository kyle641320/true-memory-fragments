import unittest

from tmf.extract import extract_module_top_levels


class ModuleTopLevelNodeTests(unittest.TestCase):
    def test_top_level_comments_blank_lines_and_docstring_are_normalized_out(self):
        before = '"""module docs"""\n\nVALUE = 1\n\ndef f():\n    return VALUE\n\ncheck("x")\n'
        after = '"""changed docs only"""\n# comment\n\nVALUE = 1\n\ndef f():\n    return VALUE\n\n\n# another comment\ncheck("x")\n'

        before_nodes = extract_module_top_levels("m.py", before)
        after_nodes = extract_module_top_levels("m.py", after)

        self.assertEqual([n.top_level_hash for n in before_nodes], [n.top_level_hash for n in after_nodes])

    def test_import_change_is_top_level_behavior_change(self):
        before = "import os\nVALUE = 1\n"
        after = "import sys\nVALUE = 1\n"

        before_nodes = extract_module_top_levels("m.py", before)
        after_nodes = extract_module_top_levels("m.py", after)

        self.assertEqual(len(before_nodes), 1)
        self.assertEqual(len(after_nodes), 1)
        self.assertNotEqual(before_nodes[0].top_level_hash, after_nodes[0].top_level_hash)

    def test_def_class_boundaries_split_regions(self):
        source = "import os\n\ndef f():\n    return 1\n\ncheck('x')\nclass C:\n    pass\ncheck('y')\n"

        nodes = extract_module_top_levels("m.py", source)

        self.assertEqual([(n.line_start, n.line_end) for n in nodes], [(1, 1), (6, 6), (9, 9)])


if __name__ == "__main__":
    unittest.main()
