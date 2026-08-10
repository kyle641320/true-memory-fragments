from __future__ import annotations

import unittest

from tmf.java_types import java_type_references, parse_java_type, unique_applicable_signature


class JavaTypeTests(unittest.TestCase):
    def test_primitives_arrays_varargs_and_annotations(self):
        self.assertTrue(parse_java_type("int").primitive)
        self.assertEqual(parse_java_type("java.lang.String[][]").canonical, "java.lang.String[][]")
        varargs = parse_java_type("@Nonnull String...")
        self.assertEqual((varargs.erased, varargs.varargs, varargs.canonical), ("String", True, "String"))

    def test_nested_generics_and_wildcards_preserve_references(self):
        refs = java_type_references("Map<String, List<? extends acme.Outer.Inner[]>>")
        self.assertEqual([item.erased for item in refs], ["Map", "String", "List", "acme.Outer.Inner"])
        inner = refs[-1]
        self.assertEqual((inner.simple_name, inner.array_dims, inner.wildcard), ("Inner", 1, "extends"))

    def test_generic_erasure_is_stable_for_signature_matching(self):
        self.assertEqual(parse_java_type("List<String>").canonical, "List")
        self.assertEqual(parse_java_type("List<Integer>").canonical, "List")
        self.assertEqual(parse_java_type("T[]").canonical, "T[]")

    def test_unbounded_wildcard_does_not_create_a_type_reference(self):
        refs = java_type_references("List<?>")
        self.assertEqual([item.erased for item in refs], ["List"])

    def test_conservative_invocation_conversion_ranking(self):
        self.assertEqual(unique_applicable_signature(("int",), [("long",), ("Integer",), ("int",)]), 2)
        self.assertEqual(unique_applicable_signature(("int",), [("long",), ("Integer",)]), 0)
        self.assertEqual(unique_applicable_signature(("Integer",), [("long",), ("int",)]), 1)
        self.assertIsNone(unique_applicable_signature(("boolean",), [("int",), ("long",)]))

    def test_crossing_and_equal_conversion_costs_remain_ambiguous(self):
        self.assertIsNone(unique_applicable_signature(("int", "int"), [("int", "long"), ("long", "int")]))
        self.assertIsNone(unique_applicable_signature(("int",), [("long",), ("long",)]))

    def test_source_reference_distance_makes_upcasts_applicable_and_ranked(self):
        distances = {("Leaf", "Mid"): 1, ("Leaf", "Root"): 2}
        distance = lambda source, target: distances.get((source, target))
        self.assertEqual(unique_applicable_signature(("Leaf",), [("Root",), ("Mid",)], distance), 1)
        self.assertEqual(unique_applicable_signature(("Leaf",), [("Root",), ("Leaf",)], distance), 1)
        self.assertIsNone(unique_applicable_signature(("Leaf",), [("Left",), ("Right",)], lambda *_: 1))
        self.assertIsNone(unique_applicable_signature(("Unknown",), [("Root",)], distance))

    def test_bounded_direct_method_type_variable_substitution(self):
        distance = lambda source, target: 1 if (source, target) == ("Leaf", "Root") else None
        self.assertEqual(0, unique_applicable_signature(("Leaf",), [("T",)], distance, [{"T": "Root"}]))
        self.assertIsNone(unique_applicable_signature(("Other",), [("T",)], distance, [{"T": "Root"}]))
        self.assertIsNone(unique_applicable_signature(("Leaf", "Other"), [("T", "T")], distance, [{"T": None}]))

    def test_equally_applicable_non_generic_beats_generic(self):
        self.assertEqual(1, unique_applicable_signature(("String",), [("T",), ("String",)], None,
                                                       [{"T": None}, {}]))

    def test_varargs_expansion_and_fixed_arity_phase(self):
        self.assertEqual(unique_applicable_signature((), [("int...",)]), 0)
        self.assertEqual(unique_applicable_signature(("int",), [("long...",), ("int...",)]), 1)
        self.assertEqual(unique_applicable_signature(("int", "int"), [("long...",), ("int...",)]), 1)
        self.assertEqual(unique_applicable_signature(("int",), [("long",), ("int...",)]), 0)
        self.assertIsNone(unique_applicable_signature(("boolean",), [("int...",)]))
        self.assertIsNone(unique_applicable_signature(("int",), [("int...",), ("int...",)]))
        self.assertEqual(unique_applicable_signature(("int[]",), [("int...",)]), 0)
        self.assertEqual(unique_applicable_signature(("String[]",), [("String...",)]), 0)
        self.assertEqual(unique_applicable_signature(("int[][]",), [("int[]...",)]), 0)
        self.assertIsNone(unique_applicable_signature(("long[]",), [("int...",)]))
        self.assertIsNone(unique_applicable_signature(("String[][]",), [("String...",)]))
        self.assertIsNone(unique_applicable_signature(("Leaf[]",), [("Root...",)], lambda *_: 1))
        self.assertIsNone(unique_applicable_signature(("String[]",), [("T...",)], None, [{"T": None}]))

    def test_exact_array_fixed_phase_beats_expansion_and_fixed_overload(self):
        self.assertEqual(0, unique_applicable_signature(("String[]",), [("String...",), ("Object...",)]))
        self.assertEqual(1, unique_applicable_signature(("String[]",), [("Object...",), ("String[]",)]))
        self.assertIsNone(unique_applicable_signature(("String[]",), [("String...",), ("String[]",)]))


if __name__ == "__main__":
    unittest.main()
