package heldout.security;
import org.springframework.security.access.prepost.PreAuthorize;
@PreAuthorize("hasRole('ADMIN')")
class SecuredService {
 @PreAuthorize(value = "#id == authentication.name")
 String load(String id) { return id; }
 @PreAuthorize("hasAuthority('AUDIT')")
 String load(long id) { return Long.toString(id); }
 void open() {}
}
