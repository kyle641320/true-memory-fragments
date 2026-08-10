package heldout.security;
@interface RolesAllowed { String[] value(); }
class Decoy { @RolesAllowed("FAKE") void fake() {} }
