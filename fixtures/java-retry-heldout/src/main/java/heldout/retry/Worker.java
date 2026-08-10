package heldout.retry;
import org.springframework.retry.annotation.Retryable;
import org.springframework.retry.annotation.Recover;
class Worker {
 @Retryable(retryFor=java.io.IOException.class,maxAttempts=3,label="io") void run() {}
 @Retryable(noRetryFor={IllegalArgumentException.class},stateful=true,listeners={"audit"}) void run(String key) {}
 @Recover String recover(Exception failure) { return "none"; }
}
