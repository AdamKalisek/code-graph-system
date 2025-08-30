<?php
/**
 * Enhanced PHP AST Parser using nikic/php-parser
 * Extracts ALL relationships: CALLS, IMPORTS, ACCESSES, and more
 */

require_once __DIR__ . '/../../vendor/autoload.php';

use PhpParser\{Node, NodeTraverser, NodeVisitorAbstract, ParserFactory};
use PhpParser\NodeVisitor\NameResolver;

/**
 * Enhanced visitor that extracts all relationship types
 */
class EnhancedGraphExtractor extends NodeVisitorAbstract {
    // Context tracking
    private $namespace = null;
    private $currentClass = null;
    private $currentMethod = null;
    private $currentFile;
    private $currentFileId;
    
    // Node storage
    private $nodes = [];
    private $relationships = [];
    
    // Relationship storage
    private $calls = [];
    private $imports = [];
    private $accesses = [];
    private $instantiates = [];
    private $throws = [];
    private $events = [];
    
    public function __construct($filePath) {
        $this->currentFile = $filePath;
        $this->currentFileId = md5($filePath);
    }
    
    public function enterNode(Node $node) {
        // Track context
        if ($node instanceof Node\Stmt\Namespace_) {
            $this->namespace = $node->name ? $node->name->toString() : null;
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
            
            // Handle extends
            if ($node->extends) {
                $parentFqn = $this->resolveClassName($node->extends);
                $this->relationships[] = [
                    'type' => 'EXTENDS',
                    'source_id' => $this->currentClass['id'],
                    'target_id' => md5($parentFqn),
                    'target_fqn' => $parentFqn
                ];
            }
            
            // Handle implements
            foreach ($node->implements as $interface) {
                $interfaceFqn = $this->resolveClassName($interface);
                $this->relationships[] = [
                    'type' => 'IMPLEMENTS',
                    'source_id' => $this->currentClass['id'],
                    'target_id' => md5($interfaceFqn),
                    'target_fqn' => $interfaceFqn
                ];
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
                'is_abstract' => $node->isAbstract(),
                'is_final' => $node->isFinal(),
                'line' => $node->getLine(),
                'file_path' => $this->currentFile,
                'return_type' => $this->getReturnType($node)
            ];
            
            $this->nodes[] = $this->currentMethod;
            
            $this->relationships[] = [
                'type' => 'HAS_METHOD',
                'source_id' => $this->currentClass['id'],
                'target_id' => $this->currentMethod['id']
            ];
        }
        
        // Handle properties
        if ($node instanceof Node\Stmt\Property && $this->currentClass) {
            foreach ($node->props as $prop) {
                $propFqn = $this->currentClass['fqn'] . '::$' . $prop->name->toString();
                $property = [
                    'id' => md5($propFqn),
                    'name' => '$' . $prop->name->toString(),
                    'fqn' => $propFqn,
                    'qualified_name' => $propFqn,
                    'kind' => 'property',
                    'visibility' => $this->getVisibility($node),
                    'is_static' => $node->isStatic(),
                    'line' => $node->getLine(),
                    'file_path' => $this->currentFile
                ];
                
                $this->nodes[] = $property;
                
                $this->relationships[] = [
                    'type' => 'HAS_PROPERTY',
                    'source_id' => $this->currentClass['id'],
                    'target_id' => $property['id']
                ];
            }
        }
        
        // === NEW: IMPORTS RELATIONSHIPS ===
        if ($node instanceof Node\Stmt\Use_) {
            foreach ($node->uses as $use) {
                $importedFqn = $use->name->toString();
                $alias = $use->alias ? $use->alias->toString() : null;
                
                $this->imports[] = [
                    'type' => 'IMPORTS',
                    'source_id' => $this->currentFileId,
                    'source_file' => $this->currentFile,
                    'target_id' => md5($importedFqn),
                    'target_fqn' => $importedFqn,
                    'alias' => $alias,
                    'line' => $node->getLine()
                ];
            }
        }
        
        if ($node instanceof Node\Stmt\GroupUse) {
            $prefix = $node->prefix->toString();
            foreach ($node->uses as $use) {
                $importedFqn = $prefix . '\\' . $use->name->toString();
                $alias = $use->alias ? $use->alias->toString() : null;
                
                $this->imports[] = [
                    'type' => 'IMPORTS',
                    'source_id' => $this->currentFileId,
                    'source_file' => $this->currentFile,
                    'target_id' => md5($importedFqn),
                    'target_fqn' => $importedFqn,
                    'alias' => $alias,
                    'line' => $node->getLine()
                ];
            }
        }
        
        if ($node instanceof Node\Expr\Include_) {
            if ($node->expr instanceof Node\Scalar\String_) {
                $this->imports[] = [
                    'type' => 'REQUIRES',
                    'source_file' => $this->currentFile,
                    'target_file' => $node->expr->value,
                    'include_type' => $this->getIncludeType($node),
                    'line' => $node->getLine()
                ];
            }
        }
        
        // === NEW: CALLS RELATIONSHIPS ===
        if ($this->currentMethod) {
            // Method calls: $obj->method()
            if ($node instanceof Node\Expr\MethodCall) {
                $methodName = $node->name instanceof Node\Identifier 
                    ? $node->name->toString() 
                    : '__dynamic__';
                
                $targetClass = '__unknown__';
                if ($node->var instanceof Node\Expr\Variable) {
                    if ($node->var->name === 'this' && $this->currentClass) {
                        $targetClass = $this->currentClass['fqn'];
                    }
                }
                
                $targetFqn = $targetClass . '::' . $methodName;
                $this->calls[] = [
                    'type' => 'CALLS',
                    'source_id' => $this->currentMethod['id'],
                    'target_id' => md5($targetFqn),
                    'target_method' => $methodName,
                    'target_class' => $targetClass,
                    'target_fqn' => $targetFqn,
                    'line' => $node->getLine()
                ];
            }
            
            // Static calls: Class::method()
            if ($node instanceof Node\Expr\StaticCall) {
                $className = $node->class instanceof Node\Name
                    ? $this->resolveClassName($node->class)
                    : '__dynamic__';
                    
                $methodName = $node->name instanceof Node\Identifier
                    ? $node->name->toString()
                    : '__dynamic__';
                
                $targetFqn = $className . '::' . $methodName;
                $this->calls[] = [
                    'type' => 'CALLS',
                    'source_id' => $this->currentMethod['id'],
                    'target_id' => md5($targetFqn),
                    'target_fqn' => $targetFqn,
                    'is_static' => true,
                    'line' => $node->getLine()
                ];
            }
            
            // Function calls: functionName()
            if ($node instanceof Node\Expr\FuncCall) {
                if ($node->name instanceof Node\Name) {
                    $funcName = $node->name->toString();
                    $this->calls[] = [
                        'type' => 'CALLS',
                        'source_id' => $this->currentMethod['id'],
                        'target_id' => md5($funcName),
                        'target_function' => $funcName,
                        'line' => $node->getLine()
                    ];
                }
            }
            
            // === NEW: INSTANTIATES RELATIONSHIPS ===
            if ($node instanceof Node\Expr\New_) {
                if ($node->class instanceof Node\Name) {
                    $className = $this->resolveClassName($node->class);
                    $this->instantiates[] = [
                        'type' => 'INSTANTIATES',
                        'source_id' => $this->currentMethod['id'],
                        'target_id' => md5($className),
                        'target_class' => $className,
                        'line' => $node->getLine()
                    ];
                }
            }
            
            // === NEW: ACCESSES RELATIONSHIPS ===
            // Property reads (not in assignment)
            if ($node instanceof Node\Expr\PropertyFetch && !$this->isAssignmentTarget($node)) {
                $this->handlePropertyAccess($node, 'READS');
            }
            
            // Property writes (in assignment)
            if ($node instanceof Node\Expr\Assign) {
                if ($node->var instanceof Node\Expr\PropertyFetch) {
                    $this->handlePropertyAccess($node->var, 'WRITES');
                }
                if ($node->var instanceof Node\Expr\StaticPropertyFetch) {
                    $this->handleStaticPropertyAccess($node->var, 'WRITES');
                }
            }
            
            // Static property access
            if ($node instanceof Node\Expr\StaticPropertyFetch && !$this->isAssignmentTarget($node)) {
                $this->handleStaticPropertyAccess($node, 'READS');
            }
            
            // === NEW: THROWS RELATIONSHIPS ===
            if ($node instanceof Node\Expr\Throw_) {
                if ($node->expr instanceof Node\Expr\New_ && $node->expr->class instanceof Node\Name) {
                    $exceptionClass = $this->resolveClassName($node->expr->class);
                    $this->throws[] = [
                        'type' => 'THROWS',
                        'source_id' => $this->currentMethod['id'],
                        'target_id' => md5($exceptionClass),
                        'exception_class' => $exceptionClass,
                        'line' => $node->getLine()
                    ];
                }
            }
            
            // === NEW: EVENT RELATIONSHIPS (EspoCRM specific) ===
            if ($node instanceof Node\Expr\MethodCall) {
                $methodName = $node->name instanceof Node\Identifier ? $node->name->toString() : null;
                
                // Detect event triggers
                if (in_array($methodName, ['trigger', 'emit', 'dispatch'])) {
                    if (isset($node->args[0]) && $node->args[0]->value instanceof Node\Scalar\String_) {
                        $eventName = $node->args[0]->value->value;
                        $this->events[] = [
                            'type' => 'EMITS',
                            'source_id' => $this->currentMethod['id'],
                            'event_name' => $eventName,
                            'line' => $node->getLine()
                        ];
                    }
                }
                
                // Detect event listeners
                if (in_array($methodName, ['on', 'listenTo', 'addEventListener'])) {
                    if (isset($node->args[0]) && $node->args[0]->value instanceof Node\Scalar\String_) {
                        $eventName = $node->args[0]->value->value;
                        $this->events[] = [
                            'type' => 'LISTENS',
                            'source_id' => $this->currentMethod['id'],
                            'event_name' => $eventName,
                            'line' => $node->getLine()
                        ];
                    }
                }
            }
        }
    }
    
