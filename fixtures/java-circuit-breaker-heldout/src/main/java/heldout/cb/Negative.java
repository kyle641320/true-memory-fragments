package heldout.cb;
import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
class Negative { static final String N="dynamic"; @CircuitBreaker(name=N) void dynamic() {} @CircuitBreaker(name="${cb}") void placeholder() {} }
