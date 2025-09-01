# EspoCRM Code Graph Implementation Plan

## Executive Summary

This document outlines a comprehensive plan to create a Neo4j-based code graph for EspoCRM, enabling advanced code analysis, dependency tracking, and impact assessment. The graph will capture both static code relationships and metadata-driven runtime connections.

## Project Goals

### Primary Objectives
1. **Complete Dependency Mapping**: Trace execution paths from frontend actions → API calls → backend processing → database operations
2. **Impact Analysis**: Identify all affected components when changing any code element
3. **Code Quality**: Detect unused code, circular dependencies, and potential security vulnerabilities
4. **Architecture Understanding**: Visualize metadata-driven connections between entities, views, and controllers
5. **Hook Flow Analysis**: Map event chains and side effects

### Success Metrics
- Parse entire codebase (~3000 files) in < 15 seconds
- Incremental updates in < 500ms per file
- Support sub-second impact analysis queries
- Resolve 80%+ of dependency injection calls
- 95%+ accuracy in hook discovery

## Architecture Overview

### Technology Stack
```yaml
Orchestration:
  - Python 3.10+ (main coordinator)
  - ProcessPoolExecutor for parallelization
  
PHP Analysis:
  - nikic/php-parser 5.x (AST generation)
  - Custom visitor patterns for extraction
  
JavaScript Analysis:
  - esbuild with --metafile (dependency graph)
  - @babel/parser for detailed AST when needed
  
Storage:
  - Neo4j 5.x (2025.07.1)
  - CSV bulk import for initial load
  - APOC procedures for batch operations
  
Caching:
  - SQLite for AST cache
  - Redis for service resolution cache (optional)
```

## Graph Schema Design

### Core Node Types

#### PHP Nodes
```cypher
(:PhpFile {
  path: string,
  module: string,
  sha1: string,
  lastParsed: datetime,
  size: integer
})

(:PhpClass {
  name: string,
  fqcn: string,  // Fully Qualified Class Name
  type: 'class' | 'interface' | 'trait' | 'enum',
  isAbstract: boolean,
  isFinal: boolean,
  namespace: string,
  file: string
})

(:PhpMethod {
  name: string,
  class: string,
  signature: string,
  visibility: 'public' | 'protected' | 'private',
  isStatic: boolean,
  isAbstract: boolean,
  returnType: string
})

(:PhpProperty {
  name: string,
  class: string,
  visibility: 'public' | 'protected' | 'private',
  isStatic: boolean,
  type: string
})
```

#### JavaScript Nodes
```cypher
(:JsFile {
  path: string,
  module: string,
  isES6: boolean,
  sha1: string,
  lastParsed: datetime
})

(:JsModule {
  id: string,  // Module identifier
  path: string,
  type: 'es6' | 'amd' | 'commonjs'
})

(:JsClass {
  name: string,
  module: string,
  extends: string,
  isBackboneView: boolean,
  isBackboneModel: boolean
})

(:JsFunction {
  name: string,
  module: string,
  isAsync: boolean,
  isExported: boolean
})
```

#### EspoCRM-Specific Nodes
```cypher
(:Entity {
  name: string,
  module: string,
  hasStream: boolean,
  isCustom: boolean
})

(:Field {
  name: string,
  entity: string,
  type: string,
  required: boolean,
  audited: boolean
})

(:Hook {
  name: string,
  entity: string,
  type: 'beforeSave' | 'afterSave' | 'beforeRemove' | etc,
  order: integer,
  class: string
})

(:Service {
  id: string,  // Service identifier in container
  class: string,  // Implementation class FQCN
  isSingleton: boolean,
  isLazy: boolean
})

(:APIEndpoint {
  route: string,
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH',
  controller: string,
  action: string,
  auth: boolean
})

(:Layout {
  name: string,
  entity: string,
  type: 'list' | 'detail' | 'edit' | 'search',
  isCustom: boolean
})

(:ACL {
  entity: string,
  action: string,
  level: string,
  role: string
})
```

#### Metadata Nodes
```cypher
(:ConfigFile {
  path: string,
  type: 'entityDefs' | 'clientDefs' | 'routes' | 'metadata',
  module: string
})

(:Binding {
  id: string,
  type: 'service' | 'parameter' | 'factory',
  value: string,
  confidence: float  // 0.0-1.0 for dynamic bindings
})
```

