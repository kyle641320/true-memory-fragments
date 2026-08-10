package heldout.retry;
import io.github.resilience4j.retry.annotation.Retry;
class Client {
 @Retry(name="inventory", fallbackMethod="fallback") String fetch() { return ""; }
 @Retry(name="priced") String fetch(String sku) { return sku; }
}
