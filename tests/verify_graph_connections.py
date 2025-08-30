#!/usr/bin/env python3
"""
Verify Graph Connections Test
Tests that the indexed graph has all expected relationships
"""

import sys
sys.path.append('.')

from code_graph_system.core.graph_store import FederatedGraphStore

def verify_graph_connections():
    """Verify all graph connections are properly created"""
    print("\n" + "="*70)
    print("GRAPH CONNECTION VERIFICATION")
    print("="*70)
    
    # Connect to Neo4j
    graph = FederatedGraphStore(
        'bolt://localhost:7688',
        ('neo4j', 'password123'),
        {'federation': {'mode': 'unified'}}
    )
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Directory hierarchy
    print("\n1. Testing directory hierarchy...")
    result = graph.query("""
        MATCH path = (root:Directory {name: 'espocrm'})-[:CONTAINS*]->(leaf:Directory)
        RETURN count(distinct path) as paths
    """)
    
    if result and result[0]['paths'] > 0:
        print(f"   ✅ Directory hierarchy: {result[0]['paths']} paths found")
        tests_passed += 1
    else:
        print(f"   ❌ Directory hierarchy: No paths found")
        tests_failed += 1
    
    # Test 2: Files in directories
    print("\n2. Testing file-to-directory relationships...")
    result = graph.query("""
        MATCH (f:File)-[:IN_DIRECTORY]->(d:Directory)
        RETURN count(f) as files_linked
    """)
    
    if result and result[0]['files_linked'] > 0:
        print(f"   ✅ File-to-directory: {result[0]['files_linked']} files linked")
        tests_passed += 1
    else:
        print(f"   ❌ File-to-directory: No files linked to directories")
        tests_failed += 1
    
    # Test 3: Symbols in files
    print("\n3. Testing symbol-to-file relationships...")
    result = graph.query("""
        MATCH (s:Symbol)-[:DEFINED_IN]->(f:File)
        RETURN count(distinct s) as symbols_defined
    """)
    
    if result and result[0]['symbols_defined'] > 0:
        print(f"   ✅ Symbol-to-file: {result[0]['symbols_defined']} symbols defined")
        tests_passed += 1
    else:
        print(f"   ❌ Symbol-to-file: No symbols defined in files")
        tests_failed += 1
    
    # Test 4: Complete path traversal
    print("\n4. Testing complete path traversal...")
    result = graph.query("""
        MATCH path = (dir:Directory)-[:CONTAINS*0..3]->(subdir:Directory)<-[:IN_DIRECTORY]-(f:File)<-[:DEFINED_IN]-(s:Symbol)
        WHERE dir.name = 'espocrm'
        RETURN count(distinct s) as connected_symbols
        LIMIT 1
    """)
    
    if result and result[0]['connected_symbols'] > 0:
        print(f"   ✅ Complete traversal: {result[0]['connected_symbols']} symbols connected through full path")
        tests_passed += 1
    else:
        print(f"   ❌ Complete traversal: No complete paths found")
        tests_failed += 1
    
    # Test 5: Class methods
    print("\n5. Testing class-method relationships...")
    result = graph.query("""
        MATCH (c:Class)-[:HAS_METHOD]->(m:Method)
        RETURN count(distinct c) as classes_with_methods
    """)
    
    if result and result[0]['classes_with_methods'] > 0:
        print(f"   ✅ Class methods: {result[0]['classes_with_methods']} classes have methods")
        tests_passed += 1
    else:
        print(f"   ❌ Class methods: No classes with methods found")
        tests_failed += 1
    
    # Test 6: Inheritance relationships
    print("\n6. Testing inheritance relationships...")
    result = graph.query("""
        MATCH (c:Class)-[:EXTENDS|IMPLEMENTS]->(parent)
        RETURN count(distinct c) as classes_with_inheritance
    """)
    
    if result and result[0]['classes_with_inheritance'] > 0:
        print(f"   ✅ Inheritance: {result[0]['classes_with_inheritance']} classes with inheritance")
        tests_passed += 1
    else:
        print(f"   ⚠️  Inheritance: No inheritance found (may be expected)")
    
    # Summary statistics
    print("\n" + "="*70)
    print("GRAPH STATISTICS")
    print("="*70)
    
    stats = {
        'Total Nodes': graph.query("MATCH (n) RETURN count(n) as c")[0]['c'],
        'Total Relationships': graph.query("MATCH ()-[r]->() RETURN count(r) as c")[0]['c'],
        'Directories': graph.query("MATCH (n:Directory) RETURN count(n) as c")[0]['c'],
        'Files': graph.query("MATCH (n:File) RETURN count(n) as c")[0]['c'],
        'Classes': graph.query("MATCH (n:Class) RETURN count(n) as c")[0]['c'],
        'Methods': graph.query("MATCH (n:Method) RETURN count(n) as c")[0]['c'],
        'CONTAINS relationships': graph.query("MATCH ()-[r:CONTAINS]->() RETURN count(r) as c")[0]['c'],
        'IN_DIRECTORY relationships': graph.query("MATCH ()-[r:IN_DIRECTORY]->() RETURN count(r) as c")[0]['c'],
        'DEFINED_IN relationships': graph.query("MATCH ()-[r:DEFINED_IN]->() RETURN count(r) as c")[0]['c'],
    }
    
    for key, value in stats.items():
        print(f"   {key}: {value:,}")
    
    # Sample graph visualization query
    print("\n" + "="*70)
    print("SAMPLE GRAPH QUERY (for Neo4j Browser)")
    print("="*70)
    print("""
    Run this in Neo4j Browser to visualize the connected graph:
    
    MATCH path = (dir:Directory {name: 'Controllers'})<-[:IN_DIRECTORY]-(f:File)<-[:DEFINED_IN]-(c:Class)-[:HAS_METHOD]->(m:Method)
    RETURN path
    LIMIT 25
    """)
    
    # Final result
    print("\n" + "="*70)
    if tests_failed == 0:
        print("✅ ALL GRAPH CONNECTIONS VERIFIED SUCCESSFULLY!")
    else:
        print(f"⚠️  {tests_passed} tests passed, {tests_failed} tests failed")
    print("="*70)
    
    return tests_failed == 0

if __name__ == "__main__":
    success = verify_graph_connections()
    sys.exit(0 if success else 1)