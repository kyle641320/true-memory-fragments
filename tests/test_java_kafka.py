from __future__ import annotations

import tempfile
import unittest
import subprocess
from pathlib import Path

from tmf.ids import stable_java_node_claim_id, stable_topic_pub_edge_claim_id, stable_topic_sub_edge_claim_id
from tmf.java_extract import JAVA_DEGRADE_HINT, java_status
from tmf.store import Store
from tmf.warm import warm_repo
from tests.test_java_inherit import init_repo


@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaKafkaTests(unittest.TestCase):
    def test_exact_import_literal_declarations_retain_group_payload_and_anchor(self):
        source = '''
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.core.KafkaTemplate;
class Producer { KafkaTemplate<String,Order> kafka; void send(Order order) { kafka.send("orders", order); } }
class Consumer { @KafkaListener(topics="orders", groupId="billing") void listen(Order order) {} }
class Order {}
'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Mq.java": source})
            warm_repo(repo)
            store = Store(repo)
            producer = stable_java_node_claim_id("Mq.java", "Producer.send", "method")
            consumer = stable_java_node_claim_id("Mq.java", "Consumer.listen", "method")
            pub = store.get_claim(stable_topic_pub_edge_claim_id(producer, "orders"))
            sub = store.get_claim(stable_topic_sub_edge_claim_id(consumer, "orders"))
            self.assertEqual(pub.body["payload_type"], "Order")
            self.assertEqual(pub.body["resolution"], "spring_kafka_template_literal_send")
            self.assertEqual(sub.body["group_id"], "billing")
            self.assertEqual(sub.body["payload_type"], "Order")
            self.assertEqual(sub.body["source_anchor"]["line_start"], 5)
            self.assertEqual(pub.bindings[0].fn_hash, store.get_claim(producer).bindings[0].fn_hash)

    def test_decoys_overloads_and_dynamic_values_fail_closed(self):
        source = '''
class KafkaTemplate<K,V> { void send(String topic, V value) {} }
@interface KafkaListener { String topics(); String groupId(); }
class Decoy { KafkaTemplate<String,String> kafka; void send(String topic) { kafka.send("fake", "x"); }
  @KafkaListener(topics="fake", groupId="fake") void listen(String value) {} }
'''
        dynamic = '''
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.core.KafkaTemplate;
class Dynamic { KafkaTemplate<String,String> kafka; void send(String topic, String value) { kafka.send(topic, value); }
 @KafkaListener(topics=TOPIC, groupId=GROUP) void listen(String value) {} }
'''
        overload = '''
import org.springframework.kafka.core.KafkaTemplate;
class P { KafkaTemplate<String,String> kafka; void send(String v) { kafka.send("orders", 0, v); } }
'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Decoy.java": source, "Dynamic.java": dynamic, "Overload.java": overload})
            warm_repo(repo)
            store = Store(repo)
            decoy = stable_java_node_claim_id("Decoy.java", "Decoy.send", "method")
            overloaded = stable_java_node_claim_id("Overload.java", "P.send", "method")
            dynamic_id = stable_java_node_claim_id("Dynamic.java", "Dynamic.send", "method")
            listener_id = stable_java_node_claim_id("Dynamic.java", "Dynamic.listen", "method")
            self.assertIsNone(store.get_claim(stable_topic_pub_edge_claim_id(decoy, "fake")))
            self.assertIsNone(store.get_claim(stable_topic_pub_edge_claim_id(overloaded, "orders")))
            self.assertEqual(store.get_claim(dynamic_id).body["graph"]["publishes_to_unresolved"][0]["reason"], "kafka_topic_not_literal")
            self.assertEqual(store.get_claim(listener_id).body["graph"]["subscribes_to_unresolved"][0]["reason"], "kafka_topic_not_literal")

    def test_cross_file_mutation_and_deletion_reconcile_edges(self):
        producer = '''import org.springframework.kafka.core.KafkaTemplate;
class P { KafkaTemplate<String,String> kafka; void send() { kafka.send("orders", "x"); } }'''
        consumer = '''import org.springframework.kafka.annotation.KafkaListener;
class C { @KafkaListener(topics="orders", groupId="g") void listen(String value) {} }'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"P.java": producer, "C.java": consumer})
            warm_repo(repo)
            pid = stable_java_node_claim_id("P.java", "P.send", "method")
            cid = stable_java_node_claim_id("C.java", "C.listen", "method")
            old_pub = stable_topic_pub_edge_claim_id(pid, "orders")
            old_sub = stable_topic_sub_edge_claim_id(cid, "orders")
            (Path(repo) / "P.java").write_text(producer.replace('"orders"', '"invoices"'))
            (Path(repo) / "C.java").unlink()
            subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "mutate kafka fixture"], cwd=repo, check=True, capture_output=True)
            warm_repo(repo)
            store = Store(repo)
            self.assertIsNone(store.get_claim(old_pub))
            self.assertIsNone(store.get_claim(old_sub))
            self.assertIsNotNone(store.get_claim(stable_topic_pub_edge_claim_id(pid, "invoices")))


if __name__ == "__main__":
    unittest.main()
