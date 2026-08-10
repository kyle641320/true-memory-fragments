package heldout.web;
import static org.springframework.web.bind.annotation.ResponseBody;
@ResponseBody class StaticImport {}
class WrongTargets { @ResponseBody void method() {} void local(){ @ResponseBody class Local {} } }
@ResponseBody(types=Object.class) class Metadata {}
@ResponseBody record WrongRecord() {}
