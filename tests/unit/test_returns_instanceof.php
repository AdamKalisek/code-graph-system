<?php

namespace Test\EdgeTypes;

use App\Models\User;
use App\Services\PaymentService;
use App\Contracts\PaymentInterface;

class EdgeTypeTest
{
    private User $user;
    
    // Test RETURNS with simple type
    public function getString(): string 
    {
        return "test";
    }
    
    // Test RETURNS with nullable type
    public function getNullableUser(): ?User 
    {
        return $this->user;
    }
    
    // Test RETURNS with union types (PHP 8+)
    public function getStringOrInt(): string|int 
    {
        return random_int(0, 1) ? "string" : 42;
    }
    
    // Test RETURNS with intersection types (PHP 8.1+)
    public function getIterableCountable(): \Traversable&\Countable
    {
        return new \ArrayIterator([]);
    }
    
    // Test RETURNS with void
    public function doNothing(): void 
    {
        // Nothing to return
    }
    
    // Test INSTANCEOF with simple check
    public function checkInstance($object): bool 
    {
        if ($object instanceof User) {
            return true;
        }
        
        return false;
    }
    
    // Test INSTANCEOF with union check
    public function checkMultipleTypes($service): string 
    {
        if ($service instanceof PaymentService) {
            return "payment";
        } elseif ($service instanceof PaymentInterface) {
            return "interface";
        }
        
        return "unknown";
    }
    
    // Test complex method with multiple edge types
    public function processPayment(?PaymentInterface $payment): User|PaymentService|null
    {
        // INSTANCEOF check
        if ($payment instanceof PaymentService) {
            // CALLS
            $result = $payment->process();
            
            // ACCESSES
            return $this->user;
        }
        
        // RETURNS union type
        return null;
    }
}