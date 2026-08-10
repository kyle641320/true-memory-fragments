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

    def test_project_index_resolves_same_package_and_fully_qualified_signature_types(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "domain/src/main/java/acme/model/Value.java": "package acme.model; public class Value {}\n",
                "app/src/main/java/acme/model/Holder.java": "package acme.model; class Holder { Value value; }\n",
                "app/src/main/java/acme/app/Service.java": "package acme.app; class Service { acme.model.Value load(acme.model.Value value) { return value; } }\n",
            })
            warm_repo(repo)
            store = Store(repo)
            value = stable_java_node_claim_id("domain/src/main/java/acme/model/Value.java", "Value", "class")
            field = stable_java_node_claim_id("app/src/main/java/acme/model/Holder.java", "Holder.value", "field")
            method = stable_java_node_claim_id("app/src/main/java/acme/app/Service.java", "Service.load", "method")
            self.assertIsNotNone(store.get_claim(stable_type_use_edge_claim_id(field, value, "field_type")))
            self.assertIsNotNone(store.get_claim(stable_type_use_edge_claim_id(method, value, "return_type")))
            self.assertIsNotNone(store.get_claim(stable_type_use_edge_claim_id(method, value, "param_type")))

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

    def test_nested_generic_array_and_wildcard_type_references_resolve(self):
        source = """class Value {}
class Box<T> { java.util.Map<String, java.util.List<? extends Value[]>> values; }
"""
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Box.java": source})
            warm_repo(repo)
            store = Store(repo)
            value_id = stable_java_node_claim_id("Box.java", "Value", "class")
            field_id = stable_java_node_claim_id("Box.java", "Box.values", "field")
            self.assertIsNotNone(store.get_claim(stable_type_use_edge_claim_id(field_id, value_id, "field_type")))

    def test_project_index_cache_invalidates_after_java_file_change(self):
        from tmf.git import GitRepo
        from tmf.java_extract import extract_java_classes, extract_java_fields, extract_java_methods, resolve_java_type_use_edges

        with tempfile.TemporaryDirectory() as td:
            root = init_repo(Path(td), {
                "model/Old.java": "package model; public class Old {}\n",
                "app/App.java": "package app; import model.Old; class App { Old value; }\n",
            })
            repo = GitRepo(root)
            source = repo.read_file("app/App.java")
            args = ("app/App.java", source, extract_java_classes("app/App.java", source), extract_java_methods("app/App.java", source), extract_java_fields("app/App.java", source))
            edges, _ = resolve_java_type_use_edges(*args, repo=repo)
            self.assertEqual(1, len(edges))
            (root / "model/Old.java").unlink()
            edges, unresolved = resolve_java_type_use_edges(*args, repo=repo)
            self.assertEqual([], edges)
            self.assertTrue(unresolved)


if __name__ == "__main__":
    unittest.main()
