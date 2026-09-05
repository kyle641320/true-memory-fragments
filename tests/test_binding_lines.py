"""回归测试：验证所有节点 Binding 包含正确的行号、role 和 hash_kind"""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tmf.git import GitRepo
from tmf.derive import derive_java_node_claim, derive_function_claim, derive_class_claim
from tmf.java_extract import extract_java_methods
from tmf.extract import extract_functions, extract_classes


class BindingLinesTests(unittest.TestCase):
    """防止 Binding 行号字段再次丢失"""

    def test_java_method_binding_has_lines_role_and_hash_kind(self):
        """Java 方法 Binding 必须包含 line_start/line_end/role/hash_kind"""
        guava_root = Path(__file__).parent.parent / 'fixtures' / 'guava'
        try:
            available = guava_root.exists()
        except PermissionError:
            available = False
        if not available:
            self.skipTest('Guava fixture is unavailable in this runner')
        repo = GitRepo(str(guava_root))
        p = 'guava/src/com/google/common/base/Preconditions.java'
        try:
            src = repo.read_file(p)
        except PermissionError as exc:
            self.skipTest(f'Guava fixture is not readable in this runner: {exc}')
        methods = extract_java_methods(p, src)
        self.assertGreater(len(methods), 0, "Should extract at least one Java method")
        
        m = methods[1]  # checkArgument
        claim = derive_java_node_claim(repo, m)
        self.assertEqual(len(claim.bindings), 1, "Should have exactly one binding")
        
        b = claim.bindings[0]
        self.assertEqual(b.line_start, m.line_start, "Binding line_start must match extracted method")
        self.assertEqual(b.line_end, m.line_end, "Binding line_end must match extracted method")
        self.assertEqual(b.role, "declaration", "Java method binding role should be 'declaration'")
        self.assertEqual(b.hash_kind, "java-treesitter-token-stream", "Java method hash_kind mismatch")

    def test_python_function_binding_has_lines_role_and_hash_kind(self):
        """Python 函数 Binding 必须包含 line_start/line_end/role/hash_kind"""
        repo = GitRepo('.')
        p = 'tmf/derive.py'
        src = repo.read_file(p)
        functions = extract_functions(p, src)
        self.assertGreater(len(functions), 0, "Should extract at least one Python function")
        
        fn = functions[0]
        claim = derive_function_claim(repo, fn)
        self.assertEqual(len(claim.bindings), 1, "Should have exactly one binding")
        
        b = claim.bindings[0]
        self.assertEqual(b.line_start, fn.line_start, "Binding line_start must match extracted function")
        self.assertEqual(b.line_end, fn.line_end, "Binding line_end must match extracted function")
        self.assertEqual(b.role, "function", "Python function binding role should be 'function'")
        self.assertEqual(b.hash_kind, "python-token-stream", "Python function hash_kind mismatch")

    def test_python_class_binding_has_lines_role_and_hash_kind(self):
        """Python 类 Binding 必须包含 line_start/line_end/role/hash_kind"""
        repo = GitRepo('.')
        p = 'tmf/schema.py'
        src = repo.read_file(p)
        classes = extract_classes(p, src)
        self.assertGreater(len(classes), 0, "Should extract at least one Python class")
        
        cls = classes[0]
        claim = derive_class_claim(repo, cls)
        self.assertEqual(len(claim.bindings), 1, "Should have exactly one binding")
        
        b = claim.bindings[0]
        self.assertEqual(b.line_start, cls.line_start, "Binding line_start must match extracted class")
        self.assertEqual(b.line_end, cls.line_end, "Binding line_end must match extracted class")
        self.assertEqual(b.role, "class", "Python class binding role should be 'class'")
        self.assertEqual(b.hash_kind, "python-token-stream", "Python class hash_kind mismatch")


if __name__ == "__main__":
    unittest.main()
