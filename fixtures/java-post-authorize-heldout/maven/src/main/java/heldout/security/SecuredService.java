package heldout.security;
import org.springframework.security.access.prepost.PostAuthorize;
@PostAuthorize("hasRole('ADMIN')")
class SecuredService {
 @PostAuthorize(value = "#id == authentication.name")
 String load(String id) { return id; }
 @PostAuthorize("hasAuthority('AUDIT')")
 String load(long id) { return Long.toString(id); }
 void open() {}
}