### Relationship Types

#### Code Structure
```cypher
// File relationships
(:PhpFile)-[:CONTAINS]->(:PhpClass)
(:JsFile)-[:CONTAINS]->(:JsModule)
(:JsModule)-[:CONTAINS]->(:JsClass|JsFunction)

// Class hierarchy
(:PhpClass)-[:EXTENDS]->(:PhpClass)
(:PhpClass)-[:IMPLEMENTS]->(:PhpClass)
(:PhpClass)-[:USES_TRAIT]->(:PhpClass)
(:JsClass)-[:EXTENDS]->(:JsClass)

// Class members
(:PhpClass)-[:HAS_METHOD]->(:PhpMethod)
(:PhpClass)-[:HAS_PROPERTY]->(:PhpProperty)
(:JsClass)-[:HAS_METHOD]->(:JsFunction)

// Dependencies
(:PhpClass)-[:USES]->(:PhpClass)
(:JsModule)-[:IMPORTS]->(:JsModule)
(:PhpMethod)-[:CALLS {confidence: float}]->(:PhpMethod)
(:PhpMethod)-[:INSTANTIATES]->(:PhpClass)
```

#### EspoCRM-Specific
```cypher
// Entity relationships
(:Entity)-[:HAS_FIELD]->(:Field)
(:Entity)-[:RELATES_TO {type: string}]->(:Entity)
(:Entity)-[:MANAGED_BY]->(:Service)
(:Entity)-[:HAS_REPOSITORY]->(:PhpClass)

// Hook system
(:Hook)-[:LISTENS_TO]->(:Entity)
(:Hook)-[:IMPLEMENTED_BY]->(:PhpMethod)
(:PhpMethod)-[:TRIGGERS_HOOK]->(:Hook)

// Service container
(:Service)-[:PROVIDED_BY]->(:PhpClass)
(:Service)-[:DEPENDS_ON]->(:Service)
(:PhpClass)-[:REQUESTS_SERVICE {id: string}]->(:Service)
(:Binding)-[:RESOLVES_TO]->(:PhpClass)

// API and routes
(:APIEndpoint)-[:HANDLED_BY]->(:PhpMethod)
(:JsClass)-[:CALLS_API]->(:APIEndpoint)
(:APIEndpoint)-[:REQUIRES_PERMISSION]->(:ACL)

// Frontend-Backend connection
(:Entity)-[:VIEWED_BY]->(:JsClass)
(:Layout)-[:USED_BY]->(:JsClass)
(:JsClass)-[:FETCHES_DATA]->(:Entity)
```

#### Metadata relationships
```cypher
(:ConfigFile)-[:DEFINES]->(:Entity|:Field|:Layout|:ACL)
(:Entity)-[:CONFIGURED_IN]->(:ConfigFile)
```

## Implementation Phases

### Phase 1: Foundation (Week 1)

#### 1.1 Environment Setup
```bash
# Setup project structure
mkdir -p espo-graph-analyzer/{
  parsers/{php,js},
  extractors,
  loaders,
  cache,
  output/{csv,json},
  tests
}

# Install dependencies
pip install py2neo pandas click tqdm
composer require nikic/php-parser
npm install esbuild @babel/parser acorn
```

#### 1.2 Neo4j Schema Setup
```cypher
// Create indexes for performance
CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name);
CREATE INDEX php_class_fqcn IF NOT EXISTS FOR (c:PhpClass) ON (c.fqcn);
CREATE INDEX js_module_id IF NOT EXISTS FOR (m:JsModule) ON (m.id);
CREATE INDEX service_id IF NOT EXISTS FOR (s:Service) ON (s.id);
CREATE INDEX file_path IF NOT EXISTS FOR (f:PhpFile) ON (f.path);
CREATE INDEX hook_entity IF NOT EXISTS FOR (h:Hook) ON (h.entity, h.type);

// Create constraints
CREATE CONSTRAINT unique_php_class IF NOT EXISTS FOR (c:PhpClass) REQUIRE c.fqcn IS UNIQUE;
CREATE CONSTRAINT unique_entity IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE;
CREATE CONSTRAINT unique_service IF NOT EXISTS FOR (s:Service) REQUIRE s.id IS UNIQUE;
```

