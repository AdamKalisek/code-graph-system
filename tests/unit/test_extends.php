<?php
namespace Test;

class BaseClass {
    public function baseMethod() {
        return "base";
    }
}

class ChildClass extends BaseClass {
    public function childMethod() {
        return "child";
    }
}

class GrandChild extends ChildClass {
    public function grandMethod() {
        return "grand";
    }
}