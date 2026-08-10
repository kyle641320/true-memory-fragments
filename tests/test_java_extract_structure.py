from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path
import unittest


_PRESENCE_RESOLVERS = {
    "resolve_java_rest_controller_advice_declarations",
    "resolve_java_init_binder_declarations",
    "resolve_java_model_attribute_declarations",
    "resolve_java_response_status_declarations",
    "resolve_java_session_attributes_declarations",
    "resolve_java_cross_origin_declarations",
    "resolve_java_rest_controller_declarations",
    "resolve_java_controller_declarations",
    "resolve_java_service_declarations",
    "resolve_java_component_declarations",
    "resolve_java_repository_stereotype_declarations",
    "resolve_java_configuration_declarations",
    "resolve_java_bean_declarations",
    "resolve_java_primary_declarations",
    "resolve_java_lazy_declarations",
    "resolve_java_post_construct_declarations",
    "resolve_java_pre_destroy_declarations",
    "resolve_java_scope_declarations",
    "resolve_java_response_body_declarations",
}


class JavaExtractStructureTests(unittest.TestCase):
    def test_top_level_symbols_are_unique(self) -> None:
        path = Path(__file__).parents[1] / "tmf" / "java_extract.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        names = [
            node.name
            for node in tree.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
        self.assertEqual([], duplicates, "top-level definitions shadow earlier code")

    def test_presence_resolvers_use_one_structural_template(self) -> None:
        path = Path(__file__).parents[1] / "tmf" / "java_extract.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertEqual(set(), _PRESENCE_RESOLVERS - functions.keys())
        annotations = []
        reason_prefixes = []
        declaration_types = []
        unresolved_types = []
        for name in sorted(_PRESENCE_RESOLVERS):
            node = functions[name]
            self.assertEqual(1, len(node.body), f"{name} drifted from the shared resolver template")
            statement = node.body[0]
            self.assertIsInstance(statement, ast.Return)
            call = statement.value
            self.assertIsInstance(call, ast.Call)
            self.assertIsInstance(call.func, ast.Name)
            self.assertEqual("_resolve_java_presence_declarations", call.func.id)
            keywords = {keyword.arg: keyword.value for keyword in call.keywords}
            self.assertTrue(
                set(keywords).issubset({"annotation", "expected_fqn", "owner_kinds", "declaration_type", "unresolved_type", "reason_prefix", "allow_nested_method_owner"})
                and {"annotation", "expected_fqn", "owner_kinds", "declaration_type", "unresolved_type", "reason_prefix"}.issubset(keywords),
                f"{name} dispatch keyword drift",
            )
            annotation = ast.literal_eval(keywords["annotation"])
            expected_fqn = ast.literal_eval(keywords["expected_fqn"])
            self.assertTrue(expected_fqn.endswith("." + annotation), f"{name} import guard drift")
            annotations.append(annotation)
            reason_prefixes.append(ast.literal_eval(keywords["reason_prefix"]))
            declaration_types.append(ast.unparse(keywords["declaration_type"]))
            unresolved_types.append(ast.unparse(keywords["unresolved_type"]))
        for label, values in {
            "annotation": annotations,
            "reason prefix": reason_prefixes,
            "declaration type": declaration_types,
            "unresolved type": unresolved_types,
        }.items():
            duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
            self.assertEqual([], duplicates, f"duplicate presence resolver {label}: {duplicates}")


if __name__ == "__main__":
    unittest.main()
