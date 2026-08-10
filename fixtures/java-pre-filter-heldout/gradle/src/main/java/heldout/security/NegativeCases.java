package heldout.security;
class NegativeCases {
 @interface PreFilter { String value(); }
 @PreFilter("decoy") void decoy() {}
}
