from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.ids import stable_call_edge_claim_id, stable_java_node_claim_id
from tmf.java_extract import JAVA_DEGRADE_HINT, extract_java_methods, java_node_id, java_status
from tmf.retrieve import retrieve_path, reverse_callers
from tmf.store import Store
from tmf.warm import warm_repo
from tests.test_java_inherit import init_repo


@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaCallEdgeTests(unittest.TestCase):
    def test_lambda_bodies_are_not_calls_of_enclosing_method(self):
        source = '''class Service {
  void run() {
    direct();
    Runnable expression = () -> deferred();
    Runnable block = () -> { deferred(); Runnable nested = () -> nestedDeferred(); };
  }
  void direct() {} void deferred() {} void nestedDeferred() {}
}\n'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Service.java": source}); warm_repo(repo)
            graph = Store(repo).get_claim(stable_java_node_claim_id("Service.java", "Service.run", "method")).body["graph"]
            target_ids = {item["target_id"] for item in graph["callees"]}
            self.assertEqual({stable_java_node_claim_id("Service.java", "Service.direct", "method")}, target_ids)
            unresolved = {(item["expr"], item["reason"]) for item in graph["unresolved_calls"]}
            self.assertIn(("() -> deferred()", "java_lambda_deferred_context_not_modeled"), unresolved)
            self.assertTrue(any(expr.startswith("() -> {") and reason == "java_lambda_deferred_context_not_modeled" for expr, reason in unresolved))

    def test_method_references_are_evidence_not_runtime_calls(self):
        source = '''import java.util.function.*;
