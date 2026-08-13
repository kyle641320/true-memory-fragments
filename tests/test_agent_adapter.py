import json
import os
from pathlib import Path
import stat
import tempfile
import textwrap
import unittest

from bench.agent_ab.adapter import AgentAdapterError, BrokerPreflight, JsonBrokerAdapter


class JsonBrokerAdapterTests(unittest.TestCase):
    def broker(self, body: str) -> Path:
        root = Path(self.addCleanupDir.name)
        path = root / "broker"
        path.write_text("#!/usr/bin/python3\n" + textwrap.dedent(body))
        path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        return path

    def setUp(self):
        self.addCleanupDir = tempfile.TemporaryDirectory()
        self.addCleanup(self.addCleanupDir.cleanup)

    def test_preflight_and_completion_use_locked_stateless_contract(self):
        path = self.broker("""
            import json, os, sys
            req=json.load(sys.stdin)
            if req['op']=='preflight':
                out={'protocol':'tmf-agent-broker-v1','model':'p/m','stateless':True,'tools':[],
                     'network_owner':'broker','credential_owner':'broker'}
            else:
                assert 'SECRET_FOR_TEST' not in os.environ
                out={'protocol':'tmf-agent-broker-v1','model':'p/m','answer':'ok','calls':1}
            print(json.dumps(out))
        """)
        os.environ["SECRET_FOR_TEST"] = "must-not-leak"
        self.addCleanup(os.environ.pop, "SECRET_FOR_TEST", None)
        adapter = JsonBrokerAdapter([str(path)], expected_model="p/m")
        self.assertEqual(adapter.preflight().model, "p/m")
        self.assertEqual(adapter.answer("question", budget=2)["answer"], "ok")

    def test_answer_fails_closed_without_preflight(self):
        path = self.broker("print('{}')")
        with self.assertRaisesRegex(AgentAdapterError, "preflight"):
            JsonBrokerAdapter([str(path)], expected_model="p/m").answer("q", budget=1)

    def test_preflight_rejects_tools_or_credential_exposure(self):
        for change in ({"tools": ["exec"]}, {"credential_owner": "arm"}, {"network_owner": "arm"}, {"stateless": False}):
            value = {'protocol':'tmf-agent-broker-v1','model':'p/m','stateless':True,'tools':[],
                     'network_owner':'broker','credential_owner':'broker'}
            value.update(change)
            with self.subTest(change=change), self.assertRaises(AgentAdapterError):
                BrokerPreflight.parse(value)

    def test_rejects_relative_or_non_executable_broker(self):
        with self.assertRaisesRegex(AgentAdapterError, "absolute"):
            JsonBrokerAdapter(["broker"], expected_model="p/m")
        path = Path(self.addCleanupDir.name) / "broker"
        path.write_text("noop")
        with self.assertRaisesRegex(AgentAdapterError, "executable"):
            JsonBrokerAdapter([str(path)], expected_model="p/m")

    def test_completion_rejects_model_drift_and_budget_breach(self):
        path = self.broker("""
            import json, sys
            req=json.load(sys.stdin)
            if req['op']=='preflight':
                out={'protocol':'tmf-agent-broker-v1','model':'p/m','stateless':True,'tools':[],
                     'network_owner':'broker','credential_owner':'broker'}
            else:
                out={'protocol':'tmf-agent-broker-v1','model':'other/model','answer':'bad','calls':99}
            print(json.dumps(out))
        """)
        adapter = JsonBrokerAdapter([str(path)], expected_model="p/m")
        adapter.preflight()
        with self.assertRaises(AgentAdapterError):
            adapter.answer("q", budget=1)


if __name__ == "__main__":
    unittest.main()
