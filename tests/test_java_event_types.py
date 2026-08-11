from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tmf.ids import stable_event_type_edge_claim_id, stable_java_node_claim_id
from tmf.java_extract import JAVA_DEGRADE_HINT, java_status
from tmf.store import Store
from tmf.warm import warm_repo
from tests.test_java_inherit import init_repo


@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaEventTypeTests(unittest.TestCase):
    def fixture(self, publisher_annotation="org.springframework.context.event.EventListener", event_type="Booked"):
        return {
            "Booked.java": "package app; public record Booked(int id) {}\n",
            "Publisher.java": """package app;
import org.springframework.context.ApplicationEventPublisher;
class Publisher { ApplicationEventPublisher events; void send() { events.publishEvent(new Booked(1)); } }
""",
            "Listener.java": f"""package app;
import {publisher_annotation};
class Listener {{ @EventListener void on({event_type} event) {{}} }}
""",
        }

    def test_publish_and_listener_share_source_observed_event_type(self):
        with tempfile.TemporaryDirectory() as td:
            repo=init_repo(Path(td),self.fixture()); warm_repo(repo); store=Store(repo)
            pub=stable_java_node_claim_id("Publisher.java","Publisher.send","method")
            sub=stable_java_node_claim_id("Listener.java","Listener.on","method")
            typ=stable_java_node_claim_id("Booked.java","Booked","class")
            pe=store.get_claim(stable_event_type_edge_claim_id(pub,typ,"publishes_type"))
            le=store.get_claim(stable_event_type_edge_claim_id(sub,typ,"listens_type"))
            self.assertIsNotNone(pe); self.assertIsNotNone(le)
            self.assertEqual(len(pe.bindings),3)
            self.assertIn("no runtime registration", pe.body["notes"][0])
            self.assertEqual(store.get_claim(pub).body["graph"]["publishes_type"][0]["type_id"],typ)
            self.assertEqual(pe.body["type_id"], le.body["type_id"])

    def test_same_named_annotation_without_exact_import_is_unresolved(self):
        files=self.fixture("app.EventListener")
        files["EventListener.java"]="package app; public @interface EventListener {}\n"
        with tempfile.TemporaryDirectory() as td:
            repo=init_repo(Path(td),files); warm_repo(repo); store=Store(repo)
            sub=stable_java_node_claim_id("Listener.java","Listener.on","method")
            self.assertEqual(store.get_claim(sub).body["graph"]["listens_type"],[])
            self.assertEqual(store.get_claim(sub).body["graph"]["event_type_unresolved"][0]["reason"],"event_listener_annotation_not_exact_explicit_import")

    def test_dynamic_classes_and_unknown_or_generic_types_fail_closed(self):
        files=self.fixture(event_type="java.util.List<Booked>")
        files["Listener.java"]="""package app;
import org.springframework.context.event.EventListener;
class Listener { @EventListener(classes = kind) void on(Object event) {} }
"""
        with tempfile.TemporaryDirectory() as td:
            repo=init_repo(Path(td),files); warm_repo(repo); store=Store(repo)
            sub=stable_java_node_claim_id("Listener.java","Listener.on","method")
            graph=store.get_claim(sub).body["graph"]
            self.assertEqual(graph["listens_type"],[])
            self.assertEqual(graph["event_type_unresolved"][0]["reason"],"event_listener_classes_attribute_unsupported")

    def test_transaction_listener_metadata_is_declaration_only(self):
        files=self.fixture("org.springframework.transaction.event.TransactionalEventListener")
        files["Listener.java"]=files["Listener.java"].replace("@EventListener","@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT, fallbackExecution = true)")
        with tempfile.TemporaryDirectory() as td:
            repo=init_repo(Path(td),files); warm_repo(repo); store=Store(repo)
            sub=stable_java_node_claim_id("Listener.java","Listener.on","method"); typ=stable_java_node_claim_id("Booked.java","Booked","class")
            edge=store.get_claim(stable_event_type_edge_claim_id(sub,typ,"listens_type"))
            self.assertEqual(edge.body["metadata"],{"phase":"TransactionPhase.AFTER_COMMIT","fallback_execution":True,"handling":"declaration-only-never-evaluated"})

    def test_event_rename_and_listener_delete_remove_precisely(self):
        with tempfile.TemporaryDirectory() as td:
            repo=init_repo(Path(td),self.fixture()); warm_repo(repo)
            pub=stable_java_node_claim_id("Publisher.java","Publisher.send","method"); sub=stable_java_node_claim_id("Listener.java","Listener.on","method"); old=stable_java_node_claim_id("Booked.java","Booked","class")
            Path(repo,"Booked.java").write_text("package app; public record Renamed(int id) {}\n")
            Path(repo,"Publisher.java").write_text(Path(repo,"Publisher.java").read_text().replace("Booked","Renamed"))
            Path(repo,"Listener.java").write_text(Path(repo,"Listener.java").read_text().replace("org.springframework.context.event.EventListener", "app.EventListener"))
            Path(repo,"EventListener.java").write_text("package app; public @interface EventListener {}\n")
            import subprocess
            subprocess.run(["git","add","."],cwd=repo,check=True); subprocess.run(["git","commit","-m","mutate"],cwd=repo,check=True,stdout=subprocess.DEVNULL)
            warm_repo(repo); store=Store(repo)
            self.assertIsNone(store.get_claim(stable_event_type_edge_claim_id(pub,old,"publishes_type")))
            self.assertIsNone(store.get_claim(stable_event_type_edge_claim_id(sub,old,"listens_type")))
            new=stable_java_node_claim_id("Booked.java","Renamed","class")
            self.assertIsNotNone(store.get_claim(stable_event_type_edge_claim_id(pub,new,"publishes_type")))


if __name__ == "__main__": unittest.main()
