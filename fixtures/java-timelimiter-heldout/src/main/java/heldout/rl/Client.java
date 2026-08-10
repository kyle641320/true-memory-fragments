package heldout.timelimiter;
import io.github.resilience4j.timelimiter.annotation.TimeLimiter;
class Client {
 @TimeLimiter(name="inventory", fallbackMethod="fallback") String fetch() { return ""; }
 @TimeLimiter(name="priced") String fetch(String sku) { return sku; }
}
