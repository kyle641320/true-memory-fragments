package heldout.security;
import org.springframework.security.access.prepost.PostAuthorize;
import decoy.PostAuthorize;
class AmbiguousImport { @PostAuthorize("ambiguous") void denied() {} }
