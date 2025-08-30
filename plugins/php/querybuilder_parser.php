<?php
/**
 * QueryBuilder Chain Parser for EspoCRM
 * Captures fluent API chains used for database queries
 */

require_once __DIR__ . '/../../vendor/autoload.php';

use PhpParser\{Node, NodeTraverser, NodeVisitorAbstract, ParserFactory};
use PhpParser\NodeVisitor\NameResolver;

class QueryBuilderChainParser extends NodeVisitorAbstract {
    private $currentMethod = null;
    private $currentClass = null;
    private $namespace = null;
    private $currentFile;
    
    // Store query chains being built
    private $queryChains = [];
    private $currentChainId = 0;
    
    // Results
    private $queries = [];
    private $relationships = [];
    
    public function __construct($filePath) {
        $this->currentFile = $filePath;
    }
    
    public function enterNode(Node $node) {
        // Track context
        if ($node instanceof Node\Stmt\Namespace_) {
            $this->namespace = $node->name ? $node->name->toString() : null;
        }
        
        if ($node instanceof Node\Stmt\Class_) {
            $this->currentClass = [
                'name' => $node->name->toString(),
                'fqn' => $this->namespace ? $this->namespace . '\\' . $node->name->toString() : $node->name->toString()
            ];
        }
        
        if ($node instanceof Node\Stmt\ClassMethod) {
            $this->currentMethod = [
                'name' => $node->name->toString(),
                'class' => $this->currentClass ? $this->currentClass['fqn'] : null
            ];
        }
        
        // Detect QueryBuilder/Repository chains
        if ($node instanceof Node\Expr\MethodCall) {
            $this->detectQueryChain($node);
        }
        
        // Detect getRepository calls
        if ($node instanceof Node\Expr\MethodCall) {
            $methodName = $node->name instanceof Node\Identifier ? $node->name->toString() : null;
            
            if (in_array($methodName, ['getRepository', 'getQueryBuilder', 'getRelation'])) {
                $this->startQueryChain($node);
            }
        }
    }
    
    private function detectQueryChain($node) {
        $methodName = $node->name instanceof Node\Identifier ? $node->name->toString() : null;
        
        // Query methods to track
        $queryMethods = [
            'where', 'whereClause', 'having', 'havingClause',
            'order', 'orderBy', 'order', 'sortBy',
            'limit', 'offset', 'skip', 'take',
            'distinct', 'groupBy', 'group',
            'join', 'leftJoin', 'innerJoin', 'rightJoin',
            'select', 'from', 'into',
            'find', 'findOne', 'findById', 'findFirst',
            'count', 'exists', 'max', 'min', 'sum', 'avg',
            'build', 'getSql', 'execute',
            'relate', 'unrelate', 'massRelate',
            'get', 'set', 'save', 'delete', 'remove'
        ];
        
        if (!in_array($methodName, $queryMethods)) {
            return;
        }
        
        // Build the chain by traversing up
        $chain = $this->buildChainFromNode($node);
        
        if (count($chain) > 1) {
            // This is a query chain!
            $this->recordQueryChain($chain, $node);
        }
    }
    
    private function buildChainFromNode($node, $chain = []) {
        // Add current method to chain
        if ($node instanceof Node\Expr\MethodCall) {
            $methodName = $node->name instanceof Node\Identifier ? $node->name->toString() : '__dynamic__';
            
            // Extract arguments for important methods
            $args = [];
            if (in_array($methodName, ['where', 'whereClause', 'select', 'from', 'join', 'order', 'limit'])) {
                $args = $this->extractArguments($node);
            }
            
            array_unshift($chain, [
                'method' => $methodName,
                'args' => $args,
                'line' => $node->getLine()
            ]);
            
            // Traverse up the chain
            if ($node->var instanceof Node\Expr\MethodCall) {
                return $this->buildChainFromNode($node->var, $chain);
            }
            
            // Check if it starts with a repository/entity manager
            if ($node->var instanceof Node\Expr\PropertyFetch) {
                $propName = $node->var->name instanceof Node\Identifier ? $node->var->name->toString() : null;
                if (in_array($propName, ['entityManager', 'repository', 'queryBuilder'])) {
                    array_unshift($chain, [
                        'method' => '__' . $propName,
                        'args' => [],
                        'line' => $node->var->getLine()
                    ]);
                }
            }
        }
        
        return $chain;
    }
    
    private function extractArguments($node) {
        $args = [];
        
        foreach ($node->args as $arg) {
            if ($arg->value instanceof Node\Scalar\String_) {
                $args[] = ['type' => 'string', 'value' => $arg->value->value];
            } elseif ($arg->value instanceof Node\Scalar\LNumber) {
                $args[] = ['type' => 'int', 'value' => $arg->value->value];
            } elseif ($arg->value instanceof Node\Expr\Array_) {
                $args[] = ['type' => 'array', 'value' => $this->extractArrayValues($arg->value)];
            } elseif ($arg->value instanceof Node\Expr\Variable) {
                $args[] = ['type' => 'variable', 'value' => '$' . $arg->value->name];
            } else {
                $args[] = ['type' => 'other', 'value' => '__complex__'];
            }
        }
        
        return $args;
    }
    
