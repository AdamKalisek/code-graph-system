# 🔍 CODEBASE AUDIT REPORT

## CURRENT WORKING PIPELINE

### ✅ Core Files (KEEP):
1. **`espocrm_complete_indexer.py`** - Main indexer that creates SQLite database
2. **`parsers/php_enhanced.py`** - PHP symbol collector
3. **`parsers/php_reference_resolver.py`** - PHP reference resolver  
4. **`parsers/js_espocrm_parser.py`** - JavaScript parser for EspoCRM
5. **`neo4j_export_with_files.py`** - Exports database to Cypher with file system
6. **`import_complete_with_files.py`** - Imports to Neo4j (partially working)

### ⚠️ Problem Files (NEED FIXING):
- **Import scripts failing at 15%** - Timeout/performance issues
- **Symbol relationships not importing** - Only file system imports successfully

## FILES TO DELETE (Dead Code)

### 🗑️ Duplicate Import Scripts (31 files!):
```
import_to_neo4j.py
import_to_neo4j_complete.py  
import_to_neo4j_mcp.py
import_full_graph.py
import_subset.py
import_symbol_relationships.py
import_remaining_relationships.py
batch_import_neo4j.py
full_import_mcp.py
fast_neo4j_import.py (maybe keep - it was fast?)
demo_import.py
import_batches.py
```

### 🗑️ Test Files in Root (should be in tests/):
```
test_*.py (10 files)
verify_*.py (2 files)
validate_current_graph.py
```

### 🗑️ Old/Duplicate Indexers:
```
index_espocrm_complete.py (old version)
enhanced_pipeline.py (old pipeline)
```

### 🗑️ Entire Duplicate Directories:
- `code-graph-system/` - Old version, use `code_graph_system/`
- `neo4j_backup_20250831_064933/` - Old backup (30+ MB)
- `node_modules/` - Should be in .gitignore
- `vendor/` - PHP dependencies, not needed
- `test_batches/` - Test data, move to data/

### 🗑️ Unused Plugin Systems:
- `plugins/framework/` - Laravel plugin, not used
- `plugins/javascript/babel_parser.py` - Not used
- `plugins/javascript/tree_sitter_*.py` - Not used
- `plugins/php/ast_parser*.py` - Not used
- `plugins/php/nikic_parser.py` - Not used

## ACTUAL DEPENDENCIES

### Used Libraries:
- `sqlite3` - Database storage
- `neo4j` - Neo4j Python driver
- `tree-sitter` - For parsing
- `tree-sitter-php` - PHP grammar
- `tree-sitter-javascript` - JS grammar

### NOT Used (can remove):
- Babel parser
- PHP-Parser (nikic)
- Most of the plugin system

## ROOT CAUSE ANALYSIS

### Why imports are failing:
1. **Too many individual statements** - 41,942 relationships one by one
2. **No batch processing** - Each relationship is a separate transaction
3. **No connection pooling** - Creating new connections repeatedly
4. **Wrong approach** - Should use `UNWIND` for bulk imports

## RECOMMENDED STRUCTURE

```
memory/
├── README.md
├── requirements.txt
├── .gitignore
├── src/
│   ├── __init__.py
│   ├── indexer.py           # Main indexer (from espocrm_complete_indexer.py)
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── php_parser.py    # From php_enhanced.py
│   │   ├── php_resolver.py  # From php_reference_resolver.py
│   │   └── js_parser.py     # From js_espocrm_parser.py
│   ├── export/
│   │   ├── __init__.py
│   │   └── neo4j_export.py  # From neo4j_export_with_files.py
│   └── import/
│       ├── __init__.py
│       └── neo4j_import.py  # NEW - Fixed bulk import
├── tests/
│   └── (all test files)
├── data/
│   └── (test data)
├── docs/
│   └── (documentation)
└── espocrm/
    └── (target codebase)
```

## IMMEDIATE ACTIONS

1. **Create backup** of current state
2. **Delete all dead code** listed above
3. **Reorganize** into proper structure
4. **Fix import script** to use bulk operations
5. **Test complete pipeline**

## Statistics:
- **Files to delete**: ~70 files
- **Directories to remove**: 5 major directories
- **Space to save**: ~150+ MB
- **Lines of dead code**: ~10,000+ lines