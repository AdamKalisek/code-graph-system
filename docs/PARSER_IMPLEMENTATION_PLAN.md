# Parser Implementation Plan: From 30% to 100% Edge Coverage
## Based on o3 and Gemini 2.5 Pro Recommendations

## Executive Summary
Both o3 and Gemini agree: **Multi-pass parsing with a Symbol Table** is essential. Current single-pass approach can't resolve cross-file references.

## Architecture Overview

```
┌─────────────────┐
│   File Watcher  │ (Git hooks / FS watch)
└────────┬────────┘
         ▼
┌────────────────────────────────────────┐
│ PASS 1: Symbol Collection              │
│ - Parse all files → AST                │
│ - Extract definitions → Symbol Table   │
│ - Create basic nodes in Neo4j          │
└────────┬───────────────────────────────┘
         ▼
┌────────────────────────────────────────┐
│ PASS 2: Reference Resolution           │
│ - Re-traverse ASTs with Symbol Table   │
│ - Resolve imports, types, inheritance  │
│ - Create cross-file edges              │
└────────┬───────────────────────────────┘
         ▼
┌────────────────────────────────────────┐
│ PASS 3: Framework Plugins              │
│ - DI container analysis                │
│ - Event system detection               │
│ - Route configuration                  │
└────────┬───────────────────────────────┘
         ▼
┌────────────────────────────────────────┐
│ Neo4j Batch Update                     │
│ - UNWIND + MERGE operations            │
│ - Maintain external ID mapping         │
└─────────────────────────────────────────┘
```

## Phase 1: Symbol Table Implementation (Week 1)

### 1.1 Symbol Table Design
```python
# core/symbol_table.py
from typing import Dict, Optional, List
from dataclasses import dataclass
import sqlite3

@dataclass
class Symbol:
    fqn: str              # Fully Qualified Name
    kind: str             # class|interface|function|trait|const|module
    file_path: str
    line: int
    exported: bool = True
    neo4j_id: Optional[str] = None
    metadata: Dict = None

class SymbolTable:
    """Persistent symbol table using SQLite for large codebases"""
    
    def __init__(self, db_path: str = ".cache/symbols.db"):
        self.conn = sqlite3.connect(db_path)
        self._create_tables()
        
    def _create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS symbols (
                fqn TEXT PRIMARY KEY,
                kind TEXT,
                file_path TEXT,
                line INTEGER,
                exported BOOLEAN,
                neo4j_id TEXT,
                metadata TEXT
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_file ON symbols(file_path)")
        
    def add_symbol(self, symbol: Symbol):
        """Add or update a symbol"""
        pass
        
    def resolve(self, name: str, current_namespace: str = "") -> Optional[Symbol]:
        """Resolve a name to FQN considering namespace context"""
        # 1. Try exact match
        # 2. Try with current namespace
        # 3. Try imported aliases
        pass
        
    def get_file_symbols(self, file_path: str) -> List[Symbol]:
        """Get all symbols defined in a file"""
        pass
```

### 1.2 Pass 1: Symbol Collection

```python
# parsers/php/symbol_collector.py
def collect_php_symbols(file_path: str, ast: Node, symbol_table: SymbolTable):
    """Extract all definitions from PHP file"""
    
    current_namespace = ""
    
    for node in traverse_ast(ast):
        if node.type == "namespace_definition":
            current_namespace = extract_namespace(node)
            
        elif node.type == "class_declaration":
            class_name = get_node_name(node)
            fqn = f"{current_namespace}\\{class_name}".strip("\\")
            
            symbol = Symbol(
                fqn=fqn,
                kind="class",
                file_path=file_path,
                line=node.start_point[0]
            )
            symbol_table.add_symbol(symbol)
            
            # Also collect methods
            for method in find_methods(node):
                method_fqn = f"{fqn}::{method.name}"
                symbol_table.add_symbol(Symbol(
                    fqn=method_fqn,
                    kind="method",
                    file_path=file_path,
                    line=method.start_point[0]
                ))
```

