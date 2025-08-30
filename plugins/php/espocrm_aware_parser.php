<?php
/**
 * EspoCRM-aware PHP Parser
 * Handles dynamic patterns specific to EspoCRM with heuristics and metadata
 */

require_once __DIR__ . '/../../vendor/autoload.php';

use PhpParser\{Node, NodeTraverser, NodeVisitorAbstract, ParserFactory};
use PhpParser\NodeVisitor\NameResolver;

class EspoCRMAwareParser extends NodeVisitorAbstract {
    // Context tracking
    private $namespace = null;
    private $currentClass = null;
    private $currentMethod = null;
    private $currentFile;
    
    // Variable tracking for constant propagation
    private $variableAssignments = [];
    
    // Service map from containerServices.json
    private $serviceMap = [];
    
    // Route definitions from routes.json
    private $routes = [];
    
    // Metadata from EspoCRM
    private $metadata = [];
    
    // Node storage
    private $nodes = [];
    private $relationships = [];
    
    public function __construct($filePath) {
        $this->currentFile = $filePath;
        $this->loadServiceMap();
        $this->loadRoutes();
    }
    
    /**
     * Load EspoCRM service definitions
     */
    private function loadServiceMap() {
        $serviceFile = __DIR__ . '/../../espocrm/application/Espo/Resources/metadata/app/containerServices.json';
        if (file_exists($serviceFile)) {
            $services = json_decode(file_get_contents($serviceFile), true);
            foreach ($services as $name => $config) {
                if (isset($config['className'])) {
                    $this->serviceMap[$name] = $config['className'];
                }
            }
        }
    }
    
    /**
     * Load route definitions
     */
    private function loadRoutes() {
        $routeFile = __DIR__ . '/../../espocrm/application/Espo/Resources/routes.json';
        if (file_exists($routeFile)) {
            $this->routes = json_decode(file_get_contents($routeFile), true);
        }
    }
    
    public function enterNode(Node $node) {
        // Track namespace
        if ($node instanceof Node\Stmt\Namespace_) {
            $this->namespace = $node->name ? $node->name->toString() : null;
        }
        
        // Track variable assignments for constant propagation
        if ($node instanceof Node\Expr\Assign) {
            if ($node->var instanceof Node\Expr\Variable && 
                $node->expr instanceof Node\Scalar\String_) {
                // Track string assignments: $var = 'ClassName'
                $varName = $node->var->name;
                $value = $node->expr->value;
                $this->variableAssignments[$varName] = $value;
            }
        }
        
        // Handle classes
        if ($node instanceof Node\Stmt\Class_) {
            $fqn = $this->buildFQN($node->name->toString());
            $this->currentClass = [
                'id' => md5($fqn),
                'name' => $node->name->toString(),
                'fqn' => $fqn,
                'qualified_name' => $fqn,
                'kind' => 'class',
                'is_abstract' => $node->isAbstract(),
                'is_final' => $node->isFinal(),
                'line' => $node->getLine(),
                'file_path' => $this->currentFile,
                'namespace' => $this->namespace
            ];
            
            $this->nodes[] = $this->currentClass;
            
            // Check if this is a Controller and map routes
            if (strpos($node->name->toString(), 'Controller') !== false) {
                $this->mapRoutesToController($fqn);
            }
        }
        
        // Handle methods
        if ($node instanceof Node\Stmt\ClassMethod && $this->currentClass) {
            $methodFqn = $this->currentClass['fqn'] . '::' . $node->name->toString();
            $this->currentMethod = [
                'id' => md5($methodFqn),
                'name' => $node->name->toString(),
                'fqn' => $methodFqn,
                'qualified_name' => $methodFqn,
                'kind' => 'method',
                'visibility' => $this->getVisibility($node),
                'is_static' => $node->isStatic(),
                'line' => $node->getLine(),
                'file_path' => $this->currentFile
            ];
            
            $this->nodes[] = $this->currentMethod;
            
            $this->relationships[] = [
                'type' => 'HAS_METHOD',
                'source_id' => $this->currentClass['id'],
                'target_id' => $this->currentMethod['id']
            ];
        }
        
        // Enhanced method call handling with heuristics
        if ($this->currentMethod && $node instanceof Node\Expr\MethodCall) {
            $this->handleMethodCall($node);
        }
        
        // Enhanced static call handling
        if ($this->currentMethod && $node instanceof Node\Expr\StaticCall) {
            $this->handleStaticCall($node);
        }
        
        // Enhanced new expression handling with constant propagation
        if ($this->currentMethod && $node instanceof Node\Expr\New_) {
            $this->handleNewExpression($node);
        }
        
        // ACL check detection
        if ($this->currentMethod && $node instanceof Node\Expr\MethodCall) {
            $this->handleAclCheck($node);
        }
        
        // Queue/Job detection
        if ($this->currentMethod && $node instanceof Node\Expr\MethodCall) {
            $this->handleJobQueue($node);
        }
        
        // Handle imports
        if ($node instanceof Node\Stmt\Use_) {
            foreach ($node->uses as $use) {
                $this->relationships[] = [
                    'type' => 'IMPORTS',
                    'source_file' => $this->currentFile,
                    'target_fqn' => $use->name->toString(),
                    'line' => $node->getLine()
                ];
            }
        }
        
        // Handle events (EspoCRM specific)
        if ($this->currentMethod && $node instanceof Node\Expr\MethodCall) {
            $methodName = $node->name instanceof Node\Identifier ? $node->name->toString() : null;
            
            if (in_array($methodName, ['trigger', 'emit', 'dispatch', 'triggerMultiple'])) {
                $this->handleEventEmit($node);
            }
            
            if (in_array($methodName, ['on', 'listenTo', 'listenToOnce', 'stopListening'])) {
                $this->handleEventListen($node);
            }
        }
    }
    
