package heldout.resource;
import jakarta.annotation.Resource;
class Negatives {
  @Resource(name="client") Object metadata;
  @Resource Object first, second;
}
@Resource interface WrongOwnerKind {}
