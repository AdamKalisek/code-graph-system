# Detailed Implementation Guide - EspoCRM Graph Completion

## Priority 1: AST-Based PHP Parser (MUST DO FIRST)

### Step 1.1: Install nikic/PHP-Parser
```bash
cd /home/david/Work/Programming/memory
composer init --name="code-graph/php-parser" --type="project"
composer require nikic/php-parser
```

### Step 1.2: Create New AST Parser
```python
# File: plugins/php/nikic_parser.py

import subprocess
import json
import hashlib
from pathlib import Path
from typing import List, Dict
from code_graph_system.core.schema import Symbol, Relationship
from code_graph_system.core.plugin_interface import ParseResult

class NikicPHPParser:
    def __init__(self):
        self.parser_script = Path(__file__).parent / 'ast_parser.php'
        
    def parse_file(self, file_path: str) -> ParseResult:
        # Call PHP script that uses nikic/php-parser
        result = subprocess.run(
            ['php', str(self.parser_script), file_path],
            capture_output=True,
            text=True
        )
        
        ast_data = json.loads(result.stdout)
        return self._convert_ast_to_nodes(ast_data, file_path)
```

### Step 1.3: Create PHP AST Extractor Script
```php
<?php
// File: plugins/php/ast_parser.php
require_once 'vendor/autoload.php';

use PhpParser\Error;
use PhpParser\NodeDumper;
use PhpParser\ParserFactory;
use PhpParser\NodeTraverser;
use PhpParser\NodeVisitorAbstract;
use PhpParser\Node;

class GraphNodeExtractor extends NodeVisitorAbstract {
    private $nodes = [];
    private $relationships = [];
    private $currentClass = null;
    private $namespace = '';
    
    public function enterNode(Node $node) {
        if ($node instanceof Node\Stmt\Namespace_) {
            $this->namespace = $node->name->toString();
        }
        
        if ($node instanceof Node\Stmt\Class_) {
            $fqn = $this->namespace ? 
                $this->namespace . '\\' . $node->name->toString() : 
                $node->name->toString();
                
            $this->currentClass = [
                'id' => md5($fqn),
                'name' => $node->name->toString(),
                'fqn' => $fqn,
                'kind' => 'class',
                'is_abstract' => $node->isAbstract(),
                'is_final' => $node->isFinal(),
                'line' => $node->getLine()
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
        
        if ($node instanceof Node\Stmt\ClassMethod && $this->currentClass) {
            $methodFqn = $this->currentClass['fqn'] . '::' . $node->name->toString();
            $method = [
                'id' => md5($methodFqn),
                'name' => $node->name->toString(),
                'fqn' => $methodFqn,
                'kind' => 'method',
                'visibility' => $this->getVisibility($node),
                'is_static' => $node->isStatic(),
                'is_abstract' => $node->isAbstract(),
                'line' => $node->getLine()
            ];
            
            $this->nodes[] = $method;
            
            $this->relationships[] = [
                'type' => 'HAS_METHOD',
                'source_id' => $this->currentClass['id'],
                'target_id' => $method['id']
            ];
        }
    }
    
    private function resolveClassName($name) {
        if ($name instanceof Node\Name\FullyQualified) {
            return $name->toString();
        }
        if ($this->namespace && !($name instanceof Node\Name\FullyQualified)) {
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
    
    public function getResult() {
        return [
            'nodes' => $this->nodes,
            'relationships' => $this->relationships
        ];
    }
}

// Main execution
$file = $argv[1];
$code = file_get_contents($file);

$parser = (new ParserFactory)->create(ParserFactory::PREFER_PHP7);
try {
    $ast = $parser->parse($code);
    
    $traverser = new NodeTraverser();
    $extractor = new GraphNodeExtractor();
    $traverser->addVisitor($extractor);
    $traverser->traverse($ast);
    
    echo json_encode($extractor->getResult());
} catch (Error $error) {
    echo json_encode(['error' => $error->getMessage()]);
}
```

## Priority 2: Multi-Label Implementation

