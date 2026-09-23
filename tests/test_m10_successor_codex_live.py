"""Real local IPC and admission failures; all peers are zero-model test processes."""
from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from bench.agent_ab.same_version_chain_v1 import successor_codex_runner as runner
from bench.agent_ab.same_version_chain_v1 import successor_codex_host as host
from bench.agent_ab.same_version_chain_v1.successor_codex_control import RuntimeGuard, runtime_profile, digest
from bench.agent_ab.same_version_chain_v1.successor_codex_live import LivePeer, _decode_frame
from bench.agent_ab.same_version_chain_v1.successor_codex_mediation import RuntimeViolation


PRELUDE = '''import json, os, socket, time
s = socket.socket(fileno=int(os.environ['SUCCESSOR_CONTROL_FD']))
f = s.makefile('rwb', buffering=0)
def send(v): f.write((json.dumps(v) + '\\n').encode())
start = json.loads(f.readline())
assert start['kind'] == 'start'
'''


class FakeWorkspace:
    messages = [{"role": "system", "content": "test"}, {"role": "user", "content": "test"}]

    def __init__(self):
        self.prepared = 0
        self.actions = []

    def prepare_agent_turn(self):
        self.prepared += 1

    def call(self, action):
        self.actions.append(action)
        return {"ok": True}


class IpcTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.events = []

    def setup_peer(self, body):
        script = self.root / "zero_model_peer.py"
        script.write_text(PRELUDE + body)
        peer = LivePeer({"argv": [sys.executable, "-B", str(script)]},
                        self.root / "runtime", self.root / "diagnostics.log")
        guard = RuntimeGuard(runtime_profile(), emit=self.events.append, abort=peer.abort)
        return peer, guard, FakeWorkspace()

    def test_two_actions_and_internal_retry_telemetry_need_only_one_external_turn(self):
        peer, guard, workspace = self.setup_peer('''
send({'kind':'event','event':{'event':'retry_observed','source':'fake_public_callback','data':{'attempt':2}}})
for i in range(2):
 send({'kind':'action','id':str(i),'args':{'action':'list'}})
 assert json.loads(f.readline()) == {'kind':'action_result','id':str(i),'result':{'ok':True}}
send({'kind':'completed','result':{'usage':{'input':12},'modelIterations':3}})
''')
        runner.run_bounded_peer(peer, guard, workspace)
        self.assertEqual(2, len(workspace.actions))
        self.assertEqual(1, workspace.prepared)
        self.assertEqual(1, guard.agent_turns)
        self.assertEqual("completed", guard.phase)
        self.assertEqual(3, peer.snapshot()["runtime_result"]["modelIterations"])
        self.assertIsNone(peer.snapshot()["native_model_calls"])
        self.assertIsNone(peer.snapshot()["cost_usd"])

    def test_fatal_event_prevents_following_action_and_reaps_process(self):
        peer, guard, workspace = self.setup_peer('''
send({'kind':'event','event':{'event':'model/rerouted','source':'fake_public_callback'}})
send({'kind':'action','id':'forbidden','args':{'action':'list'}})
time.sleep(10)
''')
        with self.assertRaisesRegex(RuntimeViolation, "model_rerouted"):
            runner.run_bounded_peer(peer, guard, workspace)
        self.assertEqual([], workspace.actions)
        self.assertIsNotNone(peer.process.poll())
        self.assertTrue(peer.snapshot()["abort_requested"])
        self.assertIsNone(peer.snapshot()["upstream_abort_acknowledged"])

    def test_duplicate_tool_id_cannot_repeat_side_effect(self):
        peer, guard, workspace = self.setup_peer('''
for i in range(2):
 send({'kind':'action','id':'same','args':{'action':'list'}})
 if i == 0: f.readline()
''')
        with self.assertRaisesRegex(RuntimeViolation, "duplicate_tool_call"):
            runner.run_bounded_peer(peer, guard, workspace)
        self.assertEqual(1, len(workspace.actions))

    def test_eof_without_completion_is_not_success(self):
        peer, guard, workspace = self.setup_peer("pass\n")
        with self.assertRaisesRegex(RuntimeViolation, "host_incomplete"):
            runner.run_bounded_peer(peer, guard, workspace)

    def test_host_completion_revokes_later_tool_authority(self):
        peer, guard, workspace = self.setup_peer('''
send({'kind':'completed','result':{}})
send({'kind':'action','id':'late','args':{'action':'list'}})
''')
        with self.assertRaisesRegex(RuntimeViolation, "event_after_host_completion"):
            runner.run_bounded_peer(peer, guard, workspace)
        self.assertEqual([], workspace.actions)

    def test_external_absolute_deadline_reaps_hung_host(self):
        peer, guard, workspace = self.setup_peer("time.sleep(10)\n")
        guard.deadline = time.monotonic() + 0.15
        with self.assertRaisesRegex(RuntimeViolation, "run_timeout"):
            runner.run_bounded_peer(peer, guard, workspace)
        self.assertIsNotNone(peer.process.poll())

    def test_noncanonical_duplicate_nonfinite_or_invalid_frame_rejected(self):
        for raw in (b'{"kind":"event","kind":"completed"}', b'{"kind":"event","data":NaN}', b'[]', b'\xff'):
            with self.subTest(raw=raw), self.assertRaises(RuntimeViolation):
                _decode_frame(raw)


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = {"seal_sha256": "a" * 64, "profile": runtime_profile(),
                         "host_qualification": {"example": "zero-model-test"},
                         "scientific": {"randomization": {"seed": 20260923, "schedule": ["original"]}}}
        self.checkout = {"commit": "b" * 40, "common_dir": str(self.root / "common-git")}
        self.receipt = {"schema": "tmf.successor.independent-readiness.v1", "ready": True,
                        "scope": "changed_execution_budget_and_live_bridge_only",
                        "commit": self.checkout["commit"], "seal_sha256": self.manifest["seal_sha256"],
                        "profile_sha256": digest(self.manifest["profile"]),
                        "host_qualification_sha256": digest(self.manifest["host_qualification"]),
                        "blocking_issues": [], "reviewer": "independent-zero-model-test"}

    def test_missing_or_wrong_audit_binding_never_admits(self):
        with patch.object(runner, "verify_manifest"), patch.object(host, "require_live_host"), \
                patch.object(runner, "frozen_checkout", return_value=self.checkout):
            for change in (None, {"commit": "wrong"}, {"seal_sha256": "wrong"},
                           {"ready": False}, {"blocking_issues": ["genuine failure"]}):
                candidate = None if change is None else {**self.receipt, **change}
                with self.subTest(change=change), self.assertRaises(RuntimeViolation):
                    runner.check_live_readiness(self.manifest, candidate)
            valid = runner.check_live_readiness(self.manifest, self.receipt)
            self.assertTrue(valid["ready"])
            self.assertEqual(0, valid["admitted_runs"])

    def test_different_output_or_new_seal_cannot_replace_original_block(self):
        with patch.object(runner, "frozen_checkout", return_value=self.checkout):
            runner._claim_original_block(self.manifest, self.receipt, self.root / "first")
            altered = {**self.manifest, "seal_sha256": "c" * 64}
            with self.assertRaisesRegex(RuntimeViolation, "already_claimed"):
                runner._claim_original_block(altered, self.receipt, self.root / "replacement")
        claims = list((self.root / "common-git" / "successor-pilot-admissions").glob("*.json"))
        self.assertEqual(1, len(claims))
        self.assertEqual(str(self.root / "first"), json.loads(claims[0].read_text())["output"])


if __name__ == "__main__":
    unittest.main()
