package heldout.kafka;
class KafkaTemplate<K,V> { void send(String topic, V value) {} }
class Decoy { KafkaTemplate<String,String> kafka; void send() { kafka.send("decoy", "x"); } }
