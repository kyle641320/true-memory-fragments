package heldout.async;
import org.springframework.scheduling.annotation.Async;
class Negative { static final String POOL="x"; @Async(POOL) void dynamic() {} @Async("${pool}") void placeholder() {} }
