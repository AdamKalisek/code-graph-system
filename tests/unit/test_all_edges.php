<?php
namespace Test\EdgeDetection;

// IMPORTS edges - Various import patterns
use Exception;
use InvalidArgumentException;
use RuntimeException as Runtime;
use App\Models\User;
use App\Services\EmailService;
use App\Repositories\UserRepository as UserRepo;
use App\Traits\LoggerTrait;
use App\Interfaces\PaymentInterface;

// Base class for EXTENDS testing
abstract class BaseController {
    protected const STATUS_ACTIVE = 'active';
    protected const STATUS_INACTIVE = 'inactive';
    
    public function baseMethod() {
        return "base";
    }
}

// Interface for IMPLEMENTS testing
interface PaymentInterface {
    public function processPayment($amount);
    public function refund($transactionId);
}

// Trait for USES_TRAIT testing
trait LoggerTrait {
    public function log($message) {
        echo "[LOG] " . $message;
    }
}

trait TimestampTrait {
    public function getTimestamp() {
        return time();
    }
}

// Main test class demonstrating all edge types
class PaymentController extends BaseController implements PaymentInterface {
    // USES_TRAIT edges
    use LoggerTrait;
    use TimestampTrait;
    
    // Properties for ACCESSES edges
    private User $user;
    private EmailService $emailService;
    private UserRepo $repository;
    
    // Constants for USES_CONSTANT edges
    public const PAYMENT_PENDING = 'pending';
    public const PAYMENT_SUCCESS = 'success';
    public const PAYMENT_FAILED = 'failed';
    
    // Constructor with PARAMETER_TYPE edges
    public function __construct(
        User $user,
        EmailService $emailService,
        UserRepo $repository
    ) {
        // ACCESSES edges - property assignments
        $this->user = $user;
        $this->emailService = $emailService;
        $this->repository = $repository;
    }
    
    // Method with RETURNS edge
    public function getUser(): User {
        return $this->user;
    }
    
    // IMPLEMENTS edge - implementing interface method
    public function processPayment($amount) {
        // CALLS edge - calling trait method
        $this->log("Processing payment of $amount");
        
        // USES_CONSTANT edges - using class constants
        $status = self::PAYMENT_PENDING;
        
        // THROWS edge - throwing exception
        if ($amount <= 0) {
            throw new InvalidArgumentException("Amount must be positive");
        }
        
        try {
            // INSTANTIATES edge - creating new instance
            $transaction = new Transaction();
            
            // CALLS edge - method call
            $result = $this->validatePayment($amount);
            
            // CALLS_STATIC edge - static method call
            $fee = PaymentCalculator::calculateFee($amount);
            
            // ACCESSES edge - property access
            $userEmail = $this->user->email;
            
            // CALLS edge - calling service method
            $this->emailService->sendPaymentNotification($userEmail, $amount);
            
            // USES_CONSTANT edge - using parent class constant
            if ($this->user->status === parent::STATUS_ACTIVE) {
                $status = self::PAYMENT_SUCCESS;
            }
            
        } catch (RuntimeException $e) {
            // THROWS edge - re-throwing exception
            throw new Exception("Payment failed: " . $e->getMessage());
        }
        
        // INSTANCEOF edge - type checking
        if ($this->user instanceof User) {
            // CALLS edge - repository method call
            $this->repository->save($this->user);
        }
        
        return $status;
    }
    
    // IMPLEMENTS edge - implementing interface method
    public function refund($transactionId) {
        // THROWS edge - different exception
        if (empty($transactionId)) {
            throw new Runtime("Transaction ID required");
        }
        
        // USES_CONSTANT edge - using external class constant
        $maxRetries = PaymentConfig::MAX_RETRIES;
        
        return true;
    }
    
    private function validatePayment($amount): bool {
        // CALLS edge - calling parent method
        $this->baseMethod();
        
        // USES_CONSTANT edge - switch with constants
        switch ($this->getPaymentStatus()) {
            case self::PAYMENT_PENDING:
                return true;
            case self::PAYMENT_FAILED:
                return false;
            default:
                return $amount > 0;
        }
    }
    
    private function getPaymentStatus(): string {
        return self::PAYMENT_PENDING;
    }
}

// Helper classes for testing
class Transaction {
    public $id;
    public $amount;
}

class PaymentCalculator {
    public static function calculateFee($amount) {
        return $amount * 0.03;
    }
}

class PaymentConfig {
    public const MAX_RETRIES = 3;
    public const TIMEOUT = 30;
}

// Test function with THROWS edge
function processOrder($orderId) {
    if (!$orderId) {
        throw new Exception("Order ID is required");
    }
    
    // INSTANTIATES edge in function context
    $controller = new PaymentController(
        new User(),
        new EmailService(),
        new UserRepo()
    );
    
    return $controller->processPayment(100);
}