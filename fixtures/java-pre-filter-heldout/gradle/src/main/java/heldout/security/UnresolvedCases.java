package heldout.security;
import org.springframework.security.access.prepost.PreFilter;
class UnresolvedCases {
 static final String POLICY = "hasRole('OPS')";
 @PreFilter(POLICY) void constant() {}
 @PreFilter("${security.policy}") void placeholder() {}
 @PreFilter(value = policy()) void dynamic() {}
 static String policy() { return "x"; }
}
