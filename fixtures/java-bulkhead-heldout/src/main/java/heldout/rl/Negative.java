package heldout.bulkhead;
import io.github.resilience4j.bulkhead.annotation.Bulkhead;
class Negative { static final String N="dynamic"; @Bulkhead(name=N) void dynamic() {} @Bulkhead(name="${cb}") void placeholder() {} }
