from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.ids import stable_java_node_claim_id, stable_read_edge_claim_id, stable_write_edge_claim_id
from tmf.java_extract import JAVA_DEGRADE_HINT, java_status
from tmf.retrieve import retrieve_path, reverse_readers, reverse_writers
from tmf.store import Store
from tmf.warm import warm_repo
from tests.test_java_inherit import init_repo


@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaFieldReadWriteTests(unittest.TestCase):
    def test_this_field_reads_and_writes_resolve(self):
        source = """class Service {
  int count;
  void run() { int x = this.count; this.count = x + 1; this.count += 2; }
}
"""
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Service.java": source})
            warm_repo(repo)
            store = Store(repo)
            run_id = stable_java_node_claim_id("Service.java", "Service.run", "method")
            field_id = stable_java_node_claim_id("Service.java", "Service.count", "field")
            graph = store.get_claim(run_id).body["graph"]
            self.assertEqual(graph["reads"][0]["target_id"], field_id)
            write_targets = {w["target_id"] for w in graph["writes"]}
            self.assertEqual(write_targets, {field_id})
            read_edge = store.get_claim(stable_read_edge_claim_id(run_id, field_id))
            write_edge = store.get_claim(stable_write_edge_claim_id(run_id, field_id))
            self.assertIsNotNone(read_edge)
            self.assertIsNotNone(write_edge)
            self.assertEqual(read_edge.body["language"], "java")
            self.assertTrue(check_freshness(GitRepo(repo), write_edge).fresh)
            self.assertEqual(reverse_readers(repo, field_id)["readers"][0]["reader_id"], run_id)
            self.assertEqual(reverse_writers(repo, field_id)["writers"][0]["writer_id"], run_id)

    def test_static_field_and_explicit_import_static_field_resolve(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "pkg/Config.java": "package pkg; public class Config { public static int LIMIT; }\n",
                "app/App.java": "package app;\nimport pkg.Config;\nclass App { static int LOCAL; void run() { int x = LOCAL + Config.LIMIT; LOCAL = x; Config.LIMIT = x; } }\n",
            })
            retrieve_path(repo, "pkg/Config.java")
            retrieve_path(repo, "app/App.java")
            store = Store(repo)
            run_id = stable_java_node_claim_id("app/App.java", "App.run", "method")
            local_id = stable_java_node_claim_id("app/App.java", "App.LOCAL", "constant")
            imported_id = stable_java_node_claim_id("pkg/Config.java", "Config.LIMIT", "constant")
            graph = store.get_claim(run_id).body["graph"]
            read_targets = {r["target_id"] for r in graph["reads"]}
            write_targets = {w["target_id"] for w in graph["writes"]}
            self.assertEqual(read_targets, {local_id, imported_id})
            self.assertEqual(write_targets, {local_id, imported_id})

    def test_local_parameter_shadow_and_variable_receiver_unresolved(self):
        source = """class Service {
  int value;
  void run(int value, Other other) { int x = value; other.value = x; }
}
class Other { int value; }
"""
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Service.java": source})
            warm_repo(repo)
            store = Store(repo)
            run_id = stable_java_node_claim_id("Service.java", "Service.run", "method")
            graph = store.get_claim(run_id).body["graph"]
            unresolved_reads = {(u["expr"], u["reason"]) for u in graph["reads_unresolved"]}
            unresolved_writes = {(u["expr"], u["reason"]) for u in graph["writes_unresolved"]}
            self.assertIn(("value", "java_local_or_parameter_shadow"), unresolved_reads)
            self.assertIn(("other.value", "java_variable_receiver_field_not_resolved"), unresolved_writes)
            self.assertEqual(graph["reads"], [])
            self.assertEqual(graph["writes"], [])

    def test_variable_receiver_field_does_not_cross_bind_to_same_named_class_field(self):
        source = """class A {
  int count;
  int read2(Foo other) { return other.count; }
  void write2(Foo other, int x) { other.count = x; }
}
class Foo { int count; }
"""
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"A.java": source})
            warm_repo(repo)
            store = Store(repo)
            read_id = stable_java_node_claim_id("A.java", "A.read2", "method")
            write_id = stable_java_node_claim_id("A.java", "A.write2", "method")
            a_count = stable_java_node_claim_id("A.java", "A.count", "field")
            foo_count = stable_java_node_claim_id("A.java", "Foo.count", "field")
            read_graph = store.get_claim(read_id).body["graph"]
            write_graph = store.get_claim(write_id).body["graph"]
            self.assertEqual(read_graph["reads"], [])
            self.assertEqual(write_graph["writes"], [])
            self.assertNotEqual(a_count, foo_count)
            self.assertIsNone(store.get_claim(stable_read_edge_claim_id(read_id, a_count)))
            self.assertIsNone(store.get_claim(stable_read_edge_claim_id(read_id, foo_count)))
            self.assertIsNone(store.get_claim(stable_write_edge_claim_id(write_id, a_count)))
            self.assertIsNone(store.get_claim(stable_write_edge_claim_id(write_id, foo_count)))
            self.assertIn({"expr": "other.count", "reason": "java_variable_receiver_field_not_resolved"}, read_graph["reads_unresolved"])
            self.assertIn({"expr": "other.count", "reason": "java_variable_receiver_field_not_resolved"}, write_graph["writes_unresolved"])

    def test_this_and_bare_same_class_fields_still_resolve_after_variable_receiver_guard(self):
        source = """class A {
  int count;
  int read() { return count + this.count; }
  void write(int x) { count = x; this.count = x + 1; }
}
"""
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"A.java": source})
            warm_repo(repo)
            store = Store(repo)
            read_id = stable_java_node_claim_id("A.java", "A.read", "method")
            write_id = stable_java_node_claim_id("A.java", "A.write", "method")
            count_id = stable_java_node_claim_id("A.java", "A.count", "field")
            read_graph = store.get_claim(read_id).body["graph"]
            write_graph = store.get_claim(write_id).body["graph"]
            self.assertEqual({r["target_id"] for r in read_graph["reads"]}, {count_id})
            self.assertEqual({w["target_id"] for w in write_graph["writes"]}, {count_id})


if __name__ == "__main__":
    unittest.main()
