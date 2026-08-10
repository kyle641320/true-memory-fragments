from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tmf.ids import stable_inherit_edge_claim_id, stable_java_node_claim_id, stable_type_use_edge_claim_id
from tmf.java_extract import JAVA_DEGRADE_HINT, java_status
from tmf.store import Store
from tmf.warm import warm_repo
from tests.test_java_inherit import init_repo


@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaRecordsSealedTests(unittest.TestCase):
    def test_record_is_stable_class_node_with_component_type_evidence_only(self):
        source = """interface Tagged {}
class Value {}
@interface Mark {}
record Box<T>(@Mark Value value, java.util.List<T> values) implements Tagged {
  Box { if (value == null) throw new IllegalArgumentException(); }
}
"""
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Box.java": source})
            warm_repo(repo)
            store = Store(repo)
            box = stable_java_node_claim_id("Box.java", "Box", "class")
            value = stable_java_node_claim_id("Box.java", "Value", "class")
            tagged = stable_java_node_claim_id("Box.java", "Tagged", "interface")
            ctor = stable_java_node_claim_id("Box.java", "Box.Box", "constructor")
            self.assertIsNotNone(store.get_claim(box))
            self.assertIsNotNone(store.get_claim(ctor))
            self.assertIsNotNone(store.get_claim(stable_type_use_edge_claim_id(box, value, "record_component_type")))
            self.assertIsNotNone(store.get_claim(stable_inherit_edge_claim_id(box, tagged, "implements")))
            # Source-only policy: no implicit record members are fabricated.
            for name, kind in [("value", "field"), ("values", "field"), ("value", "method"),
                               ("equals", "method"), ("hashCode", "method"), ("toString", "method")]:
                self.assertIsNone(store.get_claim(stable_java_node_claim_id("Box.java", f"Box.{name}", kind)))
            graph = store.get_claim(ctor).body.get("graph", {})
            self.assertEqual([], graph.get("callees", []))

            first_ids = {c.id for c in store.iter_claims() if c.body.get("language") == "java"}
            warm_repo(repo)
            second_ids = {c.id for c in Store(repo).iter_claims() if c.body.get("language") == "java"}
            self.assertEqual(first_ids, second_ids)

    def test_sealed_permits_is_explicit_subtype_edge_and_not_a_call(self):
        source = """sealed interface Shape permits Circle, Polygon {}
record Circle(int radius) implements Shape {}
non-sealed class Polygon implements Shape {}
"""
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Shape.java": source})
            warm_repo(repo)
            store = Store(repo)
            shape = stable_java_node_claim_id("Shape.java", "Shape", "interface")
            circle = stable_java_node_claim_id("Shape.java", "Circle", "class")
            polygon = stable_java_node_claim_id("Shape.java", "Polygon", "class")
            self.assertIsNotNone(store.get_claim(stable_inherit_edge_claim_id(circle, shape, "permits")))
            self.assertIsNotNone(store.get_claim(stable_inherit_edge_claim_id(polygon, shape, "permits")))
            self.assertIsNotNone(store.get_claim(stable_inherit_edge_claim_id(circle, shape, "implements")))
            self.assertEqual([], store.get_claim(shape).body.get("graph", {}).get("callees", []))

    def test_permits_ambiguity_and_external_remain_unresolved(self):
        files = {
            "a/Dup.java": "package a; public final class Dup {}\n",
            "b/Dup.java": "package b; public final class Dup {}\n",
            "app/Root.java": "package app; sealed interface Root permits Dup, ext.Missing {}\n",
        }
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), files)
            warm_repo(repo)
            root = stable_java_node_claim_id("app/Root.java", "Root", "interface")
            graph = Store(repo).get_claim(root).body["graph"]
            unresolved = {(x["expr"], x["reason"], x["relation"]) for x in graph["inherits_unresolved"]}
            self.assertIn(("Dup", "ambiguous_type", "permits"), unresolved)
            self.assertIn(("Missing", "external_or_jdk_type", "permits"), unresolved)
            self.assertEqual([], graph.get("callees", []))


if __name__ == "__main__":
    unittest.main()
