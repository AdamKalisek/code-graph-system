# Enhanced Code Graph Testing Plan

## Overview
Progressive testing strategy to validate the enhanced code graph system with Symbol Table architecture. We'll start small and gradually scale up to the full EspoCRM codebase.

## Phase 1: Environment Setup (Day 1)

### 1.1 Clean Database Environment
```bash
# Stop any existing Neo4j containers
docker stop neo4j-codegraph 2>/dev/null || true
docker rm neo4j-codegraph 2>/dev/null || true

# Clean symbol table cache
rm -rf .cache/symbols.db
rm -rf .cache/pipeline_stats.json

# Start fresh Neo4j instance
docker run -d \
  --name neo4j-codegraph \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password123 \
  -e NEO4J_PLUGINS='["apoc"]' \
  -e NEO4J_dbms_memory_heap_max__size=4G \
  -v $(pwd)/neo4j/data:/data \
  -v $(pwd)/neo4j/logs:/logs \
  neo4j:5.15.0
```

### 1.2 Verify Clean State
```cypher
MATCH (n) RETURN count(n) as nodeCount;
// Should return 0

CALL db.indexes();
// Should show only system indexes
```

## Phase 2: Unit Testing Components (Day 1)

### 2.1 Symbol Table Tests
```python
# test_symbol_table_advanced.py
- Test symbol insertion performance (target: 1000 symbols/sec)
- Test resolution speed (target: 10000 lookups/sec)
- Test cache effectiveness (90%+ hit rate)
- Test transaction handling
- Test concurrent access
```

### 2.2 Parser Tests
```python
# test_php_parser_edge_cases.py
- Test namespace handling
- Test trait usage
- Test anonymous classes
- Test PHP 8.x features (enums, attributes)
- Test error recovery
```

### 2.3 Reference Resolution Tests
```python
# test_reference_resolution.py
- Test circular dependencies
- Test forward references
- Test namespace aliases
- Test relative vs absolute names
```

## Phase 3: Small Batch Testing (Day 2)

### 3.1 Create Test Subsets
```bash
# Create test directories with increasing complexity
mkdir -p test_batches/{tiny,small,medium,large}

# Tiny: 10 files - Single module
cp -r /path/to/espocrm/application/Espo/Core/Authentication test_batches/tiny/

# Small: 100 files - Core modules
cp -r /path/to/espocrm/application/Espo/Core test_batches/small/

# Medium: 1000 files - All application code
cp -r /path/to/espocrm/application test_batches/medium/

# Large: Full codebase
cp -r /path/to/espocrm test_batches/large/
```

### 3.2 Progressive Import Tests

#### Test 1: Tiny Batch (10 files)
```bash
python enhanced_pipeline.py test_batches/tiny \
  --neo4j-password password123 \
  --verbose

# Validate:
# - All symbols collected
# - All references resolved
# - Neo4j nodes/edges created
# - No unresolved references
```

Expected Metrics:
- Symbols: ~50-100
- References: ~100-200
- Processing time: < 1 second
- Memory usage: < 100MB

#### Test 2: Small Batch (100 files)
```bash
python enhanced_pipeline.py test_batches/small \
  --neo4j-password password123 \
  --batch-size 500

# Monitor:
# - Memory usage stays under 500MB
# - Processing time < 10 seconds
# - Cache hit rate > 80%
```

Expected Metrics:
- Symbols: ~500-1000
- References: ~1000-2000
- Processing time: < 10 seconds
- Memory usage: < 500MB

#### Test 3: Medium Batch (1000 files)
```bash
python enhanced_pipeline.py test_batches/medium \
  --neo4j-password password123 \
  --batch-size 1000

# Monitor:
# - Memory usage stays under 1GB
# - Processing time < 60 seconds
# - Batch processing works correctly
```

Expected Metrics:
- Symbols: ~5000-10000
- References: ~10000-20000
- Processing time: < 60 seconds
- Memory usage: < 1GB

## Phase 4: Edge Type Validation (Day 2)

### 4.1 Query for Each Edge Type
```cypher
// EXTENDS relationships
MATCH (child)-[:EXTENDS]->(parent)
RETURN child.name, parent.name
LIMIT 10;

// IMPLEMENTS relationships
MATCH (class)-[:IMPLEMENTS]->(interface)
RETURN class.name, interface.name
LIMIT 10;

// USES_TRAIT relationships
MATCH (class)-[:USES_TRAIT]->(trait)
RETURN class.name, trait.name
LIMIT 10;

// CALLS relationships
MATCH (method1)-[:CALLS]->(method2)
RETURN method1.name, method2.name
LIMIT 10;

// INSTANTIATES relationships
MATCH (method)-[:INSTANTIATES]->(class)
RETURN method.name, class.name
LIMIT 10;

// INJECTS relationships (Laravel DI)
MATCH (class)-[:INJECTS]->(dependency)
RETURN class.name, dependency.name
LIMIT 10;
```

