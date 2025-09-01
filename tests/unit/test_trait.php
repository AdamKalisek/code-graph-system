<?php
namespace Test;

trait LoggerTrait {
    public function log($message) {
        echo $message;
    }
}

trait TimestampTrait {
    public function getTimestamp() {
        return time();
    }
}

class MyClass {
    use LoggerTrait;
    use TimestampTrait;
    
    public function doSomething() {
        $this->log("Doing something");
        return $this->getTimestamp();
    }
}