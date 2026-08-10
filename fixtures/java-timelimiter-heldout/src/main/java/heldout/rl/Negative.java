package heldout.timelimiter;
import io.github.resilience4j.timelimiter.annotation.TimeLimiter;
class Negative { static final String N="dynamic"; @TimeLimiter(name=N) void dynamic() {} @TimeLimiter(name="${cb}") void placeholder() {} }
