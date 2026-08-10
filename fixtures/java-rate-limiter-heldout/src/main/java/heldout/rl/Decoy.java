package heldout.rl; class Decoy { @interface RateLimiter { String name(); } @RateLimiter(name="fake") void fake() {} }
