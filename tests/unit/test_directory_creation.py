#!/usr/bin/env python3
"""
Unit Test: Directory Hierarchy Creation
Tests the fixed directory creation logic
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pathlib import Path
from code_graph_system.core.graph_store import FederatedGraphStore
from code_graph_system.core.schema import Symbol, Relationship

class DirectoryHierarchyBuilder:
    """Fixed implementation of directory hierarchy creation"""
    
    def __init__(self, graph):
        self.graph = graph
        self.directory_nodes = {}  # path -> node mapping
        
    def create_directory_hierarchy(self, file_paths):
        """
        Create directory hierarchy with proper CONTAINS relationships.
        Returns (nodes, relationships)
        """
        # Collect all unique directories
        all_dirs = set()
        for file_path in file_paths:
            current = Path(file_path).parent
            while current != current.parent and str(current) != '.':
                all_dirs.add(current)
                current = current.parent
        
        # Sort by depth (parents first)
        sorted_dirs = sorted(all_dirs, key=lambda p: len(p.parts))
        
        nodes = []
        relationships = []
        
        # Create all directory nodes first
        for dir_path in sorted_dirs:
            dir_node = Symbol(
                name=dir_path.name,
                qualified_name=str(dir_path),
                kind='directory',
                plugin_id='filesystem'
            )
            nodes.append(dir_node)
            self.directory_nodes[str(dir_path)] = dir_node
        
        # Create CONTAINS relationships using actual node IDs
        for dir_path in sorted_dirs:
            if dir_path.parent != dir_path and str(dir_path.parent) in self.directory_nodes:
                parent_node = self.directory_nodes[str(dir_path.parent)]
                child_node = self.directory_nodes[str(dir_path)]
                
                relationships.append(Relationship(
                    source_id=parent_node.id,
                    target_id=child_node.id,
                    type='CONTAINS'
                ))
        
        return nodes, relationships
    
    def get_file_directory_relationships(self, file_paths):
        """
        Create IN_DIRECTORY relationships for files.
        Returns list of relationships.
        """
        relationships = []
        
        for file_path in file_paths:
            file_node = Symbol(
                name=Path(file_path).name,
                qualified_name=str(file_path),
                kind='file',
                plugin_id='filesystem'
            )
            
            parent_dir = str(Path(file_path).parent)
            if parent_dir in self.directory_nodes:
                dir_node = self.directory_nodes[parent_dir]
                relationships.append(Relationship(
                    source_id=file_node.id,
                    target_id=dir_node.id,
                    type='IN_DIRECTORY'
                ))
        
        return relationships


def test_directory_hierarchy():
    """Test directory hierarchy creation"""
    print("\n" + "="*60)
    print("UNIT TEST: Directory Hierarchy Creation")
    print("="*60)
    
    # Connect to Neo4j
    print("\n1. Setting up test...")
    graph = FederatedGraphStore(
        'bolt://localhost:7688',
        ('neo4j', 'password123'),
        {'federation': {'mode': 'unified'}}
    )
    
    # Clear test data
    graph.graph.run("MATCH (n {metadata_test: 'DirTest'}) DETACH DELETE n")
    
    # Test file paths
    test_files = [
        "espocrm/application/Espo/Controllers/User.php",
        "espocrm/application/Espo/Controllers/Lead.php",
        "espocrm/application/Espo/Services/User.php",
        "espocrm/client/src/views/user/list.js",
        "espocrm/client/src/views/user/detail.js",
        "espocrm/client/src/models/user.js",
    ]
    
    # Create hierarchy
    print("\n2. Creating directory hierarchy...")
    builder = DirectoryHierarchyBuilder(graph)
    dir_nodes, dir_rels = builder.create_directory_hierarchy(test_files)
    
    print(f"   Created {len(dir_nodes)} directory nodes")
    print(f"   Created {len(dir_rels)} CONTAINS relationships")
    
    # Expected directories
    expected_dirs = {
        "espocrm",
        "espocrm/application",
        "espocrm/application/Espo",
        "espocrm/application/Espo/Controllers",
        "espocrm/application/Espo/Services",
        "espocrm/client",
        "espocrm/client/src",
        "espocrm/client/src/views",
        "espocrm/client/src/views/user",
        "espocrm/client/src/models",
    }
    
    # Verify all directories created
    print("\n3. Verifying directories...")
    created_dirs = {node.qualified_name for node in dir_nodes}
    missing = expected_dirs - created_dirs
    extra = created_dirs - expected_dirs
    
    if missing:
        print(f"   ❌ Missing directories: {missing}")
    if extra:
        print(f"   ⚠️ Extra directories: {extra}")
    if not missing and not extra:
        print(f"   ✅ All {len(expected_dirs)} directories created correctly")
    
    # Verify relationships
    print("\n4. Verifying CONTAINS relationships...")
    
    # Test specific paths
    test_paths = [
        ("espocrm", "espocrm/application"),
        ("espocrm/application", "espocrm/application/Espo"),
        ("espocrm/application/Espo", "espocrm/application/Espo/Controllers"),
        ("espocrm/client/src/views", "espocrm/client/src/views/user"),
    ]
    
    relationships_ok = True
    for parent_path, child_path in test_paths:
        rel_found = False
        for rel in dir_rels:
            parent_node = builder.directory_nodes.get(parent_path)
            child_node = builder.directory_nodes.get(child_path)
            if parent_node and child_node:
                if rel.source_id == parent_node.id and rel.target_id == child_node.id:
                    rel_found = True
                    break
        
        if rel_found:
            print(f"   ✅ {parent_path} -> {child_path}")
        else:
            print(f"   ❌ Missing: {parent_path} -> {child_path}")
            relationships_ok = False
    
    # Test file-to-directory relationships
    print("\n5. Testing file-to-directory relationships...")
    file_rels = builder.get_file_directory_relationships(test_files)
    print(f"   Created {len(file_rels)} IN_DIRECTORY relationships")
    
    if len(file_rels) == len(test_files):
        print(f"   ✅ All files linked to directories")
    else:
        print(f"   ❌ Expected {len(test_files)} relationships, got {len(file_rels)}")
    
    # Store in database and verify
    print("\n6. Storing in database...")
    
    # Add test metadata to nodes
    for node in dir_nodes:
        node.metadata = {"test": "DirTest"}
    
    nodes_stored, rels_stored = graph.store_batch(dir_nodes, dir_rels)
    print(f"   Stored {nodes_stored} nodes, {rels_stored} relationships")
    
    # Query database to verify
    print("\n7. Verifying in database...")
    
    # Check path traversal
    db_path = graph.query("""
        MATCH path = (root:Directory {name: 'espocrm'})-[:CONTAINS*]->(leaf:Directory {name: 'Controllers'})
        WHERE root.metadata_test = 'DirTest'
        RETURN length(path) as depth
    """)
    
    if db_path and db_path[0]['depth'] == 3:
        print(f"   ✅ Database path traversal works (depth: {db_path[0]['depth']})")
    else:
        print(f"   ❌ Database path traversal failed")
    
    # Cleanup
    graph.graph.run("MATCH (n {metadata_test: 'DirTest'}) DETACH DELETE n")
    
    # Results
    print("\n" + "="*60)
    success = (
        len(dir_nodes) == len(expected_dirs) and
        relationships_ok and
        len(file_rels) == len(test_files)
    )
    
    if success:
        print("✅ Directory hierarchy implementation is CORRECT!")
    else:
        print("❌ Directory hierarchy has issues")
    
    return success, builder


if __name__ == "__main__":
    success, builder = test_directory_hierarchy()
    
    if success:
        print("\n📝 Fixed implementation ready to integrate into indexer")
    
    sys.exit(0 if success else 1)