from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.ids import stable_call_edge_claim_id, stable_java_node_claim_id
from tmf.java_extract import JAVA_DEGRADE_HINT, java_status
from tmf.retrieve import retrieve_path, reverse_callers
from tmf.store import Store
from tmf.warm import warm_repo
from tests.test_java_inherit import init_repo


@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaCallEdgeTests(unittest.TestCase):
    def test_same_class_method_and_this_method_calls_resolve(self):
        source = """class Service {
  void run() { helper(); this.other(); }
  void helper() {}
  void other() {}
}
"""
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Service.java": source})
            warm_repo(repo)
            store = Store(repo)
            run_id = stable_java_node_claim_id("Service.java", "Service.run", "method")
            helper_id = stable_java_node_claim_id("Service.java", "Service.helper", "method")
            other_id = stable_java_node_claim_id("Service.java", "Service.other", "method")
            graph = store.get_claim(run_id).body["graph"]
            targets = {(c["target_id"], c["resolution"]) for c in graph["callees"]}
            self.assertIn((helper_id, "java_same_class_method"), targets)
            self.assertIn((other_id, "java_this_method"), targets)
            edge = store.get_claim(stable_call_edge_claim_id(run_id, helper_id))
            self.assertIsNotNone(edge)
            self.assertEqual(edge.body["edge_kind"], "calls")
            self.assertEqual(edge.body["language"], "java")
            self.assertTrue(check_freshness(GitRepo(repo), edge).fresh)
            callers = reverse_callers(repo, helper_id)["callers"]
            self.assertEqual(callers[0]["caller_id"], run_id)

    def test_explicit_import_static_type_call_resolves(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "pkg/Util.java": "package pkg; public class Util { public static void f() {} }\n",
                "app/App.java": "package app;\nimport pkg.Util;\nclass App { void run() { Util.f(); } }\n",
            })
            retrieve_path(repo, "pkg/Util.java")
            retrieve_path(repo, "app/App.java")
            store = Store(repo)
            run_id = stable_java_node_claim_id("app/App.java", "App.run", "method")
            f_id = stable_java_node_claim_id("pkg/Util.java", "Util.f", "method")
            graph = store.get_claim(run_id).body["graph"]
            self.assertEqual(graph["callees"][0]["target_id"], f_id)
            self.assertEqual(graph["callees"][0]["resolution"], "java_explicit_import_static_method")
            self.assertIsNotNone(store.get_claim(stable_call_edge_claim_id(run_id, f_id)))

    def test_variable_receiver_overload_and_parent_method_unresolved(self):
        source = """class Base { void inherited() {} }
class Service extends Base {
  void run(Util u) { u.f(); overloaded(1); inherited(); }
  void overloaded(int x) {}
  void overloaded(String x) {}
}
class Util { void f() {} }
"""
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Service.java": source})
            warm_repo(repo)
            store = Store(repo)
            run_id = stable_java_node_claim_id("Service.java", "Service.run", "method")
            graph = store.get_claim(run_id).body["graph"]
            unresolved = {(u["expr"], u["reason"]) for u in graph["unresolved_calls"]}
            self.assertIn(("u.f", "java_variable_or_unknown_receiver"), unresolved)
            self.assertIn(("overloaded", "java_overloaded_or_ambiguous_method"), unresolved)
            self.assertIn(("inherited", "java_parent_method_deferred_to_override_window"), unresolved)
            self.assertEqual(graph["callees"], [])


if __name__ == "__main__":
    unittest.main()