    public function leaveNode(Node $node) {
        if ($node instanceof Node\Stmt\Class_) {
            $this->currentClass = null;
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
            return $node->toString();
        }
        return '__unknown__';
    }
    
    private function getVisibility($node) {
        if ($node->isPublic()) return 'public';
        if ($node->isProtected()) return 'protected';
        if ($node->isPrivate()) return 'private';
        return 'public';
    }
    
    private function getReturnType($node) {
        if ($node->returnType) {
            if ($node->returnType instanceof Node\Name) {
                return $this->resolveClassName($node->returnType);
            }
            if ($node->returnType instanceof Node\Identifier) {
                return $node->returnType->toString();
            }
        }
        return null;
    }
    
    private function getIncludeType($node) {
        switch ($node->type) {
            case Node\Expr\Include_::TYPE_INCLUDE: return 'include';
            case Node\Expr\Include_::TYPE_INCLUDE_ONCE: return 'include_once';
            case Node\Expr\Include_::TYPE_REQUIRE: return 'require';
            case Node\Expr\Include_::TYPE_REQUIRE_ONCE: return 'require_once';
            default: return 'unknown';
        }
    }
    
    private function isAssignmentTarget($node) {
        // Check if node is the target of an assignment
        // This is simplified - would need parent tracking for accuracy
        return false;
    }
    
