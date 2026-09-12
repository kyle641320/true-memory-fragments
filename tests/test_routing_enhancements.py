"""Deterministic routing contracts; no dependency on checkout .tmf state.
Calls are source-derived integration tests. Async/override are classifier
unit tests, not extractor or whole-fragment integration claims.
"""
import subprocess
import tempfile
import unittest
from pathlib import Path
from tmf.ids import stable_function_claim_id
from tmf.mcp_server import McpService
from tmf.relations import _classify_branching
from tmf.warm import warm_repo


class RoutingEnhancementsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        for args in [('init', '-q'), ('config', 'user.email', 'fixture@example.invalid'),
                     ('config', 'user.name', 'Fixture')]:
            subprocess.run(['git', *args], cwd=self.repo, check=True)
        (self.repo / 'a.py').write_text(
            'def left():\n    return 1\n\ndef right():\n    return 2\n\n'
            'def single():\n    return left()\n\ndef branch():\n    return left() + right()\n')
        subprocess.run(['git', 'add', '.'], cwd=self.repo, check=True)
        subprocess.run(['git', 'commit', '-qm', 'fixture'], cwd=self.repo, check=True)
        warm_repo(self.repo)

    def shape(self, name):
        fragment = McpService(self.repo).tmf_fragment(
            stable_function_claim_id('a.py', name), ['calls'], 1, ['function'], 10, 3)
        self.assertTrue(fragment['verified_hops'])
        self.assertFalse(fragment['stale_or_unknown'])
        self.assertIn(1, fragment['routing_shape'])
        return fragment['routing_shape'][1]

    def test_routing_shape_single_call(self):
        shape = self.shape('single')
        self.assertEqual(shape['shape'], 'single')
        self.assertEqual(shape['next_hop_count'], 1)
        self.assertFalse(shape['async_handoff'])

    def test_routing_shape_branching(self):
        shape = self.shape('branch')
        self.assertEqual(shape['shape'], 'branching')
        self.assertEqual(shape['next_hop_count'], 2)

    def test_reverse_callers_excludes_queried_endpoint(self):
        shape = self.shape('left')
        self.assertEqual(shape['shape'], 'branching')
        self.assertEqual(shape['next_hop_count'], 2)

    def test_async_handoff_classifier(self):
        shape = _classify_branching([('fixture-edge', 'publishes_to', ['topic'])])
        self.assertTrue(shape['async_handoff'])
        self.assertFalse(shape['polymorphic'])
        self.assertFalse(_classify_branching([('control', 'calls', ['target'])])['async_handoff'])

    def test_polymorphic_classifier(self):
        shape = _classify_branching([('fixture-edge', 'overrides', ['parent'])])
        self.assertTrue(shape['polymorphic'])
        self.assertFalse(shape['async_handoff'])
        self.assertFalse(_classify_branching([('control', 'calls', ['target'])])['polymorphic'])

    @unittest.skip('Optional model-inferred contract generation not exercised by offline routing suite')
    def test_understanding_tier_in_contract(self):
        pass


if __name__ == '__main__':
    unittest.main()
