package heldout.security;
import org.springframework.security.access.prepost.PreFilter;
class AttributeCases {
 static final String TARGET = "items";
 @PreFilter(value = "x", filterTarget = TARGET) void constantTarget() {}
 @PreFilter(value = "x", filterTarget = "${target}") void placeholderTarget() {}
 @PreFilter(value = "x", unknown = "items") void unknownAttribute() {}
 @PreFilter(value = "x", value = "y") void duplicateValue() {}
 @PreFilter(value = "x", filterTarget = "a", filterTarget = "b") void duplicateTarget() {}
}
