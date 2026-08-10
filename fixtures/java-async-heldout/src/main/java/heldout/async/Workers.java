package heldout.async;
import org.springframework.scheduling.annotation.Async;
@Async("bulkPool") class Workers {
 @Async void refresh() {}
 @Async(value="ioPool") void refresh(String key) {}
}
