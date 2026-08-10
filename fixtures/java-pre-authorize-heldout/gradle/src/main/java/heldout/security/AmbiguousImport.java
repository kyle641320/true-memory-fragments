package heldout.security;
import org.springframework.security.access.prepost.PreAuthorize;
import decoy.PreAuthorize;
class AmbiguousImport { @PreAuthorize("ambiguous") void denied() {} }