class Service {
  static String stat(String s) { return s; }
  String bound() { return ""; }
  String overloaded() { return ""; } String overloaded(String s) { return s; }
  void run(Service value) {
    Function<String,String> a = Service::stat;
    Supplier<String> b = value::bound;
    Function<Service,String> c = Service::bound;
    Supplier<String> ambiguous = value::overloaded;
    Supplier<Long> external = System::currentTimeMillis;
  }
}\n'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Service.java": source}); warm_repo(repo)
            graph = Store(repo).get_claim(stable_java_node_claim_id("Service.java", "Service.run", "method")).body["graph"]
            self.assertEqual([], graph["callees"])
            refs = {item["expr"] for item in graph["unresolved_calls"] if item["reason"] == "java_method_reference_relationship_not_modeled"}
            self.assertEqual({"Service::stat", "value::bound", "Service::bound", "value::overloaded", "System::currentTimeMillis"}, refs)

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

    def test_typed_receiver_overload_and_parent_method_resolution_boundaries(self):
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
            util_f_id = stable_java_node_claim_id("Service.java", "Util.f", "method")
            base_inherited_id = stable_java_node_claim_id("Service.java", "Base.inherited", "method")
            self.assertIn((util_f_id, "java_project_typed_receiver_project_same_package"), {(c["target_id"], c["resolution"]) for c in graph["callees"]})
            overloaded_int = next(method for method in extract_java_methods("Service.java", source) if method.identity_key == "Service.overloaded(int)")
            self.assertIn(java_node_id(overloaded_int), {item["target_id"] for item in graph["callees"]})
            self.assertIn((base_inherited_id, "java_direct_parent_method"), {(c["target_id"], c["resolution"]) for c in graph["callees"]})

    def test_imported_parameter_and_local_variable_receiver_calls_resolve(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "lib/src/main/java/pkg/Worker.java": "package pkg; public class Worker { public void work() {} }\n",
                "app/src/main/java/app/App.java": "package app; import pkg.Worker; class App { void run(Worker parameter) { parameter.work(); Worker local = parameter; local.work(); unknown.work(); } }\n",
            })
            warm_repo(repo)
            store = Store(repo)
            run_id = stable_java_node_claim_id("app/src/main/java/app/App.java", "App.run", "method")
            work_id = stable_java_node_claim_id("lib/src/main/java/pkg/Worker.java", "Worker.work", "method")
            graph = store.get_claim(run_id).body["graph"]
            targets = {item["target_id"] for item in graph["callees"]}
            self.assertIn(work_id, targets)
            self.assertIn(("unknown.work", "java_variable_or_unknown_receiver"), {(u["expr"], u["reason"]) for u in graph["unresolved_calls"]})

    def test_field_receiver_call_resolves_from_field_declared_type(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "pkg/Worker.java": "package pkg; public class Worker { public void work() {} }\n",
                "app/App.java": "package app; import pkg.Worker; class App { Worker worker; void run() { worker.work(); this.worker.work(); } }\n",
            })
            warm_repo(repo)
            store = Store(repo)
            run_id = stable_java_node_claim_id("app/App.java", "App.run", "method")
            work_id = stable_java_node_claim_id("pkg/Worker.java", "Worker.work", "method")
            graph = store.get_claim(run_id).body["graph"]
            self.assertEqual(2, len([item for item in graph["callees"] if item["target_id"] == work_id]))

    def test_direct_parent_and_super_calls_resolve_without_runtime_dispatch_guessing(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "base/Base.java": "package base; public class Base { public void inherited() {} public void onlyBase() {} }\n",
                "app/Child.java": "package app; import base.Base; class Child extends Base { void run() { inherited(); super.onlyBase(); } void inherited() {} }\n",
            })
            warm_repo(repo)
            store = Store(repo)
            run_id = stable_java_node_claim_id("app/Child.java", "Child.run", "method")
            inherited_id = stable_java_node_claim_id("app/Child.java", "Child.inherited", "method")
            base_only_id = stable_java_node_claim_id("base/Base.java", "Base.onlyBase", "method")
            graph = store.get_claim(run_id).body["graph"]
            targets = {(item["target_id"], item["resolution"]) for item in graph["callees"]}
            self.assertIn((inherited_id, "java_same_class_method"), targets)
            self.assertIn((base_only_id, "java_super_method"), targets)

    def test_transitive_cross_file_parent_method_resolution(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "root/Root.java": "package root; public class Root { public void rootOnly() {} }\n",
                "mid/Mid.java": "package mid; import root.Root; public class Mid extends Root {}\n",
                "app/Leaf.java": "package app; import mid.Mid; class Leaf extends Mid { void run() { rootOnly(); super.rootOnly(); } }\n",
            })
            warm_repo(repo)
            store = Store(repo)
            run_id = stable_java_node_claim_id("app/Leaf.java", "Leaf.run", "method")
            root_id = stable_java_node_claim_id("root/Root.java", "Root.rootOnly", "method")
            targets = {(item["target_id"], item["resolution"]) for item in store.get_claim(run_id).body["graph"]["callees"]}
            self.assertIn((root_id, "java_direct_parent_method"), targets)
            self.assertIn((root_id, "java_super_method"), targets)

    def test_transitive_cross_file_inherited_field_reads_and_writes(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "root/Root.java": "package root; public class Root { protected int count; }\n",
                "mid/Mid.java": "package mid; import root.Root; public class Mid extends Root {}\n",
                "app/Leaf.java": "package app; import mid.Mid; class Leaf extends Mid { void run() { int current = count; count = current + 1; } }\n",
            })
            warm_repo(repo)
            store = Store(repo)
            run_id = stable_java_node_claim_id("app/Leaf.java", "Leaf.run", "method")
            count_id = stable_java_node_claim_id("root/Root.java", "Root.count", "field")
            graph = store.get_claim(run_id).body["graph"]
            reads = {(item["target_id"], item["resolution"]) for item in graph["reads"]}
            writes = {(item["target_id"], item["resolution"]) for item in graph["writes"]}
            self.assertIn((count_id, "java_inherited_field"), reads)
            self.assertIn((count_id, "java_inherited_field"), writes)

    def test_overloaded_methods_have_distinct_signature_identity_and_exact_literal_resolution(self):
        source = """class Service {
  void run() { overloaded(1); overloaded("x"); }
  void overloaded(int value) {}
  void overloaded(String value) {}
}
"""
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Service.java": source})
            methods = extract_java_methods("Service.java", source)
            overloads = [method for method in methods if method.qualname == "Service.overloaded"]
            self.assertEqual({method.identity_key for method in overloads}, {"Service.overloaded(int)", "Service.overloaded(String)"})
            self.assertEqual(2, len({java_node_id(method) for method in overloads}))
            warm_repo(repo)
            graph = Store(repo).get_claim(stable_java_node_claim_id("Service.java", "Service.run", "method")).body["graph"]
            targets = {item["target_id"] for item in graph["callees"]}
            self.assertEqual(targets, {java_node_id(method) for method in overloads})
            self.assertNotIn("overloaded", {item["expr"] for item in graph["unresolved_calls"]})

    def test_overload_unknown_argument_remains_unresolved(self):
        source = """class Service {
  void run() { overloaded(value()); }
  Object value() { return null; }
  void overloaded(int value) {}
  void overloaded(String value) {}
}
"""
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Service.java": source})
            warm_repo(repo)
            graph = Store(repo).get_claim(stable_java_node_claim_id("Service.java", "Service.run", "method")).body["graph"]
            self.assertIn(("overloaded", "java_overloaded_or_ambiguous_method"), {(item["expr"], item["reason"]) for item in graph["unresolved_calls"]})

    def test_cross_file_typed_receiver_exact_overload_resolution(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "lib/Worker.java": "package lib; public class Worker { public void accept(int value) {} public void accept(String value) {} }\n",
                "app/App.java": "package app; import lib.Worker; class App { void run(Worker worker, String text) { worker.accept(text); } }\n",
            })
            worker_source = (repo / "lib/Worker.java").read_text()
            expected = next(method for method in extract_java_methods("lib/Worker.java", worker_source) if method.identity_key == "Worker.accept(String)")
            warm_repo(repo)
            graph = Store(repo).get_claim(stable_java_node_claim_id("app/App.java", "App.run", "method")).body["graph"]
            self.assertIn(java_node_id(expected), {item["target_id"] for item in graph["callees"]})

    def test_non_overloaded_method_keeps_legacy_identity(self):
        method = next(method for method in extract_java_methods("Service.java", "class Service { void run() {} }") if method.qualname == "Service.run")
        self.assertEqual(method.identity_key, "Service.run")
        self.assertEqual(java_node_id(method), stable_java_node_claim_id("Service.java", "Service.run", "method"))

    def test_overload_ranks_exact_widening_and_boxing_conservatively(self):
        source = '''class Service {
  void run(Integer boxed) { pick(1); widen(1); unbox(boxed); }
  void pick(int x) {} void pick(long x) {} void pick(Integer x) {}
  void widen(long x) {} void widen(Integer x) {}
  void unbox(int x) {} void unbox(long x) {}
}\n'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Service.java": source}); warm_repo(repo)
            methods = extract_java_methods("Service.java", source)
            graph = Store(repo).get_claim(stable_java_node_claim_id("Service.java", "Service.run", "method")).body["graph"]
            targets = {item["target_id"] for item in graph["callees"]}
            expected = {"Service.pick(int)", "Service.widen(long)", "Service.unbox(int)"}
            self.assertEqual(expected, {m.identity_key for m in methods if java_node_id(m) in targets})

    def test_inapplicable_and_crossing_overloads_remain_unresolved(self):
        source = '''class Service {
  void run() { bad(true); crossed(1, 1); }
  void bad(int x) {} void bad(long x) {}
  void crossed(int a, long b) {} void crossed(long a, int b) {}
}\n'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Service.java": source}); warm_repo(repo)
            graph = Store(repo).get_claim(stable_java_node_claim_id("Service.java", "Service.run", "method")).body["graph"]
            self.assertEqual({"bad", "crossed"}, {u["expr"] for u in graph["unresolved_calls"]})

    def test_varargs_zero_one_many_and_fixed_phase(self):
        source = '''class Service {
  void run() { many(); many(1); many(1, 2); choose(1); }
  void many(int... xs) {} void choose(long x) {} void choose(int... xs) {}
}\n'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Service.java": source}); warm_repo(repo); store = Store(repo)
            methods = extract_java_methods("Service.java", source)
            graph = store.get_claim(stable_java_node_claim_id("Service.java", "Service.run", "method")).body["graph"]
            identities = [next(m.identity_key for m in methods if java_node_id(m) == c["target_id"]) for c in graph["callees"]]
            self.assertIn("Service.many", identities)
            self.assertIn("Service.choose(long)", identities)

    def test_exact_array_varargs_from_declared_and_new_arrays(self):
        source = '''class Service {
  void run(String[] refs, int[] nums) { refs(refs); refs(new String[1]); nums(nums); nums(new int[]{1}); pick(refs); unknown(value()); }
  Object value(){ return null; }
  void refs(String... xs) {} void nums(int... xs) {}
  void pick(Object... xs) {} void pick(String[] xs) {}
  void unknown(String... xs) {} void unknown(Integer... xs) {}
}\n'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Service.java": source}); warm_repo(repo); store = Store(repo)
            methods = extract_java_methods("Service.java", source)
            graph = store.get_claim(stable_java_node_claim_id("Service.java", "Service.run", "method")).body["graph"]
            identities = [next(m.identity_key for m in methods if java_node_id(m) == c["target_id"]) for c in graph["callees"]]
            self.assertEqual(2, identities.count("Service.refs"))
            self.assertEqual(2, identities.count("Service.nums"))
            self.assertIn("Service.pick(String[])", identities)
            self.assertIn("unknown", {u["expr"] for u in graph["unresolved_calls"]})


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaGenericMethodCallTests(unittest.TestCase):
    def test_direct_type_variable_and_simple_source_bound(self):
        source = '''class Root {} class Leaf extends Root {} class Other {}
class Service {
  void run(Leaf leaf) { id(leaf); bounded(leaf); }
  <T> T id(T value) { return value; }
  <T extends Root> T bounded(T value) { return value; }
}'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Service.java": source}); warm_repo(repo); store = Store(repo)
            methods = extract_java_methods("Service.java", source)
            run = next(m for m in methods if m.qualname == "Service.run")
            targets = {c["target_id"] for c in store.get_claim(java_node_id(run)).body["graph"]["callees"]}
            self.assertTrue({java_node_id(m) for m in methods if m.qualname in {"Service.id", "Service.bounded"}} <= targets)

    def test_non_generic_specific_overload_wins(self):
        source = '''class Service {
  void run(String value) { choose(value); }
  <T> T choose(T value) { return value; }
  String choose(String value) { return value; }
}'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Service.java": source}); warm_repo(repo); store = Store(repo)
            methods = extract_java_methods("Service.java", source)
            run = next(m for m in methods if m.qualname == "Service.run")
            target_ids = {c["target_id"] for c in store.get_claim(java_node_id(run)).body["graph"]["callees"]}
            expected = next(m for m in methods if m.identity_key == "Service.choose(String)")
            self.assertEqual({java_node_id(expected)}, target_ids)

    def test_conflict_unknown_bad_bound_and_nested_shape_stay_unresolved(self):
        source = '''class Root {} class Leaf extends Root {} class Other {}
class Service {
  void run(Leaf leaf, Other other) { same(leaf, other); bounded(other); nested(leaf); same(unknown(), leaf); }
  Object unknown() { return null; }
  <T> T same(T a, T b) { return a; }
  <T extends Root> T bounded(T value) { return value; }
  <T> void nested(java.util.List<T> value) {}
}'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Service.java": source}); warm_repo(repo); store = Store(repo)
            run = next(m for m in extract_java_methods("Service.java", source) if m.qualname == "Service.run")
            graph = store.get_claim(java_node_id(run)).body["graph"]
            unresolved = {(u["expr"], u["reason"]) for u in graph["unresolved_calls"]}
            self.assertIn(("same", "java_overloaded_or_ambiguous_method"), unresolved)
            self.assertIn(("bounded", "java_overloaded_or_ambiguous_method"), unresolved)
            self.assertIn(("nested", "java_overloaded_or_ambiguous_method"), unresolved)

@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaConstructorCallEdgeTests(unittest.TestCase):
    def test_anonymous_class_keeps_explicit_base_constructor_but_defers_body_calls(self):
        source = '''class Helper { Helper() {} void body() {} void init() {} }
