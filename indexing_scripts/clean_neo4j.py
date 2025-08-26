#!/usr/bin/env python3
"""
Clean all data from Neo4j database
Provides a fresh start for indexing
"""

import sys
sys.path.append('.')

from code_graph_system.core.graph_store import FederatedGraphStore

def clean_database():
    """Remove all nodes and relationships from Neo4j"""
    print("=" * 70)
    print("  NEO4J DATABASE CLEANUP")
    print("=" * 70)
    
    try:
        # Connect to Neo4j
        print("🔌 Connecting to Neo4j...")
        graph = FederatedGraphStore(
            'bolt://localhost:7688',
            ('neo4j', 'password123'),
            {'federation': {'mode': 'unified'}}
        )
        
        # Count existing data
        print("\n📊 Current database state:")
        node_count = graph.query("MATCH (n) RETURN count(n) as count")[0]['count']
        rel_count = graph.query("MATCH ()-[r]->() RETURN count(r) as count")[0]['count']
        print(f"   Nodes: {node_count:,}")
        print(f"   Relationships: {rel_count:,}")
        
        if node_count == 0 and rel_count == 0:
            print("\n✅ Database is already empty!")
            return
        
        # Clean everything
        print("\n🧹 Cleaning database...")
        graph.graph.run("MATCH (n) DETACH DELETE n")
        
        # Verify cleanup
        print("\n✅ Database cleaned!")
        node_count = graph.query("MATCH (n) RETURN count(n) as count")[0]['count']
        rel_count = graph.query("MATCH ()-[r]->() RETURN count(r) as count")[0]['count']
        print(f"   Nodes: {node_count}")
        print(f"   Relationships: {rel_count}")
        
        print("\n🎯 Ready for fresh indexing!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure Neo4j is running:")
        print("  ./run_neo4j.sh")
        sys.exit(1)

if __name__ == '__main__':
    clean_database()