#### 1.3 Basic PHP Parser
```php
<?php
// parsers/php/PhpExtractor.php
use PhpParser\{ParserFactory, NodeTraverser};

class PhpExtractor {
    private $parser;
    private $traverser;
    
    public function __construct() {
        $this->parser = (new ParserFactory)->create(ParserFactory::PREFER_PHP7);
        $this->traverser = new NodeTraverser();
        $this->traverser->addVisitor(new ClassExtractorVisitor());
        $this->traverser->addVisitor(new DependencyExtractorVisitor());
    }
    
    public function extractFromFile(string $filePath): array {
        $code = file_get_contents($filePath);
        $ast = $this->parser->parse($code);
        $this->traverser->traverse($ast);
        
        return [
            'classes' => $this->extractClasses($ast),
            'dependencies' => $this->extractDependencies($ast),
            'services' => $this->extractServiceCalls($ast),
            'hooks' => $this->extractHooks($ast)
        ];
    }
}
```

### Phase 2: Core Parsing (Week 2)

#### 2.1 Service Container Resolution
```python
# extractors/container_resolver.py
class ContainerResolver:
    def __init__(self):
        self.bindings = {}
        self.confidence_threshold = 0.7
    
    def extract_bindings(self, php_ast):
        """Extract container bindings from PHP AST"""
        bindings = []
        
        # Pattern 1: Direct set() calls
        # $container->set('serviceName', ClassName::class)
        for call in find_method_calls(php_ast, 'set'):
            if is_container_object(call.object):
                service_id = extract_string_literal(call.args[0])
                class_name = extract_class_reference(call.args[1])
                bindings.append({
                    'id': service_id,
                    'class': class_name,
                    'confidence': 1.0 if service_id else 0.5
                })
        
        # Pattern 2: Factory bindings
        # $container->factory('serviceName', function() { return new Class(); })
        for call in find_method_calls(php_ast, 'factory'):
            if is_container_object(call.object):
                service_id = extract_string_literal(call.args[0])
                factory_return = analyze_closure(call.args[1])
                bindings.append({
                    'id': service_id,
                    'class': factory_return.get('instantiates'),
                    'confidence': 0.8,
                    'type': 'factory'
                })
        
        return bindings
    
    def resolve_service_calls(self, method_ast):
        """Resolve $container->get() calls to actual classes"""
        resolutions = []
        
        for call in find_container_get_calls(method_ast):
            service_id = extract_service_id(call)
            if service_id in self.bindings:
                resolutions.append({
                    'caller': method_ast.class_name,
                    'service': service_id,
                    'resolves_to': self.bindings[service_id]['class'],
                    'confidence': self.bindings[service_id]['confidence']
                })
            else:
                # Mark as unresolved for runtime analysis
                resolutions.append({
                    'caller': method_ast.class_name,
                    'service': service_id or '<dynamic>',
                    'resolves_to': None,
                    'confidence': 0.0
                })
        
        return resolutions
```

#### 2.2 Hook Discovery
```python
# extractors/hook_extractor.py
class HookExtractor:
    HOOK_METHODS = [
        'beforeSave', 'afterSave',
        'beforeRemove', 'afterRemove',
        'beforeRelate', 'afterRelate',
        'beforeUnrelate', 'afterUnrelate',
        'beforeMassRelate', 'afterMassRelate'
    ]
    
    def extract_hooks(self, class_ast, file_path):
        """Extract hook implementations from a PHP class"""
        hooks = []
        
        # Check if class is in Hooks namespace
        if not self.is_hook_class(class_ast):
            return hooks
        
        # Extract entity name from namespace
        # Espo\Hooks\Contact\MyHook -> entity = Contact
        entity_name = self.extract_entity_from_namespace(class_ast.namespace)
        
        for method in class_ast.methods:
            if method.name in self.HOOK_METHODS:
                hooks.append({
                    'entity': entity_name or 'Common',
                    'type': method.name,
                    'class': class_ast.fqcn,
                    'method': f"{class_ast.fqcn}::{method.name}",
                    'order': self.extract_order(class_ast),
                    'file': file_path
                })
        
        return hooks
```

