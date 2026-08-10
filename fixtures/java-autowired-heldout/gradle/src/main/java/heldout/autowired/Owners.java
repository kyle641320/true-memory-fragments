package heldout.autowired;
import org.springframework.beans.factory.annotation.Autowired;
class Owners {
  @Autowired Owners(Object dependency) {}
  @Autowired Object client;
  @Autowired void setClient(Object value) {}
}
