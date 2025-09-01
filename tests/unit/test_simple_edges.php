<?php
namespace Test\Simple;

// Test IMPORTS edge
use Exception;

// Test class with simple exception
class TestException extends Exception {
    const ERROR_CODE = 500;
}

class SimpleTest {
    // Test USES_CONSTANT edge
    public function testConstant() {
        $code = TestException::ERROR_CODE;
        return $code;
    }
    
    // Test THROWS edge
    public function testThrow() {
        throw new TestException("Test error");
    }
    
    // Test THROWS with built-in exception
    public function testBuiltinThrow() {
        throw new Exception("Built-in error");
    }
}