### 4.2 Edge Coverage Report
```python
# generate_edge_coverage_report.py
def check_edge_coverage():
    required_edges = [
        'EXTENDS', 'IMPLEMENTS', 'USES_TRAIT',
        'CALLS', 'CALLS_STATIC', 'INSTANTIATES',
        'ACCESSES', 'USES_CONSTANT', 'BELONGS_TO',
        'PARAMETER_TYPE', 'RETURNS', 'THROWS',
        'IMPORTS', 'USES_NAMESPACE',
        # Laravel specific
        'INJECTS', 'ROUTES_TO_METHOD', 'LISTENS_TO',
        'HAS_RELATIONSHIP_HASONE', 'HAS_RELATIONSHIP_HASMANY'
    ]
    
    for edge_type in required_edges:
        count = neo4j.run(f"MATCH ()-[r:{edge_type}]->() RETURN count(r)")
        print(f"{edge_type}: {count}")
```

## Phase 5: Framework Pattern Testing (Day 3)

### 5.1 Laravel Pattern Detection
```bash
# Test on a Laravel project if available
python enhanced_pipeline.py /path/to/laravel-project \
  --neo4j-password password123

# Validate Laravel-specific patterns:
# - Routes connected to controllers
# - Service providers with bindings
# - Event listeners connected to events
# - Middleware in request pipeline
```

### 5.2 Query Laravel Patterns
```cypher
// Find all routes
MATCH (route:Symbol {laravel_type: 'route'})
RETURN route.name;

// Trace route to controller method
MATCH path = (route)-[:ROUTES_TO_METHOD]->(method)
RETURN path;

// Find dependency injection
MATCH (controller)-[:INJECTS]->(service)
RETURN controller.name, service.name;
```

## Phase 6: Performance Testing (Day 3)

### 6.1 Benchmark Tests
```python
# benchmark_performance.py
import time
import psutil
import os

def benchmark_parsing(directory):
    start_time = time.time()
    start_memory = psutil.Process(os.getpid()).memory_info().rss
    
    pipeline = EnhancedCodeGraphPipeline(directory)
    stats = pipeline.run_full_pipeline()
    
    end_time = time.time()
    end_memory = psutil.Process(os.getpid()).memory_info().rss
    
    return {
        'duration': end_time - start_time,
        'memory_used': (end_memory - start_memory) / 1024 / 1024,  # MB
        'files_per_second': stats['files_parsed'] / (end_time - start_time),
        'symbols_per_second': stats['total_symbols'] / (end_time - start_time)
    }
```

### 6.2 Performance Targets
- **Small (100 files)**: < 10 seconds
- **Medium (1000 files)**: < 60 seconds  
- **Large (10000 files)**: < 10 minutes
- **Memory usage**: < 100MB per 1000 files
- **Symbol resolution**: > 10,000 lookups/second
- **Neo4j batch insert**: > 1000 nodes/second

## Phase 7: Full EspoCRM Import (Day 4)

### 7.1 Pre-Import Checklist
- [ ] Neo4j has 4GB+ heap memory
- [ ] At least 10GB free disk space
- [ ] Symbol table cache directory exists
- [ ] All dependencies installed
- [ ] Monitoring tools ready

### 7.2 Full Import with Monitoring
```bash
# Run with progress monitoring
python enhanced_pipeline.py /path/to/espocrm \
  --neo4j-password password123 \
  --batch-size 5000 \
  --verbose 2>&1 | tee import.log

# Monitor in another terminal
watch -n 1 'tail -20 import.log'
```

### 7.3 Post-Import Validation
```cypher
// Total counts
MATCH (n) RETURN count(n) as totalNodes;
MATCH ()-[r]->() RETURN count(r) as totalRelationships;

// Breakdown by type
MATCH (n:Symbol)
RETURN n.type, count(n) as count
ORDER BY count DESC;

// Relationship types
CALL db.relationshipTypes() YIELD relationshipType
RETURN relationshipType;

// Sample path query - How is email sent?
MATCH path = (entry)-[:CALLS*1..5]->(target)
WHERE entry.name CONTAINS 'send' 
  AND target.name CONTAINS 'Email'
RETURN path
LIMIT 5;
```

## Phase 8: Query Testing (Day 4)

