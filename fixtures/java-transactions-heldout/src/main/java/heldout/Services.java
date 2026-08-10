package heldout;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.annotation.Propagation;
@Transactional(transactionManager="main", readOnly=true)
class Services {
 @Transactional(propagation=Propagation.REQUIRES_NEW, timeout=30, rollbackFor={java.io.IOException.class}, noRollbackForClassName={"heldout.Ignored"}) void save() {}
 @Transactional(timeout=TIMEOUT) void dynamic() {}
 static final int TIMEOUT=3;
}