    /**
     * Handle method calls with container resolution
     */
    private function handleMethodCall($node) {
        $methodName = $node->name instanceof Node\Identifier 
            ? $node->name->toString() 
            : '__dynamic__';
        
        // Special handling for container->get() and similar patterns
        if ($methodName === 'get' || $methodName === 'create') {
            if ($node->var instanceof Node\Expr\PropertyFetch) {
                $propName = $node->var->name instanceof Node\Identifier 
                    ? $node->var->name->toString() 
                    : null;
                
                // Check if it's a container/factory call
                if (in_array($propName, ['container', 'injectableFactory', 'entityFactory', 'serviceFactory'])) {
                    $this->handleServiceResolution($node, $propName);
                    return;
                }
            }
        }
        
        // Check for $this->method() calls
        if ($node->var instanceof Node\Expr\Variable && $node->var->name === 'this') {
            $targetFqn = $this->currentClass['fqn'] . '::' . $methodName;
        } else {
            $targetFqn = '__unknown__::' . $methodName;
        }
        
        $this->relationships[] = [
            'type' => 'CALLS',
            'source_id' => $this->currentMethod['id'],
            'target_fqn' => $targetFqn,
            'line' => $node->getLine()
        ];
    }
    
    /**
     * Handle service resolution with DI container
     */
    private function handleServiceResolution($node, $containerType) {
        if (isset($node->args[0]) && $node->args[0]->value instanceof Node\Scalar\String_) {
            $serviceName = $node->args[0]->value->value;
            
            // Try to resolve from service map
            $targetClass = null;
            
            if ($containerType === 'container' && isset($this->serviceMap[$serviceName])) {
                $targetClass = $this->serviceMap[$serviceName];
            } elseif ($containerType === 'entityFactory') {
                // Entity names map to Espo\Entities\{Name}
                $targetClass = 'Espo\\Entities\\' . $serviceName;
            } elseif ($containerType === 'serviceFactory') {
                // Service names map to Espo\Services\{Name}
                $targetClass = 'Espo\\Services\\' . $serviceName;
            } elseif ($containerType === 'injectableFactory' && 
                     $node->args[0]->value instanceof Node\Expr\ClassConstFetch) {
                // Handle ::class constant
                $targetClass = $this->resolveClassName($node->args[0]->value->class);
            }
            
            if ($targetClass) {
                $this->relationships[] = [
                    'type' => 'INSTANTIATES',
                    'source_id' => $this->currentMethod['id'],
                    'target_class' => $targetClass,
                    'via' => $containerType,
                    'line' => $node->getLine()
                ];
            }
        }
    }
    
