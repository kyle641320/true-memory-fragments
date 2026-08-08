from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.ids import stable_java_node_claim_id, stable_override_edge_claim_id
from tmf.java_extract import JAVA_DEGRADE_HINT, java_status
from tmf.retrieve import reverse_overridden_by
from tmf.store import Store
from tmf.warm import warm_repo
from tests.test_java_inherit import init_repo


@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaOverrideEdgeTests(unittest.TestCase):
    def test_same_file_extends_and_implements_override_candidates(self):
        source = """interface Api { void run(); }
class Base { String name(int x) { return \"\"; } }
class Child extends Base implements Api {
  void run() {}
  String name(int x) { return \"child\"; }
}
"""
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Sample.java": source})
            warm_repo(repo)
            store = Store(repo)
            child_run = stable_java_node_claim_id("Sample.java", "Child.run", "method")
            api_run = stable_java_node_claim_id("Sample.java", "Api.run", "method")
            child_name = stable_java_node_claim_id("Sample.java", "Child.name", "method")
            base_name = stable_java_node_claim_id("Sample.java", "Base.name", "method")
            run_edge = store.get_claim(stable_override_edge_claim_id(child_run, api_run))
            name_edge = store.get_claim(stable_override_edge_claim_id(child_name, base_name))
            self.assertIsNotNone(run_edge)
            self.assertIsNotNone(name_edge)
            self.assertEqual(run_edge.body["edge_kind"], "overrides")
            self.assertEqual(run_edge.body["resolution"], "java_same_file_override_candidate")
            self.assertEqual(run_edge.evidence, "inferred")
            self.assertLessEqual(run_edge.confidence, 0.6)
            self.assertTrue(check_freshness(GitRepo(repo), name_edge).fresh)
            child_graph = store.get_claim(child_name).body["graph"]
            self.assertEqual(child_graph["overrides"][0]["target_id"], base_name)
            base_graph = store.get_claim(base_name).body["graph"]
            self.assertEqual(base_graph["overridden_by"][0]["source_id"], child_name)
            reverse = reverse_overridden_by(repo, base_name)["overridden_by"]
            self.assertEqual(reverse[0]["method_id"], child_name)

    def test_overloads_cross_file_and_unknown_parent_are_unresolved(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "pkg/Base.java": "package pkg; public class Base { void imported() {} }\n",
                "Sample.java": "import pkg.Base;\nclass LocalBase { void m(int x) {} void m(String x) {} }\nclass Child extends LocalBase { void m(int x) {} void missing() {} }\nclass ExternalChild extends Base { void imported() {} }\nclass UnknownChild extends MissingBase { void ghost() {} }\n",
            })
            warm_repo(repo)
            store = Store(repo)
            child_m = stable_java_node_claim_id("Sample.java", "Child.m", "method")
            ext_imported = stable_java_node_claim_id("Sample.java", "ExternalChild.imported", "method")
            unknown_ghost = stable_java_node_claim_id("Sample.java", "UnknownChild.ghost", "method")
            child_graph = store.get_claim(child_m).body["graph"]
            ext_graph = store.get_claim(ext_imported).body["graph"]
            unknown_graph = store.get_claim(unknown_ghost).body["graph"]
            self.assertEqual(child_graph["overrides"], [])
            self.assertIn({"expr": "m", "reason": "java_overloaded_or_ambiguous_override"}, child_graph["overrides_unresolved"])
            self.assertEqual(ext_graph["overrides"], [])
            self.assertIn({"expr": "imported", "reason": "java_cross_file_override_deferred"}, ext_graph["overrides_unresolved"])
            self.assertEqual(unknown_graph["overrides"], [])
            self.assertIn({"expr": "ghost", "reason": "java_parent_type_unresolved"}, unknown_graph["overrides_unresolved"])


if __name__ == "__main__":
    unittest.main()
