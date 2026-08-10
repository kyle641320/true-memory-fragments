package heldout.web;
import org.springframework.web.bind.annotation.*;
@CrossOrigin class WildcardImport {}
class WrongTargets { @CrossOrigin void method() {} void local(){ @CrossOrigin class Local {} } }
@CrossOrigin(names="cart") class Metadata {}
@CrossOrigin record WrongRecord() {}
