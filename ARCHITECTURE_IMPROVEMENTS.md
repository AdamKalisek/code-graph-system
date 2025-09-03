# Architecture Improvements - Code Analysis System

Based on comprehensive analysis with o3 (high thinking mode), here are critical improvements needed for our PHP/JS code analysis system.

## Current Architecture Assessment

### ✅ Strengths
1. **Two-phase parsing** - Sound approach (symbols → references)
2. **SQLite intermediate storage** - Good for large datasets
3. **Neo4j graph database** - Excellent for relationship queries
4. **Optimized import** - Fixed with label-based indexing (1000x speedup)
5. **DEFINES relationships** - Now correctly implemented

### ⚠️ Critical Issues to Address

## 1. Schema Enhancements

### Missing Metadata (HIGH PRIORITY)
```sql
-- Add to symbols table:
ALTER TABLE symbols ADD COLUMN parameters TEXT; -- JSON array of {name, type, default, byRef, variadic}
ALTER TABLE symbols ADD COLUMN throws TEXT; -- Exception types thrown
ALTER TABLE symbols ADD COLUMN docblock TEXT; -- Raw PHPDoc/JSDoc
ALTER TABLE symbols ADD COLUMN attributes TEXT; -- PHP 8 attributes JSON
ALTER TABLE symbols ADD COLUMN is_readonly BOOLEAN; -- PHP 8.1+
ALTER TABLE symbols ADD COLUMN is_enum BOOLEAN; -- PHP 8.1+
ALTER TABLE symbols ADD COLUMN union_types TEXT; -- PHP 8.0+ union/intersection types
ALTER TABLE symbols ADD COLUMN git_hash TEXT; -- Version tracking
ALTER TABLE symbols ADD COLUMN analysis_run_id TEXT; -- For incremental updates
```

### Missing Relationships
- **OVERRIDES** - Method overrides parent method
- **IMPLEMENTS_METHOD** - Concrete implementation of interface method
- **THROWS** - Method → Exception class
- **HAS_ATTRIBUTE** - Symbol → Attribute (PHP 8)
- **READS/WRITES** - Differentiate property access types
- **USES_GLOBAL** - Access to global variables
- **DEPENDS_ON_PACKAGE** - Composer/npm dependencies

## 2. Parser Improvements

### PHP Namespace Resolution (CRITICAL)
Current issues:
- No handling of `use ... as` aliases
- Missing grouped use statements `use A\{B, C as D}`
- Incorrect resolution of relative names
- No special handling of `self`, `static`, `parent`

**Solution**: Create dedicated `NamespaceResolver` class:
```python
class NamespaceResolver:
    def __init__(self):
        self.current_namespace = None
        self.use_statements = {}  # alias -> FQN
        self.group_uses = []
    
    def resolve_name(self, name: str, context: str = 'class') -> str:
        # Handle special keywords
        if name in ['self', 'static', 'parent']:
            return self._resolve_special(name)
        
        # Check if it's aliased
        if name in self.use_statements:
            return self.use_statements[name]
        
        # Handle relative vs absolute
        if name.startswith('\\'):
            return name[1:]  # Already absolute
        
        # Relative to current namespace
        if self.current_namespace:
            return f"{self.current_namespace}\\{name}"
        
        return name
```

### JavaScript Parser (CRITICAL)
**Current**: Regex-based extraction - INADEQUATE
**Problems**: 
- Cannot handle ES6 modules, JSX, TypeScript
- No accurate line numbers
- Misses nested constructs

**Solution**: Use tree-sitter-javascript
```python
# Replace regex parser with:
from tree_sitter import Language, Parser
import tree_sitter_javascript

class JavaScriptParser:
    def __init__(self):
        JS_LANGUAGE = Language(tree_sitter_javascript.language(), 'javascript')
        self.parser = Parser()
        self.parser.set_language(JS_LANGUAGE)
    
    def parse_file(self, file_path: str):
        # Proper AST parsing
        tree = self.parser.parse(content)
        # Extract symbols with accurate positions
```

## 3. PHP 8+ Feature Support

