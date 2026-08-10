package heldout.restcontroller.negative;

import org.springframework.web.bind.annotation.RestController;

class WrongTarget {
    @RestController void memberTarget() {}
}
