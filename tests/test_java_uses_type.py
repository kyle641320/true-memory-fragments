from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tmf.ids import stable_java_node_claim_id, stable_type_use_edge_claim_id
from tmf.java_extract import JAVA_DEGRADE_HINT, java_status
from tmf.retrieve import reverse_used_by_types
from tmf.store import Store
from tmf.warm import warm_repo
from tests.test_java_inherit import init_repo


@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaUsesTypeTests(unittest.TestCase):
    def test_same_file_field_param_and_return_types_resolve(self):
        source = """class Foo {}
class Service {
  Foo field;
  Foo run(Foo input) { return input; }
}
"""
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Service.java": source})
            warm_repo(repo)
            store = Store(repo)
            foo_id = stable_java_node_claim_id("Service.java", "Foo", "class")
            field_id = stable_java_node_claim_id("Service.java", "Service.field", "field")
            run_id = stable_java_node_claim_id("Service.java", "Service.run", "method")
            self.assertIsNotNone(store.get_claim(stable_type_use_edge_claim_id(field_id, foo_id, "field_type")))
            self.assertIsNotNone(store.get_claim(stable_type_use_edge_claim_id(run_id, foo_id, "return_type")))
            self.assertIsNotNone(store.get_claim(stable_type_use_edge_claim_id(run_id, foo_id, "param_type")))
            graph = store.get_claim(run_id).body["graph"]
            self.assertIn(foo_id, {u["target_id"] for u in graph["uses_type"]})
            rev = reverse_used_by_types(repo, foo_id)
            self.assertIn(run_id, {u["user_id"] for u in rev["used_by_types"]})

    def test_explicit_import_type_resolves_but_jdk_and_unknown_do_not(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "pkg/Foo.java": "package pkg; public class Foo {}\n",
                "app/App.java": "package app;\nimport pkg.Foo;\nimport java.util.List;\nclass App { Foo f; String s; List<Foo> xs; Missing m; Foo[] arr; }\n",
            })
            warm_repo(repo)
            store = Store(repo)
            foo_id = stable_java_node_claim_id("pkg/Foo.java", "Foo", "class")
            f_claim = store.get_claim(stable_java_node_claim_id("app/App.java", "App.f", "field"))
            xs_claim = store.get_claim(stable_java_node_claim_id("app/App.java", "App.xs", "field"))
            s_claim = store.get_claim(stable_java_node_claim_id("app/App.java", "App.s", "field"))
            m_claim = store.get_claim(stable_java_node_claim_id("app/App.java", "App.m", "field"))
            self.assertIn(foo_id, {u["target_id"] for u in f_claim.body["graph"]["uses_type"]})
            self.assertIn(foo_id, {u["target_id"] for u in xs_claim.body["graph"]["uses_type"]})
            unresolved = {(u["type"], u["reason"]) for c in [xs_claim, s_claim, m_claim] for u in c.body["graph"]["uses_type_unresolved"]}
            self.assertIn(("String", "java_external_or_jdk_type_not_resolved"), unresolved)
            self.assertIn(("List", "java_external_or_jdk_type_not_resolved"), unresolved)
            self.assertIn(("Missing", "java_type_not_resolved"), unresolved)

    def test_nested_constructor_param_type_uses_constructor_node(self):
        source = """class Outer {
  static class Value {}
  static class Nested {
    Nested(Value value) {}
  }
}
"""
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Outer.java": source})
            warm_repo(repo)
            store = Store(repo)
            constructor_id = stable_java_node_claim_id("Outer.java", "Outer.Nested.Nested", "constructor")
            value_id = stable_java_node_claim_id("Outer.java", "Outer.Value", "class")
            edge_id = stable_type_use_edge_claim_id(constructor_id, value_id, "param_type")
            self.assertIsNotNone(store.get_claim(constructor_id))
            edge = store.get_claim(edge_id)
            self.assertIsNotNone(edge)
            assert edge is not None
            self.assertEqual(edge.body["user_id"], constructor_id)
            self.assertEqual(edge.body["user_anchor"]["line_start"], 4)

    def test_rewarm_removes_stale_constructor_type_edge(self):
        source = """class Outer {
  static class Value {}
  static class Nested {
    Nested(Value value) {}
  }
}
"""
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Outer.java": source})
            warm_repo(repo)
            store = Store(repo)
            value_id = stable_java_node_claim_id("Outer.java", "Outer.Value", "class")
            stale_user_id = stable_java_node_claim_id("Outer.java", "Outer.Nested.Nested", "method")
            stale_edge_id = stable_type_use_edge_claim_id(stale_user_id, value_id, "param_type")
            edge = store.get_claim(stable_type_use_edge_claim_id(
                stable_java_node_claim_id("Outer.java", "Outer.Nested.Nested", "constructor"),
                value_id,
                "param_type",
            ))
            assert edge is not None
            edge.id = stale_edge_id
            edge.body["user_id"] = stale_user_id
            store.put_claim(edge)
            source_path = repo / "Outer.java"
            source_path.write_text(source.replace("Value value", "Value renamed"), encoding="utf-8")
            import subprocess
            subprocess.run(["git", "add", "Outer.java"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "change"], cwd=repo, check=True, capture_output=True)
            warm_repo(repo)
            self.assertIsNone(store.get_claim(stale_edge_id))


if __name__ == "__main__":
    unittest.main()
