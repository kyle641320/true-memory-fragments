package heldout.security;
import org.springframework.security.access.prepost.PreFilter;
import decoy.PreFilter;
class AmbiguousImport { @PreFilter("ambiguous") void denied() {} }
