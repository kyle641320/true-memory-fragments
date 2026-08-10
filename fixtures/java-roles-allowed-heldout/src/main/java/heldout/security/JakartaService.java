package heldout.security;
import jakarta.annotation.security.RolesAllowed;
class JakartaService {
 @RolesAllowed("ADMIN") void fetch() {}
 @RolesAllowed({"USER", "AUDITOR"}) void fetch(String id) {}
}
