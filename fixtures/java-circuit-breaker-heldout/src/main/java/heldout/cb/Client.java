package heldout.cb;
import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
class Client {
 @CircuitBreaker(name="inventory", fallbackMethod="fallback") String fetch() { return ""; }
 @CircuitBreaker(name="priced") String fetch(String sku) { return sku; }
}
