#!/usr/bin/env python3
"""
Test script for the Universal Code Graph System
"""

import sys
from pathlib import Path
sys.path.append('.')

from code_graph_system.core.graph_store import FederatedGraphStore
from plugins.php.plugin import PHPLanguagePlugin


def main():
    print("Universal Code Graph System - Test Script")
    print("=" * 50)
    
    # Initialize components
    print("\n1. Initializing components...")
    
    # Connect to Neo4j
    graph_store = FederatedGraphStore(
        'bolt://localhost:7688',
        ('neo4j', 'password123'),
        {'federation': {'mode': 'unified'}}
    )
    print("   ✓ Connected to Neo4j")
    
    # Initialize PHP plugin
    php_plugin = PHPLanguagePlugin()
    php_plugin.initialize({})
    print("   ✓ PHP plugin initialized")
    
    # Parse sample files
    print("\n2. Parsing EspoCRM files...")
    
    test_files = [
        'espocrm/application/Espo/Core/Container.php',
        'espocrm/application/Espo/Core/Application.php',
        'espocrm/application/Espo/Core/HookManager.php',
    ]
    
    total_nodes = 0
    total_relationships = 0
    
    for file_path in test_files:
        if Path(file_path).exists():
            print(f"   Parsing {file_path}...")
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
    
    print(f"\n   Total: {total_nodes} nodes, {total_relationships} relationships")
    
    # Query the graph
    print("\n3. Running sample queries...")
    
    # Query 1: List all classes
    print("\n   Query: List all PHP classes")
    results = graph_store.query("""
        MATCH (c:Symbol {kind: 'class'})
        RETURN c.name as class_name, c.qualified_name as fqcn
        ORDER BY c.name
    """)
    
    for result in results[:5]:  # Show first 5
        print(f"     - {result['class_name']} ({result['fqcn']})")
    
    # Query 2: Find relationships
    print("\n   Query: Find class relationships")
    results = graph_store.query("""
        MATCH (c:Symbol)-[r]->(t:Symbol)
        RETURN c.name as from, type(r) as relationship, t.name as to
        LIMIT 5
    """)
    
    for result in results:
        print(f"     - {result['from']} --{result['relationship']}--> {result['to']}")
    
    # Get statistics
    print("\n4. Graph statistics:")
    stats = graph_store.get_statistics()
    
    print(f"   Total nodes: {stats['total_nodes']}")
    print(f"   Total relationships: {stats['total_relationships']}")
    
    if stats.get('node_types'):
        print("\n   Node types:")
        for node_type, count in stats['node_types'].items():
            print(f"     - {node_type}: {count}")
    
    print("\n✓ Test complete!")
    

if __name__ == '__main__':
    main()