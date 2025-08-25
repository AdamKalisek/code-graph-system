# Refined Architecture - Universal Code Graph System

## Executive Summary

Based on critical analysis from O3, this refined architecture addresses scalability, performance, and real-world viability concerns while maintaining extensibility.

## Core Design Decisions

### 1. Minimum Viable Core (MVC)
Instead of trying to support all languages immediately, we start with:
- **2 Language Plugins**: PHP and JavaScript (for EspoCRM)
- **1 Framework Plugin**: Laravel or Symfony
- **1 System Plugin**: EspoCRM
- **Focus**: Prove the architecture works before expanding

### 2. Federated Graph Approach
Instead of one massive unified graph:
```
┌─────────────────────────────────────────────┐
│            Query Federation Layer            │
├─────────────────────────────────────────────┤
│  PHP Graph  │  JS Graph   │  Python Graph   │
├─────────────────────────────────────────────┤
│             Stitching Layer                  │
├─────────────────────────────────────────────┤
│            Shared Symbol Table               │
└─────────────────────────────────────────────┘
```

Benefits:
- Better performance (language-local queries)
- Easier incremental updates
- Simpler schema management
- On-demand cross-language linking

### 3. Schema Namespacing
Prevent conflicts via strict namespacing:
```yaml
Core Schema:
  core.File
  core.Symbol
  core.Reference
  
Plugin Extensions:
  php.Class (extends core.Symbol)
  php.Trait (extends core.Symbol)
  laravel.Controller (extends php.Class)
  espocrm.Entity (extends core.Symbol)
```

### 4. Streaming Architecture
Instead of loading entire ASTs in memory:
```python
def stream_parse(file_path):
    for chunk in parse_chunks(file_path):
        edges = extract_edges(chunk)
        yield serialize_to_protobuf(edges)
        del chunk  # Free memory immediately
```

### 5. Plugin Sandboxing
Security-first plugin execution:
- Plugins run in separate processes
- Communication via gRPC/protobuf
- Resource limits (CPU, memory, I/O)
- No direct filesystem access

## Implementation Architecture

### Phase 1: Core Framework (Week 1)

#### 1.1 Base Schema Definition
```python
# core/schema.py
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from uuid import UUID
import datetime

@dataclass
class CoreNode:
    """Base node all plugins must extend"""
    id: UUID
    type: str
    name: str
    plugin_id: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = None
    created_at: datetime.datetime = None
    
@dataclass
class File(CoreNode):
    path: str
    language: str
    hash: str
    size: int
    
@dataclass
class Symbol(CoreNode):
    qualified_name: str
    kind: str  # class, function, variable, etc.
    visibility: Optional[str] = None
    source_location: Optional['SourceLocation'] = None
    
@dataclass
class Reference(CoreNode):
    from_symbol: UUID
    to_symbol: UUID
    reference_type: str  # calls, imports, extends, etc.
    line_number: int
    column: int
```

#### 1.2 Plugin Interface
```python
# core/plugin_interface.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Iterator
import grpc

class PluginCapability:
    PARSE = "parse"
    ANALYZE = "analyze"
    TRANSFORM = "transform"
    QUERY = "query"

class IPlugin(ABC):
    """Base plugin interface"""
    
    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Return plugin metadata"""
        pass
    
    @abstractmethod
    def can_handle(self, file_path: str) -> bool:
        """Check if plugin can handle this file"""
        pass
    
    @abstractmethod
    def get_namespace(self) -> str:
        """Return plugin namespace for schema extensions"""
        pass

class ILanguagePlugin(IPlugin):
    """Language-specific parsing plugin"""
    
    @abstractmethod
    def stream_parse(self, file_path: str) -> Iterator[bytes]:
        """Stream parse results as protobuf"""
        pass
    
    @abstractmethod
    def extract_symbols(self, content: str) -> List[Symbol]:
        """Extract symbols from code"""
        pass
    
    @abstractmethod
    def resolve_imports(self, content: str) -> List[str]:
        """Resolve import statements"""
        pass
```

