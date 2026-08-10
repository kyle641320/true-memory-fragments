package heldout.kafka;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.core.KafkaTemplate;
class Order {}
class Publisher {
  KafkaTemplate<String, Order> kafka;
  void publish(Order order) { kafka.send("heldout.orders", order); }
  void dynamic(String topic, Order order) { kafka.send(topic, order); }
}
class Subscriber {
  @KafkaListener(topics="heldout.orders", groupId="heldout-billing")
  void receive(Order order) {}
}
