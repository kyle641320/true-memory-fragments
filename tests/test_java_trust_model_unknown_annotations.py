from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo
from tmf.ids import stable_java_node_claim_id


def claims(source: str):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "A.java").write_text(source)
        subprocess.run(["git", "init", "-b", "master"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "x@y"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "x"], cwd=root, check=True)
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", "fixture"], cwd=root, check=True, capture_output=True)
        return derive_claims_for_path(GitRepo(root), "A.java")


class JavaTrustModelUnknownAnnotationTests(unittest.TestCase):
    def node(self, source: str, qualname: str, kind: str):
        by_id = {claim.id: claim for claim in claims(source)}
        return by_id[stable_java_node_claim_id("A.java", qualname, kind)]

    def test_role_shaped_mq_annotation_is_explicit_unknown(self):
        method = self.node("@interface MdpMafkaMsgReceive {} class A { @MdpMafkaMsgReceive void receive(String x) {} }", "A.receive", "method")
        self.assertEqual(method.body["graph"]["subscribes_to"], [])
        unknown = method.body["graph"]["subscribes_to_unresolved"]
        self.assertEqual(unknown[0]["reason"], "topic_annotation_not_recognized")
        self.assertEqual(unknown[0]["annotation"], "MdpMafkaMsgReceive")
        self.assertEqual(unknown[0]["qualname"], "A.receive")
        self.assertEqual(unknown[0]["bucket"], "topic_subscription")

    def test_arbitrary_annotation_remains_true_negative(self):
        method = self.node("@interface Audited {} class A { @Audited void receive(String x) {} }", "A.receive", "method")
        self.assertEqual(method.body["graph"]["subscribes_to"], [])
        self.assertEqual(method.body["graph"]["subscribes_to_unresolved"], [])

    def test_role_shaped_injection_annotation_is_explicit_unknown(self):
        owner = self.node("@interface VendorInject {} class A { @VendorInject Object client; }", "A", "class")
        self.assertEqual(owner.body["graph"]["injects"], [])
        unknown = owner.body["graph"]["injects_unresolved"]
        self.assertEqual(unknown[0]["reason"], "injection_annotation_not_recognized")
        self.assertEqual(unknown[0]["annotation"], "VendorInject")
        self.assertEqual(unknown[0]["qualname"], "A.client")
        self.assertEqual(unknown[0]["bucket"], "dependency_injection")

    def test_arbitrary_field_annotation_remains_true_negative(self):
        owner = self.node("@interface Audited {} class A { @Audited Object client; }", "A", "class")
        self.assertEqual(owner.body["graph"]["injects"], [])
        self.assertEqual(owner.body["graph"]["injects_unresolved"], [])

    def test_exact_javax_and_jakarta_presence_are_namespace_accurate(self):
        cases = (
            ("Resource", "javax.annotation", "jakarta.annotation"),
            ("Inject", "javax.inject", "jakarta.inject"),
            ("Named", "javax.inject", "jakarta.inject"),
            ("Singleton", "javax.inject", "jakarta.inject"),
        )
        templates = {
            "Resource": "class A { @Resource Object client; }",
            "Inject": "class A { @Inject Object client; }",
            "Named": "@Named class A {}",
            "Singleton": "@Singleton class A {}",
        }
        for annotation, javax_namespace, jakarta_namespace in cases:
            for namespace in (javax_namespace, jakarta_namespace):
                derived = claims(f"import {namespace}.{annotation}; {templates[annotation]}")
                presence = [c for c in derived if c.body.get("edge_kind") == f"declares_{annotation.lower()}_presence"]
                self.assertEqual(len(presence), 1, (annotation, namespace))
                self.assertEqual(presence[0].body["source_namespace"], namespace)

    def test_exact_resource_presence_is_not_injection_unknown(self):
        for namespace in ("javax.annotation", "jakarta.annotation"):
            owner = self.node(f"import {namespace}.Resource; class A {{ @Resource Object client; }}", "A", "class")
            self.assertEqual(owner.body["graph"]["injects"], [])
            self.assertEqual(owner.body["graph"]["injects_unresolved"], [])

    def test_resource_same_name_custom_ambiguous_and_wildcard_fail_closed(self):
        samples = (
            "@interface Resource {} class A { @Resource Object client; }",
            "import jakarta.annotation.*; class A { @Resource Object client; }",
            "import javax.annotation.Resource; import custom.Resource; class A { @Resource Object client; }",
        )
        for source in samples:
            derived = claims(source)
            self.assertFalse([c for c in derived if c.body.get("edge_kind") == "declares_resource_presence"])
            file_claim = next(c for c in derived if c.scope == "file")
            reasons = [x["reason"] for xs in file_claim.body.get("java_resource_unresolved", {}).values() for x in xs]
            self.assertIn("resource_annotation_not_exact_explicit_import", reasons)

    def test_javax_singleton_named_are_presence_only_not_injection_edges(self):
        for annotation in ("Singleton", "Named"):
            source = f"import javax.inject.{annotation}; @{annotation} class A {{}}"
            derived = claims(source)
            kinds = {c.body.get("edge_kind") for c in derived}
            self.assertIn(f"declares_{annotation.lower()}_presence", kinds)
            owner = next(c for c in derived if c.body.get("node_kind") == "class")
            self.assertEqual(owner.body["graph"]["injects"], [])

    def test_unknown_injection_rename_delete_and_exact_rebind(self):
        unknown = self.node("@interface VendorInject {} class A { @VendorInject Object client; }", "A", "class")
        self.assertEqual(unknown.body["graph"]["injects_unresolved"][0]["annotation"], "VendorInject")
        renamed = self.node("@interface VendorResource {} class A { @VendorResource Object client; }", "A", "class")
        self.assertEqual(renamed.body["graph"]["injects_unresolved"][0]["annotation"], "VendorResource")
        deleted = self.node("class A { Object client; }", "A", "class")
        self.assertEqual(deleted.body["graph"]["injects_unresolved"], [])
        rebound = self.node("import javax.annotation.Resource; class A { @Resource Object client; }", "A", "class")
        self.assertEqual(rebound.body["graph"]["injects_unresolved"], [])

    def test_unknown_listener_rename_delete_and_exact_rebind(self):
        unknown = self.node(
            "@interface VendorReceiver {} class A { @VendorReceiver void receive(String x) {} }",
            "A.receive", "method",
        )
        self.assertEqual(unknown.body["graph"]["subscribes_to_unresolved"][0]["annotation"], "VendorReceiver")

        renamed = self.node(
            "@interface VendorListener {} class A { @VendorListener void receive(String x) {} }",
            "A.receive", "method",
        )
        self.assertEqual(renamed.body["graph"]["subscribes_to_unresolved"][0]["annotation"], "VendorListener")

        deleted = self.node("class A { void receive(String x) {} }", "A.receive", "method")
        self.assertEqual(deleted.body["graph"]["subscribes_to_unresolved"], [])

        rebound = self.node(
            'import org.springframework.kafka.annotation.KafkaListener; class A { @KafkaListener(topics="orders") void receive(String x) {} }',
            "A.receive", "method",
        )
        self.assertEqual(rebound.body["graph"]["subscribes_to_unresolved"], [])
        self.assertEqual(rebound.body["graph"]["subscribes_to"][0]["topic_name"], "orders")


if __name__ == "__main__":
    unittest.main()
