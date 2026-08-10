package heldout.primary;
import org.springframework.context.annotation.Primary;
class Negatives {
  @Primary String wrongField;
  void local() { @Primary class Local {} }
}
@Primary(false)
class MetadataNegative {}
