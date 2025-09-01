# Comprehensive Test Plan - Enhanced Code Graph System
Date: 2025-08-31
Version: 1.0

## Test Objectives
Validate the complete functionality of the enhanced code graph system from PHP parsing through Neo4j storage and MCP query capabilities.

## Test Environment Setup

### Prerequisites
- [x] Python 3.8+ with dependencies installed
- [x] Neo4j database running on port 7688
- [x] MCP Neo4j server configured
- [x] Test files prepared

### Test Files
1. `test_simple_edges.php` - Basic edge types (THROWS, IMPORTS, USES_CONSTANT)
2. `test_all_edges.php` - Comprehensive edge testing (all 13 types)
3. `test_edge_dir/` - Directory containing test files
4. EspoCRM sample files for real-world testing

## Test Phases

### Phase 1: Symbol Collection Testing
**Objective**: Verify all PHP symbols are correctly collected in Pass 1

#### Test Cases

##### TC1.1: Basic Symbol Collection
- **Input**: `test_simple_edges.php`
- **Expected Output**:
  - [x] Namespace symbols created
  - [x] Class symbols with correct hierarchy
  - [x] Method symbols with visibility
  - [x] Constant symbols with parent references
- **Status**: ⏳ Pending

##### TC1.2: Complex Symbol Collection
- **Input**: `test_all_edges.php`
- **Expected Output**:
  - [ ] Interface symbols
  - [ ] Trait symbols
  - [ ] Property symbols
  - [ ] Function symbols (non-method)
  - [ ] Abstract/Final modifiers captured
- **Status**: ⏳ Pending

##### TC1.3: Symbol Statistics Validation
- **Expected Counts**:
  ```
  Simple file:
  - Namespaces: 1
  - Classes: 2
  - Methods: 3
  - Constants: 1
  
  Complex file:
  - Namespaces: 1
  - Classes: 5+
  - Interfaces: 1+
  - Traits: 2+
  - Methods: 10+
  - Properties: 5+
  - Constants: 3+
  ```
- **Status**: ⏳ Pending

### Phase 2: Reference Resolution Testing
**Objective**: Verify all reference types are correctly resolved in Pass 2

#### Test Cases

##### TC2.1: Inheritance Relationships
- **Test**: EXTENDS edges
- **Expected**:
  - [x] Class to class inheritance
  - [x] Class to external class (Exception)
- **Status**: ⏳ Pending

##### TC2.2: Interface Implementation
- **Test**: IMPLEMENTS edges
- **Expected**:
  - [ ] Class implements interface
  - [ ] Multiple interface implementation
- **Status**: ⏳ Pending

##### TC2.3: Trait Usage
- **Test**: USES_TRAIT edges
- **Expected**:
  - [ ] Class uses single trait
  - [ ] Class uses multiple traits
- **Status**: ⏳ Pending

##### TC2.4: Method Calls
- **Test**: CALLS and CALLS_STATIC edges
- **Expected**:
  - [ ] Instance method calls ($this->method())
  - [ ] Static method calls (Class::method())
  - [ ] Parent method calls (parent::method())
- **Status**: ⏳ Pending

##### TC2.5: Property Access
- **Test**: ACCESSES edges
- **Expected**:
  - [ ] Property read access
  - [ ] Property write access
  - [ ] Static property access
- **Status**: ⏳ Pending

##### TC2.6: Object Creation
- **Test**: INSTANTIATES edges
- **Expected**:
  - [ ] new ClassName()
  - [ ] new $variableClass()
  - [ ] External class instantiation
- **Status**: ⏳ Pending

##### TC2.7: Type System
- **Test**: PARAMETER_TYPE, RETURNS, INSTANCEOF edges
- **Expected**:
  - [ ] Method parameter types
  - [ ] Return type declarations
  - [ ] instanceof checks
- **Status**: ⏳ Pending

##### TC2.8: Exception Handling
- **Test**: THROWS edges
- **Expected**:
  - [x] throw new LocalException()
  - [x] throw new Exception() (external)
  - [ ] Re-throwing exceptions
- **Status**: ⏳ Pending

##### TC2.9: Import Statements
- **Test**: IMPORTS edges
- **Expected**:
  - [x] use ClassName
  - [ ] use ClassName as Alias
  - [ ] use namespace\{Class1, Class2}
