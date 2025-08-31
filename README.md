# Code Graph System - Advanced Multi-Language Code Analysis Platform

A sophisticated code analysis system that creates a comprehensive knowledge graph of your codebase, capturing all relationships, dependencies, and interactions between code elements. Currently optimized for **EspoCRM** with support for PHP and JavaScript.

## 🚀 Current Status: **FULLY OPERATIONAL**

- **21,232 nodes** indexed
- **53,342 relationships** captured
- **2,646 PHP classes** analyzed
- **All critical relationship types working**

## 📊 What This System Does

This system creates a complete graph representation of your codebase in Neo4j, allowing you to:

- **Trace method calls** across your entire codebase
- **Understand dependencies** between classes and files
- **Analyze data flow** through property reads/writes
- **Track API interactions** between frontend and backend
- **Visualize code structure** in an interactive graph
- **Debug complex issues** by following execution paths
- **Understand impact** of changes before making them

## 🏗️ Architecture

### Core Components

1. **Enhanced PHP Parser** (`plugins/php/ast_parser_enhanced.php`)
   - Uses nikic/PHP-Parser for accurate AST parsing
   - Extracts ALL relationship types with proper IDs
   - Handles dynamic PHP patterns

2. **QueryBuilder Parser** (`plugins/php/querybuilder_parser.php`)
   - Captures fluent API database query chains
   - Tracks ORM operations
   - Maps repository methods

3. **Formula DSL Parser** (`plugins/espocrm/formula_parser.py`)
   - Parses EspoCRM's business logic scripting language
   - Extracts entity operations and workflows
   - Tracks ACL checks and record CRUD

4. **JavaScript API Parser** (`plugins/javascript/api_parser.py`)
   - Captures Espo.Ajax calls
   - Tracks model operations
   - Identifies WebSocket events

5. **Comprehensive Indexer** (`indexing_scripts/index_espocrm_complete_fixed.py`)
   - Integrates all parsers
   - Handles batch processing
   - Creates complete graph with all relationships

### Database Schema

#### Node Types
- **Directory** - Folder structure (3,406 nodes)
- **File** - PHP/JS files (400+ nodes)
- **Class** - PHP classes (2,646 nodes)
- **Method** - Class methods (1,940 nodes)
- **Property** - Class properties (176 nodes)
- **Unresolved** - External dependencies

#### Relationship Types

| Relationship | Count | Description |
|-------------|-------|-------------|
| **CONTAINS** | 3,368 | Directory hierarchy |
| **DEFINED_IN** | 2,573 | Symbol to file mapping |
| **HAS_METHOD** | 2,015 | Class to method |
| **CALLS** | 681 | Method/function calls |
| **IMPORTS** | 403 | Dependencies/use statements |
| **READS** | 401 | Property read access |
| **IN_DIRECTORY** | 399 | File to directory |
| **HAS_PROPERTY** | 185 | Class to property |
| **WRITES** | 114 | Property write access |
| **INSTANTIATES** | 12 | Object creation |
| **EXTENDS** | 8 | Class inheritance |
| **IMPLEMENTS** | - | Interface implementation |
| **THROWS** | - | Exception handling |
| **HAS_QUERY** | - | QueryBuilder queries |
| **CALLS_API** | - | JS to backend API calls |

## 🔧 Installation

### Prerequisites

1. **Neo4j Database**
   ```bash
   docker run -d \
     --name neo4j \
     -p 7474:7474 -p 7688:7687 \
     -e NEO4J_AUTH=neo4j/password123 \
     neo4j:5.26.0-community
   ```

2. **Python Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **PHP with nikic/PHP-Parser**
   ```bash
   composer require nikic/php-parser
   ```

### Quick Start

1. **Clean the database**
   ```bash
   echo "yes" | python indexing_scripts/clean_neo4j_enhanced.py
   ```

2. **Run the comprehensive indexer**
   ```bash
   python indexing_scripts/index_espocrm_complete_fixed.py \
     --path /path/to/espocrm \
     --batch-size 50
   ```

3. **Access Neo4j Browser**
   - URL: http://localhost:7474
   - Connection: `bolt://localhost:7688`
   - Username: `neo4j`
   - Password: `password123`

## 📈 Neo4j Queries

### Essential Queries for Code Navigation

