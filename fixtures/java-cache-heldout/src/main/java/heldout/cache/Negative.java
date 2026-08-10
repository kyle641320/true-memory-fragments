package heldout.cache;
class Negative { @interface Cacheable { String value(); } @Cacheable("decoy") void decoy(){} }