#### 2.3 JavaScript Module Analysis
```javascript
// parsers/js/module_analyzer.js
const esbuild = require('esbuild');
const path = require('path');

class ModuleAnalyzer {
    async analyzeModules(entryPoints) {
        const result = await esbuild.build({
            entryPoints,
            bundle: true,
            metafile: true,
            write: false,
            platform: 'browser',
            format: 'esm',
            alias: {
                'views': path.resolve('./client/src/views'),
                'helpers': path.resolve('./client/src/helpers'),
                // ... other aliases
            }
        });
        
        return this.parseMetafile(result.metafile);
    }
    
    parseMetafile(metafile) {
        const modules = [];
        const dependencies = [];
        
        for (const [outputFile, output] of Object.entries(metafile.outputs)) {
            for (const [inputFile, input] of Object.entries(output.inputs)) {
                modules.push({
                    id: this.getModuleId(inputFile),
                    path: inputFile,
                    bytes: input.bytes
                });
                
                for (const imp of input.imports || []) {
                    dependencies.push({
                        from: inputFile,
                        to: imp.path,
                        kind: imp.kind
                    });
                }
            }
        }
        
        return { modules, dependencies };
    }
}
```

### Phase 3: Metadata Integration (Week 3)

#### 3.1 Entity Metadata Parser
```python
# extractors/metadata_parser.py
import json
import os
from pathlib import Path

class MetadataParser:
    def __init__(self, espo_root):
        self.espo_root = Path(espo_root)
        self.metadata_paths = [
            'application/Espo/Resources/metadata',
            'application/Espo/Modules/*/Resources/metadata',
            'custom/Espo/Custom/Resources/metadata'
        ]
    
    def parse_entity_defs(self):
        """Parse all entityDefs JSON files"""
        entities = {}
        
        for pattern in self.metadata_paths:
            for entity_file in self.espo_root.glob(f"{pattern}/entityDefs/*.json"):
                entity_name = entity_file.stem
                with open(entity_file) as f:
                    entity_def = json.load(f)
                
                entities[entity_name] = {
                    'name': entity_name,
                    'fields': self.extract_fields(entity_def),
                    'relationships': self.extract_relationships(entity_def),
                    'indexes': entity_def.get('indexes', {}),
                    'collection': entity_def.get('collection', {}),
                    'file': str(entity_file)
                }
        
        return entities
    
    def parse_client_defs(self):
        """Parse clientDefs for frontend mappings"""
        client_defs = {}
        
        for pattern in self.metadata_paths:
            for client_file in self.espo_root.glob(f"{pattern}/clientDefs/*.json"):
                entity_name = client_file.stem
                with open(client_file) as f:
                    client_def = json.load(f)
                
                client_defs[entity_name] = {
                    'entity': entity_name,
                    'controller': client_def.get('controller'),
                    'views': {
                        'list': client_def.get('views', {}).get('list'),
                        'detail': client_def.get('views', {}).get('detail'),
                        'edit': client_def.get('views', {}).get('edit')
                    },
                    'recordViews': client_def.get('recordViews', {}),
                    'file': str(client_file)
                }
        
        return client_defs
    
    def parse_routes(self):
        """Parse API route definitions"""
        routes = []
        
        for pattern in self.metadata_paths:
            for route_file in self.espo_root.glob(f"{pattern}/../routes.json"):
                with open(route_file) as f:
                    route_list = json.load(f)
                
                for route in route_list:
                    routes.append({
                        'route': route.get('route'),
                        'method': route.get('method', 'GET'),
                        'controller': route.get('controller'),
                        'action': route.get('action'),
                        'auth': route.get('auth', True),
                        'file': str(route_file)
                    })
        
        return routes
```