class Base { Base(int x) {} }
class App { void make() { new Base(1) { { new Helper().init(); } void run() { new Helper().body(); } }; } }\n'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Types.java": source}); warm_repo(repo); store = Store(repo)
            methods = extract_java_methods("Types.java", source)
            make = next(m for m in methods if m.qualname == "App.make")
            base = next(m for m in methods if m.identity_key == "Base.Base")
            graph = store.get_claim(java_node_id(make)).body["graph"]
            self.assertEqual({java_node_id(base)}, {c["target_id"] for c in graph["callees"]})
            self.assertEqual(
                {"java_anonymous_class_body_deferred_context_not_modeled"},
                {u["reason"] for u in graph["unresolved_calls"]},
            )

    def test_interface_generic_external_and_nested_anonymous_bodies_are_conservative_and_stable(self):
        source = '''import a.*; import b.*;
interface Task { void run(); }
class Box<T> { Box(T value) {} }
class App { void make() {
  new Task() { public void run() { hidden(); } };
  new Box<String>("x") { { hidden(); } };
  new missing.External(1) { void run() { hidden(); } };
  new Clash() { void run() { hidden(); } };
  new Task() { public void run() { new Task() { public void run() { hidden(); } }; } };
} void hidden() {} }\n'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "Types.java": source,
                "a/Clash.java": "package a; public class Clash {}\n",
                "b/Clash.java": "package b; public class Clash {}\n",
            }); warm_repo(repo); store = Store(repo)
            make = next(m for m in extract_java_methods("Types.java", source) if m.qualname == "App.make")
            claim_id = java_node_id(make)
            first = store.get_claim(claim_id).body["graph"]
            warm_repo(repo)
            second = Store(repo).get_claim(claim_id).body["graph"]
            self.assertEqual(first, second)
            self.assertEqual([], first["callees"])
            reasons = {u["reason"] for u in first["unresolved_calls"]}
            self.assertIn("java_anonymous_class_body_deferred_context_not_modeled", reasons)
            self.assertTrue(any(u["expr"] == "new Task" for u in first["unresolved_calls"]))
            self.assertTrue(any(u["expr"] == "new Box<String>" for u in first["unresolved_calls"]))
            self.assertTrue(any(u["expr"] == "new missing.External" for u in first["unresolved_calls"]))
            self.assertTrue(any(u["expr"] == "new Clash" for u in first["unresolved_calls"]))

    def test_constructor_exact_array_varargs(self):
        source = '''class Item { Item(String... xs) {} }
