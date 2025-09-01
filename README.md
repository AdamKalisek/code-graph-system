# EspoCRM Code Graph System

A comprehensive code analysis and graph visualization system for EspoCRM projects.

## Project Structure

```
memory/
├── src/                    # Core source code
│   ├── core/              # Core components (SymbolTable, etc.)
│   ├── indexer/           # Main indexing pipeline
│   ├── export/            # Neo4j export functionality
│   └── import/            # Neo4j import functionality
├── parsers/               # Language parsers
│   ├── php_enhanced.py    # PHP symbol collector
│   ├── php_reference_resolver.py  # PHP reference resolver
│   └── js_espocrm_parser.py      # JavaScript parser
├── data/                  # Data files
│   └── cypher_batches/    # Generated Cypher queries
├── docs/                  # Documentation
├── tests/                 # Test files
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   └── fixtures/         # Test fixtures
├── espocrm/              # Target EspoCRM codebase
└── archive/              # Archived/obsolete code (git-ignored)
```

## Working Pipeline

1. **Index**: Parse PHP and JavaScript files to build symbol table
   ```bash
   python src/indexer/main.py espocrm/
   ```

2. **Export**: Generate Neo4j Cypher statements
   ```bash
   python src/export/neo4j_exporter.py
   ```

3. **Import**: Load graph into Neo4j
   ```bash
   python src/import/neo4j_importer.py
   ```

## Features

- Complete PHP parsing with 12 edge types
- JavaScript parsing for EspoCRM frontend
- Cross-language linking (JS API calls → PHP controllers)
- File system graph structure
- Neo4j visualization

## Requirements

- Python 3.8+
- Neo4j 4.0+ (running on port 7688)
- tree-sitter, tree-sitter-php, tree-sitter-javascript
- neo4j Python driver

## Installation

```bash
pip install -r requirements.txt
```

## Neo4j Configuration

- URI: `bolt://localhost:7688`
- Username: `neo4j`
- Password: `password123`

## Known Issues

- Import performance: Large graphs (40k+ relationships) may timeout
- Solution: Use batch import with UNWIND operations (in progress)