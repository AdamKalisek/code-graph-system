#!/usr/bin/env python3
"""
Test script to index a small batch of PHP files and verify relationships
"""
import sys
sys.path.append('.')

from pathlib import Path
from plugins.php.plugin import PHPLanguagePlugin
from code_graph_system.core.graph_store import FederatedGraphStore
import json

def test_small_batch():
    print("=" * 70)
    print("TESTING ENHANCED PARSER WITH SMALL BATCH")
    print("=" * 70)
    
    # Initialize graph store
    store = FederatedGraphStore(
        uri='bolt://localhost:7688',
        auth=('neo4j', 'password123')
    )
    print("✅ Connected to Neo4j")
    
    # Initialize PHP plugin
    php_plugin = PHPLanguagePlugin()
    print(f"✅ Using parser: {php_plugin.ast_parser.parser_script}")
    
    # Find a few PHP files to test
    base_path = Path('/home/david/Work/Programming/espocrm')
    test_files = [
        base_path / 'application/Espo/Core/Container.php',
        base_path / 'application/Espo/Core/InjectableFactory.php',
        base_path / 'application/Espo/Services/User.php'
    ]
    
    # Only use files that exist
    test_files = [f for f in test_files if f.exists()]
    print(f"\n📄 Testing with {len(test_files)} files:")
    for f in test_files:
        print(f"  - {f.name}")
    
    if not test_files:
        print("❌ No test files found!")
        return
    
    # Parse each file
    all_nodes = []
    all_relationships = []
    
    for file_path in test_files:
        print(f"\n🔍 Parsing {file_path.name}...")
        result = php_plugin.parse_file(str(file_path))
        
        if result.errors:
            print(f"  ⚠️ Errors: {result.errors}")
            continue
            
        print(f"  ✅ Found {len(result.nodes)} nodes, {len(result.relationships)} relationships")
        
        # Show relationship types
        rel_types = {}
        for rel in result.relationships:
            rel_type = rel.type
            rel_types[rel_type] = rel_types.get(rel_type, 0) + 1
        
        if rel_types:
            print("  📊 Relationship types:")
            for rel_type, count in sorted(rel_types.items()):
                print(f"     - {rel_type}: {count}")
        
        all_nodes.extend(result.nodes)
        all_relationships.extend(result.relationships)
    
    print(f"\n📈 Total: {len(all_nodes)} nodes, {len(all_relationships)} relationships")
    
    # Store in database
    if all_nodes:
        print("\n💾 Storing in Neo4j...")
        print(f"  Storing {len(all_nodes)} nodes, {len(all_relationships)} relationships")
        
        # Debug: Show what we're storing
        rel_summary = {}
        for rel in all_relationships:
            rel_summary[rel.type] = rel_summary.get(rel.type, 0) + 1
        print(f"  Relationship types to store: {rel_summary}")
        
        # Create placeholder nodes for unresolved targets
        node_ids = {node.id for node in all_nodes}
        placeholder_nodes = []
        
        for rel in all_relationships:
            if rel.target_id.startswith('unresolved_') and rel.target_id not in node_ids:
                # Create a placeholder symbol for unresolved reference
                from code_graph_system.core.schema import Symbol
                placeholder = Symbol(
                    name=rel.metadata.get('target_fqn', rel.target_id) if rel.metadata else rel.target_id,
                    qualified_name=rel.metadata.get('target_fqn', rel.target_id) if rel.metadata else rel.target_id,
                    kind='unresolved',
                    plugin_id='php'
                )
                placeholder.id = rel.target_id
                placeholder_nodes.append(placeholder)
                node_ids.add(rel.target_id)
        
        if placeholder_nodes:
            print(f"  Creating {len(placeholder_nodes)} placeholder nodes for unresolved references")
            all_nodes.extend(placeholder_nodes)
        
        store.store_batch(all_nodes, all_relationships)
        print("✅ Stored successfully")
    
    # Query database to verify
    print("\n🔍 Verifying in database...")
    
    # Check node counts
    result = store.query("""
        MATCH (n)
        WITH labels(n) as nodeLabels, count(n) as nodeCount
        RETURN nodeLabels, nodeCount
        ORDER BY nodeCount DESC
    """)
    
    print("\n📊 Node types in database:")
    for record in result:
        print(f"  - {record['nodeLabels']}: {record['nodeCount']}")
    
    # Check relationship counts
    result = store.query("""
        MATCH ()-[r]->()
        RETURN type(r) as relType, count(r) as relCount
        ORDER BY relCount DESC
    """)
    
    print("\n🔗 Relationship types in database:")
    for record in result:
        print(f"  - {record['relType']}: {record['relCount']}")
    
    # Check for our new relationship types
    new_rel_types = ['CALLS', 'IMPORTS', 'ACCESSES', 'THROWS', 'INSTANTIATES']
    result = store.query(f"""
        MATCH ()-[r]->()
        WHERE type(r) IN {new_rel_types}
        RETURN type(r) as relType, count(r) as relCount
    """)
    
    print("\n✨ Enhanced relationships found:")
    found_any = False
    for record in result:
        print(f"  ✅ {record['relType']}: {record['relCount']}")
        found_any = True
    
    if not found_any:
        print("  ❌ No enhanced relationships found!")
        print("  ⚠️ Check that ast_parser_enhanced.php is being used")
    else:
        print("\n🎯 SUCCESS! Enhanced parser is working correctly!")

if __name__ == '__main__':
    test_small_batch()