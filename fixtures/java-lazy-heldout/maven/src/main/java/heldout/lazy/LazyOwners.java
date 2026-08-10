package heldout.lazy;
import org.springframework.context.annotation.Lazy;
@Lazy
class LazyType { @Lazy Object create(){ return null; } }
@Lazy
interface LazyContract {}
class Factory { @Lazy Object alpha(){ return null; } }
