package heldout.security;
import org.springframework.security.access.annotation.Secured;
class Negative { static final String ROLE="ROLE_DYNAMIC"; @Secured(ROLE) void dynamic() {} }