class App { App(String[] xs){ new Item(xs); } }\n'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"App.java": source}); warm_repo(repo); store = Store(repo)
            methods = extract_java_methods("App.java", source)
            caller = next(m for m in methods if m.qualname == "App.App")
            expected = next(m for m in methods if m.qualname == "Item.Item")
            self.assertEqual({java_node_id(expected)}, {c["target_id"] for c in store.get_claim(java_node_id(caller)).body["graph"]["callees"]})

    def test_constructor_varargs_for_new_this_and_super(self):
        source = '''class Base { Base(int... xs) {} }
class Item { Item(int... xs) {} }
class Child extends Base { Child(){ this(1, 2); } Child(int... xs){ super(1, 2); new Item(); } }\n'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Types.java": source}); warm_repo(repo); store = Store(repo)
            methods = extract_java_methods("Types.java", source)
            targets = set()
            for caller in [m for m in methods if m.qualname.startswith("Child.Child")]:
                targets |= {c["target_id"] for c in store.get_claim(java_node_id(caller)).body["graph"]["callees"]}
            expected = {java_node_id(m) for m in methods if m.identity_key in {"Child.Child(int[])", "Base.Base(int[])", "Item.Item(int[])"}}
            self.assertEqual(expected, targets)

    def test_constructor_overloads_rank_widening_for_new_this_and_super(self):
        source = '''class Base { Base(long x) {} Base(Integer x) {} }
