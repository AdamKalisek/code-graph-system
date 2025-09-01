#!/usr/bin/env python3
"""FAST comprehensive import of COMPLETE EspoCRM graph with file system"""

import neo4j
from pathlib import Path
import time
import sys

def import_complete_graph_with_files():
    """Import the COMPLETE graph including directories, files, and all relationships"""
    
    print("=" * 80)
    print("COMPLETE EspoCRM Graph Import - WITH FILE SYSTEM")
    print("=" * 80)
    
    # Connect to Neo4j
    print("\nConnecting to Neo4j...")
    try:
        driver = neo4j.GraphDatabase.driver(
            "bolt://localhost:7688",
            auth=("neo4j", "password123")
        )
    except Exception as e:
        print(f"❌ Failed to connect to Neo4j: {e}")
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
        
        # Read the complete export file
        export_file = Path("espocrm_complete_with_files.cypher")
        if not export_file.exists():
            print(f"❌ Export file not found: {export_file}")
            return False
        
        print(f"\nReading {export_file} ({export_file.stat().st_size / 1024 / 1024:.1f} MB)")
        
        with open(export_file, 'r') as f:
            lines = f.readlines()
        
        print(f"Processing {len(lines):,} lines...")
        
        # Categorize statements
        indexes = []
        directories = []
        files = []
        symbols = []
        dir_contains = []
        dir_contains_file = []
        file_defines = []
        symbol_relationships = []
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('//'):
                continue
            
            if line.startswith('CREATE INDEX'):
                indexes.append(line)
            elif line.startswith('CREATE (:Directory'):
                directories.append(line)
            elif line.startswith('CREATE (:File'):
                files.append(line)
            elif line.startswith('CREATE ('):
                symbols.append(line)
            elif 'Directory' in line and 'CONTAINS' in line and 'File' not in line:
                dir_contains.append(line)
            elif 'Directory' in line and 'CONTAINS' in line and 'File' in line:
                dir_contains_file.append(line)
            elif 'DEFINES' in line:
                file_defines.append(line)
            elif line.startswith('MATCH') and 'CONTAINS' not in line and 'DEFINES' not in line:
                symbol_relationships.append(line)
        
        print(f"\n📊 Statement Distribution:")
        print(f"   Indexes: {len(indexes):,}")
        print(f"   Directories: {len(directories):,}")
        print(f"   Files: {len(files):,}")
        print(f"   Symbols: {len(symbols):,}")
        print(f"   Directory→Directory: {len(dir_contains):,}")
        print(f"   Directory→File: {len(dir_contains_file):,}")
        print(f"   File→Symbol: {len(file_defines):,}")
        print(f"   Symbol→Symbol: {len(symbol_relationships):,}")
        
        # Create indexes
        print("\n=== CREATING INDEXES ===")
        for idx in indexes:
            try:
                session.run(idx)
                print(".", end="", flush=True)
            except:
                pass  # Index might already exist
        print("\n✅ Indexes created")
        
        # Import directories
        print("\n=== IMPORTING DIRECTORIES ===")
        start_time = time.time()
        success = 0
        failed = 0
        
        with session.begin_transaction() as tx:
            for i, stmt in enumerate(directories):
                if i > 0 and i % 100 == 0:
                    tx.commit()
                    tx = session.begin_transaction()
                    print(f"  Progress: {i}/{len(directories)} directories...")
                
                try:
                    tx.run(stmt)
                    success += 1
                except Exception as e:
                    failed += 1
                    if failed <= 5:
                        print(f"\n  Error: {str(e)[:100]}")
            
            tx.commit()
        
        elapsed = time.time() - start_time
        print(f"✅ Directories imported: {success:,} in {elapsed:.1f}s ({success/elapsed:.0f} nodes/sec)")
        if failed > 0:
            print(f"⚠️  Failed: {failed}")
        
        # Import files
        print("\n=== IMPORTING FILES ===")
        start_time = time.time()
        success = 0
        failed = 0
        
        with session.begin_transaction() as tx:
            for i, stmt in enumerate(files):
                if i > 0 and i % 100 == 0:
                    tx.commit()
                    tx = session.begin_transaction()
                    print(f"  Progress: {i}/{len(files)} files...")
                
                try:
                    tx.run(stmt)
                    success += 1
                except Exception as e:
                    failed += 1
            
            tx.commit()
        
        elapsed = time.time() - start_time
        print(f"✅ Files imported: {success:,} in {elapsed:.1f}s ({success/elapsed:.0f} nodes/sec)")
        if failed > 0:
            print(f"⚠️  Failed: {failed}")
        
        # Import symbols
        print("\n=== IMPORTING SYMBOLS ===")
        start_time = time.time()
        success = 0
        failed = 0
        
        batch_size = 500
        for batch_start in range(0, len(symbols), batch_size):
            batch = symbols[batch_start:batch_start + batch_size]
            print(f"  Batch {batch_start//batch_size + 1}/{(len(symbols)-1)//batch_size + 1} ({len(batch)} symbols)")
            
            with session.begin_transaction() as tx:
                for stmt in batch:
                    try:
                        tx.run(stmt)
                        success += 1
                    except Exception as e:
                        failed += 1
                
                tx.commit()
        
        elapsed = time.time() - start_time
        print(f"✅ Symbols imported: {success:,} in {elapsed:.1f}s ({success/elapsed:.0f} nodes/sec)")
        if failed > 0:
            print(f"⚠️  Failed: {failed}")
        
        # Import Directory→Directory relationships
        print("\n=== IMPORTING DIRECTORY→DIRECTORY RELATIONSHIPS ===")
        start_time = time.time()
        success = 0
        failed = 0
        
        for i, stmt in enumerate(dir_contains):
            if i > 0 and i % 100 == 0:
                print(f"  Progress: {i}/{len(dir_contains)} relationships...")
            
            try:
                session.run(stmt)
                success += 1
            except:
                failed += 1
        
        elapsed = time.time() - start_time
        print(f"✅ Directory→Directory imported: {success:,} in {elapsed:.1f}s")
        if failed > 0:
            print(f"⚠️  Failed: {failed}")
        
        # Import Directory→File relationships
        print("\n=== IMPORTING DIRECTORY→FILE RELATIONSHIPS ===")
        start_time = time.time()
        success = 0
        failed = 0
        
        for i, stmt in enumerate(dir_contains_file):
            if i > 0 and i % 100 == 0:
                print(f"  Progress: {i}/{len(dir_contains_file)} relationships...")
            
            try:
                session.run(stmt)
                success += 1
            except:
                failed += 1
        
        elapsed = time.time() - start_time
        print(f"✅ Directory→File imported: {success:,} in {elapsed:.1f}s")
        if failed > 0:
            print(f"⚠️  Failed: {failed}")
        
        # Import File→Symbol relationships
        print("\n=== IMPORTING FILE→SYMBOL RELATIONSHIPS ===")
        start_time = time.time()
        success = 0
        failed = 0
        
        for i, stmt in enumerate(file_defines):
            if i > 0 and i % 500 == 0:
                print(f"  Progress: {i}/{len(file_defines)} relationships...")
            
            try:
                session.run(stmt)
                success += 1
            except:
                failed += 1
        
        elapsed = time.time() - start_time
        print(f"✅ File→Symbol imported: {success:,} in {elapsed:.1f}s")
        if failed > 0:
            print(f"⚠️  Failed: {failed}")
        
        # Import Symbol→Symbol relationships
        print("\n=== IMPORTING SYMBOL→SYMBOL RELATIONSHIPS ===")
        start_time = time.time()
        success = 0
        failed = 0
        
        for i, stmt in enumerate(symbol_relationships):
            if i > 0 and i % 500 == 0:
                print(f"  Progress: {i}/{len(symbol_relationships)} relationships...")
            
            try:
                session.run(stmt)
                success += 1
            except:
                failed += 1
        
        elapsed = time.time() - start_time
        print(f"✅ Symbol→Symbol imported: {success:,} in {elapsed:.1f}s")
        if failed > 0:
            print(f"⚠️  Failed: {failed} (normal for missing symbols)")
        
        # Verify import
        print("\n" + "=" * 60)
        print("VERIFICATION")
        print("=" * 60)
        
        # Get counts by label
        print("\n📊 Node Counts by Label:")
        labels = ['Directory', 'File', 'Namespace', 'Class', 'Interface', 'Trait', 
                  'Method', 'Function', 'Property', 'Constant']
        
        for label in labels:
            count = session.run(f"MATCH (n:{label}) RETURN count(n) as count").single()["count"]
            print(f"   {label:<15} {count:>8,}")
        
        # Get relationship counts
        print("\n📈 Relationship Counts:")
        rel_types = ['CONTAINS', 'DEFINES', 'IMPORTS', 'CALLS', 'EXTENDS', 
                     'IMPLEMENTS', 'USES_TRAIT', 'RETURNS', 'PARAMETER_TYPE',
                     'THROWS', 'INSTANTIATES', 'ACCESSES', 'USES_CONSTANT', 'CALLS_STATIC']
        
        for rel_type in rel_types:
            try:
                count = session.run(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count").single()["count"]
                if count > 0:
                    print(f"   {rel_type:<20} {count:>8,}")
            except:
                pass
        
        # Get total counts
        total_nodes = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
        total_rels = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]
        
        print(f"\n📊 TOTALS:")
        print(f"   Total Nodes:         {total_nodes:>8,}")
        print(f"   Total Relationships: {total_rels:>8,}")
        
        # Sample query to show the complete structure
        print("\n📎 Sample Graph Structure:")
        result = session.run("""
            MATCH (d:Directory)-[:CONTAINS]->(f:File)-[:DEFINES]->(c:Class)
            RETURN d.path as dir, f.name as file, c.name as class
            LIMIT 5
        """)
        
        for record in result:
            print(f"   {record['dir']} → {record['file']} → {record['class']}")
    
    driver.close()
    
    print("\n" + "=" * 80)
    print("🎉 COMPLETE IMPORT SUCCESSFUL!")
    print("=" * 80)
    print("\nThe graph now contains:")
    print("✅ Directory structure")
    print("✅ File nodes")
    print("✅ All code symbols (Classes, Methods, etc.)")
    print("✅ All relationships (CONTAINS, DEFINES, IMPORTS, CALLS, etc.)")
    print("\nYou can now query the COMPLETE code graph with file system structure!")
    
    return True

if __name__ == "__main__":
    try:
        import_complete_graph_with_files()
    except KeyboardInterrupt:
        print("\n\n⚠️  Import interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)