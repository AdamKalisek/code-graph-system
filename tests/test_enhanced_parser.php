<?php
/**
 * Test file for enhanced PHP parser
 * Tests CALLS, IMPORTS, ACCESSES, and other relationships
 */

namespace Test\Sample;

// Test IMPORTS relationships
use Espo\Core\Application;
use Espo\Core\Container;
use Espo\Entities\User;
use Espo\Services\{Email, Record as RecordService};

require_once 'vendor/autoload.php';
include 'config.php';

class TestClass extends BaseClass implements TestInterface {
    
    private $container;
    protected $user;
    public static $instance;
    
    /**
     * Test constructor with instantiation
     */
    public function __construct(Container $container) {
        $this->container = $container;
        
        // Test INSTANTIATES relationship
        $this->user = new User();
        
        // Test parent call
        parent::__construct();
    }
    
    /**
     * Test various method calls
     */
    public function testMethodCalls() {
        // Test instance method call on $this
        $this->doSomething();
        
        // Test static method call
        self::staticMethod();
        static::lateStaticMethod();
        
        // Test method call on object
        $this->user->getName();
        
        // Test chained calls
        $this->getContainer()
            ->get('entityManager')
            ->getRepository('User');
        
        // Test function call
        json_encode(['test' => true]);
        file_get_contents('test.txt');
    }
    
    /**
     * Test property access patterns
     */
    public function testPropertyAccess() {
        // Test READS
        $value = $this->container;
        $name = $this->user->name;
        $static = self::$instance;
        
        // Test WRITES
        $this->container = null;
        $this->user->email = 'test@example.com';
        self::$instance = $this;
        
        // Test array access
        $this->data['key'] = 'value';
        $val = $this->data['key'];
    }
    
    /**
     * Test exception throwing
     */
    public function testExceptions() {
        if (!$this->user) {
            // Test THROWS relationship
            throw new \RuntimeException('User not found');
        }
        
        try {
            $this->riskyOperation();
        } catch (\Exception $e) {
            throw new \LogicException('Operation failed', 0, $e);
        }
    }
    
    /**
     * Test event handling (EspoCRM patterns)
     */
    public function testEvents() {
        // Test EMITS
        $this->trigger('before-save', ['entity' => $this->user]);
        $this->emit('user.created', $this->user);
        
        // Test LISTENS
        $this->listenTo($this->user, 'change', function() {
            // Handle change
        });
        
        $this->on('app:ready', [$this, 'onAppReady']);
    }
    
    /**
     * Test dynamic calls
     */
    public function testDynamicCalls() {
        $method = 'dynamicMethod';
        $this->$method();
        
        $class = 'DynamicClass';
        $class::staticCall();
        
        $callback = [$this, 'callbackMethod'];
        call_user_func($callback);
    }
    
    /**
     * Static method for testing
     */
    public static function staticMethod() {
        // Test static context
        self::$instance = new self();
        return static::$instance;
    }
    
    /**
     * Private helper method
     */
    private function doSomething() {
        return true;
    }
    
    protected function getContainer() {
        return $this->container;
    }
}