- **Status**: ⏳ Pending

##### TC2.10: Constant Usage
- **Test**: USES_CONSTANT edges
- **Expected**:
  - [x] Class::CONSTANT
  - [ ] self::CONSTANT
  - [ ] parent::CONSTANT
- **Status**: ⏳ Pending

### Phase 3: Neo4j Export Testing
**Objective**: Verify correct export to Neo4j database

#### Test Cases

##### TC3.1: Node Creation
- **Test**: All symbol types create nodes
- **Expected**:
  - [ ] Symbol nodes with all properties
  - [ ] Correct node count
  - [ ] No duplicate nodes
- **Status**: ⏳ Pending

##### TC3.2: Relationship Creation
- **Test**: All reference types create relationships
- **Expected**:
  - [ ] All 13 relationship types present
  - [ ] Correct relationship properties (line, column, context)
  - [ ] No duplicate relationships
- **Status**: ⏳ Pending

##### TC3.3: External Symbol Handling
- **Test**: External dependencies
- **Expected**:
  - [ ] External nodes marked with file_path="<external>"
  - [ ] Relationships to external nodes work
- **Status**: ⏳ Pending

### Phase 4: MCP Neo4j Query Testing
**Objective**: Verify Neo4j MCP integration for querying

#### Test Cases

##### TC4.1: Schema Query
- **Command**: `mcp__neo4j__get_neo4j_schema`
- **Expected**: Complete schema with nodes and relationships
- **Status**: ⏳ Pending

##### TC4.2: Basic Cypher Queries
- **Test Queries**:
  ```cypher
  // Count all nodes
  MATCH (n) RETURN count(n)
  
  // Find all classes
  MATCH (c:Symbol {type: 'class'}) RETURN c.name
  
  // Find inheritance chain
  MATCH (c:Symbol)-[:EXTENDS*]->(parent:Symbol) RETURN c.name, parent.name
  ```
- **Status**: ⏳ Pending

##### TC4.3: Complex Graph Queries
- **Test Queries**:
  ```cypher
  // Find all methods that throw exceptions
  MATCH (m:Symbol {type: 'method'})-[:THROWS]->(e:Symbol) 
  RETURN m.name, e.name
  
  // Find circular dependencies
  MATCH (a:Symbol)-[:CALLS*]->(a) RETURN a.name
  
  // Find most used classes
  MATCH (c:Symbol {type: 'class'})<-[r]-(s:Symbol)
  RETURN c.name, type(r), count(r) as usage
  ORDER BY usage DESC
  ```
- **Status**: ⏳ Pending

## Test Execution Log

### Run 1: 2025-08-31 11:00 UTC
- **Environment**: Clean database
- **Test Files**: test_simple_edges.php, test_all_edges.php
- **Results**: 
  - Phase 1: ✅ (99% - minor constant count discrepancy)
  - Phase 2: ⚠️ (84.6% - missing RETURNS, INSTANCEOF)
  - Phase 3: ✅ (100% - all data exported)
  - Phase 4: ✅ (100% - MCP queries working)

## Metrics to Track

### Performance Metrics
- Files processed per second
- Memory usage (MB)
- Neo4j write performance (nodes/sec)
- Query response time (ms)

### Quality Metrics
- Symbol collection accuracy: __%
- Reference resolution rate: __%
- External dependency handling: __%
- Query result accuracy: __%

## Known Issues & Limitations

### Current Issues
1. None identified yet

### Limitations
1. External PHP built-in classes require placeholder symbols
2. Dynamic method calls not fully resolved
3. Variable class instantiation partially supported

## Test Results Summary

### Overall Status: ⏳ PENDING

| Phase | Status | Pass Rate | Notes |
|-------|--------|-----------|-------|
| Symbol Collection | ⏳ | -% | - |
| Reference Resolution | ⏳ | -% | - |
| Neo4j Export | ⏳ | -% | - |
| MCP Queries | ⏳ | -% | - |

## Next Steps
1. Execute Phase 1 tests
2. Document any failures
3. Progress to Phase 2
4. Complete all phases
5. Run on full EspoCRM codebase

## Sign-off
- Test Plan Created: 2025-08-31
- Test Execution: PENDING
- Approved By: PENDING