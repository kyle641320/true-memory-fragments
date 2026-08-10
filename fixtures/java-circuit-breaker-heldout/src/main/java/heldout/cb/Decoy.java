package heldout.cb; class Decoy { @interface CircuitBreaker { String name(); } @CircuitBreaker(name="fake") void fake() {} }
