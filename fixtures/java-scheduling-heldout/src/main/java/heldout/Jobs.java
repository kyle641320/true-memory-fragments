package heldout;
import org.springframework.scheduling.annotation.Scheduled;
import java.util.concurrent.TimeUnit;
class Jobs {
 @Scheduled(fixedRate=15_000L, initialDelay=5, timeUnit=TimeUnit.MILLISECONDS) void poll() {}
 @Scheduled(fixedDelay=20) void settle() {}
 @Scheduled(cron="0 0 * * * *", zone="UTC") void hourly() {}
 static final long DYNAMIC=1;
 @Scheduled(fixedRate=DYNAMIC) void dynamic() {}
}
