# 📋 CODEBASE REVISION PLAN

## Current State Analysis

### 🔴 CRITICAL ISSUES IDENTIFIED:
1. **104 Python files** scattered across the project
2. **Multiple duplicate systems** (code-graph-system vs code_graph_system)
3. **33 import scripts** with unclear purposes
4. **Test files mixed with production code**
5. **Old Neo4j backup** from August 31
6. **Node modules** checked in (should be gitignored)
7. **Multiple parser implementations** for the same language
8. **No clear entry point or main pipeline**

## Directory Structure Issues:

### Duplicate/Confusing Directories:
- `code-graph-system/` vs `code_graph_system/` - TWO DIFFERENT SYSTEMS!
- `indexing_scripts/` - 15 different indexing scripts!
- `parsers/` vs `plugins/php/` vs `plugins/javascript/` - Multiple parser locations
- `tests/` vs `test_*.py` in root - Tests everywhere
- `test_batches/` - Test data mixed with code

### Unnecessary Files:
- `node_modules/` - 100+ MB of JavaScript dependencies (should use package.json)
- `neo4j_backup_20250831_064933/` - Old backup, 30+ MB
- `vendor/` - PHP dependencies
- `.cache/` - SQLite databases (30+ MB each)
- Multiple `__pycache__/` directories

## 📝 REVISION PHASES:

### Phase 1: INVENTORY & CATEGORIZATION
1. Identify which scripts are actually being used
2. Determine the CURRENT working pipeline
3. Map dependencies between scripts
4. Identify dead code

### Phase 2: CLEANUP
1. Remove duplicate systems
2. Delete unused/old scripts
3. Remove test files from root
4. Clean up old backups and caches
5. Add proper .gitignore

### Phase 3: REORGANIZATION
1. Create clear directory structure:
   ```
   memory/
   ├── src/
   │   ├── parsers/         # Language parsers
   │   ├── indexers/        # Database indexing
   │   ├── exporters/       # Neo4j export
   │   ├── importers/       # Neo4j import
   │   └── core/            # Core functionality
   ├── tests/
   ├── data/               # Test data
   ├── docs/               # Documentation
   └── scripts/            # Utility scripts
   ```

### Phase 4: CONSOLIDATION
1. Merge duplicate functionality
2. Create single entry point
3. Standardize naming conventions
4. Add proper error handling

### Phase 5: DOCUMENTATION
1. Document the final pipeline
2. Create README with clear instructions
3. Add docstrings to all functions
4. Create architecture diagram

## Next Steps:
1. **Audit all Python files** - Determine what each does
2. **Identify the working pipeline** - What actually works?
3. **Mark dead code** - What can be deleted?
4. **Create migration plan** - How to reorganize without breaking

## Files to Investigate First:

### Likely Core Files:
- `espocrm_complete_indexer.py` - Main indexer?
- `parsers/php_enhanced.py` - PHP parser
- `parsers/php_reference_resolver.py` - Reference resolver
- `parsers/js_espocrm_parser.py` - JavaScript parser
- `neo4j_export_with_files.py` - Latest export script
- `import_complete_with_files.py` - Latest import script

### Likely Dead Code:
- All files starting with `test_`
- Multiple versions of same functionality (index_*.py)
- Old import scripts (import_to_neo4j*.py)
- Demo files (demo_*.py)

## Questions to Answer:
1. Which indexer actually works?
2. Why are imports failing at 15%?
3. What's the difference between code-graph-system and code_graph_system?
4. Which parser implementation should we keep?
5. What's the correct import pipeline?