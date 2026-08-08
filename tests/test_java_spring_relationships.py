from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tmf.ids import stable_java_node_claim_id, stable_inject_edge_claim_id, stable_topic_claim_id, stable_topic_pub_edge_claim_id, stable_topic_sub_edge_claim_id
from tmf.java_extract import JAVA_DEGRADE_HINT, java_status
from tmf.retrieve import reverse_injected_by, reverse_saga_participants, reverse_topic_publishers, reverse_topic_subscribers
from tmf.store import Store
from tmf.warm import warm_repo
from tests.test_java_inherit import init_repo


@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaSpringRelationshipTests(unittest.TestCase):
    def test_autowired_field_unique_same_file_bean_is_attributed(self):
        source = """
import org.springframework.stereotype.Service;
import org.springframework.beans.factory.annotation.Autowired;
@Service class Repo {}
@Service class App { @Autowired Repo repo; }
"""
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"App.java": source})
            warm_repo(repo)
            store = Store(repo)
            app_id = stable_java_node_claim_id("App.java", "App", "class")
            repo_id = stable_java_node_claim_id("App.java", "Repo", "class")
            edge = store.get_claim(stable_inject_edge_claim_id(app_id, repo_id, "field"))
            self.assertIsNotNone(edge)
            self.assertEqual(edge.evidence, "attributed")
            self.assertLessEqual(edge.confidence, 0.6)
            self.assertEqual(edge.body["edge_kind"], "injects")
            self.assertEqual(edge.body["resolution"], "spring_autowired_field_type")
            graph = store.get_claim(app_id).body["graph"]
            self.assertIn(repo_id, {x["target_id"] for x in graph["injects"]})
            self.assertEqual(reverse_injected_by(repo, repo_id)["injected_by"][0]["source_id"], app_id)

    def test_interface_multiple_implementors_unresolved_no_edge(self):
        source = """
import org.springframework.stereotype.Service;
import org.springframework.beans.factory.annotation.Autowired;
interface Api {}
@Service class A implements Api {}
@Service class B implements Api {}
@Service class App { @Autowired Api api; }
"""
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"App.java": source})
            warm_repo(repo)
            store = Store(repo)
            app_id = stable_java_node_claim_id("App.java", "App", "class")
            graph = store.get_claim(app_id).body["graph"]
            self.assertEqual(graph["injects"], [])
            self.assertEqual(graph["injects_unresolved"][0]["reason"], "spring_interface_multiple_beans")
            self.assertGreaterEqual(len(graph["injects_unresolved"][0]["candidates"]), 2)

    def test_kafka_literal_topics_create_topic_edges_not_direct_producer_consumer(self):
        source = """
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.core.KafkaTemplate;
class Producer { KafkaTemplate<String,String> kafka; void send() { kafka.send("orders", "x"); kafka.send(topic, "y"); } }
class Consumer { @KafkaListener(topics="orders") void listen(String msg) {} }
"""
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Mq.java": source})
            warm_repo(repo)
            store = Store(repo)
            topic_id = stable_topic_claim_id("orders")
            producer = stable_java_node_claim_id("Mq.java", "Producer.send", "method")
            consumer = stable_java_node_claim_id("Mq.java", "Consumer.listen", "method")
            self.assertIsNotNone(store.get_claim(topic_id))
            pub = store.get_claim(stable_topic_pub_edge_claim_id(producer, "orders"))
            sub = store.get_claim(stable_topic_sub_edge_claim_id(consumer, "orders"))
            self.assertIsNotNone(pub)
            self.assertIsNotNone(sub)
            self.assertEqual(pub.evidence, "attributed")
            self.assertEqual(sub.evidence, "attributed")
            self.assertLessEqual(pub.confidence, 0.6)
            self.assertEqual(reverse_topic_publishers(repo, topic_id)["publishers"][0]["source_id"], producer)
            self.assertEqual(reverse_topic_subscribers(repo, topic_id)["subscribers"][0]["source_id"], consumer)
            graph = store.get_claim(producer).body["graph"]
            self.assertEqual(graph["publishes_to_unresolved"][0]["reason"], "kafka_topic_not_literal")

    def test_eventuate_literal_channel_creates_subscriber_edge(self):
        source = '''
import io.eventuate.tram.events.subscriber.annotations.EventuateDomainEventHandler;
class Consumer {
  @EventuateDomainEventHandler(subscriberId="orders", channel="example.orders.Order")
  void handle(Object event) {}
}
'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"Consumer.java": source})
            warm_repo(repo)
            store = Store(repo)
            topic_id = stable_topic_claim_id("example.orders.Order")
            consumer = stable_java_node_claim_id("Consumer.java", "Consumer.handle", "method")
            edge = store.get_claim(stable_topic_sub_edge_claim_id(consumer, "example.orders.Order"))
            self.assertIsNotNone(store.get_claim(topic_id))
            self.assertIsNotNone(edge)
            assert edge is not None
            self.assertEqual(edge.body["resolution"], "eventuate_literal_channel")
            self.assertEqual(reverse_topic_subscribers(repo, topic_id)["subscribers"][0]["source_id"], consumer)

    def test_topic_graph_aggregates_subscribers_across_files(self):
        first = '''
