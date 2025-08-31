# Next Level Implementation Plan: Building a Code Graph System Better Than Grep
## Complete Detailed Guide with How-To, Why, and Everything

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Phase 1: Symbol Table Foundation](#phase-1-symbol-table-foundation)
4. [Phase 2: Multi-Pass Parser Implementation](#phase-2-multi-pass-parser-implementation)
5. [Phase 3: Neo4j Integration](#phase-3-neo4j-integration)
6. [Phase 4: Framework Plugins](#phase-4-framework-plugins)
7. [Phase 5: Query Interface](#phase-5-query-interface)
8. [Performance Optimization](#performance-optimization)
9. [Testing Strategy](#testing-strategy)
10. [Deployment & Operations](#deployment-operations)

---

## Executive Summary

### What We're Building
A code intelligence system that understands code BEHAVIOR, not just text. It answers "How does X work?" in milliseconds, not the minutes/hours grep requires.

### Why Current System Fails
- **Missing 70% of edges**: No imports, no DI, no type hints
- **Single-pass parsing**: Can't resolve cross-file references
- **No separation of concerns**: Trying to do everything in one pass

### The Solution: Two-Tier Architecture
1. **Symbol Table** (SQLite/LMDB): Fast local lookups during parsing
2. **Neo4j**: Complex graph queries after parsing

### Expected Outcomes
- Query "How is email sent?" → Full execution path in <100ms
- 90%+ accuracy vs grep's ~40% (due to false positives)
- Handle 10M+ LOC codebases

---

## Architecture Overview

### The Complete Flow

```
┌─────────────────────────────────────────────────────────┐
│                     SOURCE CODE                          │
└────────────────────┬───────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              PASS 1: SYMBOL COLLECTION                   │
│  Purpose: Find all definitions (classes, functions)      │
│  Writes to: Symbol Table (SQLite)                       │
│  Speed: ~10K files/second                               │
└────────────────────┬───────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│            PASS 2: REFERENCE RESOLUTION                  │
│  Purpose: Connect imports, extends, implements          │
│  Reads from: Symbol Table                               │
│  Creates: Edge objects in memory                        │
└────────────────────┬───────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│             PASS 3: FRAMEWORK PLUGINS                    │
│  Purpose: DI, events, routes, framework-specific        │
│  Reads from: Symbol Table + Config files                │
│  Creates: Additional edge objects                       │
└────────────────────┬───────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│               NEO4J BATCH IMPORT                         │
│  Purpose: Persist final graph for queries               │
│  Method: UNWIND + MERGE in 50K batches                  │
│  Speed: ~6M nodes/second                                │
└────────────────────┬───────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                 QUERY INTERFACE                          │
│  Purpose: Answer developer questions                    │
│  Input: Natural language or Cypher                      │
│  Output: Visualized paths, impact analysis              │
└─────────────────────────────────────────────────────────┘
```

### Why This Architecture?

**Problem**: Cross-file references require knowing ALL symbols before resolving ANY references
**Solution**: Multi-pass ensures complete symbol knowledge before resolution

**Problem**: Parsing needs millions of fast lookups
**Solution**: Local Symbol Table avoids network overhead

**Problem**: Complex queries need graph traversal
**Solution**: Neo4j provides optimized graph algorithms

---

## Phase 1: Symbol Table Foundation

### 1.1 Database Schema

```sql
-- symbols.db schema
CREATE TABLE symbols (
    fqn TEXT PRIMARY KEY,           -- Fully Qualified Name (e.g., App\Services\EmailService)
    kind TEXT NOT NULL,              -- class|interface|function|trait|const|module
    file_path TEXT NOT NULL,         -- Absolute path to file
    line_number INTEGER NOT NULL,    -- Line where defined
    column_number INTEGER,           -- Column where defined
    namespace TEXT,                  -- PHP namespace or JS module path
    exported BOOLEAN DEFAULT TRUE,   -- Is this symbol exported/public?
    neo4j_id TEXT,                   -- Neo4j node ID after import
    metadata JSON                    -- Additional data (extends, implements, etc.)
);

-- Indexes for performance
CREATE INDEX idx_file_path ON symbols(file_path);
CREATE INDEX idx_namespace ON symbols(namespace);
CREATE INDEX idx_kind ON symbols(kind);

-- Import tracking
CREATE TABLE imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    imported_fqn TEXT NOT NULL,     -- What was imported
    alias TEXT,                      -- Import alias if any
    line_number INTEGER,
    kind TEXT                        -- use|import|require
);

CREATE INDEX idx_imports_file ON imports(file_path);
```

### 1.2 Symbol Table Implementation

```python
# core/symbol_table.py
import sqlite3
import json
from typing import Dict, Optional, List, Set
from dataclasses import dataclass, asdict
from pathlib import Path
import threading
from contextlib import contextmanager

@dataclass
class Symbol:
    """Represents a code symbol (class, function, etc.)"""
    fqn: str                          # Fully Qualified Name
    kind: str                         # class|interface|function|trait|const|module
    file_path: str                    # Absolute path
    line_number: int
    column_number: int = 0
    namespace: str = ""
    exported: bool = True
    neo4j_id: Optional[str] = None
    metadata: Dict = None

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v is not None}

class SymbolTable:
    """
    Thread-safe symbol table for multi-pass parsing.
    Uses SQLite for persistence and caching.
    """
    
    def __init__(self, db_path: str = ".cache/symbols.db", cache_size: int = 100000):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Thread-local storage for connections
        self._local = threading.local()
        
        # In-memory LRU cache for hot symbols
        from functools import lru_cache
        self._cache = lru_cache(maxsize=cache_size)(self._resolve_uncached)
        
        # Initialize database
        self._init_db()
        
    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-local database connection"""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(str(self.db_path))
            self._local.conn.row_factory = sqlite3.Row
            # Performance optimizations
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn.execute("PRAGMA temp_store=MEMORY")
            self._local.conn.execute("PRAGMA mmap_size=30000000000")
        return self._local.conn
    
    def _init_db(self):
        """Initialize database schema"""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS symbols (
                fqn TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                file_path TEXT NOT NULL,
                line_number INTEGER NOT NULL,
                column_number INTEGER DEFAULT 0,
                namespace TEXT DEFAULT '',
                exported BOOLEAN DEFAULT TRUE,
                neo4j_id TEXT,
                metadata TEXT
            );
            
            CREATE INDEX IF NOT EXISTS idx_file_path ON symbols(file_path);
            CREATE INDEX IF NOT EXISTS idx_namespace ON symbols(namespace);
            CREATE INDEX IF NOT EXISTS idx_kind ON symbols(kind);
            
            CREATE TABLE IF NOT EXISTS imports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                imported_fqn TEXT NOT NULL,
                alias TEXT,
                line_number INTEGER,
                kind TEXT
            );
            
            CREATE INDEX IF NOT EXISTS idx_imports_file ON imports(file_path);
        """)
        conn.commit()
    
    def add_symbol(self, symbol: Symbol) -> None:
        """
        Add or update a symbol in the table.
        This is called during Pass 1 as definitions are discovered.
        """
        conn = self._get_conn()
        metadata_json = json.dumps(symbol.metadata) if symbol.metadata else None
        
        conn.execute("""
            INSERT OR REPLACE INTO symbols 
            (fqn, kind, file_path, line_number, column_number, namespace, exported, neo4j_id, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            symbol.fqn, symbol.kind, symbol.file_path, symbol.line_number,
            symbol.column_number, symbol.namespace, symbol.exported, 
            symbol.neo4j_id, metadata_json
        ))
        conn.commit()
        
        # Invalidate cache for this FQN
        if hasattr(self._cache, 'cache_clear'):
            # Clear specific entry if possible, otherwise clear all
            self._cache.cache_clear()
    
    def bulk_add_symbols(self, symbols: List[Symbol]) -> None:
        """Efficiently add multiple symbols in a single transaction"""
        conn = self._get_conn()
        data = [
            (s.fqn, s.kind, s.file_path, s.line_number, s.column_number,
             s.namespace, s.exported, s.neo4j_id,
             json.dumps(s.metadata) if s.metadata else None)
            for s in symbols
        ]
        
        conn.executemany("""
            INSERT OR REPLACE INTO symbols 
            (fqn, kind, file_path, line_number, column_number, namespace, exported, neo4j_id, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, data)
        conn.commit()
        self._cache.cache_clear()
    
    def resolve(self, name: str, current_namespace: str = "", 
                imports: Dict[str, str] = None) -> Optional[Symbol]:
        """
        Resolve a name to a fully qualified symbol.
        This is the critical function called during Pass 2.
        
        Resolution order:
        1. Check if name is already fully qualified
        2. Check imports/aliases
        3. Check current namespace
        4. Check global namespace
        """
        # Check imports first (aliases)
        if imports and name in imports:
            fqn = imports[name]
        # Try with current namespace
        elif current_namespace and not name.startswith('\\'):
            # PHP style namespace
            if '\\' in name or '\\' in current_namespace:
                fqn = f"{current_namespace}\\{name}".strip('\\')
            # JS style module path
            else:
                fqn = f"{current_namespace}/{name}".strip('/')
        else:
            fqn = name.strip('\\/')
        
        # Try cache first
        return self._cache(fqn)
    
    def _resolve_uncached(self, fqn: str) -> Optional[Symbol]:
        """Actual database lookup (cached by LRU decorator)"""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM symbols WHERE fqn = ?", (fqn,)
        )
        row = cursor.fetchone()
        
        if row:
            metadata = json.loads(row['metadata']) if row['metadata'] else None
            return Symbol(
                fqn=row['fqn'],
                kind=row['kind'],
                file_path=row['file_path'],
                line_number=row['line_number'],
                column_number=row['column_number'],
                namespace=row['namespace'],
                exported=bool(row['exported']),
                neo4j_id=row['neo4j_id'],
                metadata=metadata
            )
        return None
    
    def get_file_symbols(self, file_path: str) -> List[Symbol]:
        """Get all symbols defined in a file"""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM symbols WHERE file_path = ?", (file_path,)
        )
        
        symbols = []
        for row in cursor:
            metadata = json.loads(row['metadata']) if row['metadata'] else None
            symbols.append(Symbol(
                fqn=row['fqn'],
                kind=row['kind'],
                file_path=row['file_path'],
                line_number=row['line_number'],
                column_number=row['column_number'],
                namespace=row['namespace'],
                exported=bool(row['exported']),
                neo4j_id=row['neo4j_id'],
                metadata=metadata
            ))
        return symbols
    
    def add_import(self, file_path: str, imported_fqn: str, 
                   alias: str = None, line_number: int = 0, kind: str = "use"):
        """Track import statements for reference resolution"""
        conn = self._get_conn()
        conn.execute("""
            INSERT INTO imports (file_path, imported_fqn, alias, line_number, kind)
            VALUES (?, ?, ?, ?, ?)
        """, (file_path, imported_fqn, alias, line_number, kind))
        conn.commit()
    
    def get_file_imports(self, file_path: str) -> Dict[str, str]:
        """Get import mappings for a file (alias -> FQN)"""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT imported_fqn, alias FROM imports WHERE file_path = ?",
            (file_path,)
        )
        
        imports = {}
        for row in cursor:
            alias = row['alias'] or row['imported_fqn'].split('\\')[-1]
            imports[alias] = row['imported_fqn']
        return imports
    
    def clear(self):
        """Clear all symbols (useful for testing)"""
        conn = self._get_conn()
        conn.execute("DELETE FROM symbols")
        conn.execute("DELETE FROM imports")
        conn.commit()
        self._cache.cache_clear()
    
    def get_stats(self) -> Dict:
        """Get statistics about the symbol table"""
        conn = self._get_conn()
        stats = {}
        
        # Total symbols
        cursor = conn.execute("SELECT COUNT(*) as count FROM symbols")
        stats['total_symbols'] = cursor.fetchone()['count']
        
        # Symbols by kind
        cursor = conn.execute("""
            SELECT kind, COUNT(*) as count 
            FROM symbols 
            GROUP BY kind
        """)
        stats['by_kind'] = {row['kind']: row['count'] for row in cursor}
        
        # Files with symbols
        cursor = conn.execute("""
            SELECT COUNT(DISTINCT file_path) as count FROM symbols
        """)
        stats['files_with_symbols'] = cursor.fetchone()['count']
        
        return stats
```

### 1.3 Why SQLite for Symbol Table?

**Advantages:**
- **Zero configuration**: No server to manage
- **Fast enough**: 150K lookups/sec with proper indexes
- **Persistent**: Survives crashes, can resume parsing
- **Transactional**: ACID guarantees for consistency
- **Debuggable**: Can inspect with any SQLite tool

**When to upgrade to LMDB/RocksDB:**
- When parsing >2M symbols (roughly 10M LOC)
- When lookup latency >1ms becomes a bottleneck
- When you need concurrent writers

---

## Phase 2: Multi-Pass Parser Implementation

### 2.1 Pass 1: Symbol Collection

```python
# parsers/php/symbol_collector.py
import tree_sitter_php as tsphp
from tree_sitter import Parser, Node
from pathlib import Path
from typing import List, Optional
from core.symbol_table import Symbol, SymbolTable

class PHPSymbolCollector:
    """
    Pass 1: Extract all symbol definitions from PHP files.
    This pass ONLY collects definitions, not references.
    """
    
    def __init__(self, symbol_table: SymbolTable):
        self.symbol_table = symbol_table
        self.parser = Parser()
        self.parser.set_language(tsphp.language())
    
    def collect_file(self, file_path: str) -> List[Symbol]:
        """
        Parse a PHP file and extract all symbol definitions.
        Returns symbols for Neo4j node creation.
        """
        symbols = []
        
        # Read file
        with open(file_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        # Parse to AST
        tree = self.parser.parse(bytes(source_code, 'utf8'))
        
        # Track current context
        context = {
            'namespace': '',
            'class': None,
            'imports': {}
        }
        
        # Traverse AST
        self._traverse(tree.root_node, source_code, file_path, context, symbols)
        
        # Bulk add to symbol table
        self.symbol_table.bulk_add_symbols(symbols)
        
        return symbols
    
    def _traverse(self, node: Node, source: str, file_path: str, 
                  context: dict, symbols: List[Symbol]):
        """Recursively traverse AST to find definitions"""
        
        # Namespace declaration
        if node.type == 'namespace_definition':
            namespace_node = self._find_child(node, 'namespace_name')
            if namespace_node:
                context['namespace'] = self._get_text(namespace_node, source)
        
        # Class declaration
        elif node.type == 'class_declaration':
            class_name = self._get_name(node, source)
            if class_name:
                # Build FQN
                fqn = self._build_fqn(context['namespace'], class_name)
                
                # Extract metadata
                metadata = {
                    'modifiers': self._get_modifiers(node, source),
                    'extends': None,
                    'implements': []
                }
                
                # Check for extends
                extends_node = self._find_child(node, 'base_clause')
                if extends_node:
                    parent_name = self._get_text(extends_node, source).replace('extends', '').strip()
                    metadata['extends'] = parent_name
                
                # Check for implements
                implements_node = self._find_child(node, 'class_interface_clause')
                if implements_node:
                    interfaces = self._extract_interfaces(implements_node, source)
                    metadata['implements'] = interfaces
                
                # Create symbol
                symbol = Symbol(
                    fqn=fqn,
                    kind='class',
                    file_path=file_path,
                    line_number=node.start_point[0] + 1,
                    column_number=node.start_point[1],
                    namespace=context['namespace'],
                    metadata=metadata
                )
                symbols.append(symbol)
                
                # Update context for methods
                old_class = context['class']
                context['class'] = fqn
                
                # Process class body
                for child in node.children:
                    self._traverse(child, source, file_path, context, symbols)
                
                # Restore context
                context['class'] = old_class
        
        # Interface declaration
        elif node.type == 'interface_declaration':
            interface_name = self._get_name(node, source)
            if interface_name:
                fqn = self._build_fqn(context['namespace'], interface_name)
                
                symbol = Symbol(
                    fqn=fqn,
                    kind='interface',
                    file_path=file_path,
                    line_number=node.start_point[0] + 1,
                    column_number=node.start_point[1],
                    namespace=context['namespace']
                )
                symbols.append(symbol)
        
        # Trait declaration
        elif node.type == 'trait_declaration':
            trait_name = self._get_name(node, source)
            if trait_name:
                fqn = self._build_fqn(context['namespace'], trait_name)
                
                symbol = Symbol(
                    fqn=fqn,
                    kind='trait',
                    file_path=file_path,
                    line_number=node.start_point[0] + 1,
                    column_number=node.start_point[1],
                    namespace=context['namespace']
                )
                symbols.append(symbol)
        
        # Method declaration (inside a class)
        elif node.type == 'method_declaration' and context['class']:
            method_name = self._get_name(node, source)
            if method_name:
                # Method FQN includes class
                fqn = f"{context['class']}::{method_name}"
                
                # Extract metadata
                metadata = {
                    'visibility': self._get_visibility(node, source),
                    'static': self._has_modifier(node, 'static', source),
                    'abstract': self._has_modifier(node, 'abstract', source),
                    'return_type': self._get_return_type(node, source),
                    'parameters': self._get_parameters(node, source)
                }
                
                symbol = Symbol(
                    fqn=fqn,
                    kind='method',
                    file_path=file_path,
                    line_number=node.start_point[0] + 1,
                    column_number=node.start_point[1],
                    namespace=context['namespace'],
                    metadata=metadata
                )
                symbols.append(symbol)
        
        # Function declaration (global or namespaced)
        elif node.type == 'function_definition':
            func_name = self._get_name(node, source)
            if func_name:
                fqn = self._build_fqn(context['namespace'], func_name)
                
                metadata = {
                    'return_type': self._get_return_type(node, source),
                    'parameters': self._get_parameters(node, source)
                }
                
                symbol = Symbol(
                    fqn=fqn,
                    kind='function',
                    file_path=file_path,
                    line_number=node.start_point[0] + 1,
                    column_number=node.start_point[1],
                    namespace=context['namespace'],
                    metadata=metadata
                )
                symbols.append(symbol)
        
        # Const declaration
        elif node.type == 'const_declaration':
            for child in node.children:
                if child.type == 'const_element':
                    const_name = self._get_name(child, source)
                    if const_name:
                        fqn = self._build_fqn(context['namespace'], const_name)
                        
                        symbol = Symbol(
                            fqn=fqn,
                            kind='const',
                            file_path=file_path,
                            line_number=child.start_point[0] + 1,
                            column_number=child.start_point[1],
                            namespace=context['namespace']
                        )
                        symbols.append(symbol)
        
        # Recurse to children
        else:
            for child in node.children:
                self._traverse(child, source, file_path, context, symbols)
    
    def _build_fqn(self, namespace: str, name: str) -> str:
        """Build fully qualified name"""
        if namespace:
            return f"{namespace}\\{name}"
        return name
    
    def _get_text(self, node: Node, source: str) -> str:
        """Extract text from node"""
        return source[node.start_byte:node.end_byte]
    
    def _get_name(self, node: Node, source: str) -> Optional[str]:
        """Extract name from declaration node"""
        for child in node.children:
            if child.type == 'name':
                return self._get_text(child, source)
        return None
    
    def _find_child(self, node: Node, type: str) -> Optional[Node]:
        """Find first child of given type"""
        for child in node.children:
            if child.type == type:
                return child
        return None
    
    def _get_modifiers(self, node: Node, source: str) -> List[str]:
        """Extract class modifiers (abstract, final, etc.)"""
        modifiers = []
        for child in node.children:
            if child.type in ['abstract_modifier', 'final_modifier', 'readonly_modifier']:
                modifiers.append(self._get_text(child, source))
        return modifiers
    
    def _get_visibility(self, node: Node, source: str) -> str:
        """Extract method visibility"""
        for child in node.children:
            if child.type == 'visibility_modifier':
                return self._get_text(child, source)
        return 'public'
    
    def _has_modifier(self, node: Node, modifier: str, source: str) -> bool:
        """Check if node has specific modifier"""
        for child in node.children:
            if modifier in self._get_text(child, source):
                return True
        return False
    
    def _get_return_type(self, node: Node, source: str) -> Optional[str]:
        """Extract return type from function/method"""
        for child in node.children:
            if child.type == 'return_type':
                return self._get_text(child, source).replace(':', '').strip()
        return None
    
    def _get_parameters(self, node: Node, source: str) -> List[dict]:
        """Extract function parameters"""
        parameters = []
        params_node = self._find_child(node, 'formal_parameters')
        if params_node:
            for child in params_node.children:
                if child.type == 'simple_parameter' or child.type == 'property_promotion_parameter':
                    param = {
                        'name': None,
                        'type': None,
                        'default': None
                    }
                    
                    # Get parameter name
                    name_node = self._find_child(child, 'variable_name')
                    if name_node:
                        param['name'] = self._get_text(name_node, source)
                    
                    # Get parameter type
                    type_node = self._find_child(child, 'type')
                    if type_node:
                        param['type'] = self._get_text(type_node, source)
                    
                    # Get default value
                    default_node = self._find_child(child, 'default_value')
                    if default_node:
                        param['default'] = self._get_text(default_node, source)
                    
                    parameters.append(param)
        
        return parameters
    
    def _extract_interfaces(self, node: Node, source: str) -> List[str]:
        """Extract interface names from implements clause"""
        interfaces = []
        for child in node.children:
            if child.type == 'qualified_name' or child.type == 'name':
                interfaces.append(self._get_text(child, source))
        return interfaces
```

### 2.2 Pass 2: Reference Resolution

```python
# parsers/php/reference_resolver.py
from typing import List, Dict, Optional
from tree_sitter import Parser, Node
import tree_sitter_php as tsphp
from core.symbol_table import SymbolTable
from core.edges import Edge, EdgeType

class PHPReferenceResolver:
    """
    Pass 2: Resolve all references using the populated Symbol Table.
    This creates edges for imports, inheritance, type hints, etc.
    """
    
    def __init__(self, symbol_table: SymbolTable):
        self.symbol_table = symbol_table
        self.parser = Parser()
        self.parser.set_language(tsphp.language())
    
    def resolve_file(self, file_path: str) -> List[Edge]:
        """
        Parse file again and resolve all references to create edges.
        """
        edges = []
        
        # Read file
        with open(file_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        # Parse to AST
        tree = self.parser.parse(bytes(source_code, 'utf8'))
        
        # Track context
        context = {
            'namespace': '',
            'imports': {},  # alias -> FQN
            'current_class': None,
            'current_method': None,
            'file_path': file_path
        }
        
        # Traverse and resolve
        self._traverse_resolve(tree.root_node, source_code, context, edges)
        
        return edges
    
    def _traverse_resolve(self, node: Node, source: str, context: dict, edges: List[Edge]):
        """Traverse AST and resolve references"""
        
        # Track namespace
        if node.type == 'namespace_definition':
            namespace_node = self._find_child(node, 'namespace_name')
            if namespace_node:
                context['namespace'] = self._get_text(namespace_node, source)
        
        # Process use statements (imports)
        elif node.type == 'use_declaration':
            self._process_use_statement(node, source, context, edges)
        
        # Process class declaration
        elif node.type == 'class_declaration':
            self._process_class(node, source, context, edges)
        
        # Process method declaration
        elif node.type == 'method_declaration':
            self._process_method(node, source, context, edges)
        
        # Process function calls
        elif node.type == 'function_call_expression':
            self._process_function_call(node, source, context, edges)
        
        # Process object creation
        elif node.type == 'object_creation_expression':
            self._process_object_creation(node, source, context, edges)
        
        # Process member access
        elif node.type == 'member_call_expression':
            self._process_member_call(node, source, context, edges)
        
        # Process scoped call (static)
        elif node.type == 'scoped_call_expression':
            self._process_static_call(node, source, context, edges)
        
        # Recurse
        else:
            for child in node.children:
                self._traverse_resolve(child, source, context, edges)
    
    def _process_use_statement(self, node: Node, source: str, context: dict, edges: List[Edge]):
        """
        Process PHP use statement to create USES_NAMESPACE edge.
        Example: use App\Services\EmailService;
        """
        # Get the imported name
        name_node = self._find_child(node, 'qualified_name')
        if not name_node:
            name_node = self._find_child(node, 'namespace_name')
        
        if name_node:
            imported_fqn = self._get_text(name_node, source)
            
            # Check for alias
            alias_node = self._find_child(node, 'namespace_aliasing_clause')
            if alias_node:
                alias = self._get_alias_name(alias_node, source)
            else:
                # Default alias is last part of name
                alias = imported_fqn.split('\\')[-1]
            
            # Store in context for later resolution
            context['imports'][alias] = imported_fqn
            
            # Also store in symbol table for persistence
            self.symbol_table.add_import(
                file_path=context['file_path'],
                imported_fqn=imported_fqn,
                alias=alias if alias != imported_fqn.split('\\')[-1] else None,
                line_number=node.start_point[0] + 1,
                kind='use'
            )
            
            # Try to resolve the imported symbol
            target_symbol = self.symbol_table.resolve(imported_fqn)
            if target_symbol:
                # Create USES_NAMESPACE edge
                edge = Edge(
                    type=EdgeType.USES_NAMESPACE,
                    source_id=context['file_path'],  # File imports the namespace
                    target_id=target_symbol.fqn,
                    properties={
                        'line': node.start_point[0] + 1,
                        'alias': alias if alias != imported_fqn.split('\\')[-1] else None
                    }
                )
                edges.append(edge)
    
    def _process_class(self, node: Node, source: str, context: dict, edges: List[Edge]):
        """Process class declaration for extends and implements edges"""
        class_name = self._get_name(node, source)
        if not class_name:
            return
        
        class_fqn = self._build_fqn(context['namespace'], class_name)
        context['current_class'] = class_fqn
        
        # Process extends
        extends_node = self._find_child(node, 'base_clause')
        if extends_node:
            parent_name = self._extract_parent_name(extends_node, source)
            if parent_name:
                # Resolve parent class
                parent_fqn = self._resolve_class_name(parent_name, context)
                parent_symbol = self.symbol_table.resolve(parent_fqn, context['namespace'], context['imports'])
                
                if parent_symbol:
                    edge = Edge(
                        type=EdgeType.EXTENDS,
                        source_id=class_fqn,
                        target_id=parent_symbol.fqn,
                        properties={'line': extends_node.start_point[0] + 1}
                    )
                    edges.append(edge)
        
        # Process implements
        implements_node = self._find_child(node, 'class_interface_clause')
        if implements_node:
            for interface_node in implements_node.children:
                if interface_node.type in ['qualified_name', 'name']:
                    interface_name = self._get_text(interface_node, source)
                    interface_fqn = self._resolve_class_name(interface_name, context)
                    interface_symbol = self.symbol_table.resolve(
                        interface_fqn, context['namespace'], context['imports']
                    )
                    
                    if interface_symbol:
                        edge = Edge(
                            type=EdgeType.IMPLEMENTS,
                            source_id=class_fqn,
                            target_id=interface_symbol.fqn,
                            properties={'line': interface_node.start_point[0] + 1}
                        )
                        edges.append(edge)
        
        # Process trait usage
        for child in node.children:
            if child.type == 'use_declaration':  # trait use
                self._process_trait_use(child, source, context, edges)
        
        # Process class body
        for child in node.children:
            self._traverse_resolve(child, source, context, edges)
        
        context['current_class'] = None
    
    def _process_method(self, node: Node, source: str, context: dict, edges: List[Edge]):
        """Process method declaration for parameter and return type edges"""
        if not context['current_class']:
            return
        
        method_name = self._get_name(node, source)
        if not method_name:
            return
        
        method_fqn = f"{context['current_class']}::{method_name}"
        context['current_method'] = method_fqn
        
        # Process parameters
        params_node = self._find_child(node, 'formal_parameters')
        if params_node:
            for param in params_node.children:
                if param.type in ['simple_parameter', 'property_promotion_parameter']:
                    # Get parameter type
                    type_node = self._find_child(param, 'type')
                    if type_node:
                        type_name = self._get_text(type_node, source)
                        
                        # Skip primitive types
                        if not self._is_primitive_type(type_name):
                            type_fqn = self._resolve_class_name(type_name, context)
                            type_symbol = self.symbol_table.resolve(
                                type_fqn, context['namespace'], context['imports']
                            )
                            
                            if type_symbol:
                                # This is also dependency injection!
                                edge = Edge(
                                    type=EdgeType.ACCEPTS_TYPE,
                                    source_id=method_fqn,
                                    target_id=type_symbol.fqn,
                                    properties={
                                        'line': param.start_point[0] + 1,
                                        'parameter': self._get_param_name(param, source)
                                    }
                                )
                                edges.append(edge)
                                
                                # If constructor, also create INJECTS edge
                                if method_name == '__construct':
                                    inject_edge = Edge(
                                        type=EdgeType.INJECTS,
                                        source_id=context['current_class'],
                                        target_id=type_symbol.fqn,
                                        properties={
                                            'line': param.start_point[0] + 1,
                                            'via': 'constructor'
                                        }
                                    )
                                    edges.append(inject_edge)
        
        # Process return type
        return_type_node = self._find_child(node, 'return_type')
        if return_type_node:
            return_type = self._get_text(return_type_node, source).replace(':', '').strip()
            
            if not self._is_primitive_type(return_type):
                type_fqn = self._resolve_class_name(return_type, context)
                type_symbol = self.symbol_table.resolve(
                    type_fqn, context['namespace'], context['imports']
                )
                
                if type_symbol:
                    edge = Edge(
                        type=EdgeType.RETURNS_TYPE,
                        source_id=method_fqn,
                        target_id=type_symbol.fqn,
                        properties={'line': return_type_node.start_point[0] + 1}
                    )
                    edges.append(edge)
        
        # Process method body
        for child in node.children:
            self._traverse_resolve(child, source, context, edges)
        
        context['current_method'] = None
    
    def _process_function_call(self, node: Node, source: str, context: dict, edges: List[Edge]):
        """Process function calls to create CALLS edges"""
        if not context['current_method']:
            return
        
        # Get function name
        name_node = self._find_child(node, 'name')
        if name_node:
            func_name = self._get_text(name_node, source)
            
            # Try to resolve as a function
            func_fqn = self._resolve_function_name(func_name, context)
            func_symbol = self.symbol_table.resolve(
                func_fqn, context['namespace'], context['imports']
            )
            
            if func_symbol:
                edge = Edge(
                    type=EdgeType.CALLS,
                    source_id=context['current_method'],
                    target_id=func_symbol.fqn,
                    properties={'line': node.start_point[0] + 1}
                )
                edges.append(edge)
    
    def _process_object_creation(self, node: Node, source: str, context: dict, edges: List[Edge]):
        """Process new ClassName() to create INSTANTIATES edges"""
        if not context['current_method']:
            return
        
        # Get class name
        class_node = self._find_child(node, 'qualified_name')
        if not class_node:
            class_node = self._find_child(node, 'name')
        
        if class_node:
            class_name = self._get_text(class_node, source)
            
            # Handle 'new self()' and 'new parent()'
            if class_name == 'self':
                class_fqn = context['current_class']
            elif class_name == 'parent':
                # Would need to look up parent class
                return
            else:
                class_fqn = self._resolve_class_name(class_name, context)
            
            class_symbol = self.symbol_table.resolve(
                class_fqn, context['namespace'], context['imports']
            )
            
            if class_symbol:
                edge = Edge(
                    type=EdgeType.INSTANTIATES,
                    source_id=context['current_method'],
                    target_id=class_symbol.fqn,
                    properties={'line': node.start_point[0] + 1}
                )
                edges.append(edge)
    
    def _process_member_call(self, node: Node, source: str, context: dict, edges: List[Edge]):
        """Process $obj->method() calls"""
        if not context['current_method']:
            return
        
        # Get method name
        name_node = self._find_child(node, 'name')
        if name_node:
            method_name = self._get_text(name_node, source)
            
            # For now, create unresolved edge
            # Full resolution would require type inference
            edge = Edge(
                type=EdgeType.CALLS,
                source_id=context['current_method'],
                target_id=f"unresolved::{method_name}",
                properties={
                    'line': node.start_point[0] + 1,
                    'dynamic': True
                }
            )
            edges.append(edge)
    
    def _process_static_call(self, node: Node, source: str, context: dict, edges: List[Edge]):
        """Process Class::method() calls"""
        if not context['current_method']:
            return
        
        # Get class and method
        scope_node = self._find_child(node, 'scope_resolution_qualifier')
        name_node = self._find_child(node, 'name')
        
        if scope_node and name_node:
            class_name = self._get_text(scope_node, source)
            method_name = self._get_text(name_node, source)
            
            # Resolve class
            if class_name == 'self':
                class_fqn = context['current_class']
            elif class_name == 'parent':
                # Would need to look up parent
                return
            else:
                class_fqn = self._resolve_class_name(class_name, context)
            
            # Create method FQN
            method_fqn = f"{class_fqn}::{method_name}"
            method_symbol = self.symbol_table.resolve(method_fqn)
            
            if method_symbol:
                edge = Edge(
                    type=EdgeType.CALLS,
                    source_id=context['current_method'],
                    target_id=method_symbol.fqn,
                    properties={'line': node.start_point[0] + 1}
                )
                edges.append(edge)
    
    def _resolve_class_name(self, name: str, context: dict) -> str:
        """Resolve a class name to FQN using imports and namespace"""
        # Already fully qualified
        if name.startswith('\\'):
            return name[1:]
        
        # Check imports
        if name in context['imports']:
            return context['imports'][name]
        
        # Check if it's a partial match in imports
        for alias, fqn in context['imports'].items():
            if name.startswith(alias + '\\'):
                return fqn + name[len(alias):]
        
        # Assume current namespace
        if context['namespace']:
            return f"{context['namespace']}\\{name}"
        
        return name
    
    def _resolve_function_name(self, name: str, context: dict) -> str:
        """Resolve function name to FQN"""
        # Check if namespaced
        if '\\' in name:
            return self._resolve_class_name(name, context)
        
        # Otherwise assume current namespace or global
        if context['namespace']:
            return f"{context['namespace']}\\{name}"
        return name
    
    def _is_primitive_type(self, type_name: str) -> bool:
        """Check if type is a PHP primitive"""
        primitives = {
            'int', 'integer', 'float', 'double', 'string', 'bool', 
            'boolean', 'array', 'object', 'mixed', 'void', 'null',
            'callable', 'iterable', 'resource', 'never'
        }
        # Handle nullable types
        type_name = type_name.replace('?', '').strip()
        # Handle union types (simplified)
        if '|' in type_name:
            return all(t.strip() in primitives for t in type_name.split('|'))
        return type_name.lower() in primitives
    
    # ... (helper methods remain the same as in Pass 1)
```

### 2.3 Edge Definition

```python
# core/edges.py
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, Optional

class EdgeType(Enum):
    """All possible edge types in the code graph"""
    
    # Import/Dependency edges
    USES_NAMESPACE = "USES_NAMESPACE"       # PHP use statement
    IMPORTS_CLASS = "IMPORTS_CLASS"         # Specific class import
    IMPORTS_ES6 = "IMPORTS_ES6"             # ES6 import
    REQUIRES_MODULE = "REQUIRES_MODULE"     # CommonJS require
    INCLUDES_FILE = "INCLUDES_FILE"         # PHP include/require
    
    # Type system edges
    EXTENDS = "EXTENDS"                     # Class inheritance
    IMPLEMENTS = "IMPLEMENTS"               # Interface implementation
    USES_TRAIT = "USES_TRAIT"               # PHP trait usage
    RETURNS_TYPE = "RETURNS_TYPE"           # Method return type
    ACCEPTS_TYPE = "ACCEPTS_TYPE"           # Parameter type
    THROWS = "THROWS"                       # Exception throwing
    CATCHES = "CATCHES"                     # Exception catching
    
    # Call edges
    CALLS = "CALLS"                         # Method/function call
    INSTANTIATES = "INSTANTIATES"           # Object creation
    CALLS_STATIC = "CALLS_STATIC"           # Static method call
    
    # Dependency injection
    INJECTS = "INJECTS"                     # DI injection
    PROVIDES = "PROVIDES"                   # DI provision
    BINDS_TO = "BINDS_TO"                   # Interface binding
    
    # Event system
    LISTENS_TO = "LISTENS_TO"               # Event listener
    EMITS = "EMITS"                         # Event emission
    SUBSCRIBES_TO = "SUBSCRIBES_TO"         # Observable subscription
    
    # Configuration
    CONFIGURED_BY = "CONFIGURED_BY"         # Config relationship
    ROUTES_TO = "ROUTES_TO"                 # URL routing
    MAPS_TO = "MAPS_TO"                     # Config mapping
    
    # Data access
    READS = "READS"                         # Property read
    WRITES = "WRITES"                       # Property write
    QUERIES = "QUERIES"                     # Database query
    MODEL_OPERATION = "MODEL_OPERATION"     # ORM operation
    
    # Framework specific
    RENDERS = "RENDERS"                     # Component rendering
    CONTAINS_COMPONENT = "CONTAINS_COMPONENT"  # Component hierarchy
    MIDDLEWARE = "MIDDLEWARE"               # Middleware chain
    
    # File system
    DEFINED_IN = "DEFINED_IN"               # Symbol defined in file
    IN_DIRECTORY = "IN_DIRECTORY"           # File in directory
    CONTAINS = "CONTAINS"                   # Directory contains file
    
    # Special
    DYNAMIC_IMPORT = "DYNAMIC_IMPORT"       # Unresolved dynamic import
    UNRESOLVED = "UNRESOLVED"               # Unresolved reference

@dataclass
class Edge:
    """Represents a relationship between code elements"""
    type: EdgeType
    source_id: str                          # FQN or ID of source
    target_id: str                          # FQN or ID of target
    properties: Dict[str, Any] = None       # Additional properties
    confidence: float = 1.0                 # 0-1 confidence score
    
    def to_cypher_params(self) -> Dict:
        """Convert to parameters for Cypher query"""
        params = {
            'type': self.type.value,
            'source_id': self.source_id,
            'target_id': self.target_id,
            'confidence': self.confidence
        }
        
        if self.properties:
            params.update(self.properties)
        
        return params
```

---

## Phase 3: Neo4j Integration

### 3.1 Neo4j Writer

```python
# core/neo4j_writer.py
from typing import List, Dict, Any
from neo4j import GraphDatabase, Transaction
import logging
from core.edges import Edge
from core.symbol_table import Symbol

class Neo4jWriter:
    """
    Handles all Neo4j operations.
    Batch writes nodes and edges after parsing completes.
    """
    
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.logger = logging.getLogger(__name__)
    
    def close(self):
        self.driver.close()
    
    def write_symbols_and_edges(self, symbols: List[Symbol], edges: List[Edge], 
                               batch_size: int = 10000):
        """
        Write all symbols as nodes and all edges to Neo4j.
        This is called AFTER all parsing passes complete.
        """
        with self.driver.session() as session:
            # Write symbols first
            self._write_symbols_batch(session, symbols, batch_size)
            
            # Then write edges
            self._write_edges_batch(session, edges, batch_size)
            
            # Create indexes
            self._create_indexes(session)
    
    def _write_symbols_batch(self, session, symbols: List[Symbol], batch_size: int):
        """Batch write symbols as nodes"""
        
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            
            # Prepare data for UNWIND
            nodes_data = []
            for symbol in batch:
                node_data = {
                    'id': symbol.fqn,
                    'name': symbol.fqn.split('::')[-1].split('\\')[-1],
                    'fqn': symbol.fqn,
                    'kind': symbol.kind,
                    'file_path': symbol.file_path,
                    'line_number': symbol.line_number,
                    'namespace': symbol.namespace or '',
                    'exported': symbol.exported
                }
                
                # Add metadata
                if symbol.metadata:
                    node_data.update(symbol.metadata)
                
                nodes_data.append(node_data)
            
            # Execute batch insert
            query = """
            UNWIND $nodes AS node
            MERGE (n:Symbol {id: node.id})
            SET n += node
            WITH n, node
            CALL apoc.create.addLabels(n, [node.kind]) YIELD node AS labeled
            RETURN count(labeled)
            """
            
            result = session.run(query, nodes=nodes_data)
            count = result.single()[0]
            self.logger.info(f"Wrote {count} symbol nodes")
    
    def _write_edges_batch(self, session, edges: List[Edge], batch_size: int):
        """Batch write edges"""
        
        # Group edges by type for more efficient queries
        edges_by_type = {}
        for edge in edges:
            edge_type = edge.type.value
            if edge_type not in edges_by_type:
                edges_by_type[edge_type] = []
            edges_by_type[edge_type].append(edge)
        
        # Write each edge type
        for edge_type, typed_edges in edges_by_type.items():
            for i in range(0, len(typed_edges), batch_size):
                batch = typed_edges[i:i + batch_size]
                
                # Prepare data
                edges_data = []
                for edge in batch:
                    edge_data = {
                        'source_id': edge.source_id,
                        'target_id': edge.target_id,
                        'confidence': edge.confidence
                    }
                    
                    if edge.properties:
                        edge_data.update(edge.properties)
                    
                    edges_data.append(edge_data)
                
                # Create edges
                query = f"""
                UNWIND $edges AS edge
                MATCH (source:Symbol {{id: edge.source_id}})
                MATCH (target:Symbol {{id: edge.target_id}})
                MERGE (source)-[r:{edge_type}]->(target)
                SET r += edge
                RETURN count(r)
                """
                
                result = session.run(query, edges=edges_data)
                count = result.single()[0]
                self.logger.info(f"Wrote {count} {edge_type} edges")
    
    def _create_indexes(self, session):
        """Create indexes for better query performance"""
        indexes = [
            "CREATE INDEX symbol_id IF NOT EXISTS FOR (n:Symbol) ON (n.id)",
            "CREATE INDEX symbol_fqn IF NOT EXISTS FOR (n:Symbol) ON (n.fqn)",
            "CREATE INDEX symbol_name IF NOT EXISTS FOR (n:Symbol) ON (n.name)",
            "CREATE INDEX symbol_kind IF NOT EXISTS FOR (n:Symbol) ON (n.kind)",
            "CREATE INDEX symbol_file IF NOT EXISTS FOR (n:Symbol) ON (n.file_path)",
            "CREATE INDEX class_name IF NOT EXISTS FOR (n:class) ON (n.name)",
            "CREATE INDEX method_name IF NOT EXISTS FOR (n:method) ON (n.name)",
            "CREATE INDEX function_name IF NOT EXISTS FOR (n:function) ON (n.name)"
        ]
        
        for index_query in indexes:
            try:
                session.run(index_query)
                self.logger.info(f"Created index: {index_query}")
            except Exception as e:
                self.logger.warning(f"Index might already exist: {e}")
    
    def clear_database(self):
        """Clear all nodes and relationships (use with caution!)"""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            self.logger.info("Cleared database")
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        with self.driver.session() as session:
            stats = {}
            
            # Count nodes
            result = session.run("MATCH (n) RETURN count(n) as count")
            stats['total_nodes'] = result.single()['count']
            
            # Count by label
            result = session.run("""
                MATCH (n)
                UNWIND labels(n) as label
                RETURN label, count(n) as count
                ORDER BY count DESC
            """)
            stats['nodes_by_label'] = {row['label']: row['count'] for row in result}
            
            # Count relationships
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            stats['total_relationships'] = result.single()['count']
            
            # Count by type
            result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as type, count(r) as count
                ORDER BY count DESC
            """)
            stats['relationships_by_type'] = {row['type']: row['count'] for row in result}
            
            return stats
```

### 3.2 Incremental Updates

```python
# core/incremental_updater.py
import hashlib
from pathlib import Path
from typing import List, Set
import json

class IncrementalUpdater:
    """
    Handles incremental updates to avoid full re-parsing.
    Tracks file changes and updates only affected parts.
    """
    
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.hash_file = self.cache_dir / "file_hashes.json"
        self.hashes = self._load_hashes()
    
    def _load_hashes(self) -> Dict[str, str]:
        """Load cached file hashes"""
        if self.hash_file.exists():
            with open(self.hash_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_hashes(self):
        """Save file hashes to cache"""
        with open(self.hash_file, 'w') as f:
            json.dump(self.hashes, f, indent=2)
    
    def get_file_hash(self, file_path: str) -> str:
        """Calculate hash of file contents"""
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    
    def get_changed_files(self, project_files: List[str]) -> tuple[List[str], List[str]]:
        """
        Determine which files have changed.
        Returns (changed_files, deleted_files)
        """
        changed = []
        current_files = set()
        
        for file_path in project_files:
            current_files.add(file_path)
            current_hash = self.get_file_hash(file_path)
            
            if file_path not in self.hashes or self.hashes[file_path] != current_hash:
                changed.append(file_path)
                self.hashes[file_path] = current_hash
        
        # Find deleted files
        deleted = []
        for file_path in list(self.hashes.keys()):
            if file_path not in current_files:
                deleted.append(file_path)
                del self.hashes[file_path]
        
        self._save_hashes()
        return changed, deleted
    
    def find_dependent_files(self, changed_files: List[str], 
                           neo4j_writer) -> Set[str]:
        """
        Find all files that depend on changed files.
        This requires querying Neo4j for incoming edges.
        """
        dependent_files = set()
        
        with neo4j_writer.driver.session() as session:
            for file_path in changed_files:
                # Find all nodes in this file
                result = session.run("""
                    MATCH (n:Symbol {file_path: $file_path})
                    RETURN n.id as symbol_id
                """, file_path=file_path)
                
                symbol_ids = [row['symbol_id'] for row in result]
                
                # Find all files that reference these symbols
                for symbol_id in symbol_ids:
                    result = session.run("""
                        MATCH (source:Symbol)-[]->(target:Symbol {id: $symbol_id})
                        RETURN DISTINCT source.file_path as file_path
                    """, symbol_id=symbol_id)
                    
                    for row in result:
                        if row['file_path'] != file_path:
                            dependent_files.add(row['file_path'])
        
        return dependent_files
    
    def remove_file_from_graph(self, file_path: str, neo4j_writer):
        """Remove all nodes and edges related to a file"""
        with neo4j_writer.driver.session() as session:
            # Delete nodes and their relationships
            session.run("""
                MATCH (n:Symbol {file_path: $file_path})
                DETACH DELETE n
            """, file_path=file_path)
```

---

## Phase 4: Framework Plugins

### 4.1 Plugin Interface

```python
# plugins/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from pathlib import Path
from core.edges import Edge
from core.symbol_table import SymbolTable

class FrameworkPlugin(ABC):
    """Base class for all framework-specific plugins"""
    
    @abstractmethod
    def detect(self, project_root: Path) -> bool:
        """Check if this plugin applies to the project"""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get plugin name"""
        pass
    
    @abstractmethod
    def analyze_file(self, file_path: str, ast: Any, 
                    symbol_table: SymbolTable) -> List[Edge]:
        """
        Analyze a single file for framework-specific patterns.
        Called during Pass 3.
        """
        pass
    
    @abstractmethod
    def analyze_config(self, project_root: Path, 
                      symbol_table: SymbolTable) -> List[Edge]:
        """
        Analyze configuration files.
        Called once after all files are processed.
        """
        pass
    
    def get_priority(self) -> int:
        """
        Plugin priority (higher = runs first).
        Useful when multiple plugins might apply.
        """
        return 0
```

### 4.2 Laravel Plugin

```python
# plugins/laravel/plugin.py
from pathlib import Path
from typing import List, Dict, Any
import json
import re
from plugins.base import FrameworkPlugin
from core.edges import Edge, EdgeType
from core.symbol_table import SymbolTable

class LaravelPlugin(FrameworkPlugin):
    """
    Laravel framework plugin.
    Detects DI container usage, routes, events, etc.
    """
    
    def detect(self, project_root: Path) -> bool:
        """Check for Laravel markers"""
        markers = [
            'artisan',
            'bootstrap/app.php',
            'config/app.php',
            'composer.json'  # Check for laravel/framework
        ]
        
        for marker in markers:
            if (project_root / marker).exists():
                # Extra check for composer.json
                if marker == 'composer.json':
                    with open(project_root / marker) as f:
                        data = json.load(f)
                        if 'laravel/framework' in data.get('require', {}):
                            return True
                else:
                    return True
        
        return False
    
    def get_name(self) -> str:
        return "Laravel"
    
    def analyze_file(self, file_path: str, ast: Any, 
                    symbol_table: SymbolTable) -> List[Edge]:
        """Detect Laravel-specific patterns in PHP files"""
        edges = []
        
        # Read source for pattern matching
        with open(file_path, 'r') as f:
            source = f.read()
        
        # Detect DI container calls
        edges.extend(self._detect_container_calls(file_path, source, symbol_table))
        
        # Detect event dispatching
        edges.extend(self._detect_events(file_path, source, symbol_table))
        
        # Detect facade usage
        edges.extend(self._detect_facades(file_path, source, symbol_table))
        
        # Detect model relationships
        edges.extend(self._detect_model_relationships(file_path, source, symbol_table))
        
        return edges
    
    def analyze_config(self, project_root: Path, 
                      symbol_table: SymbolTable) -> List[Edge]:
        """Analyze Laravel configuration files"""
        edges = []
        
        # Parse routes
        edges.extend(self._parse_routes(project_root, symbol_table))
        
        # Parse service providers
        edges.extend(self._parse_service_providers(project_root, symbol_table))
        
        # Parse event listeners
        edges.extend(self._parse_event_listeners(project_root, symbol_table))
        
        return edges
    
    def _detect_container_calls(self, file_path: str, source: str, 
                               symbol_table: SymbolTable) -> List[Edge]:
        """Detect app(), resolve(), etc."""
        edges = []
        
        # Patterns for container resolution
        patterns = [
            r'app\(\s*([\'"])([^\'"]+)\1\s*\)',           # app('service')
            r'app\(\s*(\w+)::class\s*\)',                  # app(Service::class)
            r'resolve\(\s*([\'"])([^\'"]+)\1\s*\)',        # resolve('service')
            r'resolve\(\s*(\w+)::class\s*\)',              # resolve(Service::class)
            r'\$this->app->make\(\s*([\'"])([^\'"]+)\1\s*\)',  # $this->app->make()
            r'\$this->app->make\(\s*(\w+)::class\s*\)',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, source):
                if '::class' in match.group(0):
                    # Class constant resolution
                    class_name = match.group(1)
                    # Would need to resolve imports here
                else:
                    # String resolution
                    service_name = match.group(2) if match.lastindex >= 2 else match.group(1)
                
                # Create INJECTS edge
                # This is simplified - would need proper context
                edge = Edge(
                    type=EdgeType.INJECTS,
                    source_id=file_path,
                    target_id=f"laravel:service:{service_name}",
                    properties={
                        'line': source[:match.start()].count('\n') + 1,
                        'via': 'container'
                    }
                )
                edges.append(edge)
        
        return edges
    
    def _detect_events(self, file_path: str, source: str, 
                      symbol_table: SymbolTable) -> List[Edge]:
        """Detect event dispatching and listening"""
        edges = []
        
        # Event dispatching patterns
        dispatch_patterns = [
            r'event\(\s*new\s+(\w+)\s*\(',                    # event(new UserRegistered())
            r'Event::dispatch\(\s*new\s+(\w+)\s*\(',          # Event::dispatch(new ...)
            r'\$this->dispatch\(\s*new\s+(\w+)\s*\(',         # $this->dispatch(new ...)
        ]
        
        for pattern in dispatch_patterns:
            for match in re.finditer(pattern, source):
                event_class = match.group(1)
                
                edge = Edge(
                    type=EdgeType.EMITS,
                    source_id=file_path,
                    target_id=f"event:{event_class}",
                    properties={
                        'line': source[:match.start()].count('\n') + 1
                    }
                )
                edges.append(edge)
        
        return edges
    
    def _detect_facades(self, file_path: str, source: str, 
                       symbol_table: SymbolTable) -> List[Edge]:
        """Detect Laravel facade usage"""
        edges = []
        
        # Common facades
        facades = [
            'Auth', 'Cache', 'Config', 'Cookie', 'Crypt', 'DB', 
            'Event', 'File', 'Gate', 'Hash', 'Http', 'Lang', 'Log',
            'Mail', 'Notification', 'Password', 'Queue', 'Redirect',
            'Redis', 'Request', 'Response', 'Route', 'Schema', 
            'Session', 'Storage', 'URL', 'Validator', 'View'
        ]
        
        for facade in facades:
            pattern = rf'\b{facade}::\w+'
            if re.search(pattern, source):
                edge = Edge(
                    type=EdgeType.USES_NAMESPACE,
                    source_id=file_path,
                    target_id=f"laravel:facade:{facade}",
                    properties={'facade': True}
                )
                edges.append(edge)
        
        return edges
    
    def _detect_model_relationships(self, file_path: str, source: str,
                                   symbol_table: SymbolTable) -> List[Edge]:
        """Detect Eloquent model relationships"""
        edges = []
        
        # Relationship methods
        relationships = {
            'hasOne': 'HAS_ONE',
            'hasMany': 'HAS_MANY',
            'belongsTo': 'BELONGS_TO',
            'belongsToMany': 'BELONGS_TO_MANY',
            'morphTo': 'MORPHS_TO',
            'morphMany': 'MORPHS_MANY'
        }
        
        for method, rel_type in relationships.items():
            pattern = rf'return\s+\$this->{method}\(\s*(\w+)::class'
            for match in re.finditer(pattern, source):
                related_model = match.group(1)
                
                edge = Edge(
                    type=EdgeType.MODEL_OPERATION,
                    source_id=file_path,
                    target_id=f"model:{related_model}",
                    properties={
                        'relationship': rel_type,
                        'line': source[:match.start()].count('\n') + 1
                    }
                )
                edges.append(edge)
        
        return edges
    
    def _parse_routes(self, project_root: Path, 
                     symbol_table: SymbolTable) -> List[Edge]:
        """Parse route files"""
        edges = []
        route_files = [
            'routes/web.php',
            'routes/api.php',
            'routes/console.php'
        ]
        
        for route_file in route_files:
            file_path = project_root / route_file
            if not file_path.exists():
                continue
            
            with open(file_path, 'r') as f:
                source = f.read()
            
            # Parse Route:: definitions
            # Route::get('/path', [Controller::class, 'method'])
            pattern = r'Route::(\w+)\(\s*[\'"]([^\'"]+)[\'"],\s*\[(\w+)::class,\s*[\'"](\w+)[\'"]\]'
            
            for match in re.finditer(pattern, source):
                http_method = match.group(1)
                path = match.group(2)
                controller = match.group(3)
                method = match.group(4)
                
                # Resolve controller FQN
                controller_fqn = f"App\\Http\\Controllers\\{controller}"
                controller_symbol = symbol_table.resolve(controller_fqn)
                
                if controller_symbol:
                    method_fqn = f"{controller_fqn}::{method}"
                    method_symbol = symbol_table.resolve(method_fqn)
                    
                    if method_symbol:
                        edge = Edge(
                            type=EdgeType.ROUTES_TO,
                            source_id=str(file_path),
                            target_id=method_symbol.fqn,
                            properties={
                                'path': path,
                                'http_method': http_method.upper(),
                                'line': source[:match.start()].count('\n') + 1
                            }
                        )
                        edges.append(edge)
        
        return edges
    
    def _parse_service_providers(self, project_root: Path,
                                symbol_table: SymbolTable) -> List[Edge]:
        """Parse service provider registrations"""
        edges = []
        
        # Read config/app.php
        config_file = project_root / 'config' / 'app.php'
        if config_file.exists():
            with open(config_file, 'r') as f:
                source = f.read()
            
            # Parse providers array
            # This is simplified - would need proper PHP parsing
            pattern = r"'providers'\s*=>\s*\[(.*?)\]"
            match = re.search(pattern, source, re.DOTALL)
            
            if match:
                providers_section = match.group(1)
                provider_pattern = r'(\w+\\[\w\\]+)::class'
                
                for provider_match in re.finditer(provider_pattern, providers_section):
                    provider_fqn = provider_match.group(1).replace('\\\\', '\\')
                    
                    edge = Edge(
                        type=EdgeType.PROVIDES,
                        source_id=provider_fqn,
                        target_id='laravel:application',
                        properties={'auto_discovered': False}
                    )
                    edges.append(edge)
        
        return edges
    
    def _parse_event_listeners(self, project_root: Path,
                              symbol_table: SymbolTable) -> List[Edge]:
        """Parse EventServiceProvider for event->listener mappings"""
        edges = []
        
        provider_file = project_root / 'app' / 'Providers' / 'EventServiceProvider.php'
        if provider_file.exists():
            with open(provider_file, 'r') as f:
                source = f.read()
            
            # Parse $listen array
            pattern = r'\$listen\s*=\s*\[(.*?)\];'
            match = re.search(pattern, source, re.DOTALL)
            
            if match:
                listen_section = match.group(1)
                # Parse event => [listeners] mappings
                mapping_pattern = r'(\w+)::class\s*=>\s*\[(.*?)\]'
                
                for mapping in re.finditer(mapping_pattern, listen_section, re.DOTALL):
                    event_class = mapping.group(1)
                    listeners_section = mapping.group(2)
                    
                    # Extract listener classes
                    listener_pattern = r'(\w+)::class'
                    for listener_match in re.finditer(listener_pattern, listeners_section):
                        listener_class = listener_match.group(1)
                        
                        edge = Edge(
                            type=EdgeType.LISTENS_TO,
                            source_id=listener_class,
                            target_id=event_class,
                            properties={'via': 'EventServiceProvider'}
                        )
                        edges.append(edge)
        
        return edges
```

---

## Phase 5: Query Interface

### 5.1 Query Engine

```python
# query/engine.py
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from neo4j import GraphDatabase

@dataclass
class QueryResult:
    """Result from a code graph query"""
    paths: List[List[Dict]]          # List of paths (each path is a list of nodes/edges)
    nodes: List[Dict]                # Unique nodes involved
    edges: List[Dict]                # Unique edges involved
    count: int                       # Total results
    query_time_ms: float            # Query execution time
    
class QueryEngine:
    """
    High-level query interface for the code graph.
    Translates natural language to Cypher and executes queries.
    """
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.query_templates = self._init_query_templates()
    
    def _init_query_templates(self) -> Dict[str, str]:
        """Initialize common query templates"""
        return {
            'mail_flow': """
                MATCH path = (entry)-[:CALLS|INJECTS|CONFIGURED_BY|ROUTES_TO*1..15]->(mail:Symbol)
                WHERE mail.fqn =~ '(?i).*mail.*send.*'
                   OR mail.name =~ '(?i).*send.*mail.*'
                   OR (mail)-[:USES_NAMESPACE]->(:Symbol {name: 'Laminas\\Mail'})
                RETURN path
                LIMIT 25
            """,
            
            'class_hierarchy': """
                MATCH path = (child:class)-[:EXTENDS*]->(parent:class {name: $class_name})
                RETURN path
            """,
            
            'interface_implementations': """
                MATCH (impl:class)-[:IMPLEMENTS]->(interface:interface {name: $interface_name})
                RETURN impl
            """,
            
            'method_calls': """
                MATCH path = (caller)-[:CALLS*1..5]->(target:method {name: $method_name})
                RETURN path
                LIMIT 50
            """,
            
            'dependency_injection': """
                MATCH (class:class)-[:INJECTS]->(dependency)
                WHERE class.name = $class_name
                RETURN dependency
            """,
            
            'impact_analysis': """
                MATCH (changed:Symbol {fqn: $symbol_fqn})
                MATCH path = (dependent)-[*1..3]->(changed)
                RETURN DISTINCT dependent
            """,
            
            'find_unused': """
                MATCH (n:Symbol)
                WHERE NOT (n)<-[:CALLS|IMPORTS_CLASS|EXTENDS|IMPLEMENTS]-()
                  AND n.kind IN ['class', 'method', 'function']
                RETURN n
                LIMIT 100
            """,
            
            'circular_dependencies': """
                MATCH path = (a:class)-[:IMPORTS_CLASS|EXTENDS|INJECTS*2..10]->(a)
                RETURN path
                LIMIT 10
            """,
            
            'api_endpoints': """
                MATCH (route)-[:ROUTES_TO]->(controller:method)
                RETURN route.path as endpoint, 
                       route.http_method as method,
                       controller.fqn as handler
                ORDER BY endpoint
            """,
            
            'event_flow': """
                MATCH (emitter)-[:EMITS]->(event)<-[:LISTENS_TO]-(listener)
                WHERE event.name = $event_name
                RETURN emitter, event, listener
            """
        }
    
    def query(self, natural_language: str) -> QueryResult:
        """
        Execute a natural language query.
        This is simplified - in production you'd use NLP or an LLM.
        """
        # Detect query type from keywords
        query_lower = natural_language.lower()
        
        if 'mail' in query_lower or 'email' in query_lower:
            return self.mail_flow_query()
        elif 'extends' in query_lower or 'inherits' in query_lower:
            # Extract class name
            class_name = self._extract_class_name(natural_language)
            return self.class_hierarchy_query(class_name)
        elif 'implements' in query_lower:
            interface_name = self._extract_interface_name(natural_language)
            return self.interface_implementations_query(interface_name)
        elif 'calls' in query_lower:
            method_name = self._extract_method_name(natural_language)
            return self.method_calls_query(method_name)
        elif 'unused' in query_lower or 'dead code' in query_lower:
            return self.find_unused_code()
        elif 'circular' in query_lower:
            return self.find_circular_dependencies()
        elif 'api' in query_lower or 'endpoints' in query_lower:
            return self.get_api_endpoints()
        else:
            # Fall back to generic search
            return self.generic_search(natural_language)
    
    def mail_flow_query(self) -> QueryResult:
        """Find all paths leading to mail sending"""
        return self._execute_template('mail_flow')
    
    def class_hierarchy_query(self, class_name: str) -> QueryResult:
        """Find class inheritance hierarchy"""
        return self._execute_template('class_hierarchy', class_name=class_name)
    
    def interface_implementations_query(self, interface_name: str) -> QueryResult:
        """Find all implementations of an interface"""
        return self._execute_template('interface_implementations', 
                                     interface_name=interface_name)
    
    def method_calls_query(self, method_name: str) -> QueryResult:
        """Find all calls to a method"""
        return self._execute_template('method_calls', method_name=method_name)
    
    def find_unused_code(self) -> QueryResult:
        """Find potentially unused code"""
        return self._execute_template('find_unused')
    
    def find_circular_dependencies(self) -> QueryResult:
        """Find circular dependency chains"""
        return self._execute_template('circular_dependencies')
    
    def get_api_endpoints(self) -> QueryResult:
        """Get all API endpoints"""
        return self._execute_template('api_endpoints')
    
    def impact_analysis(self, symbol_fqn: str) -> QueryResult:
        """Analyze impact of changing a symbol"""
        return self._execute_template('impact_analysis', symbol_fqn=symbol_fqn)
    
    def _execute_template(self, template_name: str, **params) -> QueryResult:
        """Execute a query template"""
        import time
        
        query = self.query_templates[template_name]
        
        with self.driver.session() as session:
            start = time.time()
            result = session.run(query, **params)
            
            paths = []
            all_nodes = {}
            all_edges = {}
            
            for record in result:
                if 'path' in record:
                    path = record['path']
                    path_data = []
                    
                    # Process nodes
                    for node in path.nodes:
                        node_data = dict(node)
                        node_id = node_data.get('id', id(node))
                        all_nodes[node_id] = node_data
                        path_data.append({'type': 'node', 'data': node_data})
                    
                    # Process relationships
                    for rel in path.relationships:
                        rel_data = {
                            'type': type(rel).__name__,
                            'properties': dict(rel),
                            'start': rel.start_node.get('id'),
                            'end': rel.end_node.get('id')
                        }
                        edge_id = f"{rel_data['start']}-{rel_data['type']}-{rel_data['end']}"
                        all_edges[edge_id] = rel_data
                        path_data.append({'type': 'edge', 'data': rel_data})
                    
                    paths.append(path_data)
                else:
                    # Non-path results
                    for key, value in record.items():
                        if hasattr(value, 'get'):  # Node
                            node_data = dict(value)
                            node_id = node_data.get('id', id(value))
                            all_nodes[node_id] = node_data
            
            query_time = (time.time() - start) * 1000
            
            return QueryResult(
                paths=paths,
                nodes=list(all_nodes.values()),
                edges=list(all_edges.values()),
                count=len(paths) if paths else len(all_nodes),
                query_time_ms=query_time
            )
    
    def cypher(self, cypher_query: str, **params) -> QueryResult:
        """Execute raw Cypher query"""
        with self.driver.session() as session:
            result = session.run(cypher_query, **params)
            
            # Simplified result processing
            records = []
            for record in result:
                records.append(dict(record))
            
            return QueryResult(
                paths=[],
                nodes=records,
                edges=[],
                count=len(records),
                query_time_ms=0
            )
    
    def _extract_class_name(self, text: str) -> str:
        """Extract class name from natural language"""
        # This is simplified - use NLP in production
        import re
        match = re.search(r'\b([A-Z]\w+)\b', text)
        return match.group(1) if match else 'Unknown'
    
    def _extract_interface_name(self, text: str) -> str:
        """Extract interface name from natural language"""
        import re
        match = re.search(r'\b([A-Z]\w+Interface)\b', text)
        if not match:
            match = re.search(r'\b([A-Z]\w+)\b', text)
        return match.group(1) if match else 'Unknown'
    
    def _extract_method_name(self, text: str) -> str:
        """Extract method name from natural language"""
        import re
        match = re.search(r'\b([a-z]\w+)\b', text)
        return match.group(1) if match else 'unknown'
    
    def generic_search(self, query: str) -> QueryResult:
        """Generic text search across symbols"""
        cypher = """
        MATCH (n:Symbol)
        WHERE n.name =~ $pattern OR n.fqn =~ $pattern
        RETURN n
        LIMIT 100
        """
        
        # Create regex pattern
        keywords = query.split()
        pattern = '(?i).*' + '.*'.join(keywords) + '.*'
        
        return self.cypher(cypher, pattern=pattern)
```

---

## Performance Optimization

### Benchmarks and Targets

| Metric | Current | Target | Method |
|--------|---------|--------|--------|
| Parse speed | ~100 files/sec | 10K files/sec | Parallel processing |
| Symbol lookup | ~10K/sec | 150K/sec | LRU cache + indexes |
| Neo4j write | ~1K nodes/sec | 6M nodes/sec | Batch UNWIND |
| Query response | 1-5 sec | <100ms | Proper indexes |
| Memory usage | Unbounded | <4GB for 1M LOC | Streaming processing |

### Optimization Strategies

1. **Parallel Processing**
```python
from multiprocessing import Pool, cpu_count

def process_files_parallel(files: List[str], symbol_table: SymbolTable):
    with Pool(cpu_count()) as pool:
        # Pass 1: Collect symbols in parallel
        symbol_batches = pool.map(collect_symbols_worker, files)
        
        # Merge into symbol table
        for symbols in symbol_batches:
            symbol_table.bulk_add_symbols(symbols)
        
        # Pass 2: Resolve references in parallel
        edge_batches = pool.map(resolve_references_worker, files)
        
        # Merge edges
        all_edges = []
        for edges in edge_batches:
            all_edges.extend(edges)
        
        return all_edges
```

2. **Memory Management**
- Process files one at a time
- Don't keep ASTs in memory
- Use generators where possible
- Set cache size limits

3. **Database Optimization**
- Use covering indexes
- Batch operations (10K+ per transaction)
- Connection pooling
- Disable constraints during bulk import

---

## Testing Strategy

### Unit Tests

```python
# tests/test_symbol_table.py
def test_symbol_resolution():
    table = SymbolTable(":memory:")
    
    # Add symbol
    symbol = Symbol(
        fqn="App\\Services\\EmailService",
        kind="class",
        file_path="/app/Services/EmailService.php",
        line_number=10
    )
    table.add_symbol(symbol)
    
    # Test exact resolution
    resolved = table.resolve("App\\Services\\EmailService")
    assert resolved.fqn == "App\\Services\\EmailService"
    
    # Test with namespace context
    resolved = table.resolve("EmailService", "App\\Services")
    assert resolved.fqn == "App\\Services\\EmailService"
    
    # Test with imports
    imports = {"EmailService": "App\\Services\\EmailService"}
    resolved = table.resolve("EmailService", imports=imports)
    assert resolved.fqn == "App\\Services\\EmailService"
```

### Integration Tests

```python
# tests/test_end_to_end.py
def test_mail_flow_detection():
    # Parse sample code
    code = """
    <?php
    namespace App\\Controllers;
    use App\\Services\\EmailService;
    
    class UserController {
        public function register(EmailService $mailer) {
            $mailer->send($email);
        }
    }
    """
    
    # Run full pipeline
    symbols = pass1_collect(code)
    edges = pass2_resolve(code, symbols)
    
    # Verify edges
    assert any(e.type == EdgeType.USES_NAMESPACE for e in edges)
    assert any(e.type == EdgeType.INJECTS for e in edges)
    assert any(e.type == EdgeType.CALLS for e in edges)
```

---

## Deployment & Operations

### Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Run
CMD ["python", "-m", "code_graph.main"]
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  neo4j:
    image: neo4j:5.27.0
    environment:
      - NEO4J_AUTH=neo4j/password
      - NEO4J_PLUGINS=["apoc"]
      - NEO4J_dbms_memory_heap_max__size=4G
    ports:
      - "7474:7474"
      - "7687:7687"
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs

  parser:
    build: .
    environment:
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=password
    volumes:
      - ./code:/code
      - ./cache:/cache
    depends_on:
      - neo4j

volumes:
  neo4j_data:
  neo4j_logs:
```

### Monitoring

```python
# monitoring/metrics.py
import time
from dataclasses import dataclass
from typing import Dict

@dataclass
class Metrics:
    files_parsed: int = 0
    symbols_created: int = 0
    edges_created: int = 0
    parse_time_ms: float = 0
    neo4j_time_ms: float = 0
    
    def to_dict(self) -> Dict:
        return {
            'files_parsed': self.files_parsed,
            'symbols_created': self.symbols_created,
            'edges_created': self.edges_created,
            'parse_time_ms': self.parse_time_ms,
            'neo4j_time_ms': self.neo4j_time_ms,
            'symbols_per_second': self.symbols_created / (self.parse_time_ms / 1000) if self.parse_time_ms else 0
        }

class MetricsCollector:
    def __init__(self):
        self.metrics = Metrics()
    
    def time_operation(self, operation: str):
        """Context manager for timing operations"""
        class Timer:
            def __init__(self, metrics, field):
                self.metrics = metrics
                self.field = field
                self.start = None
            
            def __enter__(self):
                self.start = time.time()
                return self
            
            def __exit__(self, *args):
                elapsed = (time.time() - self.start) * 1000
                current = getattr(self.metrics, self.field)
                setattr(self.metrics, self.field, current + elapsed)
        
        field_map = {
            'parse': 'parse_time_ms',
            'neo4j': 'neo4j_time_ms'
        }
        
        return Timer(self.metrics, field_map[operation])
```

---

## Conclusion

This comprehensive plan provides everything needed to build a code intelligence system that is genuinely "better than grep":

1. **Two-tier architecture** separates concerns properly
2. **Multi-pass parsing** enables complete cross-file resolution
3. **Framework plugins** capture domain-specific patterns
4. **Neo4j** provides powerful graph queries
5. **Incremental updates** keep the system fast

The system answers "How does X work?" in milliseconds, not minutes, with high accuracy and full context. While complex to build, the value for teams working on large codebases is immense.

**Time to implement**: 5-8 weeks for core system, 3-4 months for production-ready with all plugins.

**Expected outcome**: 90%+ edge coverage, <100ms query response, handling 10M+ LOC codebases.