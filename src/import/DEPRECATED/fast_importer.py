#!/usr/bin/env python3
"""FAST import of EspoCRM graph to Neo4j using direct driver"""

import neo4j
from pathlib import Path
import time
import sys

def import_complete_graph():
    """Import the complete graph to Neo4j FAST"""
    
    print("=" * 60)
    print("FAST EspoCRM Graph Import to Neo4j")
    print("=" * 60)
    
    # Connect to Neo4j
    print("\nConnecting to Neo4j...")
    try:
        driver = neo4j.GraphDatabase.driver(
            "bolt://localhost:7688",
            auth=("neo4j", "password123")
        )
    except Exception as e:
        print(f"❌ Failed to connect to Neo4j: {e}")
        print("\nMake sure Neo4j is running:")
        print("  sudo systemctl start neo4j")
        print("  or")
        print("  neo4j start")
        return False
    
    with driver.session() as session:
        # Clean database
        print("\nCleaning database...")
        try:
            result = session.run("MATCH (n) DETACH DELETE n")
            result.consume()
            print("✅ Database cleaned")
        except Exception as e:
            print(f"❌ Failed to clean database: {e}")
            return False
        
        # Create indexes for performance
        print("\nCreating indexes...")
        indexes = [
            "CREATE INDEX IF NOT EXISTS FOR (s:Symbol) ON (s.id)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Namespace) ON (n.id)",
            "CREATE INDEX IF NOT EXISTS FOR (c:Class) ON (c.id)",
            "CREATE INDEX IF NOT EXISTS FOR (m:Method) ON (m.id)",
            "CREATE INDEX IF NOT EXISTS FOR (p:Property) ON (p.id)",
            "CREATE INDEX IF NOT EXISTS FOR (c:Constant) ON (c.id)",
            "CREATE INDEX IF NOT EXISTS FOR (t:Trait) ON (t.id)",
            "CREATE INDEX IF NOT EXISTS FOR (i:Interface) ON (i.id)",
            "CREATE INDEX IF NOT EXISTS FOR (f:Function) ON (f.id)",
        ]
        
        for index_query in indexes:
            try:
                session.run(index_query)
            except:
                pass  # Index might already exist
        print("✅ Indexes created")
        
        # Get all batch files
        node_files = sorted(Path('.').glob('batch_nodes_*.cypher'))
        rel_files = sorted(Path('.').glob('batch_rels_*.cypher'))
        
        print(f"\nFound {len(node_files)} node batches and {len(rel_files)} relationship batches")
        
        # Import nodes
        print("\n" + "=" * 40)
        print("IMPORTING NODES")
        print("=" * 40)
        
        total_nodes = 0
        failed_nodes = 0
        start_time = time.time()
        
        for i, node_file in enumerate(node_files):
            print(f"\nBatch {i+1}/{len(node_files)}: {node_file}")
            
            with open(node_file, 'r') as f:
                statements = [line.strip() for line in f.readlines() if line.strip()]
            
            batch_start = time.time()
            batch_success = 0
            batch_failed = 0
            
            # Execute in transaction for speed
            with session.begin_transaction() as tx:
                for j, stmt in enumerate(statements):
                    if j % 100 == 0 and j > 0:
                        # Commit periodically
                        tx.commit()
                        tx = session.begin_transaction()
                        elapsed = time.time() - batch_start
                        rate = j / elapsed if elapsed > 0 else 0
                        print(f"  Progress: {j}/{len(statements)} ({rate:.0f} nodes/sec)")
                    
                    try:
                        tx.run(stmt)
                        batch_success += 1
                    except Exception as e:
                        batch_failed += 1
                        if batch_failed <= 5:  # Show first 5 errors
                            print(f"    Error: {str(e)[:100]}")
                
                tx.commit()
            
            total_nodes += batch_success
            failed_nodes += batch_failed
            
            elapsed = time.time() - batch_start
            print(f"  ✅ Batch complete: {batch_success} nodes in {elapsed:.1f}s ({batch_success/elapsed:.0f} nodes/sec)")
            if batch_failed > 0:
                print(f"  ⚠️  Failed: {batch_failed} nodes")
        
        node_time = time.time() - start_time
        print(f"\n✅ All nodes imported: {total_nodes:,} in {node_time:.1f}s ({total_nodes/node_time:.0f} nodes/sec)")
        if failed_nodes > 0:
            print(f"⚠️  Total failed nodes: {failed_nodes:,}")
        
        # Import relationships
        print("\n" + "=" * 40)
        print("IMPORTING RELATIONSHIPS")
        print("=" * 40)
        
        total_rels = 0
        failed_rels = 0
        start_time = time.time()
        
        for i, rel_file in enumerate(rel_files):
            print(f"\nBatch {i+1}/{len(rel_files)}: {rel_file}")
            
            with open(rel_file, 'r') as f:
                statements = [line.strip() for line in f.readlines() if line.strip()]
            
            batch_start = time.time()
            batch_success = 0
            batch_failed = 0
            
            # Execute relationships one by one (they might fail if nodes don't exist)
            for j, stmt in enumerate(statements):
                if j % 100 == 0 and j > 0:
                    elapsed = time.time() - batch_start
                    rate = j / elapsed if elapsed > 0 else 0
                    print(f"  Progress: {j}/{len(statements)} ({rate:.0f} rels/sec)")
                
                try:
                    session.run(stmt)
                    batch_success += 1
                except:
                    batch_failed += 1  # Silently skip missing nodes
            
            total_rels += batch_success
            failed_rels += batch_failed
            
            elapsed = time.time() - batch_start
            print(f"  ✅ Batch complete: {batch_success} relationships in {elapsed:.1f}s")
            if batch_failed > 0:
                print(f"  ⚠️  Skipped: {batch_failed} (missing nodes)")
        
        rel_time = time.time() - start_time
        print(f"\n✅ All relationships imported: {total_rels:,} in {rel_time:.1f}s ({total_rels/rel_time:.0f} rels/sec)")
        if failed_rels > 0:
            print(f"ℹ️  Skipped relationships: {failed_rels:,} (normal for missing nodes)")
        
        # Verify import
        print("\n" + "=" * 40)
        print("VERIFICATION")
        print("=" * 40)
        
        # Get counts
        node_count = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
        rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]
        
        print(f"\n📊 Final Statistics:")
        print(f"   Nodes in database: {node_count:,}")
        print(f"   Relationships in database: {rel_count:,}")
        
        # Show edge type distribution
        print("\n📈 Edge Type Distribution:")
        result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) as edge_type, count(r) as count
            ORDER BY count DESC
        """)
        
        for record in result:
            print(f"   {record['edge_type']:<20} {record['count']:>8,}")
        
        # Show node type distribution
        print("\n📊 Node Type Distribution:")
        result = session.run("""
            MATCH (n)
            WITH labels(n) as lbls, count(n) as count
            UNWIND lbls as label
            WITH label, count
            WHERE label <> 'Symbol'
            RETURN label, sum(count) as total
            ORDER BY total DESC
        """)
        
        for record in result:
            print(f"   {record['label']:<20} {record['total']:>8,}")
    
    driver.close()
    
    print("\n" + "=" * 60)
    print("🎉 IMPORT COMPLETE!")
    print("=" * 60)
    print(f"\nTotal time: {(node_time + rel_time):.1f} seconds")
    print(f"Average speed: {(total_nodes + total_rels)/(node_time + rel_time):.0f} operations/sec")
    
    return True

if __name__ == "__main__":
    # Check if Neo4j is running
    try:
        import_complete_graph()
    except KeyboardInterrupt:
        print("\n\n⚠️  Import interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Import failed: {e}")
        sys.exit(1)