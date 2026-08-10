package heldout.configprops;
import org.springframework.boot.context.properties.ConfigurationProperties;
class Negatives {
  @ConfigurationProperties("field") String field;
  @ConfigurationProperties("factory") Object notBean() { return null; }
}
@ConfigurationProperties(prefix = PREFIX) class DynamicProperties {}
