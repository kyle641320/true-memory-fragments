from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ten_repo_production_gate.py"


def load_gate():
    spec = importlib.util.spec_from_file_location("ten_repo_production_gate", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def claim(claim_id: str, **body):
    return SimpleNamespace(id=claim_id, body=body)


class RuntimeBoundaryClassifierTests(unittest.TestCase):
    def test_shared_message_topology_requires_runtime_proof(self):
        gate = load_gate()
        result = gate.classify_runtime_boundary([
            claim("topic", node_kind="topic", topic_name="orders"),
            claim("pub", edge_kind="publishes_to", topic_id="topic", publisher_id="producer", source_path="Producer.java", resolution="spring_kafka_literal_topic"),
            claim("sub", edge_kind="subscribes_to", topic_id="topic", subscriber_id="consumer", source_path="Consumer.java", resolution="spring_kafka_literal_topic"),
        ])

        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["features"]["message_topology"]["shared_topics"], 1)
        self.assertIn("broker_delivery", result["unproven"])
        self.assertIn("transaction_commit", result["unproven"])

    def test_shared_message_topology_accepts_persisted_source_id_schema(self):
        gate = load_gate()
        result = gate.classify_runtime_boundary([
            claim("topic", node_kind="topic", topic_name="orders"),
            claim("pub", edge_kind="publishes_to", topic_id="topic", source_id="producer"),
            claim("sub", edge_kind="subscribes_to", topic_id="topic", source_id="consumer"),
        ])

        self.assertEqual(result["features"]["message_topology"]["shared_topics"], 1)

    def test_structured_participant_saga_requires_runtime_proof(self):
        gate = load_gate()
        result = gate.classify_runtime_boundary([
            claim("saga", graph={"saga_definition": {
                "resolution": "eventuate_simple_saga_literal_dsl",
                "steps": [
                    {"kind": "local", "method": "create", "compensation": "reject"},
                    {"kind": "participant", "method": "reserve", "participant_contract": {"channel": "customers"}, "replies": [{"reply": "Failure", "handler": "failed"}]},
                ],
            }}),
        ])

        self.assertEqual(result["features"]["saga_control_flow"]["sagas"], 1)
        self.assertIn("reply_dispatch", result["unproven"])
        self.assertIn("compensation_execution", result["unproven"])

    def test_isolated_message_or_keyword_like_claim_does_not_match(self):
        gate = load_gate()
        result = gate.classify_runtime_boundary([
            claim("topic", node_kind="topic", topic_name="orders"),
            claim("pub", edge_kind="publishes_to", topic_id="topic", publisher_id="producer", resolution="spring_kafka_literal_topic"),
            claim("name-only", node_kind="class", name="TransactionSagaCompensationBroker"),
        ])

        self.assertIsNone(result)

    def test_incomplete_or_unstructured_saga_does_not_match(self):
        gate = load_gate()
        result = gate.classify_runtime_boundary([
            claim("dynamic", graph={"saga_definition_unresolved": [{"reason": "not_literal"}]}),
            claim("local-only", graph={"saga_definition": {
                "resolution": "eventuate_simple_saga_literal_dsl",
                "steps": [{"kind": "local", "method": "create", "compensation": "reject"}],
            }}),
            claim("participant-only", graph={"saga_definition": {
                "resolution": "eventuate_simple_saga_literal_dsl",
                "steps": [{"kind": "participant", "method": "reserve"}],
            }}),
        ])

        self.assertIsNone(result)

    def test_audit_preserves_clean_static_pass_and_marks_runtime_boundary_partial(self):
        gate = load_gate()
        topic = claim("topic", node_kind="topic", topic_name="orders")
        publisher = claim("pub", edge_kind="publishes_to", topic_id="topic", source_id="producer")
        subscriber = claim("sub", edge_kind="subscribes_to", topic_id="topic", source_id="consumer")
        clean_warm = {"result": {"failed_files": {}}}
        noop_warm = {"result": {"derived": 0, "failed_files": {}}}

        with mock.patch.object(gate, "GitRepo") as git_repo, mock.patch.object(gate, "Store") as store, mock.patch.object(gate, "check_freshness", return_value=SimpleNamespace(fresh=True)):
            git_repo.return_value.head.return_value = "abc123"
            store.return_value.iter_claims.return_value = [topic, publisher, subscriber]
            result = gate.audit(Path("ordinary-repository"), clean_warm, noop_warm)
            store.return_value.iter_claims.return_value = [claim("plain", node_kind="class")]
            ordinary = gate.audit(Path("eventuate-looking-name"), clean_warm, noop_warm)

        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["runtime_boundary"]["classification"], "runtime_proof_required")
        self.assertEqual(ordinary["status"], "PASS")
        self.assertIsNone(ordinary["runtime_boundary"])


if __name__ == "__main__":
    unittest.main()