#### 1. **View Complete Code Hierarchy** (⭐ RECOMMENDED)
```cypher
MATCH (d:Directory)<-[:IN_DIRECTORY]-(f:File)
WHERE d.name = 'Core'
OPTIONAL MATCH (f)-[:DEFINED_IN]-(c:Class)
OPTIONAL MATCH (c)-[:HAS_METHOD]->(m:Method)
OPTIONAL MATCH (c)-[:HAS_PROPERTY]->(p:Property)
OPTIONAL MATCH (m)-[:CALLS]->(callTarget)
OPTIONAL MATCH (m)-[:READS]->(readTarget)
OPTIONAL MATCH (m)-[:WRITES]->(writeTarget)
OPTIONAL MATCH (m)-[:INSTANTIATES]->(newTarget)
OPTIONAL MATCH (m)-[:THROWS]->(throwTarget)
OPTIONAL MATCH (f)-[:IMPORTS]->(importTarget)
OPTIONAL MATCH (c)-[:EXTENDS]->(parent)
OPTIONAL MATCH (c)-[:IMPLEMENTS]->(interface)
RETURN d, f, c, m, p, callTarget, readTarget, writeTarget, newTarget, throwTarget, importTarget, parent, interface
LIMIT 200
```

#### 2. **View Everything Connected to a Directory**
```cypher
MATCH path = (start)-[*1..4]-(end)
WHERE start:Directory AND start.name = 'Core'
RETURN path
LIMIT 300
```

#### 3. **Trace Method Calls**
```cypher
MATCH (source:Method)-[r:CALLS]->(target)
WHERE source.name = 'save'
RETURN source, r, target
LIMIT 100
```

#### 4. **Find All Classes in a Namespace**
```cypher
MATCH (c:Class)
WHERE c.qualified_name STARTS WITH 'Espo\\Core'
RETURN c
LIMIT 50
```

#### 5. **Analyze Class Dependencies**
```cypher
MATCH (c:Class {name: 'User'})-[:IMPORTS]->(dep)
RETURN c, dep
```

#### 6. **Track Property Access**
```cypher
MATCH (m:Method)-[r:READS|WRITES]->(p:Property)
WHERE p.name CONTAINS 'data'
RETURN m, r, p
LIMIT 50
```

#### 7. **View Class Hierarchy with Methods and Properties**
```cypher
MATCH (c:Class {name: 'Container'})
OPTIONAL MATCH (c)-[:HAS_METHOD]->(m:Method)
OPTIONAL MATCH (c)-[:HAS_PROPERTY]->(p:Property)
OPTIONAL MATCH (c)-[:EXTENDS]->(parent)
OPTIONAL MATCH (c)-[:IMPLEMENTS]->(interface)
RETURN c, m, p, parent, interface
```

#### 8. **Find Unused Methods**
```cypher
MATCH (m:Method)
WHERE NOT (m)<-[:CALLS]-()
RETURN m.qualified_name as UnusedMethod
LIMIT 20
```

#### 9. **Trace Execution Path**
```cypher
MATCH path = (start:Method)-[:CALLS*1..5]->(end:Method)
WHERE start.name = 'handleRequest'
RETURN path
LIMIT 10
```

#### 10. **Database Query Patterns**
```cypher
MATCH (q:Query)<-[:HAS_QUERY]-(f:File)
RETURN f.name as File, q.metadata as QueryChain
LIMIT 20
```

### Statistics Queries

#### Overall Statistics
```cypher
MATCH (n)
WITH count(n) as totalNodes
MATCH ()-[r]->()
WITH totalNodes, count(r) as totalRelationships
MATCH (c:Class)
WITH totalNodes, totalRelationships, count(c) as classes
MATCH (m:Method)
WITH totalNodes, totalRelationships, classes, count(m) as methods
MATCH ()-[call:CALLS]->()
RETURN 
  totalNodes as TotalNodes,
  totalRelationships as TotalRelationships,
  classes as Classes,
  methods as Methods,
  count(call) as MethodCalls
```

#### Relationship Distribution
```cypher
MATCH ()-[r]->()
RETURN type(r) as RelationshipType, count(r) as Count
ORDER BY Count DESC
```

## 🛠️ Advanced Features

### Enhanced PHP Parser Features

