package heldout.web;
import org.springframework.web.bind.annotation.ExceptionHandler;
class Advice {
 @ExceptionHandler(IllegalArgumentException.class) void handle() {}
 @ExceptionHandler({IllegalStateException.class, java.io.IOException.class}) void handle(String id) {}
 @ExceptionHandler void inferredFromParameter(RuntimeException error) {}
}
