package heldout.security;
import org.springframework.security.access.prepost.PostFilter;
class SecuredService {
 @PostFilter(value = "filterObject.owner == authentication.name")
 String load(String id) { return id; }
 @PostFilter("hasAuthority('AUDIT')")
 String load(long id) { return Long.toString(id); }
 void open() {}
}
