package heldout.security;
import javax.annotation.security.RolesAllowed;
class JavaxService { @RolesAllowed("LEGACY") void legacy() {} }
