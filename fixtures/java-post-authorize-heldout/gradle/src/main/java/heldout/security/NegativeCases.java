package heldout.security;
class NegativeCases {
 @interface PostAuthorize { String value(); }
 @PostAuthorize("decoy") void decoy() {}
}
