# BASE IDEA - Universal Code Graph System

## 🎯 Purpose

This software creates a **complete, searchable knowledge graph** of any codebase by parsing source code and mapping ALL relationships between code elements. It transforms codebases into Neo4j graph databases for powerful visualization and analysis.

## 🔍 What It Does

### Core Functionality
1. **Complete Code Parsing**
   - Parses ALL programming languages (currently PHP and JavaScript, easily extensible)
   - Extracts symbols: classes, interfaces, functions, methods, properties, constants
   - Captures file and directory structure (FUNDAMENTAL for any codebase analysis)

2. **Relationship Mapping**
   - **Inheritance**: EXTENDS, IMPLEMENTS, USES_TRAIT
   - **Dependencies**: IMPORTS, USES, INSTANTIATES
   - **Interactions**: CALLS, ACCESSES, THROWS, RETURNS
   - **Structure**: CONTAINS (directory→file, file→symbol)
   - **Type System**: PARAMETER_TYPE, RETURN_TYPE

3. **Cross-Language Linking**
   - Maps API calls from frontend (JS) to backend (PHP)
   - Tracks data flow across language boundaries

4. **Neo4j Visualization**
   - Exports to Neo4j for interactive graph exploration
   - Query complex relationships with Cypher
   - Visualize architecture and dependencies

## 🛠️ How to Use It

### Quick Start
```bash
# 1. Parse and index a codebase
python src/indexer/main.py --db data/my_project.db

# 2. Import to Neo4j (ensure Neo4j is running)
cat espocrm_complete.cypher | cypher-shell -u neo4j -p your_password

# 3. Explore in Neo4j Browser
# Open http://localhost:7474
```

### Example Queries in Neo4j

**Find what a class extends:**
```cypher
MATCH (c:PHPClass {name: 'UserRepository'})-[:EXTENDS]->(parent)
RETURN c, parent
```

**Find all implementations of an interface:**
```cypher
MATCH (impl)-[:IMPLEMENTS]->(i:PHPInterface {name: 'AuthInterface'})
RETURN impl, i
```

**Trace method calls:**
```cypher
MATCH path = (m1:PHPMethod)-[:CALLS*1..3]->(m2:PHPMethod)
WHERE m1.name = 'authenticate'
RETURN path
```

**Find unused code:**
```cypher
MATCH (m:PHPMethod)
WHERE NOT ()-[:CALLS]->(m)
RETURN m.name as unused_method
```

**Analyze file dependencies:**
```cypher
MATCH (f1:File)-[:CONTAINS]->(s1)-[:IMPORTS]->(s2)<-[:CONTAINS]-(f2:File)
RETURN DISTINCT f1.name as source, f2.name as dependency
```

## 🏗️ Architecture

```
┌─────────────────────────────────────┐
│         Source Codebase             │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│      Tree-sitter Parsers            │
│   (PHP, JavaScript, extensible)     │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│         Symbol Table                │
│      (SQLite intermediate)          │
│  ┌────────────────────────────────┐ │
│  │ Pass 1: Symbol Collection      │ │
│  │ - Extract all declarations     │ │
│  │ - Build symbol index           │ │
│  └────────────────────────────────┘ │
│  ┌────────────────────────────────┐ │
│  │ Pass 2: Reference Resolution   │ │
│  │ - Resolve imports/extends      │ │
│  │ - Map method calls             │ │
│  │ - Type validation              │ │
│  └────────────────────────────────┘ │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│        Cypher Export                │
│    (Neo4j import format)            │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│         Neo4j Graph DB              │
│   (Interactive visualization)       │
└─────────────────────────────────────┘
```

## 🚀 Key Features

1. **Generic & Extensible** - Works with ANY codebase, not tied to specific frameworks
2. **Complete Coverage** - Indexes EVERYTHING: code, files, directories, relationships
3. **Type-Safe** - Validates relationships (classes can't extend directories!)
4. **Prefix System** - Prevents naming collisions (php_class_, js_module_, dir_, file_)
5. **Incremental Updates** - Only re-parses changed files (via hash tracking)

## 📊 Output

The system produces:
- **SQLite Database**: Complete symbol table with all relationships
- **Cypher Export**: Neo4j import script with all nodes and edges
- **Statistics**: Symbol counts, relationship types, cross-language links
- **Neo4j Graph**: Interactive, queryable knowledge graph

## 🎭 Use Cases

- **Architecture Analysis**: Understand system structure and dependencies
- **Refactoring**: Find all usages before changing code
- **Code Review**: Trace impact of changes
- **Documentation**: Auto-generate dependency diagrams
- **Security**: Track data flow and access patterns
- **Optimization**: Find unused code and circular dependencies
- **Onboarding**: Help new developers understand codebases

## 🔮 Future Enhancements

- [ ] Support more languages (Python, Java, Go, Rust)
- [ ] Real-time incremental updates
- [ ] IDE integration plugins
- [ ] AI-powered code insights
- [ ] Automated architecture documentation
- [ ] Security vulnerability detection
- [ ] Performance bottleneck analysis

## 💡 Philosophy

> "Code is not just text files - it's a living graph of relationships, dependencies, and interactions. By mapping these connections, we transform static code into dynamic knowledge."

This system treats codebases as **knowledge graphs**, making the implicit relationships explicit and queryable. It's not just about parsing code - it's about understanding the complete ecosystem of your software.