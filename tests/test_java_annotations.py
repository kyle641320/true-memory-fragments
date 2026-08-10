from __future__ import annotations
import tempfile, unittest
from pathlib import Path
from tmf.ids import stable_java_node_claim_id
from tmf.java_extract import JAVA_DEGRADE_HINT, extract_java_classes, java_status
from tmf.store import Store
from tmf.warm import warm_repo
from tests.test_java_inherit import init_repo

@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaAnnotationTests(unittest.TestCase):
    def test_declaration_and_uses_are_stable_type_evidence(self):
        source = '''@interface Mark { String value(); }
@Mark("type") class Demo {
 @Mark(value="field") String field;
 @Mark("method") @Mark("again") String run(@Mark("param") String value) { return value; }
}'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Demo.java": source}); warm_repo(repo); store = Store(repo)
            mark = stable_java_node_claim_id("Demo.java", "Mark", "interface")
            self.assertIsNotNone(store.get_claim(mark)); self.assertEqual("interface", extract_java_classes("Demo.java", source)[0].node_kind)
            for user in [stable_java_node_claim_id("Demo.java", "Demo", "class"), stable_java_node_claim_id("Demo.java", "Demo.field", "field"), stable_java_node_claim_id("Demo.java", "Demo.run", "method")]:
                self.assertIn(mark, {x["target_id"] for x in store.get_claim(user).body["graph"]["uses_type"] if x["use_kind"] == "annotation_type"})

    def test_type_use_record_component_and_compact_constructor(self):
        source = '''@interface Mark {}
record Row(@Mark String name) { @Mark Row {} @Mark String value(@Mark String input) { return input; } }
class Box { java.util.List<@Mark String> values; }'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Model.java": source}); warm_repo(repo); store = Store(repo)
            mark = stable_java_node_claim_id("Model.java", "Mark", "interface")
            for user in [stable_java_node_claim_id("Model.java", "Row", "class"), stable_java_node_claim_id("Model.java", "Row.Row", "constructor"), stable_java_node_claim_id("Model.java", "Row.value", "method"), stable_java_node_claim_id("Model.java", "Box.values", "field")]:
                self.assertIn(mark, {x["target_id"] for x in store.get_claim(user).body["graph"]["uses_type"]})

    def test_external_wildcard_ambiguity_and_values_do_not_create_calls(self):
        files = {"a/Dup.java": "package a; public @interface Dup {}", "b/Dup.java": "package b; public @interface Dup {}", "app/App.java": '''package app; import a.*;
@External(value={String.class, Mode.ONE, @Nested(name="x")}) @Dup class App {
 void value() {} void name() {} void run() {}
}'''}
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), files); warm_repo(repo); store = Store(repo)
            claim = store.get_claim(stable_java_node_claim_id("app/App.java", "App", "class"))
            unresolved = {(x["type"], x["reason"]) for x in claim.body["graph"]["uses_type_unresolved"]}
            self.assertIn(("External", "java_external_or_jdk_type_not_resolved"), unresolved); self.assertIn(("Dup", "java_ambiguous_type"), unresolved)
            self.assertEqual([], store.get_claim(stable_java_node_claim_id("app/App.java", "App.run", "method")).body["graph"]["callees"])

    def test_repeatable_looking_extraction_is_stable(self):
        source = "@interface A {} @A @A class C {}"
        first, second = extract_java_classes("C.java", source), extract_java_classes("C.java", source)
        self.assertEqual([(n.qualname,n.node_kind,n.class_hash) for n in first], [(n.qualname,n.node_kind,n.class_hash) for n in second])

    def test_meta_annotation_remains_explicitly_unresolved(self):
        source = "@interface Meta {} @Meta @interface A {}"
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"A.java": source}); warm_repo(repo)
            claim = Store(repo).get_claim(stable_java_node_claim_id("A.java", "A", "interface"))
            self.assertIn(("Meta", "java_meta_annotation_not_modeled"),
                          {(x["type"], x["reason"]) for x in claim.body["graph"]["uses_type_unresolved"]})

if __name__ == "__main__": unittest.main()
