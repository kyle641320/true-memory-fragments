package heldout.retry; class Decoy { @interface Retry { String name(); } @Retry(name="fake") void fake() {} }