### 8.1 Essential Queries
```cypher
// 1. Find all email sending paths
MATCH path = (n)-[:CALLS*1..10]->(m)
WHERE m.name CONTAINS 'mail' OR m.name CONTAINS 'Email'
RETURN path;

// 2. Find all database models
MATCH (n:Symbol {type: 'class'})-[:EXTENDS]->(parent)
WHERE parent.name CONTAINS 'Model'
RETURN n.name;

// 3. Find authentication flow
MATCH path = (auth)-[:CALLS*1..5]->(method)
WHERE auth.name CONTAINS 'authenticate'
RETURN path;

// 4. Find all API endpoints (Laravel)
MATCH (route:Symbol)-[:ROUTES_TO_METHOD]->(method)
WHERE route.name CONTAINS 'api/'
RETURN route.name, method.name;

// 5. Find circular dependencies
MATCH path = (a)-[:EXTENDS|IMPLEMENTS*1..5]->(a)
RETURN path;
```

### 8.2 Performance Queries
```cypher
// Should complete in < 1 second
MATCH (n:Symbol {name: 'User'})
RETURN n;

// Should complete in < 5 seconds  
MATCH path = shortestPath((a:Symbol)-[*1..10]-(b:Symbol))
WHERE a.name = 'EmailSender' AND b.name = 'SmtpTransport'
RETURN path;

// Should complete in < 10 seconds
MATCH (n:Symbol)-[r]->(m:Symbol)
WHERE n.file_path CONTAINS 'Controllers'
RETURN n, r, m
LIMIT 1000;
```

## Phase 9: Incremental Updates (Day 5)

### 9.1 Test Incremental Parsing
```python
# Test that only changed files are reparsed
def test_incremental_update():
    # Initial parse
    pipeline.run_full_pipeline()
    initial_stats = pipeline.stats
    
    # Modify one file
    modify_file('test_batches/small/User.php')
    
    # Reparse
    pipeline.run_full_pipeline()
    update_stats = pipeline.stats
    
    # Only the modified file should be reparsed
    assert update_stats['files_parsed'] == 1
    assert update_stats['duration'] < 1.0  # Should be fast
```

### 9.2 Test Hash-Based Change Detection
```python
def test_hash_detection():
    # Parse file
    symbol_table.parse_file('test.php')
    
    # No change - should skip
    symbol_table.parse_file('test.php')
    assert symbol_table.get_file_hash('test.php') == original_hash
    
    # Change file
    modify_file('test.php')
    
    # Should reparse
    symbol_table.parse_file('test.php')
    assert symbol_table.get_file_hash('test.php') != original_hash
```

## Phase 10: Stress Testing (Day 5)

### 10.1 Large File Test
Create a PHP file with:
- 1000+ methods
- 100+ classes
- Deep inheritance (10+ levels)
- Complex namespace structure

### 10.2 Concurrent Access Test
```python
# Test concurrent parsing
import concurrent.futures

def parse_file_batch(files):
    for file in files:
        symbol_table.parse_file(file)

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    futures = []
    for batch in file_batches:
        futures.append(executor.submit(parse_file_batch, batch))
    
    concurrent.futures.wait(futures)
```

## Success Criteria

### ✅ Pass Criteria
1. **Correctness**
   - All 30+ edge types detected
   - < 1% unresolved references
   - No data loss during import

2. **Performance**
   - Full EspoCRM import < 30 minutes
   - Memory usage < 2GB
   - Query response < 5 seconds

3. **Reliability**
   - No crashes on 10,000+ files
   - Handles malformed PHP gracefully
   - Incremental updates work correctly

### ❌ Fail Criteria
1. Missing edge types (< 20 types found)
2. > 10% unresolved references
3. Memory usage > 4GB
4. Import takes > 1 hour
5. Crashes on valid PHP code

## Monitoring Dashboard

Create a simple monitoring script:
```python
# monitor.py
while True:
    stats = {
        'symbols': symbol_table.get_stats()['total_symbols'],
        'references': symbol_table.get_stats()['total_references'],
        'neo4j_nodes': neo4j.run("MATCH (n) RETURN count(n)"),
        'memory_mb': psutil.Process().memory_info().rss / 1024 / 1024,
        'cache_size_mb': os.path.getsize('.cache/symbols.db') / 1024 / 1024
    }
    print(f"\r{stats}", end='')
    time.sleep(1)
```

## Rollback Plan

If issues occur:
1. Stop the import process
2. Clear Neo4j: `MATCH (n) DETACH DELETE n`
3. Remove cache: `rm -rf .cache/`
4. Review logs for errors
5. Fix issues in code
6. Restart from Phase 3

## Timeline

- **Day 1**: Environment setup, unit tests
- **Day 2**: Small batch testing, edge validation
- **Day 3**: Framework patterns, performance testing
- **Day 4**: Full import, query testing
- **Day 5**: Incremental updates, stress testing

Total: 5 days for complete validation