## Phase 2: Reference Resolution (Week 2)

### 2.1 PHP Import Resolution
```python
# parsers/php/reference_resolver.py
def resolve_php_references(file_path: str, ast: Node, symbol_table: SymbolTable):
    """Pass 2: Resolve all references using the symbol table"""
    
    edges = []
    current_namespace = ""
    imports = {}  # alias -> FQN mapping
    
    for node in traverse_ast(ast):
        # Collect use statements
        if node.type == "use_declaration":
            fqn = extract_fqn(node)
            alias = extract_alias(node) or fqn.split("\\")[-1]
            imports[alias] = fqn
            
            # Create USES_NAMESPACE edge
            if target := symbol_table.resolve(fqn):
                edges.append({
                    "type": "USES_NAMESPACE",
                    "source": file_path,
                    "target": target.neo4j_id
                })
                
        # Resolve class inheritance
        elif node.type == "class_declaration":
            if extends := find_extends_clause(node):
                parent_name = get_node_text(extends)
                parent_fqn = imports.get(parent_name, f"{current_namespace}\\{parent_name}")
                
                if parent := symbol_table.resolve(parent_fqn):
                    edges.append({
                        "type": "EXTENDS",
                        "source": get_current_class_id(node),
                        "target": parent.neo4j_id
                    })
                    
        # Resolve interface implementations
        elif node.type == "interface_clause":
            for interface_name in extract_interface_names(node):
                interface_fqn = imports.get(interface_name, f"{current_namespace}\\{interface_name}")
                
                if interface := symbol_table.resolve(interface_fqn):
                    edges.append({
                        "type": "IMPLEMENTS",
                        "source": get_current_class_id(node),
                        "target": interface.neo4j_id
                    })
                    
        # Type hints (parameters and returns)
        elif node.type in ["type_hint", "return_type"]:
            type_name = get_node_text(node)
            type_fqn = imports.get(type_name, f"{current_namespace}\\{type_name}")
            
            if type_symbol := symbol_table.resolve(type_fqn):
                edge_type = "RETURNS_TYPE" if node.type == "return_type" else "ACCEPTS_TYPE"
                edges.append({
                    "type": edge_type,
                    "source": get_current_method_id(node),
                    "target": type_symbol.neo4j_id
                })
    
    return edges
```

### 2.2 JavaScript Module Resolution
```python
# parsers/javascript/reference_resolver.py
import os
from pathlib import Path

def resolve_js_module(import_path: str, current_file: str, symbol_table: SymbolTable) -> Optional[Symbol]:
    """Resolve JS module path using Node.js resolution algorithm"""
    
    current_dir = Path(current_file).parent
    
    # Relative imports
    if import_path.startswith('.'):
        resolved = current_dir / import_path
        
        # Try extensions
        for ext in ['', '.js', '.ts', '.jsx', '.tsx', '/index.js']:
            full_path = f"{resolved}{ext}"
            if symbol := symbol_table.resolve(full_path):
                return symbol
                
    # Node modules
    elif not import_path.startswith('/'):
        # Walk up directory tree looking for node_modules
        for parent in current_dir.parents:
            module_path = parent / 'node_modules' / import_path
            if module_path.exists():
                # Read package.json for main field
                pkg_json = module_path / 'package.json'
                if pkg_json.exists():
                    # Parse and get main field
                    pass
                    
    return None

def resolve_js_references(file_path: str, ast: Node, symbol_table: SymbolTable):
    """Resolve JavaScript imports and exports"""
    
    edges = []
    
    for node in traverse_ast(ast):
        # ES6 imports
        if node.type == "import_statement":
            source = extract_import_source(node)
            
            if module := resolve_js_module(source, file_path, symbol_table):
                edges.append({
                    "type": "IMPORTS_ES6",
                    "source": file_path,
                    "target": module.neo4j_id
                })
                
        # CommonJS require
        elif is_require_call(node):
            module_path = extract_require_path(node)
            
            if module := resolve_js_module(module_path, file_path, symbol_table):
                edges.append({
                    "type": "REQUIRES_MODULE",
                    "source": file_path,
                    "target": module.neo4j_id
                })
                
    return edges
```

