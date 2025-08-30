#!/usr/bin/env python3
"""
Test 1.1: Basic Neo4j Operations
Testing node and relationship creation with dummy data
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from code_graph_system.core.graph_store import FederatedGraphStore
from code_graph_system.core.schema import Symbol, Relationship

def test_basic_operations():
    """Test basic node and relationship creation"""
    print("\n" + "="*60)
    print("TEST 1.1: Basic Neo4j Operations")
    print("="*60)
    
    # Connect to Neo4j
    print("\n1. Connecting to Neo4j...")
    graph = FederatedGraphStore(
        'bolt://localhost:7688',
        ('neo4j', 'password123'),
        {'federation': {'mode': 'unified'}}
    )
    
    # Clear test data
    print("2. Clearing test nodes...")
    graph.graph.run("MATCH (n {metadata_test_type: 'TestNode'}) DETACH DELETE n")
    
    # Create test nodes
    print("\n3. Creating test nodes...")
    nodes = [
        Symbol(
            name="TestClass1",
            qualified_name="test.TestClass1",
            kind="class",
            plugin_id="test",
            metadata={"test_type": "TestNode"}  # Use metadata for test identification
        ),
        Symbol(
            name="TestClass2", 
            qualified_name="test.TestClass2",
            kind="class",
            plugin_id="test",
            metadata={"test_type": "TestNode"}
        ),
        Symbol(
            name="TestMethod1",
            qualified_name="test.TestClass1.TestMethod1",
            kind="method",
            plugin_id="test",
            metadata={"test_type": "TestNode"}
        )
    ]
    
    # Create test relationships
    print("4. Creating test relationships...")
    relationships = [
        Relationship(
            source_id=nodes[0].id,  # TestClass1
            target_id=nodes[1].id,  # TestClass2
            type="TEST_EXTENDS"
        ),
        Relationship(
            source_id=nodes[0].id,  # TestClass1
            target_id=nodes[2].id,  # TestMethod1
            type="TEST_HAS_METHOD"
        )
    ]
    
    # Store using store_batch
    print("\n5. Storing nodes and relationships...")
    nodes_created, rels_created = graph.store_batch(nodes, relationships, 'test')
    print(f"   Nodes created: {nodes_created}")
    print(f"   Relationships created: {rels_created}")
    
    # Verify nodes
    print("\n6. Verifying nodes...")
    node_count = graph.query("MATCH (n:Symbol {metadata_test_type: 'TestNode'}) RETURN count(n) as count")[0]['count']
    print(f"   TestNodes in database: {node_count}")
    
    # Verify relationships
    print("\n7. Verifying relationships...")
    rel_extends = graph.query("MATCH ()-[r:TEST_EXTENDS]->() RETURN count(r) as count")[0]['count']
    rel_has_method = graph.query("MATCH ()-[r:TEST_HAS_METHOD]->() RETURN count(r) as count")[0]['count']
    print(f"   TEST_EXTENDS relationships: {rel_extends}")
    print(f"   TEST_HAS_METHOD relationships: {rel_has_method}")
    
    # Check connectivity
    print("\n8. Checking connectivity...")
    connected = graph.query("""
        MATCH (c1:Symbol {name: 'TestClass1', metadata_test_type: 'TestNode'})-[:TEST_EXTENDS]->(c2:Symbol {name: 'TestClass2', metadata_test_type: 'TestNode'})
        RETURN c1.name as source, c2.name as target
    """)
    if connected:
        print(f"   ✓ {connected[0]['source']} -> {connected[0]['target']}")
    else:
        print("   ✗ No connection found!")
    
    # Results
    print("\n" + "="*60)
    print("RESULTS:")
    if node_count == 3 and rel_extends == 1 and rel_has_method == 1:
        print("✅ SUCCESS: Nodes and relationships created correctly!")
    else:
        print("❌ FAILURE: Missing nodes or relationships!")
        print(f"   Expected: 3 nodes, 1 extends, 1 has_method")
        print(f"   Got: {node_count} nodes, {rel_extends} extends, {rel_has_method} has_method")
    
    # Cleanup
    print("\n9. Cleaning up test data...")
    graph.graph.run("MATCH (n {metadata_test_type: 'TestNode'}) DETACH DELETE n")
    
    return node_count == 3 and rel_extends == 1 and rel_has_method == 1

if __name__ == "__main__":
    success = test_basic_operations()
    sys.exit(0 if success else 1)