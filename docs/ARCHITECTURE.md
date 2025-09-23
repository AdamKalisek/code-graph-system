# Architecture Overview

## System Purpose

The Code Graph System transforms source code into a queryable Neo4j knowledge graph, enabling:
- AI agents to understand code relationships instantly
- Developers to perform impact analysis
- Teams to detect dead code and circular dependencies
- 50-100x faster relationship queries than text search

## High-Level Architecture

```plantuml
@startuml
skinparam componentStyle rectangle

actor "Developer/AI" as User
database "Source Code" as Source
database "SQLite\n(Staging)" as SQLite
database "Neo4j\n(Graph)" as Neo4j

package "Code Graph System" {
  component "File Scanner" as Scanner
  component "Tree-sitter\nParsers" as Parser
  component "Symbol Table\nManager" as SymbolTable
  component "Plugin System" as Plugins
  component "Import Pipeline" as Importer
}

Source --> Scanner : Filesystem walk
Scanner --> Parser : Source files
Parser --> Plugins : AST nodes
Plugins --> SymbolTable : Symbols & relationships
SymbolTable --> SQLite : Batch write
SQLite --> Importer : Bulk read
Importer --> Neo4j : Graph import
User --> Neo4j : Cypher queries
@enduml
```

## Data Flow Pipeline

```plantuml
@startuml
title Code Analysis Data Flow

start
:Walk filesystem tree;
:Identify source files by extension;

while (More files?) is (yes)
  :Parse file with Tree-sitter;
  :Extract AST (Abstract Syntax Tree);

  fork
    :Extract symbols\n(classes, functions, components);
  fork again
    :Extract relationships\n(imports, calls, renders);
  fork again
    :Apply plugin transformations\n(React, Next.js specific);
  end fork

  :Write to SQLite staging;
endwhile (no)

:Read all symbols from SQLite;
:Partition data for parallel import;

fork
  :Import nodes\n(CREATE statements);
fork again
  :Import relationships\n(MATCH + CREATE);
fork again
  :Create indexes\n(performance optimization);
end fork

:Validate import completeness;
:Graph ready for queries;

stop
@enduml
```

## Component Architecture

```plantuml
@startuml
package "Core Components" {
  class CodebaseIndexer {
    - project_root: Path
    - symbol_table: SymbolTable
    - plugins: PluginRegistry
    + index_codebase()
    + process_file()
  }

  class SymbolTable {
    - db_path: Path
    - symbols: List[Symbol]
    - references: List[Reference]
    + add_symbol()
    + add_reference()
    + batch_write()
  }

  class TreeSitterParser {
    - language: Language
    - parser: Parser
    + parse_file()
    + extract_ast()
  }
}

package "Language Analyzers" {
  class TypeScriptAnalyzer {
    + analyze_module()
    + extract_components()
    + extract_imports()
  }

  class PHPAnalyzer {
    + analyze_file()
    + extract_classes()
    + extract_methods()
  }
}

package "Plugin System" {
  interface Plugin {
    + transform()
    + extract_relationships()
  }

  class NextJsPlugin implements Plugin {
    + detect_api_routes()
    + extract_jsx_renders()
    + analyze_hooks()
  }
}

package "Import Pipeline" {
  class UltraFastNeo4jImporter {
    - strategy: ImportStrategy
    + import_nodes()
    + import_relationships()
    + create_indexes()
  }

  enum ImportStrategy {
    ADMIN_EXPORT
    APOC_PARALLEL
    BOLT_PARALLEL
  }
}

CodebaseIndexer --> SymbolTable
CodebaseIndexer --> TreeSitterParser
CodebaseIndexer --> Plugin
TypeScriptAnalyzer --> NextJsPlugin
SymbolTable --> UltraFastNeo4jImporter
@enduml
```

## Key Design Decisions

### 1. Two-Stage Processing (SQLite → Neo4j)
**Why:** Decouples parsing from import, enabling:
- Incremental updates without full re-parse
- Multiple import strategies
- Debugging and validation at staging level

### 2. Tree-sitter for Parsing
**Why:**
- Language-agnostic parser framework
- Incremental parsing support
- Error recovery (partial AST on syntax errors)
- Fast C bindings

### 3. Plugin Architecture
**Why:**
- Framework-specific logic isolated from core
- Easy to add new frameworks (Vue, Angular, etc.)
- Maintains single responsibility principle

### 4. Parallel Import Strategies
**Why:** Different environments need different approaches:
- `admin-export`: Fastest for large datasets (requires file system access)
- `APOC`: Good for medium datasets with APOC plugin
- `Bolt`: Universal compatibility, works everywhere

## Performance Considerations

### Bottlenecks & Solutions
1. **Parsing**: Parallelized by file (multiprocessing)
2. **SQLite writes**: Batched transactions (1000 symbols/batch)
3. **Neo4j import**: Parallel workers + batch operations
4. **Memory usage**: Streaming where possible, configurable batch sizes

### Scaling Limits
- Tested up to 50k symbols, 150k relationships
- Memory usage: ~2GB for 10k file codebase
- Import time: ~1 second per 10k nodes

## Security Considerations

- No code execution during parsing
- Read-only filesystem access
- Neo4j credentials in environment variables
- SQLite databases are local-only

## Future Architecture Improvements

1. **Streaming Pipeline**: Replace batch loading with streaming for very large repos
2. **Incremental Updates**: Only re-parse changed files
3. **Distributed Parsing**: Support for parsing across multiple machines
4. **GraphQL API**: REST/GraphQL layer over Neo4j for IDE integrations
5. **Schema Versioning**: Migration system for graph schema changes