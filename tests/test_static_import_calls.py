"""
Regression tests for static import call edge resolution.

Before fix: TMF only resolves qualified calls like Preconditions.checkNotNull(...).
After fix: TMF also resolves static-imported calls like checkNotNull(...).
"""
import unittest
from pathlib import Path
from tmf.java_extract import resolve_java_call_edges, resolve_java_field_edges, extract_java_methods


class FakeRepo:
    """Minimal repo implementation for testing static imports."""
    def __init__(self, files: dict[str, str]):
        self.files = files
        self.root = Path("/fake/repo")
    
    def read_file(self, path: str) -> str:
        if path in self.files:
            return self.files[path]
        raise FileNotFoundError(f"Test repo does not contain {path}")
    
    def blob_sha(self, path: str) -> str:
        return "test-blob"
    
    def head(self) -> str:
        return "test-HEAD"


class TestStaticImportCalls(unittest.TestCase):
    def test_static_import_method_call(self):
        """Static imported method calls should be resolved."""
        caller_source = """
package com.example;

import static com.google.common.base.Preconditions.checkNotNull;

public class Example {
    public void validateInput(String input) {
        checkNotNull(input);
    }
}
"""
        callee_source = """
package com.google.common.base;

public class Preconditions {
    public static <T> T checkNotNull(T reference) {
        if (reference == null) throw new NullPointerException();
        return reference;
    }
}
"""
        repo = FakeRepo({
            "com/google/common/base/Preconditions.java": callee_source
        })
        methods = extract_java_methods("Example.java", caller_source)
        edges, unresolved = resolve_java_call_edges("Example.java", caller_source, methods, repo=repo)
        
        # Before fix: 0 edges, 1 unresolved (checkNotNull not found in local/parent)
        # After fix: 1 edge (Example.validateInput -> Preconditions.checkNotNull)
        self.assertEqual(len(edges), 1, f"Expected 1 call edge, got {len(edges)}")
        self.assertEqual(edges[0].caller_qualname, "Example.validateInput")
        self.assertIn("checkNotNull", edges[0].callee_qualname)
        self.assertEqual(edges[0].resolution, "java_static_import_method")

    def test_static_import_overloaded_method(self):
        """Static imported overloaded methods should match by argument count."""
        caller_source = """
package com.example;

import static com.google.common.base.Preconditions.checkNotNull;

public class Example {
    public void validate(String input, String message) {
        checkNotNull(input, message);
    }
}
"""
        callee_source = """
package com.google.common.base;

public class Preconditions {
    public static <T> T checkNotNull(T reference) {
        if (reference == null) throw new NullPointerException();
        return reference;
    }
    public static <T> T checkNotNull(T reference, Object errorMessage) {
        if (reference == null) throw new NullPointerException(String.valueOf(errorMessage));
        return reference;
    }
}
"""
        repo = FakeRepo({
            "com/google/common/base/Preconditions.java": callee_source
        })
        methods = extract_java_methods("Example.java", caller_source)
        edges, unresolved = resolve_java_call_edges("Example.java", caller_source, methods, repo=repo)
        
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].caller_qualname, "Example.validate")
        self.assertIn("checkNotNull", edges[0].callee_qualname)

    def test_qualified_call_still_works(self):
        """Qualified calls to external classes are unresolved without repo."""
        source = """
package com.example;

import com.google.common.base.Preconditions;

public class Example {
    public void validate(String input) {
        Preconditions.checkNotNull(input);
    }
}
"""
        methods = extract_java_methods("Example.java", source)
        edges, unresolved = resolve_java_call_edges("Example.java", source, methods, repo=None)
        
        # Without repo, external imports cannot be resolved
        self.assertEqual(len(edges), 0)
        self.assertEqual(len(unresolved), 1)
        unresolved_list = list(unresolved.values())[0]
        self.assertEqual(len(unresolved_list), 1)
        self.assertIn("checkNotNull", unresolved_list[0].expr)

    def test_static_import_field_access(self):
        """Static imported constant field access should be resolved."""
        source = """
package com.example;

import static java.lang.Math.PI;

public class Circle {
    public double area(double radius) {
        return PI * radius * radius;
    }
}
"""
        methods = extract_java_methods("Circle.java", source)
        edges, unresolved = resolve_java_call_edges("Circle.java", source, methods, repo=None)
        
        # This should generate a 'reads' edge, not 'calls'
        # For now we just verify it doesn't crash
        # Field resolution is a separate feature
        pass


if __name__ == "__main__":
    unittest.main()