#### 1.3 Plugin Manager
```python
# core/plugin_manager.py
import subprocess
import grpc
from concurrent import futures
from typing import Dict, List, Optional

class PluginProcess:
    """Manages a plugin running in separate process"""
    
    def __init__(self, plugin_path: str):
        self.plugin_path = plugin_path
        self.process = None
        self.channel = None
        self.stub = None
        
    def start(self):
        """Start plugin process"""
        self.process = subprocess.Popen(
            ['python', '-m', 'plugin_runner', self.plugin_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Connect via gRPC
        self.channel = grpc.insecure_channel('localhost:50051')
        self.stub = PluginStub(self.channel)
        
    def stop(self):
        """Stop plugin process"""
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)
        
        if self.channel:
            self.channel.close()

class PluginManager:
    """Manages all plugins"""
    
    def __init__(self):
        self.plugins: Dict[str, PluginProcess] = {}
        self.language_plugins: Dict[str, str] = {}
        self.framework_plugins: Dict[str, str] = {}
        
    def load_plugin(self, plugin_path: str):
        """Load and start a plugin"""
        plugin = PluginProcess(plugin_path)
        plugin.start()
        
        metadata = plugin.stub.GetMetadata()
        plugin_id = metadata['id']
        
        self.plugins[plugin_id] = plugin
        
        # Register by type
        if metadata['type'] == 'language':
            for lang in metadata['languages']:
                self.language_plugins[lang] = plugin_id
        elif metadata['type'] == 'framework':
            for fw in metadata['frameworks']:
                self.framework_plugins[fw] = plugin_id
    
    def get_handler(self, file_path: str) -> Optional[PluginProcess]:
        """Get plugin that can handle this file"""
        # Determine language from extension
        ext = file_path.split('.')[-1]
        language_map = {
            'php': 'php',
            'js': 'javascript',
            'ts': 'typescript',
            'py': 'python'
        }
        
        language = language_map.get(ext)
        if language and language in self.language_plugins:
            plugin_id = self.language_plugins[language]
            return self.plugins[plugin_id]
        
        return None
```

### Phase 2: Graph Engine (Week 2)

#### 2.1 Federated Graph Store
```python
# core/graph_store.py
from py2neo import Graph
from typing import Dict, List, Any
import json

class FederatedGraphStore:
    """Manages multiple language-specific graphs"""
    
    def __init__(self, neo4j_uri: str, auth: tuple):
        self.connection = Graph(neo4j_uri, auth=auth)
        self.language_graphs: Dict[str, str] = {}
        
    def create_language_graph(self, language: str):
        """Create a language-specific subgraph"""
        db_name = f"graph_{language}"
        
        # Create database if not exists
        self.connection.run(f"CREATE DATABASE {db_name} IF NOT EXISTS")
        
        self.language_graphs[language] = db_name
        
        # Create indexes for this language
        with self.connection.begin() as tx:
            tx.run(f"""
                CREATE INDEX {language}_symbol_name IF NOT EXISTS
                FOR (s:Symbol) ON (s.qualified_name)
            """)
            tx.run(f"""
                CREATE INDEX {language}_file_path IF NOT EXISTS
                FOR (f:File) ON (f.path)
            """)
    
    def store_batch(self, language: str, nodes: List[Dict], edges: List[Dict]):
        """Store a batch of nodes and edges"""
        db_name = self.language_graphs.get(language)
        if not db_name:
            self.create_language_graph(language)
            db_name = self.language_graphs[language]
        
        # Switch to language-specific database
        with self.connection.begin() as tx:
            # Batch insert nodes
            tx.run(f"""
                UNWIND $nodes AS node
                CREATE (n:{{node.type}})
                SET n = node.properties
            """, nodes=nodes)
            
            # Batch insert edges
            tx.run(f"""
                UNWIND $edges AS edge
                MATCH (a {{id: edge.from_id}})
                MATCH (b {{id: edge.to_id}})
                CREATE (a)-[r:{{edge.type}}]->(b)
                SET r = edge.properties
            """, edges=edges)
    
    def query_local(self, language: str, query: str, params: Dict = None):
        """Query within a language-specific graph"""
        db_name = self.language_graphs.get(language)
        if not db_name:
            return []
        
        result = self.connection.run(query, params or {})
        return result.data()
    
    def query_federated(self, query: str, params: Dict = None):
        """Query across all language graphs"""
        results = []
        
        for language, db_name in self.language_graphs.items():
            # Execute query in each language graph
            partial_result = self.query_local(language, query, params)
            results.extend(partial_result)
        
        return results
```

