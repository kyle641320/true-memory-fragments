package heldout.web;
import static org.springframework.web.bind.annotation.CrossOrigin;
@CrossOrigin class StaticImport {}
class WrongTargets { @CrossOrigin void method() {} void local(){ @CrossOrigin class Local {} } }
@CrossOrigin(types=Object.class) class Metadata {}
@CrossOrigin record WrongRecord() {}
