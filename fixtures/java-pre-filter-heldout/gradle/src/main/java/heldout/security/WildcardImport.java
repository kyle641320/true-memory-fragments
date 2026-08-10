package heldout.security;
import org.springframework.security.access.prepost.*;
class WildcardImport { @PreFilter("x") void denied() {} }
