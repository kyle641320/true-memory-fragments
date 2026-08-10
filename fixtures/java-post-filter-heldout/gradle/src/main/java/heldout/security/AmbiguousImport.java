package heldout.security;
import org.springframework.security.access.prepost.PostFilter;
import decoy.PostFilter;
class AmbiguousImport { @PostFilter("ambiguous") void denied() {} }
