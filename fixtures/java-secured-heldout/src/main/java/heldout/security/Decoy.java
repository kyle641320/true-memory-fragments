package heldout.security;
@interface Secured { String[] value(); }
class Decoy { @Secured("ROLE_FAKE") void fake() {} }
