# Deprecated Import Scripts

This directory contains old import scripts that have been superseded by `tools/ultra_fast_neo4j_import.py`.

## Why These Are Deprecated

These scripts represent the evolution of the Neo4j import functionality. They were experimental implementations that have been replaced by the current, optimized solution.

## Current Import Tool

**Use this instead:** `tools/ultra_fast_neo4j_import.py`

This is the actively maintained import tool with three strategies:
- `--admin-export`: Fastest (requires filesystem access)
- `--apoc-parallel`: Fast (requires APOC plugin)
- `--bolt-parallel`: Universal (works everywhere)

## Scripts in This Directory

- `neo4j_importer.py` - Early version
- `neo4j_direct_import.py` - Direct import attempt
- `fast_importer.py` - Speed optimization attempt
- `optimized_neo4j_import.py` - Optimization iteration
- `optimized_neo4j_import_fixed.py` - Bug fix version
- `fast_cypher_import.py` - Cypher generation approach
- `bulk_importer.py` - Bulk import attempt
- `direct_import.py` - Simple direct import
- `final_complete_import.py` - Misleading name, not final

## Should I Delete These?

**Not yet.** They're archived here in case:
1. We need to reference old approaches
2. Someone's workflow still depends on them
3. They contain useful code patterns

If no issues arise after 3 months (Jan 2026), these can be safely deleted.

## Historical Documentation

- `graph_io_notes.md` - Implementation notes about various import/export approaches that were tried. Kept for historical reference.