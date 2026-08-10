package heldout.retry;
import io.github.resilience4j.retry.annotation.Retry;
class Negative { static final String N="dynamic"; @Retry(name=N) void dynamic() {} @Retry(name="${cb}") void placeholder() {} }
