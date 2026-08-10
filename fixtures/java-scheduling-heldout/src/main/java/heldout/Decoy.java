package heldout;
@interface Scheduled { long fixedRate(); }
class Decoy { @Scheduled(fixedRate=1) void decoy() {} }