#### 3.2 Graph Loader
```python
# loaders/neo4j_loader.py
from py2neo import Graph, Node, Relationship
import pandas as pd
from typing import List, Dict
import csv

class Neo4jLoader:
    def __init__(self, uri, auth):
        self.graph = Graph(uri, auth=auth)
        self.batch_size = 5000
    
    def initial_bulk_load(self, data_dir):
        """Perform initial bulk load using neo4j-admin import"""
        # Generate CSV files
        self.generate_csv_files(data_dir)
        
        # Use neo4j-admin import (called via subprocess)
        import_cmd = f"""
        neo4j-admin database import full
            --nodes=PhpClass={data_dir}/nodes-php-class.csv
            --nodes=PhpMethod={data_dir}/nodes-php-method.csv
            --nodes=Entity={data_dir}/nodes-entity.csv
            --nodes=Service={data_dir}/nodes-service.csv
            --relationships=EXTENDS={data_dir}/rels-extends.csv
            --relationships=HAS_METHOD={data_dir}/rels-has-method.csv
            --relationships=CALLS={data_dir}/rels-calls.csv
            --relationships=PROVIDED_BY={data_dir}/rels-provided-by.csv
            --overwrite-destination=true
            neo4j
        """
        # Execute import command
    
    def incremental_update(self, changes: Dict):
        """Perform incremental updates for changed files"""
        tx = self.graph.begin()
        
        try:
            # Delete old relationships for changed files
            for file_path in changes['modified']:
                tx.run("""
                    MATCH (f:PhpFile {path: $path})-[r]-()
                    DELETE r
                """, path=file_path)
            
            # Add new nodes and relationships
            for node in changes['new_nodes']:
                tx.create(Node(node['label'], **node['properties']))
            
            for rel in changes['new_relationships']:
                tx.run("""
                    MATCH (a {id: $from_id})
                    MATCH (b {id: $to_id})
                    CREATE (a)-[r:""" + rel['type'] + """ $props]->(b)
                """, from_id=rel['from'], to_id=rel['to'], props=rel.get('properties', {}))
            
            tx.commit()
        except Exception as e:
            tx.rollback()
            raise
    
    def create_projections(self):
        """Create graph projections for performance"""
        # Create projection for impact analysis
        self.graph.run("""
            CALL gds.graph.project(
                'impact-analysis',
                ['PhpClass', 'PhpMethod', 'Service', 'Entity'],
                {
                    CALLS: {orientation: 'NATURAL'},
                    DEPENDS_ON: {orientation: 'NATURAL'},
                    PROVIDED_BY: {orientation: 'NATURAL'}
                }
            )
        """)
```

### Phase 4: Analysis Queries (Week 4)

#### 4.1 Impact Analysis Queries
```cypher
// What breaks if I change this class?
MATCH (class:PhpClass {fqcn: $className})
CALL apoc.path.subgraphNodes(class, {
    relationshipFilter: 'EXTENDS>|IMPLEMENTS>|USES>|CALLS>|INSTANTIATES>',
    minLevel: 0,
    maxLevel: 3
}) YIELD node
RETURN DISTINCT node.fqcn as AffectedClass, labels(node)[0] as Type
ORDER BY Type, AffectedClass;

// Find all hooks triggered by saving an entity
MATCH (e:Entity {name: $entityName})
MATCH (h:Hook)-[:LISTENS_TO]->(e)
WHERE h.type IN ['beforeSave', 'afterSave']
MATCH (h)-[:IMPLEMENTED_BY]->(m:PhpMethod)
RETURN h.type as HookType, m.class as Class, m.name as Method, h.order as Order
ORDER BY h.type, h.order;

// Trace API call to database
MATCH path = (js:JsClass)-[:CALLS_API]->(api:APIEndpoint)
    -[:HANDLED_BY]->(controller:PhpMethod)
    -[:CALLS*1..5]->(repo:PhpMethod)
WHERE repo.class CONTAINS 'Repository'
RETURN path;
```

#### 4.2 Code Quality Queries
```cypher
// Find unused private methods
MATCH (m:PhpMethod {visibility: 'private'})
WHERE NOT (m)<-[:CALLS]-()
RETURN m.class as Class, m.name as Method;

// Detect circular dependencies
MATCH (c1:PhpClass)
MATCH path = (c1)-[:DEPENDS_ON*2..10]->(c1)
RETURN path LIMIT 10;

// Find services without interfaces
MATCH (s:Service)-[:PROVIDED_BY]->(c:PhpClass)
WHERE NOT (c)-[:IMPLEMENTS]->()
RETURN s.id as ServiceId, c.fqcn as Class;
```

#### 4.3 Security Analysis Queries
```cypher
// Find paths from user input to database
MATCH (controller:PhpMethod)<-[:HANDLED_BY]-(api:APIEndpoint)
WHERE api.method IN ['POST', 'PUT', 'PATCH']
MATCH path = (controller)-[:CALLS*1..10]->(db:PhpMethod)
WHERE db.class CONTAINS 'PDO' OR db.name CONTAINS 'query'
AND NOT EXISTS {
    MATCH (controller)-[:CALLS*1..10]->(validator:PhpMethod)
    WHERE validator.name CONTAINS 'validate' OR validator.name CONTAINS 'sanitize'
}
RETURN path;

// Find exposed endpoints without authentication
MATCH (api:APIEndpoint {auth: false})
MATCH (api)-[:HANDLED_BY]->(m:PhpMethod)
RETURN api.route, api.method, m.class, m.name;
```