import io.eventuate.tram.events.subscriber.annotations.EventuateDomainEventHandler;
class First { @EventuateDomainEventHandler(channel="orders") void handle(Object event) {} }
'''
        second = '''
import io.eventuate.tram.events.subscriber.annotations.EventuateDomainEventHandler;
class Second { @EventuateDomainEventHandler(channel="orders") void handle(Object event) {} }
'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"First.java": first, "Second.java": second})
            warm_repo(repo)
            store = Store(repo)
            topic = store.get_claim(stable_topic_claim_id("orders"))
            self.assertIsNotNone(topic)
            assert topic is not None
            subscribers = topic.body["graph"]["subscribers"]
            self.assertEqual(len(subscribers), 2)
            self.assertEqual(topic.body["graph"]["topic_coverage"], "complete")
            self.assertEqual(len(reverse_topic_subscribers(repo, topic.id)["subscribers"]), 2)

    def test_eventuate_direct_and_unique_wrapper_publishers(self):
        publisher = '''
package example.orders;
import io.eventuate.tram.events.publisher.DomainEventPublisherForAggregate;
public interface OrderEventPublisher extends DomainEventPublisherForAggregate<Order, Long, Object> {}
'''
        service = '''
package example.orders;
class OrderService {
  private final OrderEventPublisher publisher;
  OrderService(OrderEventPublisher publisher) { this.publisher = publisher; }
  void approve(Order order) { publisher.publish(order, new Object()); }
}
'''
        direct = '''
package example.contract;
import example.orders.Order;
import io.eventuate.tram.events.publisher.DomainEventPublisher;
class ContractBase {
  private DomainEventPublisher publisher;
  void emit() { publisher.publish(Order.class, "1", new Object()); }
}
'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "OrderEventPublisher.java": publisher,
                "OrderService.java": service,
                "ContractBase.java": direct,
            })
            warm_repo(repo)
            store = Store(repo)
            topic_id = stable_topic_claim_id("example.orders.Order")
            service_id = stable_java_node_claim_id("OrderService.java", "OrderService.approve", "method")
            direct_id = stable_java_node_claim_id("ContractBase.java", "ContractBase.emit", "method")
            wrapper_edge = store.get_claim(stable_topic_pub_edge_claim_id(service_id, "example.orders.Order"))
            direct_edge = store.get_claim(stable_topic_pub_edge_claim_id(direct_id, "example.orders.Order"))
            self.assertIsNotNone(wrapper_edge)
            self.assertIsNotNone(direct_edge)
            assert wrapper_edge is not None and direct_edge is not None
            self.assertEqual(wrapper_edge.body["resolution"], "eventuate_aggregate_wrapper_unique")
            self.assertEqual(wrapper_edge.body["dependency_path"], "OrderEventPublisher.java")
            self.assertEqual(len(wrapper_edge.bindings), 2)
            self.assertEqual(direct_edge.body["resolution"], "eventuate_direct_class_literal")
            self.assertEqual(len(reverse_topic_publishers(repo, topic_id)["publishers"]), 2)

            publisher_path = Path(repo) / "OrderEventPublisher.java"
            publisher_path.write_text(publisher.replace("<Order,", "<OtherOrder,"))
            warm_result = warm_repo(repo)
            self.assertGreaterEqual(warm_result["derived"], 2)
            self.assertIsNone(Store(repo).get_claim(stable_topic_pub_edge_claim_id(service_id, "example.orders.Order")))
            other_edge = Store(repo).get_claim(stable_topic_pub_edge_claim_id(service_id, "example.orders.OtherOrder"))
            self.assertIsNotNone(other_edge)

    def test_eventuate_simple_saga_literal_definition_is_structured(self):
        source = """
import io.eventuate.tram.sagas.simpledsl.SimpleSaga;
import io.eventuate.tram.sagas.orchestration.SagaDefinition;
class CreateSaga implements SimpleSaga<Data> {
  private SagaDefinition<Data> definition = step()
    .invokeLocal(this::create).withCompensation(this::reject)
    .step().invokeParticipant(this::reserve)
      .onReply(Failure.class, this::handleFailure)
    .step().invokeLocal(this::approve).build();
}
"""
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"CreateSaga.java": source})
            warm_repo(repo)
            saga_id = stable_java_node_claim_id("CreateSaga.java", "CreateSaga", "class")
            claim = Store(repo).get_claim(saga_id)
            self.assertIsNotNone(claim)
            assert claim is not None
            graph = claim.body["graph"]
            self.assertEqual(graph["saga_definition"]["resolution"], "eventuate_simple_saga_literal_dsl")
            self.assertEqual([step["kind"] for step in graph["saga_definition"]["steps"]], ["local", "participant", "local"])
            self.assertEqual(graph["saga_definition"]["steps"][0]["compensation"], "reject")
            self.assertEqual(graph["saga_definition"]["steps"][1]["replies"][0]["reply"], "Failure.class")

            reverse = reverse_saga_participants(repo, saga_id)
            self.assertEqual(len(reverse["participants"]), 1)
            self.assertEqual(reverse["participants"][0]["resolution"], "eventuate_simple_saga_literal_dsl")

    def test_eventuate_saga_dynamic_definition_stays_unresolved(self):
        source = """
import io.eventuate.tram.sagas.simpledsl.SimpleSaga;
import io.eventuate.tram.sagas.orchestration.SagaDefinition;
class DynamicSaga implements SimpleSaga<Data> {
  private SagaDefinition<Data> definition = makeDefinition();
}
"""
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"DynamicSaga.java": source})
            warm_repo(repo)
            saga_id = stable_java_node_claim_id("DynamicSaga.java", "DynamicSaga", "class")
            graph = Store(repo).get_claim(saga_id).body["graph"]
            self.assertNotIn("saga_definition", graph)
            self.assertEqual(graph["saga_definition_unresolved"][0]["reason"], "eventuate_saga_definition_not_literal")

    def test_eventuate_saga_ambiguous_participant_contract_stays_unresolved(self):
        source = """
import io.eventuate.tram.sagas.simpledsl.SimpleSaga;
import io.eventuate.tram.sagas.orchestration.SagaDefinition;
@SagaParticipantProxy(channel = \"customerService\") class FirstProxy {
  @SagaParticipantOperation(commandClass = ReserveCreditCommand.class, replyClasses = ReserveCreditResult.class)
  public ReserveCreditResult reserveCredit(ReserveCreditCommand command) { return null; }
}
@SagaParticipantProxy(channel = \"customerService\") class SecondProxy {
  @SagaParticipantOperation(commandClass = ReserveCreditCommand.class, replyClasses = ReserveCreditResult.class)
  public ReserveCreditResult reserveCredit(ReserveCreditCommand command) { return null; }
}
class AmbiguousSaga implements SimpleSaga<Data> {
  private SagaDefinition<Data> definition = step().invokeParticipant(this::reserveCredit).build();
}
"""
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"AmbiguousSaga.java": source})
            warm_repo(repo)
            saga_id = stable_java_node_claim_id("AmbiguousSaga.java", "AmbiguousSaga", "class")
            graph = Store(repo).get_claim(saga_id).body["graph"]
            self.assertEqual(graph["saga_definition"]["steps"][0].get("participant_contract"), None)
            self.assertEqual(graph["saga_definition_unresolved"][0]["reason"], "eventuate_saga_participant_operation_not_unique")

    def test_eventuate_dynamic_direct_publisher_stays_unresolved(self):
        source = '''
import io.eventuate.tram.events.publisher.DomainEventPublisher;
class DynamicPublisher {
  private DomainEventPublisher publisher;
  void emit(Class<?> aggregateType) { publisher.publish(aggregateType, "1", new Object()); }
}
'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"DynamicPublisher.java": source})
            warm_repo(repo)
            method_id = stable_java_node_claim_id("DynamicPublisher.java", "DynamicPublisher.emit", "method")
            method = Store(repo).get_claim(method_id)
            self.assertIsNotNone(method)
            assert method is not None
            self.assertEqual(method.body["graph"]["publishes_to"], [])
            self.assertEqual(method.body["graph"]["publishes_to_unresolved"][0]["reason"], "eventuate_aggregate_not_literal")


if __name__ == "__main__":
    unittest.main()
