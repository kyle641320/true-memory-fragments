package heldout.web;
import org.springframework.web.bind.annotation.ExceptionHandler;
class Negative { static final Class<?> TYPE=RuntimeException.class; @ExceptionHandler(TYPE) void dynamic() {} }
