package heldout.web;
import org.springframework.web.bind.annotation.*;
@SessionAttributes class WildcardImport {}
class WrongTargets { @SessionAttributes void method() {} void local(){ @SessionAttributes class Local {} } }
@SessionAttributes(names="cart") class Metadata {}
@SessionAttributes record WrongRecord() {}