### Currently Missing:
- **PHP 8.0**: Union types `int|string`, Attributes `#[Route('/api')]`, Named arguments
- **PHP 8.1**: Enums, readonly properties, first-class callables
- **PHP 8.2**: DNF types `(A&B)|C`, readonly classes
- **PHP 8.3**: Typed class constants

### Implementation Priority:
1. Union/intersection types (affects type analysis)
2. Attributes (critical for frameworks)
3. Enums (new symbol type)
4. Readonly modifiers (affects mutability analysis)

## 4. Performance Optimizations

### SQLite Optimizations
```python
# Enable WAL mode for concurrent reads
conn.execute("PRAGMA journal_mode = WAL")
conn.execute("PRAGMA synchronous = NORMAL")
conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
conn.execute("PRAGMA temp_store = MEMORY")

# Add composite index for reference lookups
conn.execute("""
    CREATE UNIQUE INDEX idx_unique_ref 
    ON symbol_references(source_id, reference_type, target_id, line_number)
""")
```

### Neo4j Batch Tuning
```python
# Optimal batch sizes based on testing
NODE_BATCH_SIZE = 5000  # Nodes per transaction
REL_BATCH_SIZE = 2000   # Relationships per transaction
MAX_TX_SIZE = 16 * 1024 * 1024  # 16MB transaction limit

# Memory configuration
# dbms.memory.heap.initial_size=4G
# dbms.memory.heap.max_size=8G
# dbms.memory.pagecache.size=2G
```

### Incremental Analysis
```python
class IncrementalAnalyzer:
    def analyze_changes(self, changed_files: List[str], run_id: str):
        # 1. Mark old symbols from changed files as obsolete
        # 2. Parse only changed files
        # 3. Re-resolve references for affected symbols
        # 4. Update Neo4j with delta changes only
```

## 5. Graph Model Refinements

### Label Strategy
**Current Issue**: Multiple labels per node can hurt performance

**Better Approach**:
- Single primary label per node (PHPClass, PHPMethod, etc.)
- Use properties for modifiers: `{isAbstract: true, isFinal: true}`
- Reserve multi-labels only for language-agnostic queries: `:Symbol:Callable`

### Relationship Semantics
- **DEFINES**: Container declares member (File→Class, Class→Method)
- **CONTAINS**: Physical containment (Directory→File)
- **CALLS**: Runtime invocation
- **EXTENDS/IMPLEMENTS**: Type hierarchy
- **OVERRIDES**: Polymorphic replacement
- **DEPENDS_ON**: Package/module dependency

## 6. Testing & Validation

### Edge Cases to Test
```php
// Namespace edge cases
namespace A\B { class C {} }
namespace { class Global {} }
use A\B\{C, D as E, function F};

// PHP 8 features
#[Attribute(param: "value")]
class MyClass {
    public function __construct(
        private readonly string $prop,
        public int|string $union,
    ) {}
}

// Anonymous classes
$obj = new class extends Base {
    public function method() {}
};

// First-class callables
$fn = $this->method(...);
```

## Implementation Priority

### Phase 1 (Immediate)
1. ✅ Fix DEFINES relationships (COMPLETED)
2. ✅ Optimize Neo4j import performance (COMPLETED)
3. ⬜ Add parameter metadata to schema
4. ⬜ Implement NamespaceResolver

### Phase 2 (Next Week)
5. ⬜ Replace JS regex with tree-sitter
6. ⬜ Add PHP 8.0 union types support
7. ⬜ Store and parse DocBlocks
8. ⬜ Add OVERRIDES relationship

### Phase 3 (Future)
9. ⬜ Full PHP 8+ feature support
10. ⬜ Incremental analysis with run_id
11. ⬜ Package dependency tracking
12. ⬜ Taint analysis (READS vs WRITES)

## Success Metrics
- Parse accuracy: >99% of symbols detected
- Import speed: <10 seconds for 100k symbols
- Query performance: <100ms for typical traversals
- Memory usage: <4GB for 1M symbol codebase
- Incremental update: <30 seconds for typical changes

## Conclusion
The current architecture is fundamentally sound but needs these enhancements for production readiness. Priority should be on:
1. Fixing namespace resolution (breaks many queries)
2. Proper JS parsing (current regex is inadequate)
3. PHP 8+ support (modern codebases require this)
4. Performance tuning for large codebases