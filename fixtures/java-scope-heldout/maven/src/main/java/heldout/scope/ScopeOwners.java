package heldout.scope;
import org.springframework.context.annotation.Scope;
@Scope
class ScopeType { @Scope Object create(){ return null; } }
@Scope
interface ScopeContract {}
class Factory { @Scope Object alpha(){ return null; } }
