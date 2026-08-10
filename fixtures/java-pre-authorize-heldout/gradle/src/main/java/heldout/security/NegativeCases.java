package heldout.security;
class NegativeCases {
 @interface PreAuthorize { String value(); }
 @PreAuthorize("decoy") void decoy() {}
}
