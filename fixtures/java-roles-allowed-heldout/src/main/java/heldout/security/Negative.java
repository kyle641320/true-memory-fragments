package heldout.security;
import jakarta.annotation.security.RolesAllowed;
class Negative { static final String ROLE="DYNAMIC"; @RolesAllowed(ROLE) void dynamic() {} }