#### 2.2 Incremental Update System
```python
# core/incremental.py
import hashlib
from pathlib import Path
from typing import Set, Dict, List
import git

class IncrementalUpdater:
    """Handles incremental updates efficiently"""
    
    def __init__(self, graph_store: FederatedGraphStore, plugin_manager: PluginManager):
        self.graph_store = graph_store
        self.plugin_manager = plugin_manager
        self.file_hashes: Dict[str, str] = {}
        
    def get_changed_files(self, repo_path: str) -> Dict[str, List[str]]:
        """Get files changed since last analysis"""
        repo = git.Repo(repo_path)
        
        changes = {
            'added': [],
            'modified': [],
            'deleted': []
        }
        
        # Get uncommitted changes
        for item in repo.index.diff(None):
            if self.is_relevant_file(item.a_path):
                changes['modified'].append(item.a_path)
        
        # Get untracked files
        for item in repo.untracked_files:
            if self.is_relevant_file(item):
                changes['added'].append(item)
        
        return changes
    
    def update_file(self, file_path: str):
        """Update graph for a single file"""
        # Calculate file hash
        with open(file_path, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        
        # Check if file actually changed
        if self.file_hashes.get(file_path) == file_hash:
            return  # No changes
        
        # Get appropriate plugin
        plugin = self.plugin_manager.get_handler(file_path)
        if not plugin:
            return
        
        # Delete old data
        language = self.detect_language(file_path)
        self.graph_store.query_local(
            language,
            "MATCH (f:File {path: $path})-[r]-() DELETE r, f",
            {'path': file_path}
        )
        
        # Parse and store new data
        nodes = []
        edges = []
        
        for chunk in plugin.stub.StreamParse(file_path):
            data = json.loads(chunk)
            nodes.extend(data.get('nodes', []))
            edges.extend(data.get('edges', []))
            
            # Store in batches to avoid memory issues
            if len(nodes) > 1000:
                self.graph_store.store_batch(language, nodes, edges)
                nodes = []
                edges = []
        
        # Store remaining
        if nodes or edges:
            self.graph_store.store_batch(language, nodes, edges)
        
        # Update hash
        self.file_hashes[file_path] = file_hash
```

### Phase 3: PHP Plugin Implementation (Week 3)

#### 3.1 PHP Language Plugin
```python
# plugins/php/plugin.py
import subprocess
import json
from typing import Iterator, List, Dict
from pathlib import Path

class PHPLanguagePlugin:
    """PHP language support plugin"""
    
    def get_metadata(self) -> Dict:
        return {
            'id': 'php-language',
            'name': 'PHP Language Support',
            'version': '1.0.0',
            'type': 'language',
            'languages': ['php'],
            'namespace': 'php',
            'capabilities': ['parse', 'analyze']
        }
    
    def can_handle(self, file_path: str) -> bool:
        return file_path.endswith('.php')
    
    def stream_parse(self, file_path: str) -> Iterator[bytes]:
        """Parse PHP file and stream results"""
        
        # Use PHP parser via subprocess
        result = subprocess.run(
            ['php', Path(__file__).parent / 'parser.php', file_path],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            yield json.dumps({'error': result.stderr}).encode()
            return
        
        # Parse output and yield in chunks
        ast_data = json.loads(result.stdout)
        
        # Extract nodes
        nodes = []
        for class_data in ast_data.get('classes', []):
            nodes.append({
                'type': 'php.Class',
                'properties': {
                    'id': class_data['id'],
                    'name': class_data['name'],
                    'qualified_name': class_data['fqcn'],
                    'namespace': class_data['namespace'],
                    'is_abstract': class_data.get('is_abstract', False),
                    'is_final': class_data.get('is_final', False)
                }
            })
        
        # Extract edges
        edges = []
        for class_data in ast_data.get('classes', []):
            if class_data.get('extends'):
                edges.append({
                    'type': 'EXTENDS',
                    'from_id': class_data['id'],
                    'to_id': class_data['extends'],
                    'properties': {}
                })
            
            for interface in class_data.get('implements', []):
                edges.append({
                    'type': 'IMPLEMENTS',
                    'from_id': class_data['id'],
                    'to_id': interface,
                    'properties': {}
                })
        
        # Yield in chunks
        chunk_size = 100
        for i in range(0, len(nodes), chunk_size):
            chunk_nodes = nodes[i:i+chunk_size]
            chunk_edges = edges[i:i+chunk_size]
            
            yield json.dumps({
                'nodes': chunk_nodes,
                'edges': chunk_edges
            }).encode()
```

