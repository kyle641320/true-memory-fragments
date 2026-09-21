from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_java_inherit import init_repo, run
from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.ids import stable_java_node_claim_id
from tmf.java_extract import JAVA_DEGRADE_HINT, java_status
from tmf.java_extract import extract_java_methods, java_node_id
from tmf.retrieve import retrieve_path
from tmf.store import Store
from tmf.warm import warm_repo


@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaInheritedReceiverTests(unittest.TestCase):
    def fixture(self, files, *, compile=True):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = init_repo(Path(temporary.name), files)
        if compile and shutil.which("javac"):
            result = subprocess.run(["javac", "-d", str(root / "classes"),
                                     *[str(root / path) for path in files if path.endswith(".java")]],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(warm_repo(root)["coverage"], "complete")
        store = Store(root)
        self.addCleanup(store.index.close)
        return root, store

    def caller(self, store):
        return store.get_claim(stable_java_node_claim_id("app/Service.java", "Service.execute", "method"))

    def graph(self, root, store):
        claim = self.caller(store)
        graph = claim.body["graph"]
        edges = [store.get_claim(edge_id) for edge_id in store.index.edge_ids(claim.id, {"calls"}, 100)]
        edges = [edge for edge in edges if edge.body["caller_id"] == claim.id]
        self.assertEqual({edge.body["callee_id"] for edge in edges},
                         {item["target_id"] for item in graph["callees"]})
        retrieved = retrieve_path(root, "app/Service.java")
        actual = next(item.claim for item in retrieved.claims if item.claim.id == claim.id)
        self.assertEqual(actual.body["graph"], graph)
        self.assertEqual(graph["calls_coverage"], "partial")
        return graph, edges

    @staticmethod
    def targets(graph):
        return [(item["target_path"], item["target_qualname"]) for item in graph["callees"]]

    @staticmethod
    def typed_files():
        return {
            "api/Base.java": "package api; public class Base { public void run() {} }\n",
            "api/Other.java": "package api; public class Other { public void run() {} }\n",
            "api/Child.java": "package api; public class Child extends Base {}\n",
            "app/Service.java": "package app; import api.Child; class Service { Child target; void execute() { target.run(); } }\n",
        }

    def test_inherited_field_uses_declaring_imports_and_local_shadowing(self):
        for imported in ("real.Delegate", "real.*"):
            with self.subTest(imported=imported):
                root, store = self.fixture({
                    "real/Delegate.java": "package real; public interface Delegate { void run(); }\n",
                    "wrong/Delegate.java": "package wrong; public interface Delegate { void run(); }\n",
                    "base/Base.java": f"package base; import {imported}; public class Base {{ protected Delegate target; }}\n",
                    "app/Service.java": "package app; import base.Base; import wrong.Delegate; class Service extends Base { void execute(Delegate target) { target.run(); this.target.run(); } }\n",
                })
                graph, edges = self.graph(root, store)
                self.assertEqual(self.targets(graph), [("wrong/Delegate.java", "Delegate.run"), ("real/Delegate.java", "Delegate.run")])
                inherited = next(edge for edge in edges if edge.body["callee_path"] == "real/Delegate.java")
                self.assertIn("base/Base.java", inherited.body["java_resolution_context"]["dependency_paths"])

    def test_transitive_interface_diamond_deduplicates_same_origin(self):
        root, store = self.fixture({
            "api/Root.java": "package api; public interface Root { void run(); }\n",
            "api/Left.java": "package api; public interface Left extends Root {}\n",
            "api/Right.java": "package api; public interface Right extends Root {}\n",
            "api/Child.java": "package api; public interface Child extends Left, Right {}\n",
            "app/Service.java": self.typed_files()["app/Service.java"],
        })
        graph, _ = self.graph(root, store)
        self.assertEqual(self.targets(graph), [("api/Root.java", "Root.run")])
        self.assertEqual(graph["unresolved_calls"], [])

    def test_inherited_overload_and_own_override_do_not_mask_by_name(self):
        root, store = self.fixture({
            "api/Base.java": "package api; public class Base { public void run(int x) {} public void run(String x) {} }\n",
            "api/Child.java": "package api; public class Child extends Base { public void run(String x) {} }\n",
            "app/Service.java": "package app; import api.Child; class Service { Child target; void execute() { target.run(1); target.run(\"ok\"); } }\n",
        })
        graph, _ = self.graph(root, store)
        self.assertEqual(self.targets(graph), [("api/Base.java", "Base.run"), ("api/Child.java", "Child.run")])

    def test_signature_types_resolve_in_each_declaring_context(self):
        root, store = self.fixture({
            "x/Arg.java": "package x; public class Arg {}\n", "y/Arg.java": "package y; public class Arg {}\n",
            "api/Base.java": "package api; import x.Arg; public class Base { public void run(Arg x) {} }\n",
            "api/Child.java": "package api; import y.Arg; public class Child extends Base { public void run(Arg x) {} }\n",
            "app/Service.java": "package app; import api.Child; class Service { Child target; void execute(x.Arg x, y.Arg y) { target.run(x); target.run(y); } }\n",
        })
        graph, _ = self.graph(root, store)
        self.assertEqual(self.targets(graph), [("api/Base.java", "Base.run"), ("api/Child.java", "Child.run")])

    def test_retargeted_parent_invalidates_edge_and_graph_then_warm_repairs(self):
        root, store = self.fixture(self.typed_files())
        caller = self.caller(store)
        _, edges = self.graph(root, store)
        self.assertEqual(len(edges), 1)
        (root / "api/Child.java").write_text("package api; public class Child extends Other {}\n")
        for claim in (caller, edges[0]):
            self.assertFalse(check_freshness(GitRepo(root), claim).fresh)
        warm_repo(root)
        graph, edges = self.graph(root, store)
        self.assertEqual(self.targets(graph), [("api/Other.java", "Other.run")])
        self.assertTrue(check_freshness(GitRepo(root), self.caller(store)).fresh)

    def test_inherited_field_type_change_invalidates_without_endpoint_change(self):
        files = self.typed_files()
        files["app/Service.java"] = "package app; import api.Child; class Service extends Child { void execute() { target.run(); } }\n"
        files["api/Child.java"] = "package api; public class Child { protected Base target; }\n"
        root, store = self.fixture(files)
        caller = self.caller(store)
        _, edges = self.graph(root, store)
        self.assertEqual(len(edges), 1)
        (root / "api/Child.java").write_text("package api; public class Child { protected Other target; }\n")
        self.assertFalse(check_freshness(GitRepo(root), caller).fresh)
        self.assertFalse(check_freshness(GitRepo(root), edges[0]).fresh)
        warm_repo(root)
        graph, _ = self.graph(root, store)
        self.assertEqual(self.targets(graph), [("api/Other.java", "Other.run")])

    def test_new_duplicate_symbol_invalidates_negative_lookup_evidence(self):
        root, store = self.fixture(self.typed_files())
        caller = self.caller(store)
        _, edges = self.graph(root, store)
        added = root / "second/api/Base.java"
        added.parent.mkdir(parents=True)
        added.write_text("package api; public class Base { public void run() {} }\n")
        run(["git", "add", "second/api/Base.java"], root)
        for claim in (caller, edges[0]):
            result = check_freshness(GitRepo(root), claim)
            self.assertFalse(result.fresh)
            self.assertIn("java resolution symbol manifest mismatch", result.stale_bindings)
        warm_repo(root)
        graph, _ = self.graph(root, store)
        self.assertEqual(self.targets(graph), [])
        self.assertTrue(graph["unresolved_calls"])

    def test_manifest_cache_does_not_trust_restored_mtime(self):
        root, store = self.fixture(self.typed_files())
        claim = self.caller(store)
        repo = GitRepo(root)
        self.assertTrue(check_freshness(repo, claim).fresh)
        target = root / "api/Other.java"
        previous = target.stat()
        target.write_text(target.read_text().replace("Other", "Base "))
        os.utime(target, ns=(previous.st_atime_ns, previous.st_mtime_ns))
        self.assertFalse(check_freshness(repo, claim).fresh)

    def test_unresolved_method_is_bound_and_repaired_by_normal_warm(self):
        files = self.typed_files()
        files["api/Base.java"] = "package api; public class Base {}\n"
        root, store = self.fixture(files, compile=False)
        caller = self.caller(store)
        graph, _ = self.graph(root, store)
        self.assertEqual(self.targets(graph), [])
        self.assertIn("java_resolution_context", caller.body)
        (root / "api/Base.java").write_text(self.typed_files()["api/Base.java"])
        self.assertFalse(check_freshness(GitRepo(root), caller).fresh)
        warm_repo(root)
        graph, _ = self.graph(root, store)
        self.assertEqual(self.targets(graph), [("api/Base.java", "Base.run")])

    def test_missing_ancestor_added_later_repairs_negative_graph(self):
        files = self.typed_files()
        del files["api/Base.java"]
        root, store = self.fixture(files, compile=False)
        caller = self.caller(store)
        self.assertEqual(self.targets(caller.body["graph"]), [])
        (root / "api/Base.java").write_text(self.typed_files()["api/Base.java"])
        run(["git", "add", "api/Base.java"], root)
        self.assertFalse(check_freshness(GitRepo(root), caller).fresh)
        warm_repo(root)
        graph, _ = self.graph(root, store)
        self.assertEqual(self.targets(graph), [("api/Base.java", "Base.run")])

    def test_unrelated_body_edit_does_not_change_symbol_digest(self):
        root, store = self.fixture(self.typed_files())
        caller = self.caller(store)
        _, edges = self.graph(root, store)
        (root / "api/Other.java").write_text("package api; public class Other { public void run() { int x = 1; } }\n")
        for claim in (caller, edges[0]):
            self.assertTrue(check_freshness(GitRepo(root), claim).fresh)

    def test_inaccessible_hidden_field_cannot_fall_through(self):
        root, store = self.fixture({
            **self.typed_files(),
            "api/Ancestor.java": "package api; public class Ancestor { public Base target; }\n",
            "api/Child.java": "package api; public class Child extends Ancestor { private Other target; }\n",
            "app/Service.java": "package app; import api.Child; class Service extends Child { void execute() { target.run(); } }\n",
        }, compile=False)
        graph, _ = self.graph(root, store)
        self.assertEqual(self.targets(graph), [])
        self.assertTrue(graph["unresolved_calls"])

    def test_unsupported_generic_ancestor_is_not_erased_to_a_guess(self):
        files = self.typed_files()
        files["api/Base.java"] = "package api; public class Base<T> { public void run() {} }\n"
        files["api/Child.java"] = "package api; public class Child extends Base<String> {}\n"
        root, store = self.fixture(files)
        graph, _ = self.graph(root, store)
        self.assertEqual(self.targets(graph), [])
        self.assertTrue(graph["unresolved_calls"])

    def test_static_caller_cannot_use_inherited_instance_field(self):
        files = self.typed_files()
        files["api/Child.java"] = "package api; public class Child { protected Base target; }\n"
        files["app/Service.java"] = "package app; import api.Child; class Service extends Child { static void execute() { target.run(); } }\n"
        root, store = self.fixture(files, compile=False)
        graph, _ = self.graph(root, store)
        self.assertEqual(self.targets(graph), [])
        self.assertIn("java_inherited_field_static_context_not_supported", [item["reason"] for item in graph["unresolved_calls"]])

    def test_static_caller_cannot_use_own_instance_field_with_inherited_target(self):
        files = self.typed_files()
        files["app/Service.java"] = files["app/Service.java"].replace("void execute()", "static void execute()")
        root, store = self.fixture(files, compile=False)
        graph, _ = self.graph(root, store)
        self.assertEqual(self.targets(graph), [])
        self.assertIn("java_inherited_field_static_context_not_supported", [item["reason"] for item in graph["unresolved_calls"]])

    def test_build_only_change_cannot_take_warm_complete_noop(self):
        files = {**self.typed_files(), "settings.gradle": "rootProject.name = 'demo'\n"}
        root, store = self.fixture(files)
        caller = self.caller(store)
        (root / "settings.gradle").write_text("rootProject.name = 'demo'\ninclude ':api'\n")
        self.assertFalse(check_freshness(GitRepo(root), caller).fresh)
        result = warm_repo(root)
        self.assertGreater(result["derived"], 0)
        graph, _ = self.graph(root, store)
        self.assertEqual(self.targets(graph), [("api/Base.java", "Base.run")])
        self.assertTrue(check_freshness(GitRepo(root), self.caller(store)).fresh)
        self.assertEqual(warm_repo(root)["derived"], 0)

    def test_new_inherited_field_invalidates_prior_static_type_lookup(self):
        root, store = self.fixture({
            "api/Base.java": "package api; public class Base {}\n",
            "d/Worker.java": "package d; public class Worker { public static void run() {} }\n",
            "d/Helper.java": "package d; public class Helper { public void run() {} }\n",
            "app/Service.java": "package app; import api.Base; import d.Worker; class Service extends Base { void execute(){ Worker.run(); } }\n",
        })
        caller = self.caller(store)
        graph, edges = self.graph(root, store)
        self.assertEqual(self.targets(graph), [("d/Worker.java", "Worker.run")])
        (root / "api/Base.java").write_text("package api; public class Base { protected d.Helper Worker; }\n")
        for claim in (caller, edges[0]):
            self.assertFalse(check_freshness(GitRepo(root), claim).fresh)
        warm_repo(root)
        graph, _ = self.graph(root, store)
        self.assertEqual(self.targets(graph), [("d/Helper.java", "Helper.run")])

    def test_inherited_member_type_is_not_promoted_to_imported_receiver(self):
        root, store = self.fixture({
            "base/Base.java": "package base; public class Base { public static class Worker { public void run() {} } }\n",
            "fake/Root.java": "package fake; public class Root { public void run() {} }\n",
            "fake/Worker.java": "package fake; public class Worker extends Root {}\n",
            "app/Service.java": "package app; import base.Base; import fake.Worker; class Service extends Base { Worker target; void execute(){ target.run(); } }\n",
        })
        graph, _ = self.graph(root, store)
        self.assertEqual(self.targets(graph), [])
        self.assertTrue(graph["unresolved_calls"])

    def test_literal_types_preserve_suffixes_and_unshadowable_string_type(self):
        for signatures, expression, chosen in (
            (("int", "long"), "1L", "long"),
            (("double", "float"), "1.0f", "float"),
            (("fake.String", "java.lang.String"), '"text"', "java.lang.String"),
        ):
            with self.subTest(expression=expression):
                files = self.typed_files()
                files["fake/String.java"] = "package fake; public class String {}\n"
                files["api/Base.java"] = "package api; public class Base {\n" + "\n".join(
                    f"public void run({arg} x) {{}}" for arg in signatures) + "\n}\n"
                files["app/Service.java"] = "package app; import api.Child; import fake.String; class Service { Child target; void execute() { target.run(" + expression + "); } }\n"
                root, store = self.fixture(files)
                graph, _ = self.graph(root, store)
                expected = next(method for method in extract_java_methods("api/Base.java", files["api/Base.java"])
                                if method.identity_key == f"Base.run({chosen})")
                self.assertEqual([item["target_id"] for item in graph["callees"]], [java_node_id(expected)])

    def test_tracking_existing_duplicate_bypasses_no_complete_noop_checks(self):
        root, store = self.fixture(self.typed_files())
        duplicate = root / "second/api/Base.java"
        duplicate.parent.mkdir(parents=True)
        duplicate.write_text(self.typed_files()["api/Base.java"])
        # warm enumerates this source, but source-symbol lookup uses the Git
        # tracked universe; adding it to the index changes no source bytes.
        warm_repo(root)
        old = self.caller(store)
        run(["git", "add", "second/api/Base.java"], root)
        self.assertFalse(check_freshness(GitRepo(root), old).fresh)
        self.assertGreater(warm_repo(root)["derived"], 0)
        graph, _ = self.graph(root, store)
        self.assertEqual(self.targets(graph), [])

    def test_unrelated_record_does_not_make_pinned_and_live_manifests_disagree(self):
        root, store = self.fixture({**self.typed_files(),
                                   "api/RecordValue.java": "package api; public record RecordValue(int value) {}\n"}, compile=False)
        caller = self.caller(store)
        self.assertTrue(check_freshness(GitRepo(root), caller).fresh)
        graph, _ = self.graph(root, store)
        self.assertEqual(self.targets(graph), [("api/Base.java", "Base.run")])
        self.assertEqual(warm_repo(root)["derived"], 0)

    def test_symbol_manifest_preserves_index_free_source_lookup(self):
        from tmf.java_index import java_symbol_manifest_digest
        root, _ = self.fixture(self.typed_files())
        with tempfile.TemporaryDirectory() as td:
            exported = Path(td)
            for name, content in self.typed_files().items():
                path = exported / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            self.assertEqual(java_symbol_manifest_digest(GitRepo(root)),
                             java_symbol_manifest_digest(GitRepo(exported)))
