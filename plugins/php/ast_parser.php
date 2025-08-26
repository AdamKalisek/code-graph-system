<?php
/**
 * PHP AST Parser using nikic/php-parser
 * Extracts classes, methods, properties, traits, interfaces with relationships
 */

require_once __DIR__ . '/../../vendor/autoload.php';

use PhpParser\Error;
use PhpParser\NodeDumper;
use PhpParser\ParserFactory;
use PhpParser\Node;
use PhpParser\NodeVisitorAbstract;
use PhpParser\NodeTraverser;

class GraphNodeExtractor extends NodeVisitorAbstract {
    private $namespace = null;
    private $currentClass = null;
    private $nodes = [];
    private $relationships = [];
    private $filePath;
    
    public function __construct($filePath) {
        $this->filePath = $filePath;
    }
    
    public function enterNode(Node $node) {
        // Handle namespace
        if ($node instanceof Node\Stmt\Namespace_) {
            $this->namespace = $node->name->toString();
        }
        
        // Handle classes
        if ($node instanceof Node\Stmt\Class_) {
            $fqn = $this->namespace ? 
                $this->namespace . '\\' . $node->name->toString() : 
                $node->name->toString();
                
            $this->currentClass = [
                'id' => md5($fqn),
                'name' => $node->name->toString(),
                'fqn' => $fqn,
                'qualified_name' => $fqn,
                'kind' => 'class',
                'is_abstract' => $node->isAbstract(),
                'is_final' => $node->isFinal(),
                'line' => $node->getLine(),
                'file_path' => $this->filePath,
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
        
        // Handle interfaces
        if ($node instanceof Node\Stmt\Interface_) {
            $fqn = $this->namespace ? 
                $this->namespace . '\\' . $node->name->toString() : 
                $node->name->toString();
                
            $interface = [
                'id' => md5($fqn),
                'name' => $node->name->toString(),
                'fqn' => $fqn,
                'qualified_name' => $fqn,
                'kind' => 'interface',
                'line' => $node->getLine(),
                'file_path' => $this->filePath,
                'namespace' => $this->namespace
            ];
            
            $this->nodes[] = $interface;
            
            // Handle interface inheritance
            foreach ($node->extends as $parent) {
                $parentFqn = $this->resolveClassName($parent);
                $this->relationships[] = [
                    'type' => 'EXTENDS',
                    'source_id' => $interface['id'],
                    'target_id' => md5($parentFqn),
                    'target_fqn' => $parentFqn
                ];
            }
        }
        
        // Handle traits
        if ($node instanceof Node\Stmt\Trait_) {
            $fqn = $this->namespace ? 
                $this->namespace . '\\' . $node->name->toString() : 
                $node->name->toString();
                
            $trait = [
                'id' => md5($fqn),
                'name' => $node->name->toString(),
                'fqn' => $fqn,
                'qualified_name' => $fqn,
                'kind' => 'trait',
                'line' => $node->getLine(),
                'file_path' => $this->filePath,
                'namespace' => $this->namespace
            ];
            
            $this->nodes[] = $trait;
            $this->currentClass = $trait; // Treat as class for methods
        }
        
        // Handle methods
        if ($node instanceof Node\Stmt\ClassMethod && $this->currentClass) {
            $methodFqn = $this->currentClass['fqn'] . '::' . $node->name->toString();
            $method = [
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
                'file_path' => $this->filePath,
                'return_type' => $this->getReturnType($node)
            ];
            
            $this->nodes[] = $method;
            
            $this->relationships[] = [
                'type' => 'HAS_METHOD',
                'source_id' => $this->currentClass['id'],
                'target_id' => $method['id']
            ];
        }
        
        // Handle properties
        if ($node instanceof Node\Stmt\Property && $this->currentClass) {
            foreach ($node->props as $prop) {
                $propFqn = $this->currentClass['fqn'] . '::$' . $prop->name->toString();
                $property = [
                    'id' => md5($propFqn),
                    'name' => $prop->name->toString(),
                    'fqn' => $propFqn,
                    'qualified_name' => $propFqn,
                    'kind' => 'property',
                    'visibility' => $this->getVisibility($node),
                    'is_static' => $node->isStatic(),
                    'is_readonly' => $node->isReadonly(),
                    'line' => $node->getLine(),
                    'file_path' => $this->filePath,
                    'type' => $this->getPropertyType($node)
                ];
                
                $this->nodes[] = $property;
                
                $this->relationships[] = [
                    'type' => 'HAS_PROPERTY',
                    'source_id' => $this->currentClass['id'],
                    'target_id' => $property['id']
                ];
            }
        }
        
        // Handle trait use
        if ($node instanceof Node\Stmt\TraitUse && $this->currentClass) {
            foreach ($node->traits as $trait) {
                $traitFqn = $this->resolveClassName($trait);
                $this->relationships[] = [
                    'type' => 'USES_TRAIT',
                    'source_id' => $this->currentClass['id'],
                    'target_id' => md5($traitFqn),
                    'target_fqn' => $traitFqn
                ];
            }
        }
    }
    
    public function leaveNode(Node $node) {
        // Reset current class when leaving class/interface/trait
        if ($node instanceof Node\Stmt\Class_ || 
            $node instanceof Node\Stmt\Trait_ ||
            $node instanceof Node\Stmt\Interface_) {
            $this->currentClass = null;
        }
    }
    
    private function resolveClassName($name) {
        if ($name instanceof Node\Name\FullyQualified) {
            return $name->toString();
        }
        if ($this->namespace && !($name instanceof Node\Name\FullyQualified)) {
            // Check if it's a relative name
            if ($name instanceof Node\Name\Relative) {
                return $this->namespace . '\\' . $name->toString();
            }
            // For unqualified names, prepend namespace
            return $this->namespace . '\\' . $name->toString();
        }
        return $name->toString();
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
            if ($node->returnType instanceof Node\NullableType) {
                return '?' . $this->getReturnType((object)['returnType' => $node->returnType->type]);
            }
            if ($node->returnType instanceof Node\UnionType) {
                $types = [];
                foreach ($node->returnType->types as $type) {
                    if ($type instanceof Node\Name) {
                        $types[] = $this->resolveClassName($type);
                    } elseif ($type instanceof Node\Identifier) {
                        $types[] = $type->toString();
                    }
                }
                return implode('|', $types);
            }
        }
        return null;
    }
    
    private function getPropertyType($node) {
        if ($node->type) {
            if ($node->type instanceof Node\Name) {
                return $this->resolveClassName($node->type);
            }
            if ($node->type instanceof Node\Identifier) {
                return $node->type->toString();
            }
            if ($node->type instanceof Node\NullableType) {
                return '?' . $this->getPropertyType((object)['type' => $node->type->type]);
            }
        }
        return null;
    }
    
    public function getNodes() {
        return $this->nodes;
    }
    
    public function getRelationships() {
        return $this->relationships;
    }
}

// Main execution
if ($argc < 2) {
    echo "Usage: php ast_parser.php <file_path>\n";
    exit(1);
}

$filePath = $argv[1];

if (!file_exists($filePath)) {
    echo json_encode(['error' => "File not found: $filePath"]);
    exit(1);
}

$code = file_get_contents($filePath);

$parser = (new ParserFactory())->createForNewestSupportedVersion();

try {
    $ast = $parser->parse($code);
    
    $traverser = new NodeTraverser;
    $extractor = new GraphNodeExtractor($filePath);
    $traverser->addVisitor($extractor);
    $traverser->traverse($ast);
    
    echo json_encode([
        'nodes' => $extractor->getNodes(),
        'relationships' => $extractor->getRelationships()
    ], JSON_PRETTY_PRINT);
    
} catch (Error $error) {
    echo json_encode(['error' => $error->getMessage()]);
}