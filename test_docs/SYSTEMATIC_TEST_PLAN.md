# Systematic Test Plan for Universal Code Graph System

## Purpose of the Codebase
The Universal Code Graph System transforms ANY codebase into a searchable Neo4j knowledge graph, enabling:
- Deep code understanding through relationship analysis
- Natural language queries about code functionality
- Cross-language dependency tracking
- Architecture visualization and navigation

## Current Neo4j Status
- **Database**: Running on port 7688 (bolt://localhost:7688)
- **Nodes**: 49,063 total
- **Relationships**: 91,364 total
- **Last Import**: Complete EspoCRM codebase (PHP backend + JS frontend)

## Test Plan Structure

### Phase 1: Data Integrity Verification
Verify that Neo4j accurately represents the EspoCRM codebase structure.

### Phase 2: Relationship Validation
Ensure all code relationships are correctly mapped.

### Phase 3: Search Capability Testing
Test both structured and natural language queries.

### Phase 4: Performance Benchmarks
Measure query performance on the complete graph.

---

## PHASE 1: DATA INTEGRITY VERIFICATION

### 1.1 Node Type Verification

#### PHP Nodes
```cypher
// Test: Count PHP classes
MATCH (c:PHPClass) RETURN COUNT(c) as php_classes
// Expected: Should match count of PHP classes in EspoCRM

// Test: Verify PHP class naming
MATCH (c:PHPClass) WHERE c.name = 'User' AND c.namespace = 'Espo\\Entities'
RETURN c
// Expected: User entity class exists with correct namespace

// Test: Check PHP interfaces
MATCH (i:PHPInterface) RETURN COUNT(i) as interfaces
// Expected: Non-zero count matching actual interfaces

// Test: Verify PHP traits
MATCH (t:PHPTrait) RETURN COUNT(t) as traits
// Expected: Should find traits like DateTime, etc.

// Test: PHP methods exist
MATCH (m:PHPMethod) WHERE m.name = 'save' RETURN COUNT(m) as save_methods
// Expected: Multiple save methods across different classes

// Test: PHP properties
MATCH (p:PHPProperty) RETURN COUNT(p) as properties
// Expected: Thousands of class properties
```

#### JavaScript Nodes
```cypher
// Test: Count JS modules
MATCH (m:JSModule) RETURN COUNT(m) as js_modules
// Expected: ~1,055 JS files

// Test: JS functions
MATCH (f:JSFunction) RETURN COUNT(f) as js_functions
// Expected: Thousands of JS functions

// Test: Verify specific JS module
MATCH (m:JSModule) WHERE m.file_path CONTAINS 'app.js' RETURN m
// Expected: Main application JS file
```

#### File System Nodes
```cypher
// Test: Directory structure
MATCH (d:Directory) RETURN COUNT(d) as directories
// Expected: 2,170 directories

// Test: File nodes
MATCH (f:File) RETURN COUNT(f) as files
// Expected: 8,109 files

// Test: Root directory
MATCH (d:Directory) WHERE d.name = 'espocrm' RETURN d
// Expected: Root project directory exists
```

### 1.2 Sample Manual Verification Checklist

- [ ] Check `application/Espo/Core/Application.php` exists as PHPClass node
- [ ] Verify `application/Espo/Controllers/User.php` has correct methods
- [ ] Confirm `client/src/app.js` exists as JSModule
- [ ] Check directory structure: `application/` → `Espo/` → `Core/` → files
- [ ] Verify namespace `Espo\\Services` contains service classes
- [ ] Check that NO PHP class extends a Directory node

---

## PHASE 2: RELATIONSHIP VALIDATION

### 2.1 Inheritance Relationships
```cypher
// Test: Class inheritance
MATCH (c:PHPClass)-[:EXTENDS]->(p:PHPClass)
RETURN c.name as child, p.name as parent LIMIT 10
// Expected: Valid class inheritance chains

// Test: Interface implementation
MATCH (c:PHPClass)-[:IMPLEMENTS]->(i:PHPInterface)
RETURN c.name as class, i.name as interface LIMIT 10
// Expected: Classes implementing interfaces

// Test: Trait usage
MATCH (c:PHPClass)-[:USES_TRAIT]->(t:PHPTrait)
RETURN c.name as class, t.name as trait LIMIT 10
// Expected: Classes using traits

// CRITICAL: Verify NO wrong relationships
MATCH (c:PHPClass)-[r]->(d:Directory)
RETURN COUNT(r) as wrong_relationships
// Expected: 0 (classes should NEVER extend/implement directories)
```

### 2.2 Method Relationships
```cypher
// Test: Method calls
MATCH (m1:PHPMethod)-[:CALLS]->(m2:PHPMethod)
RETURN m1.name as caller, m2.name as callee LIMIT 10
// Expected: Method call chains

// Test: Instantiation
MATCH (m:PHPMethod)-[:INSTANTIATES]->(c:PHPClass)
RETURN m.name as method, c.name as instantiated_class LIMIT 10
// Expected: Methods creating new objects
```

### 2.3 File Relationships
```cypher
// Test: Directory contains files
MATCH (d:Directory)-[:CONTAINS]->(f:File)
WHERE d.name = 'Controllers'
RETURN f.name LIMIT 10
// Expected: Controller PHP files

// Test: File defines symbols
MATCH (f:File)-[:DEFINES]->(c:PHPClass)
WHERE f.name = 'User.php'
RETURN c.name, c.namespace
// Expected: User class definition
```

### 2.4 Cross-Language Relationships
```cypher
// Test: JS calls PHP API
MATCH (js:JSFunction)-[:CALLS_API]->(php:PHPMethod)
RETURN js.name as js_function, php.name as api_endpoint LIMIT 10
// Expected: Frontend-backend connections
```

---

## PHASE 3: SEARCH CAPABILITY TESTING

### 3.1 Natural Language Query Tests

#### Query: "How is email sent?"
```cypher
// Approach 1: Find email-related classes and methods
MATCH (n)
WHERE toLower(n.name) CONTAINS 'email' OR toLower(n.name) CONTAINS 'mail'
RETURN n.type, n.name, n.file_path
LIMIT 20

// Approach 2: Find send methods in email context
MATCH (c:PHPClass)-[:DEFINES]->(m:PHPMethod)
WHERE toLower(c.name) CONTAINS 'email' AND toLower(m.name) CONTAINS 'send'
RETURN c.name as class, m.name as method, m.file_path

// Approach 3: Trace email sending flow
MATCH path = (m1:PHPMethod)-[:CALLS*1..3]->(m2:PHPMethod)
WHERE toLower(m2.name) CONTAINS 'send' AND toLower(m2.name) CONTAINS 'mail'
RETURN path
```

#### Query: "Where is user authentication handled?"
```cypher
// Find auth-related classes
MATCH (c:PHPClass)
WHERE toLower(c.name) CONTAINS 'auth' OR toLower(c.name) CONTAINS 'login'
RETURN c.name, c.namespace, c.file_path

// Find login methods
MATCH (m:PHPMethod)
WHERE toLower(m.name) IN ['login', 'authenticate', 'checkpassword', 'verify']
RETURN m.name, m.file_path
```

#### Query: "What validates user input?"
```cypher
// Find validation classes and methods
MATCH (n)
WHERE toLower(n.name) CONTAINS 'validat' OR toLower(n.name) CONTAINS 'sanitiz'
RETURN n.type, n.name, n.file_path

// Find validation method calls
MATCH (m1:PHPMethod)-[:CALLS]->(m2:PHPMethod)
WHERE toLower(m2.name) CONTAINS 'validat'
RETURN m1.name as caller, m2.name as validator
```

#### Query: "How are database queries executed?"
```cypher
// Find ORM/database classes
MATCH (c:PHPClass)
WHERE toLower(c.name) CONTAINS 'query' OR toLower(c.name) CONTAINS 'repository' 
   OR toLower(c.name) CONTAINS 'entity'
RETURN c.name, c.namespace

// Find database methods
MATCH (m:PHPMethod)
WHERE toLower(m.name) IN ['find', 'save', 'delete', 'update', 'query', 'execute']
RETURN m.name, m.file_path
```

### 3.2 Generic Query Patterns

```cypher
// Pattern 1: Find functionality by keyword
MATCH (n)
WHERE toLower(n.name) CONTAINS $keyword
RETURN n

// Pattern 2: Find method call chains
MATCH path = (m1:PHPMethod)-[:CALLS*1..3]->(m2:PHPMethod)
WHERE toLower(m2.name) CONTAINS $target_action
RETURN path

// Pattern 3: Find classes in namespace
MATCH (c:PHPClass)
WHERE c.namespace STARTS WITH $namespace_prefix
RETURN c

// Pattern 4: Find all implementations of interface
MATCH (c:PHPClass)-[:IMPLEMENTS]->(i:PHPInterface {name: $interface_name})
RETURN c

// Pattern 5: Find unused code
MATCH (m:PHPMethod)
WHERE NOT (m)<-[:CALLS]-()
RETURN m.name as potentially_unused_method
```

---

## PHASE 4: PERFORMANCE BENCHMARKS

### 4.1 Query Performance Tests

```cypher
// Test 1: Simple node lookup
// Expected: < 10ms
MATCH (c:PHPClass {name: 'User'}) RETURN c

// Test 2: 1-hop traversal
// Expected: < 50ms
MATCH (c:PHPClass {name: 'User'})-[r]->(n) RETURN c, r, n

// Test 3: 3-hop traversal
// Expected: < 200ms
MATCH path = (c:PHPClass {name: 'User'})-[*1..3]->() RETURN path LIMIT 100

// Test 4: Full-text search simulation
// Expected: < 100ms
MATCH (n) WHERE toLower(n.name) CONTAINS 'email' RETURN n LIMIT 50

// Test 5: Complex aggregation
// Expected: < 500ms
MATCH (c:PHPClass)-[:DEFINES]->(m:PHPMethod)
RETURN c.name, COUNT(m) as method_count
ORDER BY method_count DESC
LIMIT 20
```

---

## Test Execution Script

Create `test_docs/run_tests.py`:

```python
#!/usr/bin/env python3
"""Execute systematic tests against Neo4j database"""

import time
from neo4j import GraphDatabase

class GraphTester:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            "bolt://localhost:7688", 
            auth=("neo4j", "password123")
        )
        self.results = []
    
    def test_node_counts(self):
        """Test Phase 1.1: Node counts"""
        with self.driver.session() as session:
            tests = [
                ("PHP Classes", "MATCH (c:PHPClass) RETURN COUNT(c) as count"),
                ("PHP Interfaces", "MATCH (i:PHPInterface) RETURN COUNT(i) as count"),
                ("PHP Methods", "MATCH (m:PHPMethod) RETURN COUNT(m) as count"),
                ("JS Modules", "MATCH (m:JSModule) RETURN COUNT(m) as count"),
                ("Directories", "MATCH (d:Directory) RETURN COUNT(d) as count"),
                ("Files", "MATCH (f:File) RETURN COUNT(f) as count"),
            ]
            
            for name, query in tests:
                result = session.run(query)
                count = result.single()['count']
                self.results.append(f"{name}: {count}")
                print(f"✓ {name}: {count}")
    
    def test_relationships(self):
        """Test Phase 2: Relationships"""
        with self.driver.session() as session:
            # Check for wrong relationships
            result = session.run("""
                MATCH (c:PHPClass)-[r]->(d:Directory)
                RETURN COUNT(r) as count
            """)
            wrong_count = result.single()['count']
            if wrong_count == 0:
                print("✓ No classes extending directories (CORRECT)")
            else:
                print(f"✗ CRITICAL: {wrong_count} classes extend directories!")
    
    def test_search_capability(self, keyword):
        """Test Phase 3: Search by keyword"""
        with self.driver.session() as session:
            query = """
                MATCH (n)
                WHERE toLower(n.name) CONTAINS $keyword
                RETURN n.type as type, n.name as name
                LIMIT 10
            """
            results = session.run(query, keyword=keyword)
            matches = []
            for record in results:
                matches.append(f"{record['type']}: {record['name']}")
            return matches
    
    def run_all_tests(self):
        """Execute all tests"""
        print("=" * 60)
        print("SYSTEMATIC TEST EXECUTION")
        print("=" * 60)
        
        print("\n1. NODE COUNT VERIFICATION")
        self.test_node_counts()
        
        print("\n2. RELATIONSHIP VALIDATION")
        self.test_relationships()
        
        print("\n3. SEARCH TESTS")
        for keyword in ['email', 'auth', 'user', 'database']:
            matches = self.test_search_capability(keyword)
            print(f"\nSearch '{keyword}': Found {len(matches)} matches")
            for match in matches[:3]:
                print(f"  - {match}")
        
        self.driver.close()

if __name__ == "__main__":
    tester = GraphTester()
    tester.run_all_tests()
```

---

## Natural Language Query Capability Assessment

### Current Capabilities ✅
1. **Keyword-based search**: Find code elements by name patterns
2. **Relationship traversal**: Follow code dependencies
3. **Namespace navigation**: Explore package structures
4. **Call chain analysis**: Trace execution flows

### Limitations ⚠️
1. **No semantic understanding**: Can't understand "email sending" means "SMTP" or "mailer"
2. **No NLP processing**: Queries must use exact keywords from code
3. **No context awareness**: Can't infer related concepts

### Enhancement Recommendations
1. Add semantic layer with synonyms/concepts mapping
2. Implement text embeddings for similarity search
3. Create domain-specific query templates
4. Add code documentation to graph for richer search

---

## Test Success Criteria

- [ ] All node counts match actual codebase
- [ ] Zero classes extending directories
- [ ] All inheritance relationships valid
- [ ] File structure correctly represented
- [ ] Natural language queries return relevant results
- [ ] Query performance within benchmarks
- [ ] Cross-language relationships mapped

## Next Steps
1. Execute manual verification queries
2. Run automated test script
3. Document any discrepancies
4. Create query templates for common searches
5. Consider adding semantic layer for better NLP