#### 3.2 PHP Parser Implementation
```php
<?php
// plugins/php/parser.php

require_once __DIR__ . '/vendor/autoload.php';

use PhpParser\ParserFactory;
use PhpParser\NodeTraverser;
use PhpParser\NodeVisitorAbstract;
use PhpParser\Node;

class ClassExtractor extends NodeVisitorAbstract {
    public $classes = [];
    public $currentNamespace = '';
    
    public function enterNode(Node $node) {
        if ($node instanceof Node\Stmt\Namespace_) {
            $this->currentNamespace = $node->name->toString();
        }
        
        if ($node instanceof Node\Stmt\Class_) {
            $classData = [
                'id' => uniqid('php_class_'),
                'name' => $node->name->toString(),
                'fqcn' => $this->currentNamespace . '\\' . $node->name->toString(),
                'namespace' => $this->currentNamespace,
                'is_abstract' => $node->isAbstract(),
                'is_final' => $node->isFinal(),
                'extends' => null,
                'implements' => [],
                'methods' => [],
                'properties' => []
            ];
            
            if ($node->extends) {
                $classData['extends'] = $node->extends->toString();
            }
            
            foreach ($node->implements as $interface) {
                $classData['implements'][] = $interface->toString();
            }
            
            // Extract methods
            foreach ($node->stmts as $stmt) {
                if ($stmt instanceof Node\Stmt\ClassMethod) {
                    $classData['methods'][] = [
                        'name' => $stmt->name->toString(),
                        'visibility' => $this->getVisibility($stmt),
                        'is_static' => $stmt->isStatic(),
                        'is_abstract' => $stmt->isAbstract()
                    ];
                }
                
                if ($stmt instanceof Node\Stmt\Property) {
                    $classData['properties'][] = [
                        'name' => $stmt->props[0]->name->toString(),
                        'visibility' => $this->getVisibility($stmt),
                        'is_static' => $stmt->isStatic()
                    ];
                }
            }
            
            $this->classes[] = $classData;
        }
    }
    
    private function getVisibility($node) {
        if ($node->isPublic()) return 'public';
        if ($node->isProtected()) return 'protected';
        if ($node->isPrivate()) return 'private';
        return 'public';
    }
}

// Main execution
$filePath = $argv[1] ?? '';
if (!file_exists($filePath)) {
    echo json_encode(['error' => 'File not found']);
    exit(1);
}

$code = file_get_contents($filePath);
$parser = (new ParserFactory)->create(ParserFactory::PREFER_PHP7);

try {
    $ast = $parser->parse($code);
    
    $traverser = new NodeTraverser();
    $extractor = new ClassExtractor();
    $traverser->addVisitor($extractor);
    $traverser->traverse($ast);
    
    echo json_encode([
        'file' => $filePath,
        'classes' => $extractor->classes
    ]);
} catch (Exception $e) {
    echo json_encode(['error' => $e->getMessage()]);
    exit(1);
}
```

### Phase 4: CLI Implementation (Week 4)