class Item { Item(long x) {} Item(Integer x) {} }
class Child extends Base { Child(){ this(1); } Child(long x){ super(1); new Item(1); } Child(Integer x){ super(x); } }\n'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Types.java": source}); warm_repo(repo); store = Store(repo)
            methods = extract_java_methods("Types.java", source)
            child0 = next(m for m in methods if m.identity_key == "Child.Child()")
            child_long = next(m for m in methods if m.identity_key == "Child.Child(long)")
            base_long = next(m for m in methods if m.identity_key == "Base.Base(long)")
            item_long = next(m for m in methods if m.identity_key == "Item.Item(long)")
            self.assertIn(java_node_id(child_long), {c["target_id"] for c in store.get_claim(java_node_id(child0)).body["graph"]["callees"]})
            targets = {c["target_id"] for c in store.get_claim(java_node_id(child_long)).body["graph"]["callees"]}
            self.assertEqual({java_node_id(base_long), java_node_id(item_long)}, targets)

    def test_overloaded_new_exact_and_unknown_are_conservative(self):
        source = '''class Item { Item(int x) {} Item(String x) {} }
class App { void known() { new Item(1); new Item("x"); } void unknown() { new Item(value()); } Object value(){return null;} }\n'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"App.java": source}); warm_repo(repo); store = Store(repo)
            constructors = [m for m in extract_java_methods("App.java", source) if m.node_kind == "constructor"]
            self.assertEqual({m.identity_key for m in constructors}, {"Item.Item(int)", "Item.Item(String)"})
            known = store.get_claim(stable_java_node_claim_id("App.java", "App.known", "method")).body["graph"]
            self.assertEqual({c["target_id"] for c in known["callees"]}, {java_node_id(c) for c in constructors})
            unknown = store.get_claim(stable_java_node_claim_id("App.java", "App.unknown", "method")).body["graph"]
            self.assertIn(("new Item", "java_overloaded_or_ambiguous_constructor"), {(u["expr"], u["reason"]) for u in unknown["unresolved_calls"]})

    def test_cross_file_new_and_reverse_caller(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"lib/Item.java": "package lib; public class Item { public Item(int x) {} }\n", "app/App.java": "package app; import lib.Item; class App { void make(){ new Item(1); } }\n"})
            warm_repo(repo); store = Store(repo)
            caller = stable_java_node_claim_id("app/App.java", "App.make", "method")
            callee = stable_java_node_claim_id("lib/Item.java", "Item.Item", "constructor")
            graph = store.get_claim(caller).body["graph"]
            self.assertIn((callee, "java_project_constructor_project_explicit_import"), {(c["target_id"], c["resolution"]) for c in graph["callees"]})
            self.assertEqual(reverse_callers(repo, callee)["callers"][0]["caller_id"], caller)

    def test_this_and_super_constructor_delegation(self):
        source = '''class Base { Base(int x) {} }
class Child extends Base { Child(){ this(1); } Child(int x){ super(x); } }\n'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Types.java": source}); warm_repo(repo); store = Store(repo)
            constructors = extract_java_methods("Types.java", source)
            child0 = next(c for c in constructors if c.identity_key == "Child.Child()")
            child1 = next(c for c in constructors if c.identity_key == "Child.Child(int)")
            base = next(c for c in constructors if c.qualname == "Base.Base")
            self.assertIn((java_node_id(child1), "java_this_constructor"), {(c["target_id"], c["resolution"]) for c in store.get_claim(java_node_id(child0)).body["graph"]["callees"]})
            self.assertIn((java_node_id(base), "java_super_constructor"), {(c["target_id"], c["resolution"]) for c in store.get_claim(java_node_id(child1)).body["graph"]["callees"]})

    def test_non_overloaded_constructor_keeps_deterministic_legacy_shape(self):
        constructor = next(m for m in extract_java_methods("Only.java", "class Only { Only(int x) {} }") if m.node_kind == "constructor")
        self.assertEqual(constructor.identity_key, "Only.Only")
        self.assertEqual(java_node_id(constructor), stable_java_node_claim_id("Only.java", "Only.Only", "constructor"))
