package heldout.retry;
import org.springframework.retry.annotation.Retryable;
class Negative { static final int N=4; @Retryable(maxAttempts=N) void dynamic() {} @Retryable(maxAttemptsExpression="${attempts}") void placeholder() {} }
