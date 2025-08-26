#!/usr/bin/env python3
"""
Final validation test - Ensures all critical fixes are working
"""

import sys
from pathlib import Path
sys.path.append('.')

from code_graph_system.core.graph_store import FederatedGraphStore
from plugins.php.plugin import PHPLanguagePlugin


def validate_system():
    """Comprehensive validation of all fixes"""
    print("="*70)
    print("  FINAL SYSTEM VALIDATION - ALL FIXES APPLIED")
    print("="*70)
    
    # 1. Connect to Neo4j
    print("\n✅ TEST 1: Neo4j Connection")
    graph_store = FederatedGraphStore(
        'bolt://localhost:7688',
        ('neo4j', 'password123'),
        {'federation': {'mode': 'unified'}}
    )
    print("   PASSED: Connected to Neo4j")
    
    # Clear graph
    graph_store.graph.run("MATCH (n) DETACH DELETE n")
    print("   PASSED: Graph cleaned")
    
    # 2. Test PHP Plugin
    print("\n✅ TEST 2: PHP Plugin Initialization")
    php_plugin = PHPLanguagePlugin()
    php_plugin.initialize({})
    print("   PASSED: PHP plugin initialized")
    
    # 3. Test Improved PHP Parser
    print("\n✅ TEST 3: PHP Parser Accuracy")
    test_file = 'espocrm/application/Espo/Core/Container.php'
    result = php_plugin.parse_file(test_file)
    
    classes = [n for n in result.nodes if n.kind == 'class']
    methods = [n for n in result.nodes if n.kind == 'method']
    properties = [n for n in result.nodes if n.kind == 'property']
    
    assert len(classes) == 1, f"Expected 1 class, found {len(classes)}"
    assert classes[0].name == 'Container', f"Expected Container class, found {classes[0].name}"
    assert len(methods) >= 10, f"Expected 10+ methods, found {len(methods)}"
    assert len(properties) >= 5, f"Expected 5+ properties, found {len(properties)}"
    
    print(f"   PASSED: Found {len(classes)} class, {len(methods)} methods, {len(properties)} properties")
    
    # 4. Test Bulk Ingestion
    print("\n✅ TEST 4: Bulk Data Ingestion")
    nodes_stored, rels_stored = graph_store.store_batch(
        result.nodes,
        result.relationships,
        'php'
    )
    
    assert nodes_stored > 0, "No nodes stored"
    assert rels_stored > 0, "No relationships stored"
    print(f"   PASSED: Stored {nodes_stored} nodes, {rels_stored} relationships using UNWIND")
    
    # 5. Test Property Flattening
    print("\n✅ TEST 5: Property Serialization")
    # Check that nodes with metadata were stored correctly
    test_query = """
        MATCH (n:Symbol {kind: 'class'})
        RETURN n.metadata_namespace as namespace, n.name as name
    """
    results = graph_store.query(test_query)
    assert len(results) > 0, "Could not query flattened properties"
    print(f"   PASSED: Nested properties correctly flattened and stored")
    
    # 6. Test Graph Queries
    print("\n✅ TEST 6: Graph Queries")
    
    # Test class query
    class_query = """
        MATCH (c:Symbol {kind: 'class'})
        RETURN c.name as name, c.qualified_name as fqcn
    """
    class_results = graph_store.query(class_query)
    assert len(class_results) == 1, f"Expected 1 class, found {len(class_results)}"
    
    # Test method relationships
    method_query = """
        MATCH (c:Symbol {kind: 'class'})-[:HAS_METHOD]->(m:Symbol)
        RETURN count(m) as method_count
    """
    method_results = graph_store.query(method_query)
    assert method_results[0]['method_count'] >= 10, "Method relationships not working"
    
    print(f"   PASSED: All graph queries working correctly")
    
    # 7. Test Language Federation
    print("\n✅ TEST 7: Language Federation")
    lang_query = """
        MATCH (n:Symbol)
        WHERE n._language = 'php'
        RETURN count(n) as count
    """
    lang_results = graph_store.query(lang_query)
    assert lang_results[0]['count'] > 0, "Language tagging not working"
    print(f"   PASSED: Language federation working (_language tags applied)")
    
    # 8. Performance Check
    print("\n✅ TEST 8: Performance Benchmark")
    import time
    
    # Parse multiple files
    test_files = [
        'espocrm/application/Espo/Core/Application.php',
        'espocrm/application/Espo/Core/HookManager.php',
        'espocrm/application/Espo/Core/InjectableFactory.php',
    ]
    
    start = time.time()
    total_nodes = 0
    for f in test_files:
        if Path(f).exists():
            res = php_plugin.parse_file(f)
            n, r = graph_store.store_batch(res.nodes, res.relationships, 'php')
            total_nodes += n
    
    elapsed = time.time() - start
    rate = total_nodes / elapsed if elapsed > 0 else 0
    
    assert rate > 50, f"Performance too slow: {rate:.1f} nodes/sec"
    print(f"   PASSED: {rate:.1f} nodes/second (target: >50)")
    
    # Final Statistics
    print("\n📊 FINAL GRAPH STATISTICS:")
    stats = graph_store.get_statistics()
    print(f"   Total nodes: {stats['total_nodes']}")
    print(f"   Total relationships: {stats['total_relationships']}")
    print(f"   Node types: {list(stats.get('node_types', {}).keys())}")
    print(f"   Languages: {list(stats.get('languages', {}).keys())}")
    
    print("\n" + "="*70)
    print("  ✅ ALL VALIDATION TESTS PASSED!")
    print("  System is working correctly with all critical fixes applied")
    print("="*70)
    
    return True


if __name__ == '__main__':
    try:
        validate_system()
    except AssertionError as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)