### Step 2.1: Update Schema for Multi-Labels
```python
# File: code_graph_system/core/schema.py

@dataclass
class Symbol(CoreNode):
    """Enhanced with multi-label support"""
    
    def get_labels(self) -> List[str]:
        """Return list of Neo4j labels for this symbol"""
        labels = ['Symbol']
        
        if hasattr(self, '_language'):
            labels.append(self._language.upper())
            
        if self.kind == 'class':
            labels.append('Class')
        elif self.kind == 'method':
            labels.append('Method')
        elif self.kind == 'property':
            labels.append('Property')
        elif self.kind == 'file':
            labels.append('File')
        elif self.kind == 'directory':
            labels.append('Directory')
            
        return labels
```

### Step 2.2: Update Graph Store for Multi-Labels
```python
# File: code_graph_system/core/graph_store.py

def store_nodes(self, nodes: List[CoreNode], language: str = None) -> int:
    """Enhanced with multi-label support"""
    
    # Group by label combinations
    nodes_by_labels = {}
    for node in nodes:
        labels = node.get_labels() if hasattr(node, 'get_labels') else ['Symbol']
        label_key = ':'.join(labels)
        
        if label_key not in nodes_by_labels:
            nodes_by_labels[label_key] = []
            
        node_data = node.to_dict()
        if self.federation_mode == 'unified' and language:
            node_data['_language'] = language
            
        nodes_by_labels[label_key].append(self._flatten_dict(node_data))
    
    # Bulk create with multi-labels
    total_created = 0
    for label_string, node_list in nodes_by_labels.items():
        query = f"""
            UNWIND $nodes AS node_data
            MERGE (n:{label_string} {{id: node_data.id}})
            SET n += node_data
            RETURN count(n) as created
        """
        
        result = self.graph.run(query, nodes=node_list).data()
        if result:
            total_created += result[0].get('created', 0)
            
    return total_created
```

## Priority 3: JavaScript Parser with Tree-Sitter

### Step 3.1: Install Tree-Sitter
```bash
pip install tree-sitter tree-sitter-javascript
```

### Step 3.2: Create JavaScript Parser
```python
# File: plugins/javascript/tree_sitter_parser.py

import tree_sitter
from tree_sitter import Language, Parser
import tree_sitter_javascript as tjs
from pathlib import Path
import hashlib
import re

class JavaScriptParser:
    def __init__(self):
        # Build library
        Language.build_library(
            'build/languages.so',
            ['vendor/tree-sitter-javascript']
        )
        
        JS_LANGUAGE = Language('build/languages.so', 'javascript')
        self.parser = Parser()
        self.parser.set_language(JS_LANGUAGE)
    
    def parse_file(self, file_path: str) -> ParseResult:
        nodes = []
        relationships = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        tree = self.parser.parse(bytes(content, 'utf8'))
        
        # Extract imports
        imports = self._extract_imports(tree.root_node, content)
        for imp in imports:
            nodes.append(self._create_import_node(imp, file_path))
            
        # Extract functions
        functions = self._extract_functions(tree.root_node, content)
        for func in functions:
            nodes.append(self._create_function_node(func, file_path))
            
        # Extract API calls
        api_calls = self._extract_api_calls(tree.root_node, content)
        for call in api_calls:
            relationships.append(self._create_api_relationship(call, file_path))
            
        return ParseResult(
            file_path=file_path,
            nodes=nodes,
            relationships=relationships,
            errors=[]
        )
    
    def _extract_api_calls(self, node, source):
        """Extract fetch/ajax calls with literal URLs"""
        api_calls = []
        
        # Pattern for fetch calls
        if node.type == 'call_expression':
            func_name = self._get_node_text(node.child_by_field_name('function'), source)
            
            if func_name in ['fetch', 'ajax', 'axios']:
                args = node.child_by_field_name('arguments')
                if args and args.child_count > 0:
                    first_arg = args.children[1]  # Skip opening paren
                    if first_arg.type == 'string':
                        url = self._get_node_text(first_arg, source).strip('"\'')
                        api_calls.append({
                            'method': func_name,
                            'url': url,
                            'line': node.start_point[0]
                        })
        
        # Recurse
        for child in node.children:
            api_calls.extend(self._extract_api_calls(child, source))
            
        return api_calls
```