## Performance Optimization

### Parsing Performance
```python
# Use multiprocessing for parallel parsing
from multiprocessing import Pool
from functools import partial

def parse_files_parallel(file_list, parser_func, num_workers=8):
    with Pool(num_workers) as pool:
        results = pool.map(parser_func, file_list)
    return results

# Cache parsed ASTs
import hashlib
import pickle
import sqlite3

class ASTCache:
    def __init__(self, cache_file='ast_cache.db'):
        self.conn = sqlite3.connect(cache_file)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS ast_cache (
                file_path TEXT PRIMARY KEY,
                file_hash TEXT,
                ast_data BLOB,
                parsed_at TIMESTAMP
            )
        ''')
    
    def get_or_parse(self, file_path, parser_func):
        file_hash = self.hash_file(file_path)
        cached = self.conn.execute(
            'SELECT ast_data FROM ast_cache WHERE file_path = ? AND file_hash = ?',
            (file_path, file_hash)
        ).fetchone()
        
        if cached:
            return pickle.loads(cached[0])
        
        ast = parser_func(file_path)
        self.conn.execute(
            'INSERT OR REPLACE INTO ast_cache VALUES (?, ?, ?, datetime("now"))',
            (file_path, file_hash, pickle.dumps(ast))
        )
        self.conn.commit()
        return ast
```

### Query Performance
```cypher
// Add composite indexes for common query patterns
CREATE INDEX composite_method_class IF NOT EXISTS 
FOR (m:PhpMethod) ON (m.class, m.name);

CREATE INDEX composite_hook_entity_type IF NOT EXISTS 
FOR (h:Hook) ON (h.entity, h.type);

// Use APOC for batch operations
CALL apoc.periodic.iterate(
    'MATCH (n) WHERE n.needsUpdate = true RETURN n',
    'CALL apoc.do.something(n) YIELD value RETURN value',
    {batchSize: 1000, parallel: true}
);
```

## Incremental Updates

### File Watcher
```python
# watch/file_monitor.py
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import git

class CodeChangeHandler(FileSystemEventHandler):
    def __init__(self, graph_updater):
        self.graph_updater = graph_updater
        self.pending_changes = set()
        self.debounce_timer = None
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        if self.is_relevant_file(event.src_path):
            self.pending_changes.add(event.src_path)
            self.schedule_update()
    
    def is_relevant_file(self, path):
        return path.endswith(('.php', '.js', '.json'))
    
    def schedule_update(self):
        # Debounce updates to batch changes
        if self.debounce_timer:
            self.debounce_timer.cancel()
        
        self.debounce_timer = Timer(2.0, self.process_changes)
        self.debounce_timer.start()
    
    def process_changes(self):
        if self.pending_changes:
            self.graph_updater.update_files(list(self.pending_changes))
            self.pending_changes.clear()
```

### Git Integration
```python
# integrations/git_analyzer.py
def get_changed_files(repo_path, since_commit=None):
    repo = git.Repo(repo_path)
    
    if since_commit:
        diff = repo.head.commit.diff(since_commit)
    else:
        # Get uncommitted changes
        diff = repo.head.commit.diff(None)
    
    changed_files = {
        'added': [],
        'modified': [],
        'deleted': []
    }
    
    for item in diff:
        if item.a_path.endswith(('.php', '.js', '.json')):
            if item.change_type == 'A':
                changed_files['added'].append(item.a_path)
            elif item.change_type == 'M':
                changed_files['modified'].append(item.a_path)
            elif item.change_type == 'D':
                changed_files['deleted'].append(item.a_path)
    
    return changed_files
```

## Risk Mitigation

