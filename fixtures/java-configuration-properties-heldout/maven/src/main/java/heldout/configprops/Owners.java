package heldout.configprops;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Bean;
@ConfigurationProperties(prefix = "app.http") class HttpProperties {}
@ConfigurationProperties("app.db") record DatabaseProperties(String url) {}
class Factories {
  @Bean @ConfigurationProperties(value = "app.worker") Worker worker() { return null; }
}
class Worker {}