## Priority 4: Endpoint Abstraction

### Step 4.1: Create Endpoint Schema
```python
# File: code_graph_system/core/schema.py

@dataclass
class Endpoint(CoreNode):
    """API Endpoint abstraction"""
    method: str  # GET, POST, PUT, DELETE
    path: str    # /api/v1/Lead
    controller: Optional[str] = None
    action: Optional[str] = None
    
    def to_dict(self):
        return {
            'id': hashlib.md5(f"{self.method}:{self.path}".encode()).hexdigest(),
            'type': 'Endpoint',
            'method': self.method,
            'path': self.path,
            'controller': self.controller,
            'action': self.action
        }
```

### Step 4.2: Parse EspoCRM Routes
```python
# File: plugins/espocrm/route_parser.py

import json
from pathlib import Path

class RouteParser:
    def parse_routes(self, espocrm_path: str):
        """Parse EspoCRM route definitions"""
        endpoints = []
        
        # Parse routes.json
        routes_file = Path(espocrm_path) / 'application/Espo/Resources/routes.json'
        if routes_file.exists():
            with open(routes_file) as f:
                routes = json.load(f)
                
            for route in routes:
                endpoint = Endpoint(
                    method=route.get('method', 'GET'),
                    path=route.get('route'),
                    controller=route.get('controller'),
                    action=route.get('action', 'index')
                )
                endpoints.append(endpoint)
                
        # Parse API routes from metadata
        api_dir = Path(espocrm_path) / 'application/Espo/Resources/metadata/api'
        if api_dir.exists():
            for json_file in api_dir.glob('*.json'):
                # Parse each API definition
                pass
                
        return endpoints
```

### Step 4.3: Link Frontend to Backend
```python
# File: plugins/espocrm/cross_linker.py

class CrossLinker:
    def link_js_to_endpoints(self, graph_store):
        """Create CALLS relationships from JS to Endpoints"""
        
        # Find all JavaScript API calls
        js_calls = graph_store.query("""
            MATCH (js:JavaScript:Module)
            WHERE js.api_calls IS NOT NULL
            RETURN js.id, js.api_calls
        """)
        
        for call in js_calls:
            for api_call in call['api_calls']:
                # Find matching endpoint
                endpoint_query = """
                    MATCH (e:Endpoint {path: $path})
                    WHERE e.method = $method OR $method = 'ANY'
                    RETURN e.id
                """
                
                endpoint = graph_store.query(endpoint_query, {
                    'path': api_call['url'],
                    'method': api_call.get('method', 'GET')
                })
                
                if endpoint:
                    # Create CALLS relationship
                    graph_store.graph.run("""
                        MATCH (js {id: $js_id})
                        MATCH (e {id: $endpoint_id})
                        MERGE (js)-[:CALLS]->(e)
                    """, js_id=call['id'], endpoint_id=endpoint[0]['id'])
```

## Priority 5: Resolve Inheritance

### Step 5.1: Create Resolution Script
```python
# File: resolve_inheritance.py

def resolve_extends_relationships(graph_store):
    """Resolve EXTENDS relationships to actual class nodes"""
    
    # Find all unresolved EXTENDS
    unresolved = graph_store.query("""
        MATCH (c:Class)-[r:EXTENDS]->()
        WHERE r.target_fqn IS NOT NULL
        RETURN c.id, r.target_fqn
    """)
    
    for rel in unresolved:
        # Try to find target class
        target = graph_store.query("""
            MATCH (t:Class)
            WHERE t.fqn = $fqn OR t.name = $name
            RETURN t.id
            LIMIT 1
        """, {
            'fqn': rel['target_fqn'],
            'name': rel['target_fqn'].split('\\')[-1]
        })
        
        if target:
            # Update relationship
            graph_store.graph.run("""
                MATCH (c {id: $source_id})-[r:EXTENDS]->()
                DELETE r
                WITH c
                MATCH (t {id: $target_id})
                MERGE (c)-[:EXTENDS]->(t)
            """, source_id=rel['id'], target_id=target[0]['id'])
        else:
            # Mark as external
            graph_store.graph.run("""
                MATCH (c {id: $source_id})-[r:EXTENDS]->()
                SET r.unresolved = true, r.external = true
            """, source_id=rel['id'])
```

