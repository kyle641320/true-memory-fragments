package heldout.bulkhead;
import io.github.resilience4j.bulkhead.annotation.Bulkhead;
class Client {
 @Bulkhead(name="inventory", fallbackMethod="fallback") String fetch() { return ""; }
 @Bulkhead(name="priced") String fetch(String sku) { return sku; }
}
