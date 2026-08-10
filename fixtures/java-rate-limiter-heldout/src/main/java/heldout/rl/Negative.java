package heldout.rl;
import io.github.resilience4j.ratelimiter.annotation.RateLimiter;
class Negative { static final String N="dynamic"; @RateLimiter(name=N) void dynamic() {} @RateLimiter(name="${cb}") void placeholder() {} }