### Dynamic Code Handling
```python
class DynamicCodeHandler:
    def handle_dynamic_call(self, call_site, context):
        """Mark dynamic calls with low confidence"""
        return {
            'type': 'DynamicCall',
            'from': call_site,
            'to': 'Unknown',
            'confidence': 0.1,
            'reason': 'Variable method name or class',
            'context': context,
            'needs_runtime_analysis': True
        }
    
    def suggest_runtime_probe(self, dynamic_calls):
        """Generate runtime instrumentation code"""
        probes = []
        for call in dynamic_calls:
            probe = f"""
            // Add to {call['from']}
            error_log("ESPO_GRAPH_PROBE: " . get_class($obj) . "::" . $method);
            """
            probes.append(probe)
        return probes
```

### Plugin Support
```yaml
# .espo-graph.yml - Configuration file
scan_paths:
  - application/Espo
  - custom/Espo
  - vendor/mycompany/espo-plugin/src
  
exclude_patterns:
  - "**/tests/**"
  - "**/vendor/**"
  - "*.test.php"
  
custom_patterns:
  hooks:
    - pattern: "Plugins/{name}/Hooks/{entity}/{class}.php"
  services:
    - pattern: "Plugins/{name}/Resources/services.php"
```

## Monitoring and Maintenance

### Health Checks
```python
# monitoring/health_check.py
class GraphHealthCheck:
    def check_graph_integrity(self):
        checks = []
        
        # Check for orphaned nodes
        orphans = self.graph.run("""
            MATCH (n)
            WHERE NOT (n)--()
            RETURN labels(n)[0] as Label, count(n) as Count
        """).to_data_frame()
        
        # Check for missing relationships
        missing_services = self.graph.run("""
            MATCH (c:PhpClass)-[:REQUESTS_SERVICE]->(s:Service)
            WHERE NOT (s)-[:PROVIDED_BY]->()
            RETURN s.id as ServiceId
        """).to_data_frame()
        
        # Check parsing coverage
        coverage = self.calculate_parsing_coverage()
        
        return {
            'orphaned_nodes': orphans.to_dict(),
            'missing_services': missing_services.to_dict(),
            'parsing_coverage': coverage,
            'timestamp': datetime.now()
        }
```

### Metrics Collection
```python
# metrics/collector.py
class MetricsCollector:
    def collect_parsing_metrics(self):
        return {
            'total_files': self.count_files(),
            'parsed_files': self.count_parsed_files(),
            'parse_time_avg': self.get_average_parse_time(),
            'cache_hit_rate': self.get_cache_hit_rate(),
            'graph_size': {
                'nodes': self.graph.run("MATCH (n) RETURN count(n)").evaluate(),
                'relationships': self.graph.run("MATCH ()-[r]->() RETURN count(r)").evaluate()
            }
        }
```

## Testing Strategy

### Unit Tests
```python
# tests/test_php_parser.py
import unittest
from parsers.php import PhpExtractor

class TestPhpParser(unittest.TestCase):
    def test_extract_class_hierarchy(self):
        code = '''<?php
        namespace Espo\\Core;
        class MyService extends BaseService implements ServiceInterface {
            use ServiceTrait;
        }
        '''
        
        extractor = PhpExtractor()
        result = extractor.extract_from_string(code)
        
        self.assertEqual(result['classes'][0]['name'], 'MyService')
        self.assertEqual(result['classes'][0]['extends'], 'BaseService')
        self.assertIn('ServiceInterface', result['classes'][0]['implements'])
        self.assertIn('ServiceTrait', result['classes'][0]['uses'])
    
    def test_extract_container_calls(self):
        code = '''<?php
        $service = $this->container->get('entityManager');
        '''
        
        extractor = PhpExtractor()
        result = extractor.extract_from_string(code)
        
        self.assertIn('entityManager', result['service_calls'])
```

### Integration Tests
```python
# tests/test_integration.py
class TestEndToEnd(unittest.TestCase):
    def test_full_pipeline(self):
        # Parse sample files
        parser = CodeGraphPipeline()
        parser.parse_directory('tests/fixtures/sample_module')
        
        # Load into test graph
        loader = Neo4jLoader('bolt://localhost:7688', ('neo4j', 'test'))
        loader.load_data(parser.get_results())
        
        # Verify graph structure
        result = loader.graph.run("""
            MATCH (c:PhpClass {name: 'TestController'})
            -[:HAS_METHOD]->(m:PhpMethod {name: 'actionList'})
            RETURN m
        """).evaluate()
        
        self.assertIsNotNone(result)
```

## Deployment

