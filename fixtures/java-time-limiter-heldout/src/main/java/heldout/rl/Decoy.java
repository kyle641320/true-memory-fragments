package heldout.timelimiter; class Decoy { @interface TimeLimiter { String name(); } @TimeLimiter(name="fake") void fake() {} }
