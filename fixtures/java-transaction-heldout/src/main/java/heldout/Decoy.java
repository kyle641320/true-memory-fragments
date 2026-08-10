package heldout;
@interface Transactional { boolean readOnly() default false; }
class Decoy { @Transactional(readOnly=true) void fake() {} }
