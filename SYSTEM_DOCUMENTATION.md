# EspoCRM Code Analysis System - Complete Documentation

## 🎯 System Overview

This system provides comprehensive code analysis for EspoCRM by parsing PHP and JavaScript code into a graph database (Neo4j) for advanced querying and relationship analysis.

### Architecture Flow:
```
Source Code → Parser → SQLite (intermediate) → Neo4j (graph DB) → Analysis Queries
```

## 📊 Current Capabilities

### ✅ What's Working:
1. **PHP Parsing** - Extracts classes, methods, properties, interfaces, traits
2. **JavaScript Parsing** - Basic extraction (regex-based)
3. **Relationship Tracking**:
   - DEFINES (container→member)
   - CALLS (method invocations)
   - EXTENDS/IMPLEMENTS/USES_TRAIT (inheritance)
   - IMPORTS (file dependencies)
   - ACCESSES (property access)
   - INSTANTIATES (new Class())
   - REGISTERED_IN (config→class mappings) **[NEW]**
4. **Metadata Integration** - Parses JSON configs for runtime behavior
5. **Optimized Import** - 1000x faster with label-based indexing

### Database Statistics:
- **38,893 nodes** (including 185 ConfigFile nodes)
- **128,593 relationships** (including 678 REGISTERED_IN)
- **Import time**: ~13 seconds for complete codebase

## ⚠️ Critical Missing Features

### 1. Missing Relationships (931 found):
- **297 OVERRIDES** - Method inheritance tracking
- **634 IMPLEMENTS_METHOD** - Interface contract fulfillment
- **0 THROWS** - Exception flow analysis
- **0 HAS_ATTRIBUTE** - PHP 8 attributes
- **0 READS/WRITES** - Property access types

