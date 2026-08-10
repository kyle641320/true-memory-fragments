package heldout.security;
import org.springframework.security.access.prepost.PreFilter;
class SecuredService {
 @PreFilter(value = "filterObject.owner == authentication.name", filterTarget = "items")
 String load(String id) { return id; }
 @PreFilter("hasAuthority('AUDIT')")
 String load(long id) { return Long.toString(id); }
 void open() {}
}
