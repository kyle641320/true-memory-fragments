from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.test_java_inherit import init_repo
from tmf.git import GitRepo
from tmf.java_extract import JAVA_DEGRADE_HINT, java_status
from tmf.java_members import JavaMemberResolver


@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaMemberTests(unittest.TestCase):
    def resolver(self, files):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = init_repo(Path(temporary.name), files)
        return JavaMemberResolver(GitRepo(root))

    def method(self, resolver, arguments=(), path="p/Child.java", owner="Child", name="work",
               caller_path="p/Caller.java", caller="Caller.run"):
        return resolver.lookup_method(path, owner, name, arguments,
                                      caller_path=caller_path, caller_qualname=caller)

    @staticmethod
    def declarations(extra=None):
        return {
            "p/Base.java": "package p; public class Base { public void work() {} }",
            "p/Child.java": "package p; public class Child extends Base {}",
            "p/Caller.java": "package p; public class Caller { void run() {} }",
            **(extra or {}),
        }

    def test_direct_and_transitive_source_methods(self):
        resolver = self.resolver(self.declarations({
            "p/Middle.java": "package p; public class Middle extends Base {}",
            "p/Child.java": "package p; public class Child extends Middle {}",
        }))
        result = self.method(resolver)
        self.assertIsNone(result.reason)
        self.assertEqual((result.method.path, result.method.qualname), ("p/Base.java", "Base.work"))
        self.assertEqual(set(result.dependency_paths), {"p/Base.java", "p/Child.java", "p/Middle.java", "p/Caller.java"})
        self.assertTrue(resolver.has_parents("p/Child.java", "Child"))
        self.assertFalse(resolver.has_parents("p/Base.java", "Base"))

    def test_inherited_field_uses_declaring_context_not_child_import(self):
        resolver = self.resolver({
            "actual/Worker.java": "package actual; public interface Worker { void work(); }",
            "wrong/Worker.java": "package wrong; public interface Worker { void work(); }",
            "base/Base.java": "package base;\nimport actual.Worker;\npublic class Base { @Resource protected Worker worker; }",
            "app/Child.java": "package app;\nimport wrong.Worker;\nimport base.Base;\npublic class Child extends Base {}",
        })
        field = resolver.lookup_field("app/Child.java", "Child", "worker")
        self.assertIsNone(field.reason)
        self.assertEqual((field.target_path, field.target_qualname), ("actual/Worker.java", "Worker"))
        self.assertEqual(set(field.dependency_paths), {"base/Base.java", "app/Child.java", "actual/Worker.java"})
        result = self.method(resolver, path=field.target_path, owner=field.target_qualname,
                             caller_path="app/Child.java", caller="Child")
        self.assertIsNone(result.reason)
        self.assertEqual(result.method.qualname, "Worker.work")

    def test_wildcard_ancestor_and_field_imports(self):
        resolver = self.resolver({
            "dep/Worker.java": "package dep; public interface Worker { void work(); }",
            "base/Base.java": "package base;\nimport dep.*;\npublic class Base { protected Worker worker; }",
            "app/Child.java": "package app;\nimport base.*;\npublic class Child extends Base {}",
        })
        field = resolver.lookup_field("app/Child.java", "Child", "worker")
        self.assertIsNone(field.reason)
        self.assertEqual(field.target_path, "dep/Worker.java")

    def test_nearer_private_field_masks_public_ancestor(self):
        resolver = self.resolver({
            "p/Worker.java": "package p; public interface Worker {}",
            "p/Old.java": "package p; public class Old { public Worker worker; }",
            "p/Middle.java": "package p; public class Middle extends Old { private Worker worker; }",
            "p/Child.java": "package p; public class Child extends Middle {}",
        })
        field = resolver.lookup_field("p/Child.java", "Child", "worker")
        self.assertEqual(field.reason, "java_inherited_field_inaccessible")
        self.assertIsNone(field.target_path)
        self.assertTrue({"p/Old.java", "p/Middle.java", "p/Child.java"} <= set(field.dependency_paths))

    def test_own_private_field_is_accessible_and_masks_parent(self):
        resolver = self.resolver({
            "p/Worker.java": "package p; public interface Worker {}",
            "p/Other.java": "package p; public interface Other {}",
            "p/Base.java": "package p; public class Base { public Other worker; }",
            "p/Child.java": "package p; public class Child extends Base { private Worker worker; }",
        })
        field = resolver.lookup_field("p/Child.java", "Child", "worker")
        self.assertIsNone(field.reason)
        self.assertEqual(field.target_path, "p/Worker.java")

    def test_package_private_field_does_not_reappear_after_package_hop(self):
        resolver = self.resolver({
            "p/Worker.java": "package p; public interface Worker {}",
            "p/Base.java": "package p; public class Base { Worker worker; }",
            "q/Middle.java": "package q; public class Middle extends p.Base {}",
            "p/Child.java": "package p; public class Child extends q.Middle {}",
        })
        field = resolver.lookup_field("p/Child.java", "Child", "worker")
        self.assertEqual(field.reason, "java_inherited_field_inaccessible")

    def test_same_package_field_and_method_are_accessible(self):
        resolver = self.resolver(self.declarations({
            "p/Worker.java": "package p; public interface Worker {}",
            "p/Base.java": "package p; public class Base { Worker worker; void work() {} }",
        }))
        self.assertIsNone(resolver.lookup_field("p/Child.java", "Child", "worker").reason)
        self.assertIsNone(self.method(resolver).reason)

    def test_static_and_interface_fields_are_not_instance_dependencies(self):
        for parent in ("class Base { public static Worker worker; }", "interface Base { Worker worker = null; }"):
            with self.subTest(parent=parent):
                relation = "implements" if parent.startswith("interface") else "extends"
                resolver = self.resolver({
                    "p/Worker.java": "package p; public interface Worker {}",
                    "p/Base.java": "package p; public " + parent,
                    "p/Child.java": f"package p; public class Child {relation} Base {{}}",
                })
                self.assertEqual(resolver.lookup_field("p/Child.java", "Child", "worker").reason,
                                 "java_inherited_static_field_unsupported")

    def test_fields_on_unrelated_interfaces_do_not_pick_first(self):
        resolver = self.resolver({
            "p/A.java": "package p; public interface A { Object worker = null; }",
            "p/B.java": "package p; public interface B { Object worker = null; }",
            "p/Child.java": "package p; public class Child implements A, B {}",
        })
        field = resolver.lookup_field("p/Child.java", "Child", "worker")
        self.assertEqual(field.reason, "java_inherited_field_ambiguous")

    def test_field_receiver_shapes_are_not_erased_or_rebound(self):
        for declared in ("Worker<String> worker;", "Worker[] worker;", "Worker worker[];"):
            with self.subTest(declared=declared):
                resolver = self.resolver({
                    "p/Worker.java": "package p; public interface Worker<T> {}",
                    "p/Base.java": "package p; public class Base { protected " + declared + " }",
                    "p/Child.java": "package p; public class Child extends Base {}",
                })
                self.assertIsNone(resolver.lookup_field("p/Child.java", "Child", "worker").target_path)

    def test_inherited_overloads_are_not_masked_by_name_or_arity(self):
        resolver = self.resolver(self.declarations({
            "p/Base.java": "package p; public class Base { public void work(int x) {} }",
            "p/Child.java": "package p; public class Child extends Base { public void work(String x) {} }",
        }))
        result = self.method(resolver, ("int",))
        self.assertIsNone(result.reason)
        self.assertEqual(result.method.qualname, "Base.work")
        result = self.method(resolver, ("String",))
        self.assertIsNone(result.reason)
        self.assertEqual(result.method.qualname, "Child.work")

    def test_primitive_overloads_and_override_keep_production_identity(self):
        resolver = self.resolver(self.declarations({
            "p/Base.java": "package p; public class Base { public void work(int x) {} public void work(double x) {} }",
            "p/Child.java": "package p; public class Child extends Base { public void work(int x) {} public void work(long x) {} }",
        }))
        result = self.method(resolver, ("int",))
        self.assertIsNone(result.reason)
        self.assertEqual(result.method.identity_key, "Child.work(int)")
        result = self.method(resolver, ("double",))
        self.assertIsNone(result.reason)
        self.assertEqual(result.method.identity_key, "Base.work(double)")

    def test_override_signature_canonicalized_in_declaration_context(self):
        resolver = self.resolver(self.declarations({
            "args/Arg.java": "package args; public class Arg {}",
            "p/Base.java": "package p;\nimport args.Arg;\npublic class Base { public void work(Arg arg) {} }",
            "p/Child.java": "package p; public class Child extends Base { public void work(args.Arg arg) {} }",
            "p/Caller.java": "package p;\nimport args.Arg;\npublic class Caller { void run() {} }",
        }))
        result = self.method(resolver, ("Arg",))
        self.assertIsNone(result.reason)
        self.assertEqual(result.method.path, "p/Child.java")
        self.assertIn("args/Arg.java", result.dependency_paths)

    def test_same_simple_parameter_name_from_different_imports_is_not_override(self):
        resolver = self.resolver(self.declarations({
            "a/Arg.java": "package a; public class Arg {}",
            "b/Arg.java": "package b; public class Arg {}",
            "p/Base.java": "package p;\nimport a.Arg;\npublic class Base { public void work(Arg arg) {} }",
            "p/Child.java": "package p;\nimport b.Arg;\npublic class Child extends Base { public void work(Arg arg) {} }",
            "p/Caller.java": "package p;\nimport a.Arg;\npublic class Caller { void run() {} }",
        }))
        result = self.method(resolver, ("Arg",))
        self.assertIsNone(result.reason)
        self.assertEqual(result.method.path, "p/Base.java")
        self.assertIn("a/Arg.java", result.dependency_paths)
        self.assertIn("b/Arg.java", result.dependency_paths)

    def test_same_origin_interface_diamond_is_deduplicated(self):
        resolver = self.resolver(self.declarations({
            "p/Base.java": "package p; public interface Base { default void work() {} }",
            "p/Left.java": "package p; public interface Left extends Base {}",
            "p/Right.java": "package p; public interface Right extends Base {}",
            "p/Child.java": "package p; public class Child implements Left, Right {}",
        }))
        result = self.method(resolver)
        self.assertIsNone(result.reason)
        self.assertEqual(result.method.path, "p/Base.java")

    def test_unrelated_interface_contracts_and_defaults_are_not_guessed(self):
        for body in ("void work();", "default void work() {}"):
            with self.subTest(body=body):
                resolver = self.resolver(self.declarations({
                    "p/Left.java": "package p; public interface Left { " + body + " }",
                    "p/Right.java": "package p; public interface Right { " + body + " }",
                    "p/Child.java": "package p; public abstract class Child implements Left, Right {}",
                }))
                self.assertEqual(self.method(resolver).reason, "java_inherited_method_ambiguous")

    def test_interface_subtype_override_dominates_ancestor(self):
        resolver = self.resolver(self.declarations({
            "p/Base.java": "package p; public interface Base { void work(); }",
            "p/Child.java": "package p; public interface Child extends Base { void work(); }",
        }))
        self.assertEqual(self.method(resolver).method.path, "p/Child.java")

    def test_unknown_parent_branch_refuses_even_if_known_branch_has_method(self):
        resolver = self.resolver(self.declarations({
            "p/Known.java": "package p; public interface Known { void work(); }",
            "p/Child.java": "package p; public abstract class Child extends missing.External implements Known {}",
        }))
        result = self.method(resolver)
        self.assertIsNone(result.method)
        self.assertIn("type_not_found", result.reason)
        self.assertIn("p/Child.java", result.dependency_paths)

    def test_cycle_duplicate_fqn_and_generic_ancestry_refuse(self):
        fixtures = [
            ({"p/Base.java": "package p; public class Base extends Child {}"}, "java_inherited_cycle"),
            ({"other/Base.java": "package p; public class Base { public void work() {} }"}, "ambiguous"),
            ({"p/Base.java": "package p; public class Base<T> { public void work() {} }"}, "generic"),
            ({"p/Child.java": "package p; public class Child extends Base<String> {}"}, "generic"),
        ]
        for files, reason in fixtures:
            with self.subTest(reason=reason):
                result = self.method(self.resolver(self.declarations(files)))
                self.assertIsNone(result.method)
                self.assertIn(reason, result.reason)
                self.assertIn("p/Child.java", result.dependency_paths)

    def test_method_access_refusals_do_not_fall_through(self):
        for modifier in ("private", "static", "protected", ""):
            with self.subTest(modifier=modifier):
                resolver = self.resolver(self.declarations({
                    "p/Base.java": f"package p; public class Base {{ {modifier} void work() {{}} }}",
                    "other/Caller.java": "package other; public class Caller { void run() {} }",
                }))
                result = self.method(resolver, caller_path="other/Caller.java")
                self.assertIsNone(result.method)
                self.assertIn("method_", result.reason)

    def test_argument_unknown_or_inapplicable_never_selects_lone_arity_match(self):
        resolver = self.resolver(self.declarations({
            "p/Base.java": "package p; public class Base { public void work(int arg) {} }",
        }))
        for args in (None, (None,), ("",), ("boolean",), ("Unknown",)):
            with self.subTest(args=args):
                self.assertIsNone(self.method(resolver, args).method)

    def test_primitive_widening_and_boxing_are_bounded(self):
        resolver = self.resolver(self.declarations({
            "p/Base.java": "package p; public class Base { public void work(long arg) {} public void work(Integer arg) {} }",
        }))
        result = self.method(resolver, ("int",))
        self.assertIsNone(result.reason)
        self.assertEqual(result.method.identity_key, "Base.work(long)")
        result = self.method(resolver, ("Integer",))
        self.assertIsNone(result.reason)
        self.assertEqual(result.method.identity_key, "Base.work(Integer)")

    def test_project_wrapper_name_cannot_box_primitive(self):
        resolver = self.resolver(self.declarations({
            "p/Integer.java": "package p; public class Integer {}",
            "p/Base.java": "package p; public class Base { public void work(Integer arg) {} }",
        }))
        self.assertIsNone(self.method(resolver, ("int",)).method)
        self.assertIsNone(self.method(resolver, ("Integer",)).reason)

    def test_generic_method_array_varargs_and_lexical_shadow_refuse(self):
        for method in ("public <T> void work(T arg) {}", "public void work(String... arg) {}",
                       "public void work(String[] arg) {}", "public void work(String arg[]) {}"):
            with self.subTest(method=method):
                resolver = self.resolver(self.declarations({"p/Base.java": "package p; public class Base { " + method + " }"}))
                self.assertIsNone(self.method(resolver, ("String",)).method)
        for caller in ("public class Caller { <String> void run() {} }",
                       "public class Caller { class String {} void run() {} }",
                       "public class Caller { void run() { class String {} } }"):
            with self.subTest(caller=caller):
                resolver = self.resolver(self.declarations({
                    "p/Base.java": "package p; public class Base { public void work(String arg) {} }",
                    "p/Caller.java": "package p; " + caller,
                }))
                self.assertEqual(self.method(resolver, ("String",)).reason, "java_inherited_lexical_type_unsupported")

    def test_field_missing_and_method_missing_retain_negative_dependencies(self):
        resolver = self.resolver(self.declarations())
        result = resolver.lookup_field("p/Child.java", "Child", "missing")
        self.assertEqual(result.reason, "java_inherited_field_not_found")
        self.assertEqual(set(result.dependency_paths), {"p/Child.java", "p/Base.java"})
        result = self.method(resolver, name="missing")
        self.assertEqual(result.reason, "java_inherited_method_not_found")
        self.assertEqual(set(result.dependency_paths), {"p/Child.java", "p/Base.java", "p/Caller.java"})

    def test_inherited_caller_member_type_cannot_be_rebound_to_import(self):
        resolver = self.resolver(self.declarations({
            "args/Arg.java": "package args; public class Arg {}",
            "p/CallerParent.java": "package p; public class CallerParent { public static class Arg {} }",
            "p/Caller.java": "package p;\nimport args.Arg;\npublic class Caller extends CallerParent { void run(Arg x) {} }",
            "p/Base.java": "package p; public class Base { public void work(args.Arg x) {} }",
        }))
        result = self.method(resolver, ("Arg",))
        self.assertEqual(result.reason, "java_inherited_lexical_type_unsupported")
        self.assertIn("p/CallerParent.java", result.dependency_paths)

    def test_public_method_on_inaccessible_receiver_type_is_not_promoted(self):
        resolver = self.resolver(self.declarations({
            "p/Child.java": "package p; class Child extends Base {}",
            "q/Caller.java": "package q; public class Caller { void run() {} }",
        }))
        result = self.method(resolver, caller_path="q/Caller.java")
        self.assertEqual(result.reason, "java_inherited_receiver_type_inaccessible")

    def test_primitive_widening_excludes_provably_incompatible_reference_overload(self):
        resolver = self.resolver(self.declarations({
            "p/Base.java": "package p; public class Base { public void work(long arg) {} public void work(String arg) {} }",
        }))
        result = self.method(resolver, ("int",))
        self.assertIsNone(result.reason)
        self.assertEqual(result.method.identity_key, "Base.work(long)")

    def test_bad_parse_and_nested_type_do_not_bypass_hierarchy_path(self):
        resolver = self.resolver(self.declarations({"p/Child.java": "package p; public class Child extends {"}))
        self.assertTrue(resolver.has_parents("p/Child.java", "Child"))
        self.assertEqual(self.method(resolver).reason, "java_inherited_parse_error")
        resolver = self.resolver(self.declarations())
        self.assertTrue(resolver.has_parents("p/Child.java", "Child.Nested"))
        self.assertEqual(self.method(resolver, owner="Child.Nested").reason, "java_inherited_nested_type_unsupported")


if __name__ == "__main__":
    unittest.main()
