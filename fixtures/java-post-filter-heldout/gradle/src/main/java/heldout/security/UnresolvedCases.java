package heldout.security;
import org.springframework.security.access.prepost.PostFilter;
class UnresolvedCases {
 static final String POLICY = "hasRole('OPS')";
 @PostFilter(POLICY) void constant() {}
 @PostFilter("${security.policy}") void placeholder() {}
 @PostFilter(value = policy()) void dynamic() {}
 static String policy() { return "x"; }
}
