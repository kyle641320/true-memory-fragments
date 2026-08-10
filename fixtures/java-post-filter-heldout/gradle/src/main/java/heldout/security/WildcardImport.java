package heldout.security;
import org.springframework.security.access.prepost.*;
class WildcardImport { @PostFilter("x") void denied() {} }
