package heldout.security;
import org.springframework.security.access.prepost.PostAuthorize;
class UnresolvedCases {
 static final String POLICY = "hasRole('OPS')";
 @PostAuthorize(POLICY) void constant() {}
 @PostAuthorize("${security.policy}") void placeholder() {}
 @PostAuthorize(value = policy()) void dynamic() {}
 static String policy() { return "x"; }
}