## Phase 3: Framework Plugins (Week 3)

### 3.1 Plugin Architecture
```python
# core/plugin_interface.py
from abc import ABC, abstractmethod
from typing import List, Dict

class FrameworkPlugin(ABC):
    """Base class for framework-specific analyzers"""
    
    @abstractmethod
    def detect(self, project_root: str) -> bool:
        """Check if this plugin applies to the project"""
        pass
        
    @abstractmethod
    def analyze(self, file_path: str, ast: Node, symbol_table: SymbolTable) -> List[Dict]:
        """Extract framework-specific edges"""
        pass
        
    @abstractmethod
    def analyze_config(self, project_root: str, symbol_table: SymbolTable) -> List[Dict]:
        """Analyze configuration files"""
        pass
```

### 3.2 Laravel Plugin Example
```python
# plugins/laravel/plugin.py
class LaravelPlugin(FrameworkPlugin):
    def detect(self, project_root: str) -> bool:
        return (Path(project_root) / "artisan").exists()
        
    def analyze(self, file_path: str, ast: Node, symbol_table: SymbolTable) -> List[Dict]:
        edges = []
        
        # Detect DI container usage
        for node in find_function_calls(ast, ["app", "resolve", "make"]):
            if arg := get_first_string_arg(node):
                if arg.endswith("::class"):
                    class_name = arg.replace("::class", "")
                    if target := symbol_table.resolve(class_name):
                        edges.append({
                            "type": "INJECTS",
                            "source": get_current_class(node),
                            "target": target.neo4j_id
                        })
                        
        # Detect event dispatching
        for node in find_method_calls(ast, "dispatch", "Event"):
            event_class = extract_event_class(node)
            if event := symbol_table.resolve(event_class):
                edges.append({
                    "type": "EMITS",
                    "source": get_current_method(node),
                    "target": event.neo4j_id
                })
                
        return edges
        
    def analyze_config(self, project_root: str, symbol_table: SymbolTable) -> List[Dict]:
        edges = []
        
        # Parse routes/web.php
        routes_file = Path(project_root) / "routes" / "web.php"
        if routes_file.exists():
            # Parse Route::get('/path', [Controller::class, 'method'])
            for route in parse_routes(routes_file):
                controller_fqn = route['controller']
                method_name = route['method']
                
                if controller := symbol_table.resolve(controller_fqn):
                    method_fqn = f"{controller_fqn}::{method_name}"
                    if method := symbol_table.resolve(method_fqn):
                        edges.append({
                            "type": "ROUTES_TO",
                            "source": str(routes_file),
                            "target": method.neo4j_id,
                            "properties": {"path": route['path'], "method": route['http_method']}
                        })
                        
        return edges
```

### 3.3 Event System Detection
```python
# plugins/symfony/event_analyzer.py
def analyze_symfony_events(ast: Node, symbol_table: SymbolTable) -> List[Dict]:
    """Detect Symfony event listeners and subscribers"""
    
    edges = []
    
    # Find EventSubscriber implementations
    for class_node in find_classes_implementing(ast, "EventSubscriberInterface"):
        # Find getSubscribedEvents method
        if method := find_method(class_node, "getSubscribedEvents"):
            # Parse the returned array
            for event_mapping in parse_event_subscriptions(method):
                event_class = event_mapping['event']
                handler_method = event_mapping['method']
                
                if event := symbol_table.resolve(event_class):
                    edges.append({
                        "type": "LISTENS_TO",
                        "source": f"{get_class_fqn(class_node)}::{handler_method}",
                        "target": event.neo4j_id
                    })
                    
    return edges
```

