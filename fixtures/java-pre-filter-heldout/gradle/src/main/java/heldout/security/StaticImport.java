package heldout.security;
import static org.springframework.security.access.prepost.PreFilter;
class StaticImport { @PreFilter("x") void denied() {} }
