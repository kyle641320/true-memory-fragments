package heldout.security;
import org.springframework.security.access.prepost.PreAuthorize;
class UnresolvedCases {
 static final String POLICY = "hasRole('OPS')";
 @PreAuthorize(POLICY) void constant() {}
 @PreAuthorize("${security.policy}") void placeholder() {}
 @PreAuthorize(value = policy()) void dynamic() {}
 static String policy() { return "x"; }
}
