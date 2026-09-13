"""Transport-sized budget and actionable relation regressions for locator mode."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_readonly_locator_compat import fixture, fingerprint
from tmf.locator_server import McpService
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo


class LocatorContextBudgetTests(unittest.TestCase):
    def test_actual_response_budget_and_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            repo, state = fixture(Path(td))
            before = fingerprint(state)
            svc = McpService(repo, state, load_assist_provider=False)
            try:
                for budget in (180, 181, 220, 500, 900, 1500, 3000):
                    for question in ('helper', '找调用者\\"\n' * 200):
                        with self.subTest(budget=budget, question=question[:10]):
                            response = svc.call_tool('tmf_context', {'question': question, 'max_chars': budget})
                            text = response['content'][0]['text']
                            self.assertLessEqual(len(text), budget)
                            payload = json.loads(text)
                            self.assertEqual(payload['max_chars'], budget)
                            self.assertEqual(payload['view'], 'thin_context')
                self.assertEqual(before, fingerprint(state))
            finally:
                svc.close()

    def test_oversized_fallback_metadata_cannot_break_minimum_budget(self):
        svc = object.__new__(McpService)
        payload = {'question': 'helper', 'view': 'thin_context', 'coverage': 'partial',
                   'truncated': False, 'max_chars': 180, 'claims': [], 'relations': [],
                   'source_fallback_paths': ['nested/' * 100], 'source_fallback_count': 1}
        with patch.object(svc, '_context_payload', return_value=payload):
            result = svc.tmf_context('helper', 180)
        self.assertLessEqual(len(json.dumps(result, ensure_ascii=False, sort_keys=True)), 180)
        self.assertTrue(result['truncated'])
        self.assertEqual(result['coverage'], 'partial')
        self.assertFalse(payload['truncated'])

    def test_real_call_relation_expands_and_stale_caller_is_withheld(self):
        with tempfile.TemporaryDirectory() as td:
            repo, state = fixture(Path(td))
            source = "def helper():\n    return 1\n\ndef caller():\n    return helper()\n"
            (repo / 'a.py').write_text(source)
            for claim in derive_claims_for_path(GitRepo(repo), 'a.py'):
                (state / 'claims' / (claim.id + '.json')).write_text(json.dumps(claim.to_dict()))
            svc = McpService(repo, state, load_assist_provider=False)
            try:
                before = fingerprint(state)
                payload = svc.tmf_context('helper caller', 900)
                self.assertTrue(payload['truncated'])
                self.assertTrue(payload['relations'])
                relation = payload['relations'][0]
                expanded = svc.tmf_callers(claim_id=relation['for'])
                self.assertTrue(expanded['callers'])
                (repo / 'a.py').write_text(source.replace('return helper()', 'return 2'))
                self.assertFalse(svc.tmf_callers(claim_id=relation['for'])['callers'])
                self.assertFalse(svc.tmf_context('helper caller', 900)['relations'])
                self.assertEqual(before, fingerprint(state))
            finally:
                svc.close()

    def test_relation_pointer_survives_when_relation_details_do_not_fit(self):
        with tempfile.TemporaryDirectory() as td:
            repo, state = fixture(Path(td))
            svc = McpService(repo, state, load_assist_provider=False)
            try:
                claim = next(c for c in svc.store.iter_claims() if c.scope == 'function')
                relation = {'for': claim.id, 'kind': 'callers', 'items': [{'details': 'x' * 4000}], 'coverage': 'partial'}
                source = {'question': 'helper', 'view': 'thin_context', 'coverage': 'partial',
                          'truncated': False, 'max_chars': 700, 'claims': [],
                          'relations': [relation], 'source_fallback_paths': []}
                with patch.object(svc, '_context_payload', return_value=source):
                    first = svc.tmf_context('helper', 700)
                    self.assertEqual(first, svc.tmf_context('helper', 700))
                self.assertTrue(first['truncated'])
                self.assertLessEqual(len(json.dumps(first, ensure_ascii=False, sort_keys=True)), 700)
                pointer = first['relations'][0]
                self.assertEqual(pointer['for'], claim.id)
                self.assertEqual(pointer['expand'], 'tmf_callers')
                # The emitted continuation actually addresses a supported tool.
                self.assertIn('content', svc.call_tool(pointer['expand'], {'claim_id': pointer['for']}))
                self.assertEqual(source['relations'], [relation])
            finally:
                svc.close()