### Docker Setup
```dockerfile
# Dockerfile
FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    php8.2-cli \
    composer \
    nodejs \
    npm \
    git

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY composer.json .
RUN composer install

COPY package.json .
RUN npm install

COPY . .

CMD ["python", "main.py", "analyze", "/espocrm"]
```

### CI/CD Integration
```yaml
# .github/workflows/code-graph.yml
name: Update Code Graph

on:
  push:
    branches: [main, develop]
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM

jobs:
  update-graph:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup environment
        run: |
          docker-compose up -d neo4j
          pip install -r requirements.txt
      
      - name: Parse codebase
        run: |
          python main.py parse --incremental
      
      - name: Update graph
        run: |
          python main.py load --neo4j-uri ${{ secrets.NEO4J_URI }}
      
      - name: Run quality checks
        run: |
          python main.py analyze --check-unused-code
          python main.py analyze --check-circular-deps
      
      - name: Generate report
        run: |
          python main.py report --output reports/code-graph.html
      
      - name: Upload artifacts
        uses: actions/upload-artifact@v2
        with:
          name: code-graph-report
          path: reports/
```

## Command-Line Interface

```python
# cli/main.py
import click
from pathlib import Path

@click.group()
def cli():
    """EspoCRM Code Graph Analyzer"""
    pass

@cli.command()
@click.option('--path', default='.', help='Path to EspoCRM root')
@click.option('--parallel', default=8, help='Number of parallel workers')
@click.option('--cache/--no-cache', default=True, help='Use AST cache')
def parse(path, parallel, cache):
    """Parse EspoCRM codebase"""
    analyzer = CodeGraphAnalyzer(Path(path))
    analyzer.parse(workers=parallel, use_cache=cache)
    click.echo(f"Parsed {analyzer.file_count} files")

@cli.command()
@click.option('--neo4j-uri', default='bolt://localhost:7688')
@click.option('--username', default='neo4j')
@click.option('--password', prompt=True, hide_input=True)
def load(neo4j_uri, username, password):
    """Load parsed data into Neo4j"""
    loader = Neo4jLoader(neo4j_uri, (username, password))
    loader.load_from_cache()
    click.echo("Data loaded successfully")

@cli.command()
@click.option('--query', help='Cypher query to execute')
@click.option('--impact', help='Analyze impact of changing a class')
@click.option('--unused', is_flag=True, help='Find unused code')
def analyze(query, impact, unused):
    """Run analysis queries"""
    analyzer = GraphAnalyzer()
    
    if query:
        results = analyzer.run_query(query)
    elif impact:
        results = analyzer.impact_analysis(impact)
    elif unused:
        results = analyzer.find_unused_code()
    
    click.echo(results)

@cli.command()
def watch():
    """Watch for file changes and update graph"""
    watcher = FileWatcher()
    watcher.start()
    click.echo("Watching for changes... Press Ctrl+C to stop")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        watcher.stop()

if __name__ == '__main__':
    cli()
```

## Next Steps

### Immediate Actions (Week 1)
1. ✅ Set up Neo4j with Docker
2. ⬜ Create project structure
3. ⬜ Implement basic PHP parser
4. ⬜ Test with single module

### Short-term Goals (Month 1)
1. Complete Phase 1-2 implementation
2. Parse entire EspoCRM codebase
3. Validate graph completeness
4. Create basic query library

### Long-term Goals (Quarter 1)
1. Implement incremental updates
2. Add runtime analysis integration
3. Create visualization dashboard
4. Deploy to production CI/CD

### Future Enhancements
1. **AI-Powered Analysis**: Use ML to predict bug-prone code
2. **Real-time Monitoring**: Connect to production logs
3. **IDE Integration**: VSCode/PhpStorm plugins
4. **Collaboration Features**: Share analysis results
5. **Performance Profiling**: Integrate with XHProf/Blackfire

## Conclusion

This comprehensive plan provides a solid foundation for building a production-ready code graph for EspoCRM. The system is designed to be:

- **Scalable**: Handles thousands of files efficiently
- **Accurate**: Resolves 80%+ of dependencies
- **Maintainable**: Clear architecture and testing
- **Extensible**: Plugin support and custom patterns
- **Practical**: Immediate value through impact analysis

The implementation follows industry best practices and leverages proven tools while accounting for EspoCRM's unique architecture. With this graph in place, developers will have unprecedented visibility into their codebase's structure and dependencies.