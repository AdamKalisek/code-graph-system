# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Code Graph System transforms source code into a queryable Neo4j knowledge graph for AI-assisted code analysis. It parses TypeScript/React/PHP codebases using Tree-sitter, stages data in SQLite, and imports into Neo4j for complex relationship queries that are 50-100x faster than text-based search.

**Key Concept:** Unlike grep/ripgrep which can only search text, this system understands code relationships (imports, calls, renders, extends) as first-class graph edges, enabling questions like "What components call this API?" or "Find circular dependencies."

## Development Commands

### Setup & Prerequisites
```bash
# Install dependencies (using uv)
uv sync
# Or with make:
make install

# Start Neo4j (required for imports)
docker run -d \
  --name neo4j-code \
  -p 7474:7474 -p 7688:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest
# Or with make:
make neo4j-start
```

### Core Workflow
```bash
# 1. Place code to analyze in code_to_analyze/ directory
#    Example: code_to_analyze/your-project/

# 2. Parse codebase (creates SQLite staging database)
uv run python src/indexer/main.py --config your-project.yaml
# Or with make:
make parse CONFIG=your-project.yaml

# 3. Import to Neo4j (multiple strategies available)
uv run python tools/ultra_fast_neo4j_import.py --config your-project.yaml --bolt-parallel
# Or with make:
make import CONFIG=your-project.yaml

# 4. Query graph at http://localhost:7474
# Example: MATCH (c:ReactComponent)-[:RENDERS]->(e) RETURN c, e LIMIT 50
```

### Testing
```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_e2e.py

# Run integration tests
python -m pytest tests/integration/
```

## Architecture

### Two-Stage Pipeline
```
Source Code → Tree-sitter Parser → SQLite Staging → Neo4j Import → Cypher Queries
```

**Why SQLite staging?** Decouples parsing from import, enabling incremental updates, multiple import strategies, and debugging at the staging level.

### Key Components

#### 1. Indexer (`src/indexer/main.py`)
- **Entry point:** `CompleteEspoCRMIndexer` orchestrates entire indexing process
- **Config-driven:** Uses YAML configuration to define project, languages, and plugins
- **Multi-pass:** Symbol collection → Reference resolution → Cross-language linking
- **Outputs:** SQLite database in `data/` directory

#### 2. Language Analyzers (`src/pipeline/`)
- **TypeScript/React:** `typescript.py` - Extracts components, hooks, JSX relationships
- **JavaScript:** Uses `parsers/js_parser.py` with Babel parser
- **PHP:** Uses `parsers/php_enhanced.py` with Tree-sitter
- **Python:** Uses `parsers/python_parser.py` with Tree-sitter
- **Extensible:** Add new languages by implementing language module interface

#### 3. Symbol Table (`src/core/symbol_table.py`)
- **Central registry:** All parsed symbols stored here with SQLite backend
- **Schema:** `symbols` table (id, name, type, file_path, line_number, metadata)
- **References:** `symbol_references` table (source_id, target_id, reference_type)
- **File structure:** Directory and file nodes created with CONTAINS relationships

#### 4. Plugin System (`src/plugins/`)
- **Framework-specific:** NextJS (`nextjs.py`), EspoCRM (`espocrm.py`)
- **Purpose:** Extract framework-specific patterns (API routes, metadata configs, hooks)
- **Registry:** Plugins auto-registered via `registry.py`
- **Add plugins:** Subclass `BasePlugin` and register in config YAML

#### 5. Import Pipeline (`tools/ultra_fast_neo4j_import.py`)
Three optimization strategies:
- **`--admin-export`**: Fastest (5-30x), requires Neo4j filesystem access, uses CSV bulk import
- **`--apoc-parallel`**: Fast, requires APOC plugin
- **`--bolt-parallel`**: Universal, works everywhere (default)

### Data Model

**Node Labels:**
- `File`, `Directory` - Filesystem structure
- `PHPClass`, `PHPMethod`, `PHPFunction` - PHP symbols
- `ReactComponent`, `TSFunction`, `TSInterface` - TypeScript/React symbols
- `JSModule`, `APICall` - JavaScript symbols
- `PythonClass`, `PythonFunction`, `PythonMethod` - Python symbols

**Relationship Types:**
- `CONTAINS` - Directory→File, File→Symbol
- `IMPORTS`, `EXPORTS` - Module dependencies
- `RENDERS` - React component rendering
- `CALLS` - Function invocations
- `EXTENDS`, `IMPLEMENTS` - Inheritance
- `JS_CALLS_PHP` - Cross-language API links (JavaScript API call → PHP controller method)

Full schema details in `docs/DATA_MODEL.md`.

## Configuration

Configuration files are YAML (see `memory.yaml`, `webslicer.yaml` as examples):