The PHP parser captures:
- **Method calls** - Instance, static, parent, self calls
- **Property access** - Reads and writes with distinction
- **Object instantiation** - `new Class()` tracking
- **Exception handling** - `throw` and `try-catch` blocks
- **Imports** - `use` statements and `require`/`include`
- **Dynamic patterns** - Variable classes, magic methods

### QueryBuilder Parser

Captures database query patterns:
```php
$query = $entityManager->getQueryBuilder()
    ->select(['id', 'name'])
    ->from('User')
    ->where(['status' => 'Active'])
    ->orderBy('createdAt', 'DESC')
    ->limit(10)
    ->build();
```

### Formula DSL Parser

Parses EspoCRM formulas:
```javascript
entity\setAttribute('status', 'Active');
record\create('Note', {
    'name': entity\getAttribute('name')
});
workflow\trigger('StatusChanged');
```

### JavaScript API Parser

Tracks frontend-backend communication:
```javascript
Espo.Ajax.getRequest('User/action/list');
this.model.fetch();
this.model.save(attributes);
```

## 📁 Project Structure

```
code-graph-system/
├── indexing_scripts/
│   ├── index_espocrm_complete_fixed.py  # Main comprehensive indexer
│   ├── clean_neo4j_enhanced.py          # Database cleanup utility
│   └── index_complete_espocrm_optimized.py
├── plugins/
│   ├── php/
│   │   ├── ast_parser_enhanced.php      # Enhanced PHP parser
│   │   ├── querybuilder_parser.php      # QueryBuilder chain parser
│   │   ├── espocrm_aware_parser.php     # EspoCRM-specific patterns
│   │   └── nikic_parser.py              # Python wrapper for PHP parser
│   ├── javascript/
│   │   └── api_parser.py                # JavaScript API call parser
│   └── espocrm/
│       ├── formula_parser.py            # Formula DSL parser
│       └── metadata_parser.py           # Metadata JSON parser
├── tests/
│   ├── test_complete_coverage.py        # Comprehensive test suite
│   ├── test_enhanced_parser.php         # PHP parser tests
│   └── test_querybuilder_chains.php     # QueryBuilder tests
├── code_graph_system/
│   └── core/
│       ├── graph_store.py               # Neo4j interface
│       └── schema.py                    # Data models
└── DEBUG_PLAN.md                        # Detailed debug documentation
```

## 🐛 Debugging & Troubleshooting

### Common Issues

1. **Neo4j Connection Issues**
   - Ensure Neo4j is running: `docker ps`
   - Check port mapping: Should be 7688 for bolt
   - Verify credentials: neo4j/password123

2. **Parser Errors**
   - Check PHP is installed: `php --version`
   - Verify nikic/PHP-Parser: `composer show nikic/php-parser`
   - Check file permissions

3. **Missing Relationships**
   - Some relationships require target nodes to exist
   - External dependencies create "unresolved" placeholder nodes
   - Run with `--log-level DEBUG` for detailed output

### Debug Commands

```bash
# Check what's in the database
python validate_current_graph.py

# Test small batch
python test_small_batch.py

# Run with debug logging
python indexing_scripts/index_espocrm_complete_fixed.py --log-level DEBUG

# Test individual parser
php plugins/php/ast_parser_enhanced.php /path/to/file.php
```

## 🚀 Performance

- Indexes ~3,000 PHP files in ~5 minutes
- Batch processing with configurable size
- Optimized Neo4j bulk ingestion
- Cached directory structure
- Generator-based file iteration

## 📚 Use Cases

1. **Code Navigation** - Jump from method to method following calls
2. **Impact Analysis** - See what breaks if you change something
3. **Dependency Management** - Understand coupling between modules
4. **Security Auditing** - Trace data flow and access patterns
5. **Performance Optimization** - Find hot paths and bottlenecks
6. **Documentation** - Generate relationship diagrams
7. **Refactoring** - Safely restructure with full visibility
8. **Debugging** - Follow execution paths to find issues

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📝 License

MIT License - See LICENSE file for details

## 🙏 Acknowledgments

- Built with [nikic/PHP-Parser](https://github.com/nikic/PHP-Parser)
- Powered by [Neo4j](https://neo4j.com/)
- Optimized for [EspoCRM](https://www.espocrm.com/)

## 📞 Support

For issues, questions, or contributions, please open an issue on GitHub.

---

**Last Updated:** 2025-08-30
**Version:** 2.0.0
**Status:** Production Ready