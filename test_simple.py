#!/usr/bin/env python3
"""
Simple test script for the Universal Code Graph System
"""

import sys
from pathlib import Path
sys.path.append('.')

from code_graph_system.core.graph_store import FederatedGraphStore
from plugins.php.plugin import PHPLanguagePlugin


def main():
    print("Universal Code Graph System - Simple Test")
    print("=" * 50)
    
    # 1. Connect to Neo4j
    print("\n1. Connecting to Neo4j...")
    graph_store = FederatedGraphStore(
        'bolt://localhost:7688',
        ('neo4j', 'password123'),
        {'federation': {'mode': 'unified'}}
    )
    print("   ✓ Connected to Neo4j")
    
    # Clear existing data
    graph_store.graph.run("MATCH (n) DETACH DELETE n")
    print("   ✓ Cleared existing data")
    
    # 2. Initialize PHP plugin
    print("\n2. Initializing PHP plugin...")
    php_plugin = PHPLanguagePlugin()
    php_plugin.initialize({})
    print("   ✓ PHP plugin initialized")
    
    # 3. Parse EspoCRM files
    print("\n3. Parsing PHP files...")
    
    test_files = [
        'espocrm/application/Espo/Core/Container.php',
        'espocrm/application/Espo/Core/Application.php',
        'espocrm/application/Espo/Core/HookManager.php',
    ]
    
    total_nodes = 0
    total_relationships = 0
    
    for file_path in test_files:
        if Path(file_path).exists():
            print(f"\n   Parsing {file_path}...")
            result = php_plugin.parse_file(file_path)
            
            # Store in graph
            n, r = graph_store.store_batch(
                result.nodes,
                result.relationships,
                'php'
            )
            
            total_nodes += n
            total_relationships += r
            
            print(f"     → {n} nodes, {r} relationships")
            
            # Show some parsed elements
            classes = [node for node in result.nodes if hasattr(node, 'kind') and node.kind == 'class']
            methods = [node for node in result.nodes if hasattr(node, 'kind') and node.kind == 'method']
            
            if classes:
                print(f"     → Classes found: {', '.join([c.name for c in classes[:3]])}")
            if methods:
                print(f"     → Methods found: {len(methods)}")
    
    print(f"\n   Total: {total_nodes} nodes, {total_relationships} relationships")
    
    # 4. Query the graph
    print("\n4. Querying the graph...")
    
    # Query 1: List all classes
    print("\n   Query: All PHP classes")
    results = graph_store.query("""
        MATCH (c:Symbol {kind: 'class'})
        RETURN c.name as class_name, c.qualified_name as fqcn
        ORDER BY c.name
        LIMIT 5
    """)
    
    if results:
        for result in results:
            print(f"     - {result['class_name']} ({result['fqcn']})")
    else:
        print("     No classes found")
    
    # Query 2: Count node types
    print("\n   Query: Node type distribution")
    results = graph_store.query("""
        MATCH (n)
        RETURN labels(n)[0] as type, count(n) as count
        ORDER BY count DESC
    """)
    
    for result in results[:5]:
        print(f"     - {result['type']}: {result['count']}")
    
    # Query 3: Find relationships
    print("\n   Query: Relationships")
    results = graph_store.query("""
        MATCH (s)-[r]->(t)
        RETURN type(r) as relationship, count(r) as count
        ORDER BY count DESC
        LIMIT 5
    """)
    
    for result in results:
        print(f"     - {result['relationship']}: {result['count']}")
    
    # 5. Test impact analysis
    print("\n5. Impact analysis...")
    
    # Find Container class
    results = graph_store.query("""
        MATCH (c:Symbol {name: 'Container', kind: 'class'})
        RETURN c.id as id, c.name as name, c.qualified_name as fqcn
        LIMIT 1
    """)
    
    if results:
        container_id = results[0]['id']
        print(f"   Found Container class: {results[0]['fqcn']}")
        
        # Find methods in Container
        results = graph_store.query("""
            MATCH (c:Symbol {id: $id})-[:DEFINES_METHOD]->(m:Symbol)
            RETURN m.name as method_name
            LIMIT 10
        """, {'id': container_id})
        
        if results:
            print(f"   Container methods: {', '.join([r['method_name'] for r in results[:5]])}")
    
    # 6. Get statistics
    print("\n6. Graph statistics:")
    stats = graph_store.get_statistics()
    
    print(f"   Total nodes: {stats['total_nodes']}")
    print(f"   Total relationships: {stats['total_relationships']}")
    
    if stats.get('node_types'):
        print("\n   Node types:")
        for node_type, count in list(stats['node_types'].items())[:5]:
            print(f"     - {node_type}: {count}")
    
    print("\n✓ Test complete!")


if __name__ == '__main__':
    main()