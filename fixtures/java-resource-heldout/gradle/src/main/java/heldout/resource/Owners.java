package heldout.resource;
import jakarta.annotation.Resource;
@Resource
class Owners {
  @Resource Object client;
  @Resource void setClient(Object value) {}
}
