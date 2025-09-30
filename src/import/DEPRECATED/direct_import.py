#!/usr/bin/env python3
"""Direct Neo4j import - simple and fast"""

import sys
from neo4j import GraphDatabase
import time

def import_cypher_file(file_path, uri="bolt://localhost:7688", user="neo4j", password="password123"):
    """Import Cypher file directly to Neo4j"""
    
    driver = GraphDatabase.driver(uri, auth=(user, password))
    
    print(f"📖 Reading {file_path}...")
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    nodes = []
    relationships = []
    
    for line in lines:
        line = line.strip()
        if line.startswith('CREATE (n:'):
            nodes.append(line)
        elif line.startswith('MATCH'):
            relationships.append(line)
    
    print(f"📊 Found {len(nodes)} nodes and {len(relationships)} relationships")
    
    with driver.session() as session:
        # Clear database
        print("🗑️ Clearing database...")
        session.run("MATCH (n) DETACH DELETE n")
        
        # Import nodes in batches
        print(f"📦 Importing {len(nodes)} nodes...")
        batch_size = 500
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i+batch_size]
            for stmt in batch:
                try:
                    session.run(stmt)
                except Exception as e:
                    print(f"Error on node: {e}")
            
            if i % 5000 == 0:
                print(f"  Progress: {i}/{len(nodes)}")
        
        print(f"✅ Imported {len(nodes)} nodes")
        
        # Import relationships in batches
        print(f"🔗 Importing {len(relationships)} relationships...")
        for i in range(0, len(relationships), batch_size):
            batch = relationships[i:i+batch_size]
            for stmt in batch:
                try:
                    session.run(stmt)
                except:
                    pass  # Some relationships might fail if nodes don't exist
            
            if i % 5000 == 0:
                print(f"  Progress: {i}/{len(relationships)}")
        
        print(f"✅ Import complete!")
        
        # Verify
        result = session.run("MATCH (n) RETURN COUNT(n) as nodes")
        node_count = result.single()['nodes']
        
        result = session.run("MATCH ()-[r]->() RETURN COUNT(r) as rels")
        rel_count = result.single()['rels']
        
        print(f"\n📊 Final Statistics:")
        print(f"  Nodes: {node_count:,}")
        print(f"  Relationships: {rel_count:,}")
    
    driver.close()

if __name__ == "__main__":
    file_path = sys.argv[1] if len(sys.argv) > 1 else "espocrm_complete.cypher"
    import_cypher_file(file_path)