```yaml
project:
  name: my-project
  root: code_to_analyze/my-project  # Relative to repo root
  languages:
    - typescript
    - javascript
    - php
    - python

storage:
  sqlite: data/my-project.db

neo4j:
  uri: bolt://localhost:7688
  username: neo4j
  password: password
  database: neo4j
  wipe_before_import: false  # DANGER: true deletes all Neo4j data

plugins:
  - nextjs
  - espocrm
```

**Important:** Configuration paths are resolved relative to the config file location. When adding a new codebase, create a new YAML config and place source in `code_to_analyze/`.

## Common Development Tasks

### Adding Support for a New Framework

1. Create plugin in `src/plugins/your_framework.py`:
```python
from src.plugins.base import BasePlugin

class YourFrameworkPlugin(BasePlugin):
    def analyze_file(self, file_path: str, ast, symbol_table):
        # Extract framework-specific patterns
        pass
```

2. Register in `src/plugins/registry.py`
3. Add to config: `plugins: [your_framework]`

### Debugging Failed Imports

1. Check SQLite staging database:
```bash
sqlite3 data/your-project.db
sqlite> SELECT COUNT(*) FROM symbols;
sqlite> SELECT * FROM symbol_references LIMIT 10;
```

2. Verify Neo4j connection:
```bash
# Test connection
docker exec -it neo4j-code cypher-shell -u neo4j -p password
```

3. Enable verbose logging:
```python
# In src/indexer/main.py
logging.getLogger().setLevel(logging.DEBUG)
```

### Adding a New Language Parser

1. Implement language module in `src/pipeline/` (see `typescript.py` as template)
2. Create parser in `parsers/` directory (can use Tree-sitter or Babel)
3. Register in `src/pipeline/indexer.py` language module registry
4. Add language to config: `languages: [your_language]`

## Performance Characteristics

- **Parsing:** Parallelizable by file, bottleneck is AST traversal
- **SQLite writes:** Batched (1000 symbols/batch), ~5k writes/sec
- **Neo4j import:** Parallel workers + batch operations, ~10k nodes/sec
- **Tested scale:** 50k symbols, 150k relationships
- **Memory usage:** ~2GB for 10k file codebase

### Optimization Tips
- Use `--admin-export` for large codebases (>10k files)
- Increase `parallel_workers` in config for faster imports
- Exclude test files in config: `ignore_patterns: ["*.test.ts", "*.spec.js"]`

## Directory Structure

```
code-graph-system/
├── code_to_analyze/       # Place codebases to analyze here (gitignored)
├── data/                   # SQLite staging databases (gitignored)
├── docs/                   # Architecture, data model, configuration guides
├── parsers/                # Language-specific parsers
│   ├── js_parser.py       # JavaScript/Babel parser
│   ├── php_enhanced.py    # PHP Tree-sitter parser
│   ├── python_parser.py   # Python Tree-sitter parser
│   └── metadata_parser.py # EspoCRM JSON metadata
├── src/
│   ├── core/              # Symbol table, resolution
│   ├── indexer/           # Main indexing orchestrator
│   ├── pipeline/          # Language modules, config
│   ├── plugins/           # Framework-specific analyzers
│   ├── export/            # Neo4j export logic
│   └── import/            # Neo4j import strategies
├── tests/                 # Unit and integration tests
├── tools/                 # Import utilities
│   └── ultra_fast_neo4j_import.py  # Primary import tool
├── memory.yaml            # Example config (EspoCRM)
└── webslicer.yaml         # Example config (WebSlicer)
```

## Cross-Language Linking

The system creates `JS_CALLS_PHP` relationships by:
1. **JS side:** Detecting API calls in JavaScript (e.g., `Ajax.postRequest('Lead/action/convert')`)
2. **PHP side:** Finding controller methods (`LeadController::actionConvert`)
3. **Linking:** Normalizing endpoints and creating graph edges

This enables queries like "Find all frontend components that call this backend endpoint."

## Querying Examples

```cypher
# Find unused React components
MATCH (c:ReactComponent)
WHERE NOT EXISTS(()-[:IMPORTS]->(c))
RETURN c.name, c.file_path

# Find circular dependencies
MATCH path = (m1)-[:IMPORTS*2..5]->(m1)
RETURN path

# Find high-coupling components (>15 dependencies)
MATCH (c:ReactComponent)
WITH c, COUNT {(c)-[:RENDERS|USES|CALLS]->()} as deps
WHERE deps > 15
RETURN c.name, deps ORDER BY deps DESC

# Trace API call to backend implementation
MATCH (js:APICall)-[:JS_CALLS_PHP]->(php:PHPMethod)
RETURN js.file_path, js.endpoint, php.name, php.file_path
```

## Important Notes

- **code_to_analyze/ directory:** All codebases to analyze must be placed here
- **SQLite is ephemeral:** It's just staging; Neo4j is the source of truth
- **Wipe with caution:** `wipe_before_import: true` deletes ALL Neo4j data, not just your project
- **Import strategies:** Start with `--bolt-parallel`, upgrade to `--admin-export` for speed on large codebases
- **File/Directory nodes:** Always created first; symbols link to files via CONTAINS relationships