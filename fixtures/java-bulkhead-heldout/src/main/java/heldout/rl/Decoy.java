package heldout.bulkhead; class Decoy { @interface Bulkhead { String name(); } @Bulkhead(name="fake") void fake() {} }
