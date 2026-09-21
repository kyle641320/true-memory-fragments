from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.test_java_inherit import init_repo
from tmf.git import GitRepo
from tmf.ids import stable_java_node_claim_id
from tmf.java_extract import JAVA_DEGRADE_HINT, java_status
from tmf.java_index import java_project_index
from tmf.retrieve import retrieve_path, reverse_callers
from tmf.store import Store
from tmf.warm import warm_repo


@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaFieldReceiverTests(unittest.TestCase):
    def derive(self, files, path="app/Service.java"):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = init_repo(Path(temporary.name), files)
        warm_repo(root)
        store = Store(root)
        self.addCleanup(store.index.close)
        caller = stable_java_node_claim_id(path, "Service.execute", "method")
        claim = store.get_claim(caller)
        graph = claim.body["graph"]
        edges = [store.get_claim(edge_id) for edge_id in store.index.edge_ids(caller, {"calls"}, 100)]
        indexed = {edge.body["callee_id"] for edge in edges if edge.body.get("caller_id") == caller}
        self.assertEqual(indexed, {item["target_id"] for item in graph["callees"]})
        retrieved = retrieve_path(root, path)
        self.assertEqual(next(item.claim.body["graph"] for item in retrieved.claims if item.claim.id == caller), graph)
        self.assertEqual(graph["calls_coverage"], "partial")
        return root, graph

    @staticmethod
    def targets(graph):
        return [(item["anchor"]["path"], item["anchor"]["qualname"]) for item in graph["callees"]]

    def test_injected_repository_delegate_import_module_matrix(self):
        for kind in ("Repository", "Delegate"):
            for cross_module in (False, True):
                for wildcard in (False, True):
                    with self.subTest(kind=kind, cross_module=cross_module, wildcard=wildcard):
                        dep = ("lib/" if cross_module else "") + f"src/main/java/api/{kind}.java"
                        app = ("app/" if cross_module else "") + "src/main/java/app/Service.java"
                        imported = "*" if wildcard else kind
                        _, graph = self.derive({
                            "pom.xml": "<project><modules><module>lib</module><module>app</module></modules></project>",
                            "lib/pom.xml": "<project/>", "app/pom.xml": "<project/>",
                            dep: f"package api; public interface {kind} {{ void run(); }}\n",
                            app: f"package app;\nimport api.{imported};\nclass Service {{\n"
                                 f"@Resource {kind} first;\n@Inject {kind} second;\n"
                                 "void execute() { first.run(); this.second.run(); }\n}\n",
                        }, app)
                        self.assertEqual(self.targets(graph), [(dep, f"{kind}.run")] * 2)
                        self.assertEqual(graph["unresolved_calls"], [])
                        expected = "project_wildcard_import" if wildcard else "project_explicit_import"
                        self.assertEqual({c["resolution"] for c in graph["callees"]}, {"java_project_typed_receiver_" + expected})

    def test_generic_receiver_erases_only_outer_type(self):
        _, graph = self.derive({
            "api/Delegate.java": "package api; public interface Delegate<T> { void run(); }\n",
            "app/Service.java": "package app;\nimport api.*;\nclass Service { Delegate<java.util.List<String>> target; void execute() { target.run(); } }\n",
        })
        self.assertEqual(self.targets(graph), [("api/Delegate.java", "Delegate.run")])

    def test_generic_chained_return_is_not_rebound_to_callers_import(self):
        _, graph = self.derive({
            "actual/Delegate.java": "package actual; public interface Delegate<T> { void run(); }\n",
            "wrong/Delegate.java": "package wrong; public interface Delegate<T> { void run(); }\n",
            "api/Factory.java": "package api;\nimport actual.Delegate;\npublic interface Factory { Delegate<String> get(); }\n",
            "app/Service.java": "package app;\nimport api.Factory;\nimport wrong.Delegate;\nclass Service { Factory target; void execute() { target.get().run(); } }\n",
        })
        self.assertEqual(self.targets(graph), [("api/Factory.java", "Factory.get")])
        self.assertIn({"expr": "target.get().run", "reason": "java_chained_return_type_unresolved"}, graph["unresolved_calls"])

    def test_wildcard_does_not_guess_ambiguous_or_missing_types(self):
        for imports, reason in (("import a.*;\nimport b.*;", "java_receiver_project_ambiguous_wildcard_import"),
                                ("import missing.*;", "java_receiver_project_wildcard_type_not_found")):
            with self.subTest(imports=imports):
                _, graph = self.derive({
                    "a/Delegate.java": "package a; public interface Delegate { void run(); }\n",
                    "b/Delegate.java": "package b; public interface Delegate { void run(); }\n",
                    "app/Service.java": "package app;\n" + imports + "\nclass Service { Delegate target; void execute() { target.run(); } }\n",
                })
                self.assertEqual(self.targets(graph), [])
                self.assertEqual(graph["unresolved_calls"], [{"expr": "target.run", "reason": reason}])

    def test_static_wildcard_is_not_a_package_import(self):
        _, graph = self.derive({
            "a/Holder/Delegate.java": "package a.Holder; public interface Delegate { void run(); }\n",
            "app/Service.java": "package app;\nimport static a.Holder.*;\nclass Service { Delegate target; void execute() { target.run(); } }\n",
        })
        self.assertEqual(self.targets(graph), [])

    def test_explicit_and_same_package_precede_wildcards(self):
        for explicit, expected in ((False, "app"), (True, "b")):
            with self.subTest(explicit=explicit):
                imports = "import a.*;\n" + ("import b.Delegate;\n" if explicit else "")
                _, graph = self.derive({
                    **{f"{pkg}/Delegate.java": f"package {pkg}; public interface Delegate {{ void run(); }}\n" for pkg in ("a", "b", "app")},
                    "app/Service.java": "package app;\n" + imports + "class Service { Delegate target; void execute() { target.run(); } }\n",
                })
                self.assertEqual(self.targets(graph), [(f"{expected}/Delegate.java", "Delegate.run")])

    def test_qualified_receiver_ignores_conflicting_simple_import(self):
        for typename in ("b.Delegate", "b . Delegate", "b. Delegate", "b /*comment*/ . Delegate", "b. /*comment*/ Delegate"):
            with self.subTest(typename=typename):
                _, graph = self.derive({
                    "a/Delegate.java": "package a; public interface Delegate { void run(); }\n",
                    "b/Delegate.java": "package b; public interface Delegate { void run(); }\n",
                    "app/Service.java": "package app;\nimport a.Delegate;\nclass Service { " + typename + " target; void execute() { target.run(); } }\n",
                })
                self.assertEqual(self.targets(graph), [("b/Delegate.java", "Delegate.run")])

    def test_duplicate_fqn_is_ambiguous_in_all_lookup_forms(self):
        root, _ = self.derive({
            "one/api/Delegate.java": "package api; public interface Delegate { void run(); }\n",
            "two/api/Delegate.java": "package api; public interface Delegate { void run(); }\n",
            "app/Service.java": "package app;\nimport api.Delegate;\nclass Service { Delegate target; void execute() { target.run(); } }\n",
        })
        index = java_project_index(GitRepo(root))
        for expression, kwargs in (("api.Delegate", {}), ("Delegate", {"imports": {"Delegate": "api/Delegate.java"}}),
                                  ("Delegate", {"package": "api"}), ("Delegate", {"wildcard_imports": {"api"}})):
            with self.subTest(expression=expression, kwargs=kwargs):
                symbol, reason = index.resolve(expression, **kwargs)
                self.assertIsNone(symbol)
                self.assertIn("ambiguous", reason)

    def test_parameter_shadow_and_explicit_this_are_distinct(self):
        _, graph = self.derive({
            "api/Delegate.java": "package api; public interface Delegate { void run(); }\n",
            "api/Other.java": "package api; public interface Other { void run(); }\n",
            "app/Service.java": "package app;\nimport api.*;\nclass Service { Delegate target; void execute(Other target) { target.run(); this.target.run(); } }\n",
        })
        self.assertEqual(self.targets(graph), [("api/Other.java", "Other.run"), ("api/Delegate.java", "Delegate.run")])

    def test_local_shadow_lifetime_does_not_leak_from_block(self):
        _, graph = self.derive({
            "api/Delegate.java": "package api; public interface Delegate { void run(); }\n",
            "api/Other.java": "package api; public interface Other { void run(); }\n",
            "app/Service.java": "package app;\nimport api.*;\nclass Service { Delegate target; void execute() { target.run(); { Other target = null; target.run(); this.target.run(); } target.run(); } }\n",
        })
        self.assertEqual(self.targets(graph), [("api/Delegate.java", "Delegate.run"), ("api/Other.java", "Other.run"),
                                              ("api/Delegate.java", "Delegate.run"), ("api/Delegate.java", "Delegate.run")])

    def test_variable_named_like_import_is_not_a_static_type_receiver(self):
        _, graph = self.derive({
            "api/Delegate.java": "package api; public interface Delegate { void run(); }\n",
            "api/Other.java": "package api; public interface Other { void run(); }\n",
            "app/Service.java": "package app;\nimport api.Delegate;\nimport api.Other;\nclass Service { void execute(Other Delegate) { Delegate.run(); } }\n",
        })
        self.assertEqual(self.targets(graph), [("api/Other.java", "Other.run")])

    def test_this_cannot_resolve_a_parameter_as_a_field(self):
        _, graph = self.derive({
            "api/Delegate.java": "package api; public interface Delegate { void run(); }\n",
            "app/Service.java": "package app;\nimport api.Delegate;\nclass Service { void execute(Delegate target) { this.target.run(); } }\n",
        })
        self.assertEqual(self.targets(graph), [])

    def test_nested_type_method_is_not_an_outer_receiver_method(self):
        _, graph = self.derive({
            "api/Delegate.java": "package api; public class Delegate { public static class Inner { public void run() {} } }\n",
            "app/Service.java": "package app;\nimport api.Delegate;\nclass Service { Delegate target; void execute() { target.run(); } }\n",
        })
        self.assertEqual(self.targets(graph), [])

    def test_unsupported_receiver_shapes_do_not_become_element_or_argument_types(self):
        for declaration in ("Delegate[] target", "Delegate target[]", "Outer<Delegate>.Inner<Delegate> target"):
            with self.subTest(declaration=declaration):
                _, graph = self.derive({
                    "api/Delegate.java": "package api; public interface Delegate { void run(); }\n",
                    "app/Service.java": "package app;\nimport api.Delegate;\nclass Service { " + declaration + "; void execute() { target.run(); } }\n",
                })
                self.assertEqual(self.targets(graph), [])
                self.assertEqual(graph["unresolved_calls"][0]["reason"], "java_receiver_type_not_supported")

    def test_lexical_type_names_do_not_become_imported_project_types(self):
        for body in ("class Service<Delegate> { Delegate target; void execute() { target.run(); } }",
                     "class Service { <Delegate> void execute(Delegate target) { target.run(); } }",
                     "class Service { class Delegate { void run() {} } Delegate target; void execute() { target.run(); } }"):
            with self.subTest(body=body):
                _, graph = self.derive({
                    "api/Delegate.java": "package api; public interface Delegate { void run(); }\n",
                    "app/Service.java": "package app;\nimport api.Delegate;\n" + body + "\n",
                })
                self.assertEqual(self.targets(graph), [])
                self.assertEqual(graph["unresolved_calls"][0]["reason"], "java_receiver_lexical_type_not_supported")

    def test_inherited_members_remain_explicit_boundaries_and_warm_is_not_recall(self):
        root, graph = self.derive({
            "api/Base.java": "package api; public interface Base { void run(); }\n",
            "api/Delegate.java": "package api; public interface Delegate extends Base {}\n",
            "app/Parent.java": "package app;\nimport api.Delegate;\nclass Parent { protected Delegate inherited; }\n",
            "app/Service.java": "package app;\nimport api.Delegate;\nclass Service extends Parent { Delegate target; void execute() { target.run(); inherited.run(); } }\n",
        })
        self.assertEqual(self.targets(graph), [])
        self.assertEqual({item["reason"] for item in graph["unresolved_calls"]},
                         {"java_receiver_method_not_declared_or_inherited", "java_variable_or_unknown_receiver"})
        result = reverse_callers(root, stable_java_node_claim_id("api/Base.java", "Base.run", "method"))
        self.assertEqual(result["coverage"], "complete")
        self.assertIn("not complete semantic call resolution", result["note"])

    def test_type_is_resolved_in_declaration_not_call_context(self):
        for body in (
            "Delegate target; <Delegate> void execute() { target.run(); }",
            "Delegate target; void execute() { class Delegate {} target.run(); }",
            "void execute() { Delegate target = null; class Delegate {} target.run(); }",
        ):
            with self.subTest(body=body):
                _, graph = self.derive({
                    "api/Delegate.java": "package api; public interface Delegate { void run(); }\n",
                    "app/Service.java": "package app;\nimport api.Delegate;\nclass Service { " + body + " }\n",
                })
                self.assertEqual(self.targets(graph), [("api/Delegate.java", "Delegate.run")])

    def test_catch_and_resource_shadow_fields_but_do_not_escape_scope(self):
        bodies = (
            "try { throw new Other(); } catch (Other target) { target.run(); } target.run();",
            "try (Other target = new Other()) { target.run(); } finally { target.run(); }",
        )
        for body in bodies:
            with self.subTest(body=body):
                _, graph = self.derive({
                    "api/Delegate.java": "package api; public interface Delegate { void run(); }\n",
                    "api/Other.java": "package api; public class Other extends RuntimeException implements AutoCloseable { public void run() {} public void close() {} }\n",
                    "app/Service.java": "package app;\nimport api.*;\nclass Service { Delegate target; void execute() { " + body + " } }\n",
                })
                methods = [t for t in self.targets(graph) if t[1].endswith(".run")]
                self.assertEqual(methods, [("api/Other.java", "Other.run"), ("api/Delegate.java", "Delegate.run")])

    def test_varargs_and_flow_pattern_never_fall_back_to_shadowed_field(self):
        for method in (
            "void execute(Other... target) { target.clone(); }",
            "void execute(Object value) { if (value instanceof Other target) { target.clone(); } }",
        ):
            with self.subTest(method=method):
                _, graph = self.derive({
                    "api/Delegate.java": "package api; public interface Delegate { Object clone(); }\n",
                    "api/Other.java": "package api; public class Other { public Object clone() { return this; } }\n",
                    "app/Service.java": "package app;\nimport api.*;\nclass Service { Delegate target; " + method + " }\n",
                })
                self.assertEqual(self.targets(graph), [])
                self.assertEqual(graph["unresolved_calls"][0]["reason"], "java_receiver_type_not_supported")

    def test_anonymous_class_fields_cannot_replace_enclosing_fields(self):
        _, graph = self.derive({
            "api/Delegate.java": "package api; public interface Delegate { void run(); }\n",
            "api/Other.java": "package api; public interface Other { void run(); }\n",
            "app/Service.java": "package app;\nimport api.*;\nclass Service { Delegate target; Object value = new Object() { Other target; }; void execute() { Object inner = new Object() { Other target; }; target.run(); this.target.run(); } }\n",
        })
        self.assertEqual(self.targets(graph), [("api/Delegate.java", "Delegate.run")] * 2)

    def test_imported_member_type_is_not_an_unrelated_fully_qualified_type(self):
        for imports, body in (
            ("import actual.Outer;", "Outer.Inner<String> target; void execute() { target.run(); }"),
            ("import actual.*;", "Outer.Inner<String> target; void execute() { target.run(); }"),
            ("", "static class Outer { static class Inner<T> { void run() {} } } Outer.Inner<String> target; void execute() { target.run(); }"),
            ("", "void execute() { class Outer { class Inner<T> { void run() {} } } Outer.Inner<String> target = null; target.run(); }"),
        ):
            with self.subTest(imports=imports, body=body):
                _, graph = self.derive({
                    "actual/Outer.java": "package actual; public class Outer { public static class Inner<T> { public void run() {} } }\n",
                    "Outer/Inner.java": "package Outer; public class Inner<T> { public void run() {} }\n",
                    "app/Service.java": "package app;\n" + imports + "\nclass Service { " + body + " }\n",
                })
                self.assertEqual(self.targets(graph), [])
                self.assertIn(graph["unresolved_calls"][0]["reason"],
                              {"java_receiver_type_not_supported", "java_receiver_lexical_type_not_supported"})
