package heldout.security;
class NegativeCases {
 @interface PostFilter { String value(); }
 @PostFilter("decoy") void decoy() {}
}
