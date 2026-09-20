from __future__ import annotations

import unittest
from dataclasses import asdict
from unittest.mock import patch

from bench.agent_ab.same_version_chain_v1.m10_successor_fixture import FILE, mutate_dispatcher, source_base
from bench.agent_ab.same_version_chain_v1.m10_successor_scoring import (
    CURRENT_METHOD,
    OBSOLETE_METHOD,
    score_placement_ast,
)


class M10SuccessorScoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.reference = mutate_dispatcher((source_base() / FILE).read_text(encoding="utf-8"))
        cls.target = "      prepared.subscriber.dispatchEvent(prepared.event);"
        cls.old_target = "              dispatchQueuedSubscriber(nextEvent.event, nextSubscriber);"

    def score(self, candidate: str):
        return score_placement_ast(candidate, reference_source=self.reference)

    def at_target(self, replacement: str) -> str:
        self.assertEqual(1, self.reference.count(self.target))
        return self.reference.replace(self.target, replacement, 1)

    def correct(self) -> str:
        return self.at_target("      hook();\n" + self.target)

    def test_canonical_correct_and_full_method_signature(self) -> None:
        score = self.score(self.correct())
        self.assertTrue(score.semantic_pass)
        self.assertEqual("correct_current_boundary", score.outcome)
        self.assertEqual((CURRENT_METHOD,), score.enclosing_methods)
        self.assertEqual((), score.constraint_violations)
        self.assertIn("diagnostic_regex_wrong_inline", asdict(score))

    def test_comments_and_whitespace_do_not_change_score(self) -> None:
        replacements = (
            "      hook(); // between statements\n" + self.target,
            "      hook(); /* prepared.subscriber.dispatchEvent(null); */\n" + self.target,
            "      hook /* invocation */ ( /* no args */ );\n"
            "      prepared /* receiver */ . subscriber . dispatchEvent ( prepared /* arg */ . event );",
            "\t  hook ( ) ; \n prepared . subscriber . dispatchEvent (\n prepared . event\n ) ;",
        )
        for replacement in replacements:
            with self.subTest(replacement=replacement):
                score = self.score(self.at_target(replacement))
                self.assertTrue(score.semantic_pass, score)
                self.assertEqual((), score.constraint_violations)

    def test_qualified_existing_hook_is_accepted(self) -> None:
        for hook in ("this.hook();", "PerThreadQueuedDispatcher.this.hook();",
                     "Dispatcher.PerThreadQueuedDispatcher.this.hook();",
                     "com.google.common.eventbus.Dispatcher.PerThreadQueuedDispatcher.this.hook();"):
            with self.subTest(hook=hook):
                self.assertTrue(self.score(self.at_target("      " + hook + "\n" + self.target)).semantic_pass)

    def test_wrong_receiver_and_arguments_cannot_impersonate_hook(self) -> None:
        for hook, violation in (
            ("prepared.hook();", "hook_must_target_existing_lexical_instance"),
            ("PerThreadQueuedDispatcher.hook();", "hook_must_target_existing_lexical_instance"),
            ("super.hook();", "hook_must_target_existing_lexical_instance"),
            ("((PerThreadQueuedDispatcher) null).hook();", "hook_must_target_existing_lexical_instance"),
            ("hook(null);", "hook_must_have_no_arguments"),
        ):
            with self.subTest(hook=hook):
                score = self.score(self.at_target("      " + hook + "\n" + self.target))
                self.assertFalse(score.semantic_pass)
                self.assertFalse(score.correct_current_boundary)
                self.assertIn(violation, score.constraint_violations)

    def test_hook_after_target_is_exhaustively_other(self) -> None:
        score = self.score(self.at_target(self.target + "\n      hook();"))
        self.assertFalse(score.semantic_pass)
        self.assertFalse(score.obsolete_queue_loop)
        self.assertTrue(score.other_incorrect_placement)
        self.assertEqual("other_incorrect_placement", score.outcome)

    def test_obsolete_site_is_specific_queue_loop(self) -> None:
        score = self.score(self.reference.replace(self.old_target, "              hook();\n" + self.old_target, 1))
        self.assertFalse(score.semantic_pass)
        self.assertTrue(score.obsolete_queue_loop)
        self.assertFalse(score.other_incorrect_placement)
        self.assertEqual("obsolete_queue_loop", score.outcome)
        self.assertEqual((OBSOLETE_METHOD,), score.enclosing_methods)

    def test_same_dispatch_method_outside_queue_loop_is_not_obsolete(self) -> None:
        anchor = "      queueForThread.offer(new Event(event, subscribers));"
        score = self.score(self.reference.replace(anchor, "      hook();\n" + anchor, 1))
        self.assertFalse(score.obsolete_queue_loop)
        self.assertTrue(score.other_incorrect_placement)
        self.assertEqual("other_incorrect_placement", score.outcome)

    def test_other_dispatchers_are_not_obsolete(self) -> None:
        for anchor in ("        e.subscriber.dispatchEvent(e.event);", "        subscribers.next().dispatchEvent(event);"):
            with self.subTest(anchor=anchor):
                score = self.score(self.reference.replace(anchor, "        hook();\n" + anchor, 1))
                self.assertFalse(score.obsolete_queue_loop)
                self.assertTrue(score.other_incorrect_placement)
                self.assertFalse(score.correct_current_boundary)
                self.assertEqual("other_incorrect_placement", score.outcome)

    def test_other_helper_is_other(self) -> None:
        anchor = "      dispatchPreparedSubscriber(new EventWithPreparedSubscriber(event, subscriber));"
        score = self.score(self.reference.replace(anchor, "      hook();\n" + anchor, 1))
        self.assertEqual("other_incorrect_placement", score.outcome)
        self.assertTrue(score.other_incorrect_placement)

    def test_both_real_sites_remain_diagnostic_but_never_pass(self) -> None:
        source = self.correct().replace(self.old_target, "              hook();\n" + self.old_target, 1)
        score = self.score(source)
        self.assertEqual(2, score.hook_call_count)
        self.assertTrue(score.correct_current_boundary)
        self.assertTrue(score.obsolete_queue_loop)
        self.assertFalse(score.semantic_pass)
        self.assertEqual("multiple_hooks", score.outcome)

    def test_nested_or_deferred_target_cannot_be_current_handoff(self) -> None:
        replacements = (
            "      hook();\n      Runnable deferred = () -> prepared.subscriber.dispatchEvent(prepared.event);",
            "      Runnable deferred = () -> { hook(); prepared.subscriber.dispatchEvent(prepared.event); };",
            "      if (false) { hook(); prepared.subscriber.dispatchEvent(prepared.event); }",
            "      if (false) { hook(); }\n" + self.target,
            "      if (true) { hook(); prepared.subscriber.dispatchEvent(prepared.event); }",
            "      hook();\n      if (prepared.event != null) { prepared.subscriber.dispatchEvent(prepared.event); }",
            "      if (prepared.event == null) return;\n      hook();\n" + self.target,
        )
        for replacement in replacements:
            with self.subTest(replacement=replacement):
                score = self.score(self.at_target(replacement))
                self.assertFalse(score.semantic_pass)
                self.assertFalse(score.correct_current_boundary)
                self.assertEqual("constraint_violation", score.outcome)
                self.assertIn("program_changed_beyond_hook_insertion", score.constraint_violations)

    def test_actual_receiver_and_arguments_are_not_comment_substrings(self) -> None:
        for expression in (
            "prepared.subscriber.dispatchEvent(null /* prepared.subscriber.dispatchEvent(prepared.event) */);",
            "prepared.subscriber.dispatchEvent(\"prepared.subscriber.dispatchEvent(prepared.event)\");",
            "prepared.other.dispatchEvent(prepared.event); // prepared.subscriber.dispatchEvent(prepared.event)",
            "prepared.subscriber.dispatchEvent(prepared.subscriber);",
        ):
            with self.subTest(expression=expression):
                score = self.score(self.at_target("      hook();\n      " + expression))
                self.assertFalse(score.correct_current_boundary)
                self.assertFalse(score.semantic_pass)
                self.assertIn("program_changed_beyond_hook_insertion", score.constraint_violations)

    def test_unused_same_named_overload_cannot_pass(self) -> None:
        anchor = "    private void hook() {}"
        overload = (
            "    private void dispatchPreparedSubscriber(EventWithPreparedSubscriber prepared, boolean unused) {\n"
            "      hook();\n      prepared.subscriber.dispatchEvent(prepared.event);\n    }\n\n"
        )
        score = self.score(self.reference.replace(anchor, overload + anchor, 1))
        self.assertFalse(score.semantic_pass)
        self.assertFalse(score.correct_current_boundary)
        self.assertTrue(score.other_incorrect_placement)
        self.assertIn("(EventWithPreparedSubscriber,boolean):void", score.enclosing_methods[0])

    def test_same_named_method_in_other_class_cannot_pass(self) -> None:
        anchor = "  private static final class ImmediateDispatcher extends Dispatcher {"
        extra = (
            "\n    private void dispatchPreparedSubscriber(Object prepared) {\n"
            "      hook();\n      prepared.subscriber.dispatchEvent(prepared.event);\n    }\n"
        )
        score = self.score(self.reference.replace(anchor, anchor + extra, 1))
        self.assertFalse(score.semantic_pass)
        self.assertFalse(score.correct_current_boundary)
        self.assertFalse(score.obsolete_queue_loop)

    def test_extra_program_edits_invalidate_even_correct_local_position(self) -> None:
        candidates = (
            self.correct().replace("dispatching.set(true);", "dispatching.set(false);", 1),
            self.correct().replace("private void hook() {}", "private void hook() { throw new RuntimeException(); }", 1),
            self.correct().replace("private void hook() {}", "private void hook() {}\n    private void hook(Object value) {}", 1),
            self.correct().replace("      checkNotNull(event);", "", 1),
            self.correct().replace("abstract class Dispatcher", "abstract class RenamedDispatcher", 1),
            self.correct().replace("package com.google.common.eventbus;", "package other;", 1),
        )
        for candidate in candidates:
            with self.subTest(candidate=candidate[-180:]):
                score = self.score(candidate)
                self.assertFalse(score.semantic_pass)
                self.assertFalse(score.correct_current_boundary)
                self.assertEqual("constraint_violation", score.outcome)
                self.assertIn("program_changed_beyond_hook_insertion", score.constraint_violations)

    def test_missing_call_and_comments_only_are_missing_not_syntax_errors(self) -> None:
        for candidate in (self.reference, self.at_target("      // hook();\n" + self.target)):
            with self.subTest(candidate=candidate[-80:]):
                score = self.score(candidate)
                self.assertTrue(score.parse_ok)
                self.assertEqual(0, score.hook_call_count)
                self.assertEqual("missing_hook", score.outcome)
                self.assertFalse(score.semantic_pass)

    def test_string_hook_is_not_a_call_and_extra_statement_is_a_constraint_failure(self) -> None:
        score = self.score(self.at_target("      String ignored = \"hook();\";\n" + self.target))
        self.assertEqual(0, score.hook_call_count)
        self.assertEqual("constraint_violation", score.outcome)

    def test_syntax_errors_are_separate_from_semantic_placement(self) -> None:
        score = self.score(self.correct()[:-4])
        self.assertFalse(score.parse_ok)
        self.assertTrue(score.syntax_error)
        self.assertEqual("parse_error", score.outcome)
        self.assertFalse(score.semantic_pass)

    def test_java_prelexing_escape_cannot_hide_live_code_inside_comment(self) -> None:
        source = self.at_target(
            r"      hook(); // \u000a if (prepared.event != null) return;" + "\n" + self.target
        )
        score = self.score(source)
        self.assertTrue(score.parse_ok)  # tree-sitter alone sees a harmless comment
        self.assertFalse(score.semantic_pass)
        self.assertFalse(score.correct_current_boundary)
        self.assertIn("java_unicode_escape_not_supported", score.constraint_violations)

    def test_unavailable_parser_fails_closed_without_claiming_a_java_syntax_error(self) -> None:
        with patch(
            "bench.agent_ab.same_version_chain_v1.m10_successor_scoring._language_and_parser",
            side_effect=ImportError("unavailable"),
        ):
            score = self.score(self.correct())
        self.assertFalse(score.parse_ok)
        self.assertFalse(score.syntax_error)
        self.assertFalse(score.semantic_pass)
        self.assertEqual("parser_unavailable", score.outcome)

    def test_reference_is_required_and_cannot_be_candidate_with_hook(self) -> None:
        with self.assertRaises(TypeError):
            score_placement_ast(self.correct())
        score = score_placement_ast(self.correct(), reference_source=self.correct())
        self.assertEqual("invalid_reference", score.outcome)
        self.assertIn("reference_already_contains_hook_call", score.constraint_violations)
        self.assertFalse(score.semantic_pass)

    def test_reference_rejects_ambiguous_signature_and_wrong_semantic_target(self) -> None:
        references = (
            self.reference.replace("EventWithPreparedSubscriber prepared)", "Object prepared)", 1),
            self.reference.replace("prepared.subscriber.dispatchEvent(prepared.event)", "prepared.subscriber.dispatchEvent(null)", 1),
            self.reference.replace("private void hook() {}", "private void hook() { throw new RuntimeException(); }", 1),
            self.reference.replace("private void hook() {}", "private void hook() {}\n    private void hook() {}", 1),
        )
        for reference in references:
            with self.subTest(reference=reference[-80:]):
                score = score_placement_ast(self.correct(), reference_source=reference)
                self.assertEqual("invalid_reference", score.outcome)
                self.assertFalse(score.semantic_pass)


if __name__ == "__main__":
    unittest.main()
