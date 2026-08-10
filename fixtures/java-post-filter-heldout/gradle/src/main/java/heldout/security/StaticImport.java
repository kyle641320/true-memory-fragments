package heldout.security;
import static org.springframework.security.access.prepost.PostFilter;
class StaticImport { @PostFilter("x") void denied() {} }
