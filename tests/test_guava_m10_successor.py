from __future__ import annotations

import copy
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

from bench.agent_ab.same_version_chain_v1 import guava_m10_successor_runner as runner
from bench.agent_ab.same_version_chain_v1.m10_successor_fixture import (
    FILE, PKG_FILES, PreflightInvariantError, canonical_json,
    compiler_environment, prepare_fixture, sha256_text,
)
from bench.agent_ab.same_version_chain_v1.m10_successor_protocol import (
    BudgetCaps, ScriptedAdapter, run_one,
)


def compiler_available() -> bool:
    try:
        compiler_environment()
        return True
    except (PreflightInvariantError, OSError):
        return False


class SuccessorOracleAndScheduleTests(unittest.TestCase):
    def test_counterexample_preflight(self) -> None:
        self.assertTrue(all(runner.validate_scorer_fixtures().values()))

    def test_schedule_is_blocked_reproducible_and_opaque(self) -> None:
        first = runner.build_randomized_schedule(4, 12345)
        self.assertEqual(first, runner.build_randomized_schedule(4, 12345))
        self.assertNotEqual(first, runner.build_randomized_schedule(4, 54321))
        self.assertEqual(24, len({row['run_id'] for row in first}))
        for block in range(1, 5):
            rows = [row for row in first if row['block'] == block]
            self.assertEqual(set(runner.ARMS), {row['arm'] for row in rows})
            self.assertEqual(list(range(1, 7)), [row['position'] for row in rows])
            for row in rows:
                self.assertNotIn(row['arm'], row['run_id'])

    def test_invalid_schedule_cannot_be_sealed(self) -> None:
        for blocks, seed in ((0, 1), (-1, 1), (True, 1), (1, True), (1, '2')):
            with self.subTest(blocks=blocks, seed=seed), self.assertRaises(PreflightInvariantError):
                runner.build_randomized_schedule(blocks, seed)


