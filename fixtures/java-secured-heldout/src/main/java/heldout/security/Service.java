package heldout.security;
import org.springframework.security.access.annotation.Secured;
class Service {
 @Secured("ROLE_ADMIN") void fetch() {}
 @Secured({"ROLE_USER", "ROLE_AUDITOR"}) void fetch(String id) {}
}