    /**
     * Handle static calls
     */
    private function handleStaticCall($node) {
        $className = $node->class instanceof Node\Name
            ? $this->resolveClassName($node->class)
            : '__dynamic__';
            
        $methodName = $node->name instanceof Node\Identifier
            ? $node->name->toString()
            : '__dynamic__';
        
        $this->relationships[] = [
            'type' => 'CALLS',
            'source_id' => $this->currentMethod['id'],
            'target_fqn' => $className . '::' . $methodName,
            'is_static' => true,
            'line' => $node->getLine()
        ];
    }
    
    /**
     * Handle new expressions with constant propagation
     */
    private function handleNewExpression($node) {
        $className = null;
        
        if ($node->class instanceof Node\Name) {
            $className = $this->resolveClassName($node->class);
        } elseif ($node->class instanceof Node\Expr\Variable) {
            // Try constant propagation for: $class = 'User'; new $class()
            $varName = $node->class->name;
            if (isset($this->variableAssignments[$varName])) {
                $className = $this->variableAssignments[$varName];
                // Add namespace if needed
                if ($this->namespace && strpos($className, '\\') === false) {
                    $className = $this->namespace . '\\' . $className;
                }
            }
        }
        
        if ($className) {
            $this->relationships[] = [
                'type' => 'INSTANTIATES',
                'source_id' => $this->currentMethod['id'],
                'target_class' => $className,
                'line' => $node->getLine()
            ];
        }
    }
    
    /**
     * Handle event emission
     */
    private function handleEventEmit($node) {
        if (isset($node->args[0]) && $node->args[0]->value instanceof Node\Scalar\String_) {
            $eventName = $node->args[0]->value->value;
            $this->relationships[] = [
                'type' => 'EMITS',
                'source_id' => $this->currentMethod['id'],
                'event_name' => $eventName,
                'line' => $node->getLine()
            ];
        }
    }
    
    /**
     * Handle event listening
     */
    private function handleEventListen($node) {
        $eventName = null;
        
        // For listenTo($entity, 'event', handler)
        if (isset($node->args[1]) && $node->args[1]->value instanceof Node\Scalar\String_) {
            $eventName = $node->args[1]->value->value;
        }
        // For on('event', handler)
        elseif (isset($node->args[0]) && $node->args[0]->value instanceof Node\Scalar\String_) {
            $eventName = $node->args[0]->value->value;
        }
        
        if ($eventName) {
            $this->relationships[] = [
                'type' => 'LISTENS',
                'source_id' => $this->currentMethod['id'],
                'event_name' => $eventName,
                'line' => $node->getLine()
            ];
        }
    }
    
    /**
     * Handle ACL permission checks
     */
    private function handleAclCheck($node) {
        $methodName = $node->name instanceof Node\Identifier 
            ? $node->name->toString() 
            : null;
        
        // Check for ACL methods
        if (in_array($methodName, ['check', 'checkEntity', 'checkScope', 'checkOwnershipOwn', 'checkOwnershipTeam'])) {
            // Check if it's an ACL object
            if ($node->var instanceof Node\Expr\PropertyFetch || 
                $node->var instanceof Node\Expr\MethodCall) {
                
                $permission = null;
                $entity = null;
                $action = null;
                
                // Parse arguments
                if (isset($node->args[0])) {
                    // First arg is usually entity or scope
                    if ($node->args[0]->value instanceof Node\Scalar\String_) {
                        $entity = $node->args[0]->value->value;
                    }
                }
                
                if (isset($node->args[1])) {
                    // Second arg is usually action
                    if ($node->args[1]->value instanceof Node\Scalar\String_) {
                        $action = $node->args[1]->value->value;
                    }
                }
                
                if ($entity && $action) {
                    $permission = $entity . ':' . $action;
                } elseif ($entity) {
                    $permission = $entity;
                }
                
                if ($permission) {
                    $this->relationships[] = [
                        'type' => 'CHECKS_PERMISSION',
                        'source_id' => $this->currentMethod['id'],
                        'permission' => $permission,
                        'method' => $methodName,
                        'line' => $node->getLine()
                    ];
                }
            }
        }
    }
    
