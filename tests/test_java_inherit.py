from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.ids import stable_inherit_edge_claim_id, stable_java_node_claim_id
from tmf.java_extract import JAVA_DEGRADE_HINT, java_status
from tmf.retrieve import refresh_path, reverse_implementors, reverse_subtypes
from tmf.store import Store
from tmf.warm import warm_repo


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def init_repo(root: Path, files: dict[str, str]) -> Path:
    repo = root / "repo"
    repo.mkdir(parents=True)
    run(["git", "init", "-b", "master"], repo)
    run(["git", "config", "user.email", "tmf@example.com"], repo)
    run(["git", "config", "user.name", "tmf"], repo)
    for path, content in files.items():
        full = repo / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
    run(["git", "add", *files.keys()], repo)
    run(["git", "commit", "-m", "init"], repo)
    return repo


@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaInheritEdgeTests(unittest.TestCase):
    def test_same_file_extends_implements_and_interface_extends_edges(self):
        source = """package demo;
interface Marker {}
interface ChildMarker extends Marker {}
class Base {}
class Child extends Base implements ChildMarker {}
"""
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Sample.java": source})
            warm_repo(repo)
            store = Store(repo)
            child = stable_java_node_claim_id("Sample.java", "Child", "class")
            base = stable_java_node_claim_id("Sample.java", "Base", "class")
            iface = stable_java_node_claim_id("Sample.java", "ChildMarker", "interface")
            marker = stable_java_node_claim_id("Sample.java", "Marker", "interface")
            extends_edge = store.get_claim(stable_inherit_edge_claim_id(child, base, "extends"))
            impl_edge = store.get_claim(stable_inherit_edge_claim_id(child, iface, "implements"))
            iface_edge = store.get_claim(stable_inherit_edge_claim_id(iface, marker, "extends"))
            self.assertIsNotNone(extends_edge)
            self.assertIsNotNone(impl_edge)
            self.assertIsNotNone(iface_edge)
            self.assertEqual(extends_edge.body.get("edge_kind"), "inherits")
            self.assertEqual(extends_edge.body.get("relation"), "extends")
            self.assertEqual(impl_edge.body.get("relation"), "implements")
            self.assertEqual(extends_edge.body.get("child_id"), child)
            self.assertEqual(extends_edge.body.get("parent_id"), base)
            self.assertEqual(extends_edge.body.get("child_anchor", {}).get("qualname"), "Child")
            self.assertEqual(extends_edge.body.get("parent_anchor", {}).get("qualname"), "Base")
            child_claim = store.get_claim(child)
            base_claim = store.get_claim(base)
            iface_claim = store.get_claim(iface)
            self.assertEqual(child_claim.body["graph"]["inherits"][0]["target_id"], base)
            self.assertTrue(any(item["target_id"] == iface for item in child_claim.body["graph"]["inherits"]))
            self.assertEqual(child_claim.body["graph"]["inherits_coverage"], "partial")
            self.assertEqual(base_claim.body["graph"]["subtypes"][0]["source_id"], child)
            self.assertEqual(base_claim.body["graph"]["subtypes_coverage"], "partial")
            self.assertEqual(iface_claim.body["graph"]["implementors"][0]["source_id"], child)
            self.assertEqual(iface_claim.body["graph"]["implementors_coverage"], "partial")
            self.assertEqual(reverse_subtypes(repo, base)["subtypes"][0]["child_id"], child)
            self.assertEqual(reverse_implementors(repo, iface)["implementors"][0]["child_id"], child)

    def test_explicit_import_top_level_resolves_but_external_wildcard_and_ambiguous_do_not(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "pkg/Base.java": "package pkg; public class Base {}\n",
                "pkg/Left.java": "package pkg; public interface Left {}\n",
                "app/Child.java": "package app;\nimport pkg.Base;\nimport pkg.Left;\nimport java.util.List;\nimport pkg.*;\nclass LocalA {}\nclass LocalB {}\nclass Child extends Base implements Left, List, WildThing {}\nclass Ambiguous extends LocalA {}\ninterface WildIface extends WildThing {}\n",
            })
            # Make LocalA ambiguous in the same file; Ambiguous must not link by guessing.
            child_path = repo / "app/Child.java"
            child_path.write_text(child_path.read_text(encoding="utf-8") + "class LocalA {}\n", encoding="utf-8")
            refresh_path(repo, "pkg/Base.java")
            refresh_path(repo, "pkg/Left.java")
            refresh_path(repo, "app/Child.java")
            store = Store(repo)
            child = stable_java_node_claim_id("app/Child.java", "Child", "class")
            base = stable_java_node_claim_id("pkg/Base.java", "Base", "class")
            left = stable_java_node_claim_id("pkg/Left.java", "Left", "interface")
            self.assertIsNotNone(store.get_claim(stable_inherit_edge_claim_id(child, base, "extends")))
            self.assertIsNotNone(store.get_claim(stable_inherit_edge_claim_id(child, left, "implements")))
            graph = store.get_claim(child).body["graph"]
            unresolved = {(item["expr"], item["reason"]) for item in graph.get("inherits_unresolved", [])}
            self.assertIn(("List", "external_or_jdk_type"), unresolved)
            self.assertIn(("WildThing", "wildcard_import"), unresolved)
            ambiguous = stable_java_node_claim_id("app/Child.java", "Ambiguous", "class")
            unresolved_amb = {(item["expr"], item["reason"]) for item in store.get_claim(ambiguous).body["graph"].get("inherits_unresolved", [])}
            self.assertIn(("LocalA", "ambiguous_type"), unresolved_amb)
            self.assertFalse(any(c.body.get("qualname") in {"List", "WildThing"} and c.body.get("language") == "java" for c in store.iter_claims()))

    def test_generics_are_erased_and_freshness_retarget_reconciles_old_edge(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Sample.java": "interface Box {}\nclass Base {}\nclass Other {}\nclass Child extends Base implements Box<String> {}\n"})
            warm_repo(repo)
            store = Store(repo)
            child = stable_java_node_claim_id("Sample.java", "Child", "class")
            base = stable_java_node_claim_id("Sample.java", "Base", "class")
            box = stable_java_node_claim_id("Sample.java", "Box", "interface")
            old_edge_id = stable_inherit_edge_claim_id(child, base, "extends")
            impl_id = stable_inherit_edge_claim_id(child, box, "implements")
            old_edge = store.get_claim(old_edge_id)
            self.assertIsNotNone(old_edge)
            self.assertIsNotNone(store.get_claim(impl_id))
            self.assertTrue(check_freshness(GitRepo(repo), old_edge).fresh)
            (repo / "Sample.java").write_text("interface Box {}\nclass Base {}\nclass Other {}\nclass Child extends Other implements Box<String> {}\n", encoding="utf-8")
            self.assertFalse(check_freshness(GitRepo(repo), store.get_claim(child)).fresh)
            self.assertFalse(check_freshness(GitRepo(repo), old_edge).fresh)
            refresh_path(repo, "Sample.java")
            new_parent = stable_java_node_claim_id("Sample.java", "Other", "class")
            self.assertIsNone(Store(repo).get_claim(old_edge_id))
            self.assertIsNotNone(Store(repo).get_claim(stable_inherit_edge_claim_id(child, new_parent, "extends")))
            self.assertIsNotNone(Store(repo).get_claim(impl_id))

    def test_project_index_resolves_same_package_import_and_fqn_across_source_roots(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "lib/src/main/java/acme/base/Base.java": "package acme.base; public class Base {}\n",
                "lib/src/main/java/acme/base/Marker.java": "package acme.base; public interface Marker {}\n",
                "app/src/main/java/acme/base/SamePackage.java": "package acme.base; class SamePackage extends Base {}\n",
                "app/src/main/java/acme/app/Imported.java": "package acme.app; import acme.base.Base; class Imported extends Base {}\n",
                "app/src/main/java/acme/app/Qualified.java": "package acme.app; class Qualified implements acme.base.Marker {}\n",
            })
            warm_repo(repo)
            store = Store(repo)
            base = stable_java_node_claim_id("lib/src/main/java/acme/base/Base.java", "Base", "class")
            marker = stable_java_node_claim_id("lib/src/main/java/acme/base/Marker.java", "Marker", "interface")
            same = stable_java_node_claim_id("app/src/main/java/acme/base/SamePackage.java", "SamePackage", "class")
            imported = stable_java_node_claim_id("app/src/main/java/acme/app/Imported.java", "Imported", "class")
            qualified = stable_java_node_claim_id("app/src/main/java/acme/app/Qualified.java", "Qualified", "class")
            self.assertIsNotNone(store.get_claim(stable_inherit_edge_claim_id(same, base, "extends")))
            self.assertIsNotNone(store.get_claim(stable_inherit_edge_claim_id(imported, base, "extends")))
            self.assertIsNotNone(store.get_claim(stable_inherit_edge_claim_id(qualified, marker, "implements")))

    def test_project_index_does_not_guess_cross_package_ambiguous_or_unimported_type(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "a/Thing.java": "package a; public class Thing {}\n",
                "b/Thing.java": "package b; public class Thing {}\n",
                "app/Bad.java": "package app; class Bad extends Thing {}\n",
            })
            warm_repo(repo)
            bad = stable_java_node_claim_id("app/Bad.java", "Bad", "class")
            unresolved = Store(repo).get_claim(bad).body["graph"]["inherits_unresolved"]
            self.assertIn(("Thing", "ambiguous_type"), {(x["expr"], x["reason"]) for x in unresolved})

    def test_unrelated_change_fresh_parent_body_change_stale_and_endpoint_delete_clears_edge(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Sample.java": "class Base { int x = 1; }\nclass Child extends Base {}\nclass Spare { int y = 1; }\n"})
            warm_repo(repo)
            store = Store(repo)
            child = stable_java_node_claim_id("Sample.java", "Child", "class")
            base = stable_java_node_claim_id("Sample.java", "Base", "class")
            edge_id = stable_inherit_edge_claim_id(child, base, "extends")
            edge = store.get_claim(edge_id)
            self.assertTrue(check_freshness(GitRepo(repo), edge).fresh)
            (repo / "Sample.java").write_text("class Base { int x = 1; }\nclass Child extends Base {}\nclass Spare { int y = 2; }\n", encoding="utf-8")
            self.assertTrue(check_freshness(GitRepo(repo), edge).fresh)
            (repo / "Sample.java").write_text("class Base { int x = 2; }\nclass Child extends Base {}\nclass Spare { int y = 1; }\n", encoding="utf-8")
            self.assertFalse(check_freshness(GitRepo(repo), edge).fresh)
            (repo / "Sample.java").write_text("class Child {}\nclass Spare { int y = 1; }\n", encoding="utf-8")
            refresh_path(repo, "Sample.java")
            self.assertIsNone(Store(repo).get_claim(edge_id))


if __name__ == "__main__":
    unittest.main()