### 2. Missing Metadata:
- Method parameters (name, type, default, by-reference)
- DocBlock comments (@param, @throws, @return)
- PHP 8+ features (union types, readonly, enums)
- Exception declarations
- Attribute payloads (#[Route('/api')])

### 3. Parser Limitations:
- JavaScript uses regex (needs tree-sitter)
- No namespace resolution (use...as aliases)
- No anonymous classes/closures
- No self/static/parent resolution

## 🔧 How to Use

### 1. Complete Indexing with Metadata:
```bash
# Parse codebase including JSON metadata
python -m src.indexer.main --db data/espocrm_complete.db --verbose

# This runs 7 steps:
# [1/7] File structure indexing
# [2/7] PHP backend parsing
# [3/7] JavaScript frontend parsing  
# [4/7] Metadata JSON parsing (authentication hooks, etc.)
# [5/7] Cross-language linking
# [6/7] Neo4j export
# [7/7] Statistics generation
```

### 2. Import to Neo4j:
```bash
# Use the optimized importer (NOT the slow MCP version)
python src/import/optimized_neo4j_import_fixed.py --db data/espocrm_complete.db

# Features:
# - Clears Neo4j first
# - Creates indexes/constraints
# - Imports nodes by label groups
# - Imports relationships with proper indexing
# - Imports config references
# - ~13 seconds for complete import
```

### 3. Query Examples:

#### Find Most Used Service:
```cypher
MATCH (c:PHPClass)-[:DEFINES]->(m:PHPMethod)<-[:CALLS]-()
WHERE c.name CONTAINS 'Service'
RETURN c.name, COUNT(DISTINCT m) as MethodCount
ORDER BY MethodCount DESC
```
**Result**: Espo\Core\Record\Service (38 callers)

#### Find Orphaned Authentication Hooks:
```cypher
MATCH (c:PHPClass)-[:IMPLEMENTS]->(i:PHPInterface)
WHERE i.name CONTAINS 'Authentication\\Hook'
AND NOT EXISTS((c)-[:REGISTERED_IN]->(:ConfigFile))
RETURN c.name as OrphanedHook
```
**Result**: None (all hooks properly registered)

#### Find Method Overrides (currently missing):
```cypher
MATCH (child:PHPClass)-[:EXTENDS]->(parent:PHPClass)
MATCH (child)-[:DEFINES]->(cm:PHPMethod)
MATCH (parent)-[:DEFINES]->(pm:PHPMethod)
WHERE cm.name = pm.name
RETURN child.name, cm.name as OverriddenMethod
```

## 🏗️ System Components

### 1. Parsers:
- **`parsers/php_enhanced.py`** - First pass: collect symbols
- **`parsers/php_reference_resolver.py`** - Second pass: resolve references
- **`parsers/js_espocrm_parser.py`** - JavaScript parser (regex-based)
- **`parsers/metadata_parser.py`** - JSON metadata parser **[NEW]**

### 2. Core:
- **`src/core/symbol_table.py`** - Symbol storage and management
- **`src/indexer/main.py`** - Main orchestrator (7-step process)

### 3. Import:
- **`src/import/optimized_neo4j_import_fixed.py`** - Fast Neo4j importer **[USE THIS]**
- ❌ `final_complete_import.py` - Too slow (MCP-based)
- ❌ `neo4j_direct_import.py` - Deprecated

### 4. Database Schema:

#### SQLite Tables:
```sql
-- symbols table
CREATE TABLE symbols (
    id TEXT PRIMARY KEY,
    name TEXT,
    type TEXT,
    file_path TEXT,
    line_number INTEGER,
    namespace TEXT,
    visibility TEXT,
    is_static BOOLEAN,
    is_abstract BOOLEAN,
    is_final BOOLEAN,
    return_type TEXT,
    extends TEXT,
    implements TEXT,
    parent_id TEXT
);

-- symbol_references table
CREATE TABLE symbol_references (
    source_id TEXT,
    target_id TEXT,
    reference_type TEXT,
    line_number INTEGER,
    column_number INTEGER
);

-- config_references table [NEW]
CREATE TABLE config_references (
    config_file TEXT,
    config_key TEXT,
    class_name TEXT,
    reference_type TEXT
);
```

#### Neo4j Node Labels:
- Symbol (base for all)
- PHPClass, PHPInterface, PHPTrait
- PHPMethod, PHPProperty, PHPFunction, PHPConstant
- File, Directory, ConfigFile
- JSModule, JSSymbol

#### Neo4j Relationship Types:
- **DEFINES**: Container declares member
- **CALLS**: Method invocation
- **EXTENDS/IMPLEMENTS/USES_TRAIT**: Inheritance
- **IMPORTS**: File dependencies
- **ACCESSES**: Property access
- **INSTANTIATES**: Object creation
- **REGISTERED_IN**: Config registration **[NEW]**
- **CONTAINS**: Directory/file containment

## 🐛 Known Issues

1. **Missing 331 CONTAINS relationships** - Some file relationships fail
2. **No incremental updates** - Must reparse entire codebase
3. **Memory usage** - Can use 4GB+ for large codebases
4. **JavaScript parser inadequate** - Regex can't handle modern JS

## 🚀 Performance Tuning

### Neo4j Configuration:
```
dbms.memory.heap.initial_size=4G
dbms.memory.heap.max_size=8G
dbms.memory.pagecache.size=2G
```

### Key Performance Fixes:
1. **Use labels in MATCH queries**: `MATCH (s:PHPClass {id: ...})` not `MATCH (s {id: ...})`
2. **Create constraints first**: Unique constraints create indexes automatically
3. **Batch with UNWIND**: Process 5000 nodes/relationships at once
4. **Use bolt://localhost:7688** (not default 7687)

## 📈 Future Improvements (Priority Order)

### Phase 1 - Critical Gaps:
1. Add OVERRIDES and IMPLEMENTS_METHOD relationships
2. Capture method parameters metadata
3. Parse and store DocBlocks
4. Add namespace resolver for proper imports

### Phase 2 - Modern PHP:
5. PHP 8+ features (union types, attributes, readonly)
6. Exception tracking (THROWS relationships)
7. Replace JS regex with tree-sitter parser

### Phase 3 - Advanced:
8. Incremental analysis with run_id
9. SQLite WAL mode optimization
10. Taint analysis (READS vs WRITES)
11. Package dependency tracking

## 🔍 Debugging Tips

### Check Import Progress:
```bash
tail -f import_log.txt
```

### Verify Database Content:
```cypher
// Node count by type
MATCH (n)
UNWIND labels(n) as label
RETURN label, COUNT(*) as count
ORDER BY count DESC

// Relationship count by type
MATCH ()-[r]->()
RETURN TYPE(r), COUNT(r) as count
ORDER BY count DESC
```

### Find Missing Symbols:
```bash
sqlite3 data/espocrm_complete.db "
SELECT type, COUNT(*) FROM symbols GROUP BY type;
"
```

## 📝 Commit History

### Latest Fixes:
1. **Fixed DEFINES relationships** - Added during PHP parsing
2. **Optimized Neo4j import** - 1000x speedup with label indexing
3. **Integrated metadata parser** - Captures JSON configurations
4. **Added REGISTERED_IN relationships** - Links classes to configs

---

**Last Updated**: 2025-09-03
**Maintainer**: Claude Code Assistant
**Version**: 2.0 (with metadata integration)