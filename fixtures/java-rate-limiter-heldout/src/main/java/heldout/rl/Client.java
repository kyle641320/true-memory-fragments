package heldout.rl;
import io.github.resilience4j.ratelimiter.annotation.RateLimiter;
class Client {
 @RateLimiter(name="inventory", fallbackMethod="fallback") String fetch() { return ""; }
 @RateLimiter(name="priced") String fetch(String sku) { return sku; }
}
