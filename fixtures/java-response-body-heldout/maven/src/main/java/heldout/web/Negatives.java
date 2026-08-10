package heldout.web;
import org.springframework.web.bind.annotation.*;
@ResponseBody class WildcardImport {}
class WrongTargets { @ResponseBody void method() {} void local(){ @ResponseBody class Local {} } }
@ResponseBody(names="cart") class Metadata {}
@ResponseBody record WrongRecord() {}
