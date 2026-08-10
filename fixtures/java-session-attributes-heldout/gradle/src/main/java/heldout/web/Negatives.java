package heldout.web;
import static org.springframework.web.bind.annotation.SessionAttributes;
@SessionAttributes class StaticImport {}
class WrongTargets { @SessionAttributes void method() {} void local(){ @SessionAttributes class Local {} } }
@SessionAttributes(types=Object.class) class Metadata {}
@SessionAttributes record WrongRecord() {}
