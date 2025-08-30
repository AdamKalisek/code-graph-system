#!/usr/bin/env python3
"""
Test 1.2: Directory Hierarchy
Testing directory structure with CONTAINS relationships
This is CRITICAL - the main issue in our indexing!
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pathlib import Path
from code_graph_system.core.graph_store import FederatedGraphStore
from code_graph_system.core.schema import Symbol, Relationship

def test_directory_hierarchy():
    """Test directory hierarchy creation with CONTAINS relationships"""
    print("\n" + "="*60)
    print("TEST 1.2: Directory Hierarchy")
    print("="*60)
    
    # Connect to Neo4j
    print("\n1. Connecting to Neo4j...")
    graph = FederatedGraphStore(
        'bolt://localhost:7688',
        ('neo4j', 'password123'),
        {'federation': {'mode': 'unified'}}
    )
    
    # Clear test data
    print("2. Clearing test directories...")
    graph.graph.run("MATCH (n:Directory {metadata_test: 'TestDir'}) DETACH DELETE n")
    
    # Create directory structure: project/src/components/Button.js
    print("\n3. Creating directory nodes...")
    directories = [
        Symbol(
            name="project",
            qualified_name="project",
            kind="directory",
            plugin_id="filesystem",
            metadata={"test": "TestDir"}
        ),
        Symbol(
            name="src",
            qualified_name="project/src",
            kind="directory",
            plugin_id="filesystem",
            metadata={"test": "TestDir"}
        ),
        Symbol(
            name="components",
            qualified_name="project/src/components",
            kind="directory",
            plugin_id="filesystem",
            metadata={"test": "TestDir"}
        )
    ]
    
    # Create CONTAINS relationships (parent -> child)
    print("4. Creating CONTAINS relationships...")
    relationships = [
        Relationship(
            source_id=directories[0].id,  # project
            target_id=directories[1].id,  # src
            type="CONTAINS"
        ),
        Relationship(
            source_id=directories[1].id,  # src
            target_id=directories[2].id,  # components
            type="CONTAINS"
        )
    ]
    
    # Store using store_batch
    print("\n5. Storing directories and relationships...")
    nodes_created, rels_created = graph.store_batch(directories, relationships, 'filesystem')
    print(f"   Directories created: {nodes_created}")
    print(f"   CONTAINS relationships created: {rels_created}")
    
    # Verify directories
    print("\n6. Verifying directories...")
    dir_count = graph.query("MATCH (n:Directory {metadata_test: 'TestDir'}) RETURN count(n) as count")[0]['count']
    print(f"   Directories in database: {dir_count}")
    
    # Verify CONTAINS relationships
    print("\n7. Verifying CONTAINS relationships...")
    contains_count = graph.query("MATCH ()-[r:CONTAINS]->() RETURN count(r) as count")[0]['count']
    print(f"   CONTAINS relationships: {contains_count}")
    
    # Check hierarchy
    print("\n8. Checking directory hierarchy...")
    hierarchy = graph.query("""
        MATCH path = (root:Directory {name: 'project'})-[:CONTAINS*]->(leaf:Directory {name: 'components'})
        WHERE root.metadata_test = 'TestDir'
        RETURN length(path) as depth, 
               [n IN nodes(path) | n.name] as path_names
    """)
    
    if hierarchy:
        print(f"   ✓ Hierarchy depth: {hierarchy[0]['depth']}")
        print(f"   ✓ Path: {' -> '.join(hierarchy[0]['path_names'])}")
    else:
        print("   ✗ No hierarchy found!")
    
    # Test path traversal
    print("\n9. Testing path traversal...")
    children = graph.query("""
        MATCH (parent:Directory {name: 'src', metadata_test: 'TestDir'})-[:CONTAINS]->(child)
        RETURN child.name as name
    """)
    if children:
        print(f"   ✓ Children of 'src': {[c['name'] for c in children]}")
    else:
        print("   ✗ No children found for 'src'")
    
    # Results
    print("\n" + "="*60)
    print("RESULTS:")
    success = (dir_count == 3 and 
               contains_count >= 2 and  # May have more from other tests
               hierarchy and 
               hierarchy[0]['depth'] == 2)
    
    if success:
        print("✅ SUCCESS: Directory hierarchy created correctly!")
    else:
        print("❌ FAILURE: Directory hierarchy not working!")
        print(f"   Expected: 3 directories, 2 CONTAINS relationships, depth 2")
        print(f"   Got: {dir_count} directories, {contains_count} CONTAINS, depth {hierarchy[0]['depth'] if hierarchy else 0}")
    
    # Cleanup
    print("\n10. Cleaning up test data...")
    graph.graph.run("MATCH (n:Directory {metadata_test: 'TestDir'}) DETACH DELETE n")
    
    return success

if __name__ == "__main__":
    success = test_directory_hierarchy()
    sys.exit(0 if success else 1)