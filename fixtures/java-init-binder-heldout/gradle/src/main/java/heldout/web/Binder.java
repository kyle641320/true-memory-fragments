package heldout.web;
import org.springframework.web.bind.annotation.InitBinder;
class Binder {
 @InitBinder void bind() {}
 @InitBinder void bind(String value) {}
}