    private function extractArrayValues($arrayNode) {
        $values = [];
        
        foreach ($arrayNode->items as $item) {
            if (!$item) continue;
            
            $key = null;
            $value = null;
            
            // Extract key
            if ($item->key instanceof Node\Scalar\String_) {
                $key = $item->key->value;
            } elseif ($item->key instanceof Node\Scalar\LNumber) {
                $key = $item->key->value;
            }
            
            // Extract value
            if ($item->value instanceof Node\Scalar\String_) {
                $value = $item->value->value;
            } elseif ($item->value instanceof Node\Scalar\LNumber) {
                $value = $item->value->value;
            } elseif ($item->value instanceof Node\Expr\ConstFetch) {
                $value = $item->value->name->toString();
            } else {
                $value = '__complex__';
            }
            
            if ($key !== null) {
                $values[$key] = $value;
            } else {
                $values[] = $value;
            }
        }
        
        return $values;
    }
    
    private function recordQueryChain($chain, $node) {
        $chainId = 'qc_' . md5(json_encode($chain) . $this->currentChainId++);
        
        // Determine query type
        $queryType = $this->determineQueryType($chain);
        
        // Extract entity if possible
        $entity = $this->extractEntity($chain);
        
        // Extract conditions
        $conditions = $this->extractConditions($chain);
        
        // Create query node
        $query = [
            'id' => $chainId,
            'type' => $queryType,
            'entity' => $entity,
            'chain' => $chain,
            'conditions' => $conditions,
            'method_count' => count($chain),
            'file' => $this->currentFile,
            'line' => $node->getLine(),
            'in_method' => $this->currentMethod ? $this->currentMethod['name'] : null,
            'in_class' => $this->currentClass ? $this->currentClass['fqn'] : null
        ];
        
        $this->queries[] = $query;
        
        // Create relationship from method to query
        if ($this->currentMethod) {
            $methodId = md5($this->currentMethod['class'] . '::' . $this->currentMethod['name']);
            
            $this->relationships[] = [
                'type' => 'EXECUTES_QUERY',
                'source_id' => $methodId,
                'target_id' => $chainId,
                'query_type' => $queryType,
                'entity' => $entity
            ];
        }
    }
    
    private function determineQueryType($chain) {
        $lastMethod = end($chain);
        
        $typeMap = [
            'find' => 'SELECT_MULTIPLE',
            'findOne' => 'SELECT_ONE',
            'findFirst' => 'SELECT_ONE',
            'findById' => 'SELECT_BY_ID',
            'count' => 'COUNT',
            'exists' => 'EXISTS',
            'save' => 'SAVE',
            'delete' => 'DELETE',
            'remove' => 'DELETE',
            'relate' => 'RELATE',
            'unrelate' => 'UNRELATE',
            'massRelate' => 'MASS_RELATE',
            'build' => 'BUILD_QUERY',
            'getSql' => 'GET_SQL',
            'execute' => 'EXECUTE'
        ];
        
        return $typeMap[$lastMethod['method']] ?? 'QUERY';
    }
    
    private function extractEntity($chain) {
        foreach ($chain as $step) {
            // Look for getRepository('Entity')
            if ($step['method'] === 'getRepository' && !empty($step['args'])) {
                if ($step['args'][0]['type'] === 'string') {
                    return $step['args'][0]['value'];
                }
            }
            
            // Look for from('Entity')
            if ($step['method'] === 'from' && !empty($step['args'])) {
                if ($step['args'][0]['type'] === 'string') {
                    return $step['args'][0]['value'];
                }
            }
        }
        
        return null;
    }
    
    private function extractConditions($chain) {
        $conditions = [];
        
        foreach ($chain as $step) {
            if ($step['method'] === 'where' || $step['method'] === 'whereClause') {
                if (!empty($step['args']) && $step['args'][0]['type'] === 'array') {
                    $conditions = array_merge($conditions, array_keys($step['args'][0]['value']));
                }
            }
        }
        
        return array_unique($conditions);
    }
    
    private function startQueryChain($node) {
        // Mark the start of a potential query chain
        // This helps track repository/entity manager usage
        if ($node->args && $node->args[0]->value instanceof Node\Scalar\String_) {
            $entity = $node->args[0]->value->value;
            
            if ($this->currentMethod) {
                $methodId = md5($this->currentMethod['class'] . '::' . $this->currentMethod['name']);
                
                $this->relationships[] = [
                    'type' => 'QUERIES_ENTITY',
                    'source_id' => $methodId,
                    'target_entity' => $entity,
                    'line' => $node->getLine()
                ];
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
    
    public function getResult() {
        return [
            'queries' => $this->queries,
            'relationships' => $this->relationships,
            'file' => $this->currentFile,
            'stats' => [
                'total_queries' => count($this->queries),
                'unique_entities' => count(array_unique(array_column($this->queries, 'entity'))),
                'query_types' => array_count_values(array_column($this->queries, 'type'))
            ]
        ];
    }
}

// Main parser function
function parseQueryChains($filePath) {
    try {
        $code = file_get_contents($filePath);
        $parser = (new ParserFactory())->createForNewestSupportedVersion();
        $stmts = $parser->parse($code);
        
        $traverser = new NodeTraverser();
        $traverser->addVisitor(new NameResolver());
        
        $chainParser = new QueryBuilderChainParser($filePath);
        $traverser->addVisitor($chainParser);
        
        $traverser->traverse($stmts);
        
        return $chainParser->getResult();
        
    } catch (Exception $e) {
        return [
            'error' => $e->getMessage(),
            'file' => $filePath
        ];
    }
}

// CLI usage
if (isset($argv[1])) {
    $result = parseQueryChains($argv[1]);
    echo json_encode($result, JSON_PRETTY_PRINT);
}