    private function handlePropertyAccess($node, $accessType) {
        if ($node->var instanceof Node\Expr\Variable && $node->var->name === 'this') {
            $propName = $node->name instanceof Node\Identifier
                ? $node->name->toString()
                : '__dynamic__';
            
            if ($this->currentClass) {
                $targetProperty = $this->currentClass['fqn'] . '::$' . $propName;
                $this->accesses[] = [
                    'type' => $accessType,
                    'source_id' => $this->currentMethod['id'],
                    'target_id' => md5($targetProperty),
                    'target_property' => $targetProperty,
                    'line' => $node->getLine()
                ];
            }
        }
    }
    
    private function handleStaticPropertyAccess($node, $accessType) {
        $className = $node->class instanceof Node\Name
            ? $this->resolveClassName($node->class)
            : '__dynamic__';
            
        $propName = $node->name instanceof Node\VarLikeIdentifier
            ? $node->name->toString()
            : '__dynamic__';
        
        $targetProperty = $className . '::$' . $propName;
        $this->accesses[] = [
            'type' => $accessType,
            'source_id' => $this->currentMethod['id'],
            'target_id' => md5($targetProperty),
            'target_property' => $targetProperty,
            'is_static' => true,
            'line' => $node->getLine()
        ];
    }
    
    public function getResult() {
        // Merge all relationships
        foreach ($this->calls as $call) {
            $this->relationships[] = $call;
        }
        foreach ($this->imports as $import) {
            $this->relationships[] = $import;
        }
        foreach ($this->accesses as $access) {
            $this->relationships[] = $access;
        }
        foreach ($this->instantiates as $inst) {
            $this->relationships[] = $inst;
        }
        foreach ($this->throws as $throw) {
            $this->relationships[] = $throw;
        }
        foreach ($this->events as $event) {
            $this->relationships[] = $event;
        }
        
        return [
            'nodes' => $this->nodes,
            'relationships' => $this->relationships,
            'file' => $this->currentFile
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
        
        // Use our enhanced extractor
        $extractor = new EnhancedGraphExtractor($filePath);
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