```python
# cli.py
import click
import yaml
from pathlib import Path
from core.plugin_manager import PluginManager
from core.graph_store import FederatedGraphStore
from core.incremental import IncrementalUpdater

@click.group()
def cli():
    """Universal Code Graph System CLI"""
    pass

@cli.command()
@click.argument('path')
@click.option('--config', default='config.yaml', help='Configuration file')
@click.option('--incremental/--full', default=True, help='Incremental or full analysis')
def analyze(path, config, incremental):
    """Analyze a codebase"""
    # Load configuration
    with open(config) as f:
        cfg = yaml.safe_load(f)
    
    # Initialize components
    plugin_manager = PluginManager()
    graph_store = FederatedGraphStore(
        cfg['neo4j']['uri'],
        (cfg['neo4j']['username'], cfg['neo4j']['password'])
    )
    
    # Load plugins
    for plugin_path in cfg['plugins']['enabled']:
        plugin_manager.load_plugin(plugin_path)
    
    if incremental:
        # Incremental update
        updater = IncrementalUpdater(graph_store, plugin_manager)
        changes = updater.get_changed_files(path)
        
        click.echo(f"Found {len(changes['modified'])} modified files")
        
        with click.progressbar(changes['modified']) as files:
            for file in files:
                updater.update_file(file)
    else:
        # Full analysis
        files = list(Path(path).rglob('*.php')) + list(Path(path).rglob('*.js'))
        
        click.echo(f"Analyzing {len(files)} files...")
        
        with click.progressbar(files) as file_list:
            for file in file_list:
                plugin = plugin_manager.get_handler(str(file))
                if plugin:
                    # Parse and store
                    for chunk in plugin.stub.StreamParse(str(file)):
                        data = json.loads(chunk)
                        language = file.suffix[1:]  # Remove dot
                        graph_store.store_batch(
                            language,
                            data.get('nodes', []),
                            data.get('edges', [])
                        )
    
    click.echo("Analysis complete!")

@cli.command()
@click.option('--target', required=True, help='Target symbol for impact analysis')
@click.option('--depth', default=3, help='Analysis depth')
def impact(target, depth):
    """Analyze impact of changing a symbol"""
    # Query implementation
    click.echo(f"Analyzing impact of {target} with depth {depth}")

if __name__ == '__main__':
    cli()
```

## Configuration

```yaml
# config.yaml
neo4j:
  uri: bolt://localhost:7688
  username: neo4j
  password: password123

plugins:
  enabled:
    - ./plugins/php
    - ./plugins/javascript
    - ./plugins/espocrm
  
  directories:
    - ./plugins/builtin
    - ~/.cgs/plugins

analysis:
  parallel_workers: 8
  batch_size: 1000
  stream_chunk_size: 100
  
  exclude:
    - "vendor/"
    - "node_modules/"
    - ".git/"
    - "*.test.php"
    - "*.spec.js"

federation:
  mode: per-language  # or 'unified'
  cross_language_linking: on-demand
  
security:
  plugin_sandboxing: true
  resource_limits:
    memory_mb: 512
    cpu_percent: 50
    timeout_seconds: 30
```

## Next Steps

### Immediate (Today)
1. Set up Python project structure
2. Implement core schema
3. Create plugin interface
4. Build basic PHP parser

### This Week
1. Complete PHP plugin
2. Add JavaScript plugin
3. Implement federated graph store
4. Create CLI interface

### Next Week
1. Add EspoCRM system plugin
2. Implement incremental updates
3. Add cross-language linking
4. Performance testing

### Future
1. Plugin marketplace
2. Web UI for queries
3. IDE integrations
4. Cloud hosting option

## Benefits of Refined Architecture

1. **Practical**: Starts with MVP, proves concept before scaling
2. **Performant**: Federated graphs, streaming, proper sharding
3. **Secure**: Process isolation, resource limits
4. **Maintainable**: Clear separation, namespace isolation
5. **Extensible**: Plugin system allows community contributions
6. **Real-world Ready**: Addresses actual pain points from O3's analysis