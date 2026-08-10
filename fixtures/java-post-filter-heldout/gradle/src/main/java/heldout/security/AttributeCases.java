package heldout.security;
import org.springframework.security.access.prepost.PostFilter;
class AttributeCases {
 static final String TARGET = "items";
 @PostFilter(value = "x", filterTarget = TARGET) void constantTarget() {}
 @PostFilter(value = "x", filterTarget = "${target}") void placeholderTarget() {}
 @PostFilter(value = "x", unknown = "items") void unknownAttribute() {}
 @PostFilter(value = "x", value = "y") void duplicateValue() {}
 @PostFilter(value = "x", filterTarget = "a", filterTarget = "b") void duplicateTarget() {}
}