    /**
     * Handle job queue operations
     */
    private function handleJobQueue($node) {
        $methodName = $node->name instanceof Node\Identifier 
            ? $node->name->toString() 
            : null;
        
        // Check for queue methods
        if (in_array($methodName, ['push', 'createJob', 'scheduleJob', 'submit'])) {
            // Check for job class name
            if (isset($node->args[0])) {
                $jobClass = null;
                
                if ($node->args[0]->value instanceof Node\Scalar\String_) {
                    $jobClass = $node->args[0]->value->value;
                } elseif ($node->args[0]->value instanceof Node\Expr\ClassConstFetch) {
                    $jobClass = $this->resolveClassName($node->args[0]->value->class);
                }
                
                if ($jobClass) {
                    $this->relationships[] = [
                        'type' => 'QUEUES_JOB',
                        'source_id' => $this->currentMethod['id'],
                        'job_class' => $jobClass,
                        'method' => $methodName,
                        'line' => $node->getLine()
                    ];
                }
            }
        }
    }
    
    /**
     * Map routes to controller methods
     */
    private function mapRoutesToController($controllerFqn) {
        $controllerName = substr($controllerFqn, strrpos($controllerFqn, '\\') + 1);
        $controllerName = str_replace('Controller', '', $controllerName);
        
        foreach ($this->routes as $route) {
            $routeController = null;
            $action = null;
            
            if (isset($route['params']['controller'])) {
                $routeController = $route['params']['controller'];
                $action = $route['params']['action'] ?? 'index';
            } elseif (isset($route['actionClassName'])) {
                // Direct action class mapping
                continue; // Skip for now
            }
            
            if ($routeController === $controllerName) {
                $endpoint = [
                    'id' => md5($route['route'] . ':' . $route['method']),
                    'route' => $route['route'],
                    'method' => strtoupper($route['method']),
                    'kind' => 'endpoint'
                ];
                
                $this->nodes[] = $endpoint;
                
                // Create HANDLES relationship
                $actionMethod = 'action' . ucfirst($action);
                $this->relationships[] = [
                    'type' => 'HANDLES',
                    'source_id' => $endpoint['id'],
                    'target_fqn' => $controllerFqn . '::' . $actionMethod,
                    'http_method' => $route['method']
                ];
            }
        }
    }
    
    public function leaveNode(Node $node) {
        if ($node instanceof Node\Stmt\Class_) {
            $this->currentClass = null;
            // Clear variable assignments when leaving class scope
            $this->variableAssignments = [];
        }
        if ($node instanceof Node\Stmt\ClassMethod) {
            $this->currentMethod = null;
        }
    }
    
    // Helper methods
    private function buildFQN($name) {
        return $this->namespace ? $this->namespace . '\\' . $name : $name;
    }
    
    private function resolveClassName($node) {
        if ($node instanceof Node\Name) {
            if ($node->hasAttribute('resolvedName')) {
                return $node->getAttribute('resolvedName')->toString();
            }
            
            $name = $node->toString();
            
            // Handle relative names
            if ($name === 'self' && $this->currentClass) {
                return $this->currentClass['fqn'];
            }
            if ($name === 'parent') {
                return 'parent'; // Would need inheritance tracking
            }
            
            return $name;
        }
        return '__unknown__';
    }
    
    private function getVisibility($node) {
        if ($node->isPublic()) return 'public';
        if ($node->isProtected()) return 'protected';
        if ($node->isPrivate()) return 'private';
        return 'public';
    }
    
    public function getResult() {
        return [
            'nodes' => $this->nodes,
            'relationships' => $this->relationships,
            'file' => $this->currentFile,
            'service_map_loaded' => count($this->serviceMap) > 0,
            'routes_loaded' => count($this->routes) > 0
        ];
    }
}

// Main parser function
function parseFile($filePath) {
    try {
        $code = file_get_contents($filePath);
        $parser = (new ParserFactory())->createForNewestSupportedVersion();
        $stmts = $parser->parse($code);
        
        // Use NameResolver to resolve names
        $traverser = new NodeTraverser();
        $traverser->addVisitor(new NameResolver());
        
        // Use our EspoCRM-aware parser
        $extractor = new EspoCRMAwareParser($filePath);
        $traverser->addVisitor($extractor);
        
        // Traverse the AST
        $traverser->traverse($stmts);
        
        return $extractor->getResult();
        
    } catch (Exception $e) {
        return [
            'error' => $e->getMessage(),
            'file' => $filePath
        ];
    }
}

// CLI usage
if (isset($argv[1])) {
    $result = parseFile($argv[1]);
    echo json_encode($result, JSON_PRETTY_PRINT);
}