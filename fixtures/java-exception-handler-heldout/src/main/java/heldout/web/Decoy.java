package heldout.web;
@interface ExceptionHandler { Class<?>[] value() default {}; }
class Decoy { @ExceptionHandler(RuntimeException.class) void fake() {} }