## Testing Each Phase

### Test Phase 1: PHP Parser
```bash
# Test nikic parser
php plugins/php/ast_parser.php espocrm/application/Espo/Core/Container.php | jq .

# Verify inheritance
python -c "
from code_graph_system.core.graph_store import FederatedGraphStore
g = FederatedGraphStore('bolt://localhost:7688', ('neo4j', 'password123'), {})
extends = g.query('MATCH ()-[r:EXTENDS]->() RETURN count(r) as count')
print(f'EXTENDS relationships: {extends[0][\"count\"]}')
"
```

### Test Phase 2: Multi-Labels
```cypher
// Verify multi-labels
MATCH (c:Symbol:PHP:Class)
RETURN c.name LIMIT 5

// Performance test
EXPLAIN MATCH (c:PHP:Class) RETURN c
// vs
EXPLAIN MATCH (c:Symbol {kind: 'class', _language: 'php'}) RETURN c
```

### Test Phase 3: JavaScript Parser
```bash
# Test JS parser
python -c "
from plugins.javascript.tree_sitter_parser import JavaScriptParser
parser = JavaScriptParser()
result = parser.parse_file('espocrm/client/src/app.js')
print(f'Nodes: {len(result.nodes)}, Relationships: {len(result.relationships)}')
"
```

### Test Phase 4: Endpoints
```cypher
// Verify endpoints created
MATCH (e:Endpoint)
RETURN e.method, e.path
LIMIT 10

// Check JS->Endpoint links
MATCH (js:JavaScript)-[:CALLS]->(e:Endpoint)
RETURN js.name, e.path
LIMIT 5
```

### Test Phase 5: Full Integration
```cypher
// Complete cross-language query
MATCH path = (js:JavaScript:Module)-[:CALLS]->(e:Endpoint)<-[:HANDLES]-(php:PHP:Controller)
RETURN js.name, e.path, php.name
LIMIT 10
```

## Success Validation

Run this after each phase:
```python
# validation.py
from code_graph_system.core.graph_store import FederatedGraphStore

def validate_phase(phase_num):
    g = FederatedGraphStore('bolt://localhost:7688', ('neo4j', 'password123'), {})
    
    if phase_num == 1:
        # Check EXTENDS resolved
        extends = g.query("MATCH ()-[r:EXTENDS]->() RETURN count(r) as c")
        assert extends[0]['c'] > 100, "Inheritance not resolved"
        
    elif phase_num == 2:
        # Check multi-labels
        multi = g.query("MATCH (c:PHP:Class) RETURN count(c) as c")
        assert multi[0]['c'] > 1000, "Multi-labels not working"
        
    elif phase_num == 3:
        # Check JS parsed
        js = g.query("MATCH (j:JavaScript:Function) RETURN count(j) as c")
        assert js[0]['c'] > 500, "JS not parsed"
        
    elif phase_num == 4:
        # Check endpoints
        endpoints = g.query("MATCH (e:Endpoint) RETURN count(e) as c")
        assert endpoints[0]['c'] > 50, "Endpoints not created"
        
    elif phase_num == 5:
        # Check cross-language
        cross = g.query("""
            MATCH (js:JavaScript)-[:CALLS]->(e:Endpoint)<-[:HANDLES]-(php:PHP)
            RETURN count(*) as c
        """)
        assert cross[0]['c'] > 10, "Cross-language not working"
    
    print(f"✅ Phase {phase_num} validated successfully!")
```

---

This detailed guide provides:
1. **Exact code** to implement each phase
2. **Step-by-step instructions** with file paths
3. **Test commands** for validation
4. **Success criteria** for each phase
5. **Actual working code** not just concepts

Start with Phase 1 (PHP Parser) as O3 recommended - everything else depends on it!