## Phase 4: Incremental Updates (Week 4)

### 4.1 Change Detection
```python
# core/incremental_updater.py
import hashlib
from pathlib import Path

class IncrementalUpdater:
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.hash_cache = self.load_hash_cache()
        
    def get_changed_files(self, project_root: str) -> List[str]:
        """Get list of files that have changed since last parse"""
        changed = []
        
        for file_path in Path(project_root).rglob("*.php"):
            current_hash = self.hash_file(file_path)
            cached_hash = self.hash_cache.get(str(file_path))
            
            if current_hash != cached_hash:
                changed.append(str(file_path))
                self.hash_cache[str(file_path)] = current_hash
                
        return changed
        
    def update_graph(self, changed_files: List[str], symbol_table: SymbolTable):
        """Update only changed parts of the graph"""
        
        # 1. Find affected files (files that import changed files)
        affected_files = set(changed_files)
        for file in changed_files:
            # Query Neo4j for files that depend on this file
            dependents = self.find_dependents(file)
            affected_files.update(dependents)
            
        # 2. Remove old data
        for file in affected_files:
            self.remove_file_from_graph(file)
            
        # 3. Re-parse affected files
        for file in affected_files:
            # Run Pass 1, 2, 3 on this file
            pass
```

## Phase 5: Testing & Validation (Week 5)

### 5.1 Edge Coverage Tests
```python
# tests/test_edge_coverage.py
def test_php_imports_captured():
    """Verify PHP use statements create USES_NAMESPACE edges"""
    code = """
    <?php
    namespace App\\Controllers;
    use App\\Services\\EmailService;
    
    class UserController {
        public function __construct(EmailService $service) {}
    }
    """
    
    graph = parse_code(code)
    
    # Should have USES_NAMESPACE edge
    assert graph.has_edge(
        type="USES_NAMESPACE",
        source="App\\Controllers\\UserController",
        target="App\\Services\\EmailService"
    )
    
    # Should have INJECTS edge
    assert graph.has_edge(
        type="INJECTS",
        source="App\\Controllers\\UserController",
        target="App\\Services\\EmailService"
    )
```

### 5.2 Validation Queries
```cypher
// Verify all imports are resolved
MATCH (f:File)-[:USES_NAMESPACE]->(target)
WHERE NOT exists(target.fqn)
RETURN f.path, target
// Should return empty - all imports resolved

// Check for orphaned nodes
MATCH (n)
WHERE NOT (n)-[]-()
RETURN n
// Minimal orphans expected
```

## Implementation Timeline

| Week | Phase | Deliverable |
|------|-------|------------|
| 1 | Symbol Table | In-memory/SQLite symbol index |
| 2 | Reference Resolution | IMPORTS, EXTENDS, IMPLEMENTS edges |
| 3 | Framework Plugins | Laravel/Symfony DI, events, routes |
| 4 | Incremental Updates | Change detection, partial re-parsing |
| 5 | Testing | Edge coverage validation, benchmarks |

## Success Metrics

1. **Edge Coverage**: From 30% → 85%+ of critical edges
2. **Query Performance**: Mail flow trace in <100ms
3. **Parsing Speed**: Full parse <5min for 1M LOC
4. **Incremental Speed**: Update in <5s for typical change
5. **Accuracy**: <1% false positive rate on edges

## Key Insights from AI Models

**o3 emphasized:**
- "Always separate 'extract syntax' from 'resolve semantics'"
- "Keep a fast symbol index in front of Neo4j"
- "Model ambiguous/dynamic things explicitly"

**Gemini 2.5 Pro emphasized:**
- "Three-pass system is crucial"
- "Symbol Table is the key to cross-file resolution"
- "Plugin architecture for framework-specific patterns"

Both agree: **Multi-pass with Symbol Table is non-negotiable** for achieving comprehensive edge coverage.