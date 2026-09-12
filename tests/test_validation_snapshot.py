import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tmf.java_project import JavaProjectModel
from tmf.validation import _measure_graph_coverage


class ValidationSnapshotTests(unittest.TestCase):
    def test_coverage_bounds_enumeration_and_observes_next_run_changes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)  # Like self-validation: exported source, no .git.
            (root / 'Base.java').write_text('class Base {}\n')
            for i in range(8):
                (root / f'Child{i}.java').write_text(f'class Child{i} extends Base {{ Base value; }}\n')
            original = JavaProjectModel._tracked_paths
            calls = []
            def tracked(model):
                calls.append(1)
                return original(model)
            with mock.patch.object(JavaProjectModel, '_tracked_paths', tracked):
                first = _measure_graph_coverage(root)
            self.assertLessEqual(len(calls), 3, 'project enumeration must not grow per relation')
            self.assertEqual(8, first['java']['inherits']['resolved'])
            (root / 'Extra.java').write_text('class Extra extends Base {}\n')
            second = _measure_graph_coverage(root)
            self.assertEqual(9, second['java']['inherits']['resolved'])
            (root / 'Extra.java').unlink()
            self.assertEqual(first, _measure_graph_coverage(root))


if __name__ == '__main__':
    unittest.main()