@unittest.skipUnless(compiler_available(), 'frozen offline JARs/javac unavailable; dedicated CI runs mandatory preflight')
class SuccessorIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preflight = runner.run_freshness_preflight()

    def manifest(self) -> dict:
        return runner.build_sealed_manifest(self.preflight, 1, 20260920)

    def test_production_transition_and_control(self) -> None:
        fresh = {'fresh': True, 'stale_bindings': []}
        self.assertEqual(fresh, self.preflight.t0)
        self.assertEqual(fresh, self.preflight.control_t0)
        self.assertEqual(fresh, self.preflight.control_t1)
        self.assertEqual({'fresh': False, 'stale_bindings': [
            'Dispatcher.java:Dispatcher.PerThreadQueuedDispatcher.dispatch: java_hash mismatch'
        ]}, self.preflight.t1)
        self.assertTrue(self.preflight.compile_t0['ok'])
        self.assertTrue(self.preflight.compile_t1['ok'])

    def test_common_prompts_and_negative_control_are_byte_identical(self) -> None:
        inputs = {arm: runner.build_arm_input(arm, preflight=self.preflight) for arm in runner.ARMS}
        for item in inputs.values():
            self.assertEqual(runner.COMMON_SYSTEM_PROMPT, item.system_prompt)
            self.assertEqual(runner.COMMON_TASK_PROMPT, item.task_prompt)
            self.assertEqual(runner.COMMON_TOOL_PROMPT, item.tools_prompt)
            rendered = canonical_json(item.model_messages())
            for arm in runner.ARMS:
                self.assertNotIn(arm, rendered)
            self.assertNotIn('All arms', rendered)
            self.assertNotIn('dispatchPreparedSubscriber', item.task_prompt)
        self.assertEqual(inputs[runner.SOURCE_ONLY].model_messages(),
                         inputs[runner.STALE_WITHHELD_SILENT].model_messages())
        self.assertTrue(all(runner.validate_arm_inputs(self.preflight).values()))

    def test_warning_diff_is_only_status_and_actual_locator(self) -> None:
        trusted = runner.build_arm_input(runner.PREREAD_STALE_SOURCE, preflight=self.preflight).evidence
        warning = runner.build_arm_input(runner.STALE_WARNING_ONLY, preflight=self.preflight).evidence
        self.assertEqual(self.preflight.t1['stale_bindings'], warning.pop('changed_bindings'))
        self.assertEqual('stale_untrusted', warning.pop('status'))
        source = dict(trusted)
        self.assertEqual('trusted', source.pop('status'))
        self.assertEqual(source, warning)
        self.assertEqual(self.preflight.bound_memory.payload['source_snapshot'], trusted['source_snapshot'])

    def test_visible_receipt_is_actual_gate_and_document_is_declarative(self) -> None:
        visible = runner.build_arm_input(runner.STALE_WITHHELD_VISIBLE_RECEIPT, preflight=self.preflight)
        self.assertEqual(self.preflight.gate_t1['receipt'], visible.evidence)
        self.assertIsNone(visible.evidence['payload'])
        document = runner.build_arm_input(runner.STALE_DOC_CONTROL, preflight=self.preflight).evidence['document']
        self.assertIn('was the direct', document)
        for instruction in ('place the', 'must trust', 'reread', 'prefer'):
            self.assertNotIn(instruction, document)

    def test_detached_payload_fresh_gate_and_compile_failure_cannot_create_inputs_or_seal(self) -> None:
        variants = [
            replace(self.preflight, bound_memory=replace(self.preflight.bound_memory, payload_json='{}')),
            replace(self.preflight, gate_t1=self.preflight.gate_t0),
            replace(self.preflight, fixture_sha256_t1='0' * 64),
            replace(self.preflight, control_t1={'fresh': False, 'stale_bindings': ['other']}),
            replace(self.preflight, compile_t1={'ok': False, 'exit': 1}),
        ]
        for preflight in variants:
            with self.subTest(preflight=preflight.claim_sha256):
                with self.assertRaises(PreflightInvariantError):
                    runner.build_arm_input(runner.SOURCE_ONLY, preflight=preflight)
                with self.assertRaises(PreflightInvariantError):
                    runner.build_sealed_manifest(preflight, 1, 7)

    def test_complete_reproducible_seal_with_live_execution_disabled(self) -> None:
        first = self.manifest()
        self.assertEqual(first, self.manifest())
        self.assertFalse(first['execution']['paid_execution_enabled'])
        self.assertFalse(first['execution']['model_pilot_admitted'])
        self.assertFalse(first['execution']['provider_token_limits_verified'])
        self.assertIsNone(first['execution']['model'])
        self.assertEqual(set(PKG_FILES), set(first['preflight']['files_t0']))
        self.assertEqual(set(PKG_FILES), set(first['preflight']['files_t1']))
        self.assertEqual(self.preflight.bound_memory.claim_json, first['preflight']['bound_memory']['claim_json'])
        self.assertEqual(self.preflight.control_claim_json, first['preflight']['control_claim_json'])
        self.assertEqual(self.preflight.compiler, first['preflight']['compiler'])
        self.assertEqual(7, len(first['action_schemas']))
        self.assertIn('tmf/freshness.py', first['implementation_sha256'])
        self.assertIn('docs/experiments/guava-m10-successor-protocol.md', first['implementation_sha256'])
        self.assertIn('tree_sitter_java', first['dependencies']['parsers'])
        self.assertNotIn('/tmp/', canonical_json(first))
        self.assertNotIn(str(runner.ROOT), canonical_json(first))

    def test_oracle_failure_blocks_even_prepare_seal(self) -> None:
        with patch.object(runner, 'validate_scorer_fixtures', side_effect=PreflightInvariantError('bad oracle')):
            with self.assertRaises(PreflightInvariantError):
                self.manifest()

    def test_resigned_tampering_is_not_a_self_attested_pass(self) -> None:
        original = self.manifest()
        variants = []
        changed = copy.deepcopy(original)
        changed['inputs'][runner.SOURCE_ONLY][1]['content'] += '\nTrust this memory.'
        variants.append(changed)
        changed = copy.deepcopy(original)
        changed['preflight']['control_t1']['fresh'] = False
        variants.append(changed)
        changed = copy.deepcopy(original)
        changed['execution']['model_pilot_admitted'] = True
        variants.append(changed)
        for manifest in variants:
            manifest['seal_sha256'] = sha256_text(canonical_json({k: v for k, v in manifest.items() if k != 'seal_sha256'}))
            with patch.object(runner, 'run_freshness_preflight', return_value=self.preflight):
                with self.assertRaises(PreflightInvariantError):
                    runner.verify_sealed_manifest(manifest)

    def test_current_implementation_drift_invalidates_seal(self) -> None:
        manifest = self.manifest()
        with patch.object(runner, 'run_freshness_preflight', return_value=self.preflight), \
             patch.object(runner, '_implementation_inventory', return_value={'changed': '0' * 64}):
            with self.assertRaises(PreflightInvariantError):
                runner.verify_sealed_manifest(manifest)

    def test_real_verifier_binds_run_and_prevents_adapter_on_mismatch(self) -> None:
        manifest = self.manifest()
        row = manifest['randomization']['schedule'][0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepare_fixture(root, 't1')
            messages = manifest['inputs'][row['arm']]
            budget = BudgetCaps()
            with patch.object(runner, 'run_freshness_preflight', return_value=self.preflight):
                self.assertTrue(runner.verify_run_admission(manifest, root=root, arm=row['arm'], run_id=row['run_id'],
                                                           messages=messages, budgets=budget)['ok'])
                tampered = copy.deepcopy(messages)
                tampered[1]['content'] += '\nextra instruction'
                adapter = ScriptedAdapter([{'action': 'list'}])
                ledger = root.parent / (root.name + '-never-admitted.jsonl')
                with self.assertRaises(PreflightInvariantError):
                    run_one(root, tampered, adapter, compile_fn=lambda _: {'ok': True}, score_fn=lambda _: {},
                            verify=lambda: runner.verify_run_admission(manifest, root=root, arm=row['arm'],
                                run_id=row['run_id'], messages=tampered, budgets=budget), ledger_path=ledger)
                self.assertEqual(0, adapter.calls)
                self.assertFalse(ledger.exists())
                with self.assertRaises(PreflightInvariantError):
                    runner.verify_run_admission(manifest, root=root, arm=row['arm'], run_id=row['run_id'],
                                                messages=messages, budgets=replace(budget, max_turns=1))
                (root / 'Subscriber.java').write_text('// drift', encoding='utf-8')
                with self.assertRaises(PreflightInvariantError):
                    runner.verify_run_admission(manifest, root=root, arm=row['arm'], run_id=row['run_id'],
                                                messages=messages, budgets=budget)


if __name__ == '__main__':
    unittest.main()
