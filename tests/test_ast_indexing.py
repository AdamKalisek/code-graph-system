#!/usr/bin/env python3
"""
Test AST indexing with a small subset of files
"""

import sys
import time
from pathlib import Path

sys.path.append('.')

from code_graph_system.core.graph_store import FederatedGraphStore
from plugins.php.plugin import PHPLanguagePlugin


def test_indexing():
    """Test indexing with 100 files"""
    print("=" * 70)
    print("  TEST AST INDEXING (100 FILES)")
    print("=" * 70)
    
    # Connect to Neo4j
    print("\n🔌 Connecting to Neo4j...")
    graph_store = FederatedGraphStore(
        'bolt://localhost:7688',
        ('neo4j', 'password123'),
        {'federation': {'mode': 'unified'}}
    )
    
    # Clear existing data
    print("🧹 Clearing existing graph...")
    graph_store.graph.run("MATCH (n) DETACH DELETE n")
    
    # Initialize PHP plugin
    print("📦 Initializing PHP plugin...")
    php_plugin = PHPLanguagePlugin()
    php_plugin.initialize({})
    
    # Test with 100 files
    espocrm_path = Path('espocrm')
    php_files = list(espocrm_path.rglob('*.php'))[:100]
    print(f"\n📂 Testing with {len(php_files)} PHP files")
    
    start_time = time.time()
    total_nodes = 0
    total_relationships = 0
    errors = []
    
    for i, file_path in enumerate(php_files):
        try:
            result = php_plugin.parse_file(str(file_path))
            
            if len(result.errors) == 0:
                n, r = graph_store.store_batch(result.nodes, result.relationships, 'php')
                total_nodes += n
                total_relationships += r
            else:
                errors.extend(result.errors)
                
            if (i + 1) % 10 == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed
                print(f"  Progress: {i + 1}/{len(php_files)} ({rate:.1f} files/sec)")
                
        except Exception as e:
            errors.append(f"Error: {e}")
            
    elapsed = time.time() - start_time
    
    print(f"""
📊 Results:
   Files: {len(php_files)}
   Nodes: {total_nodes}
   Relationships: {total_relationships}
   Time: {elapsed:.2f}s
   Rate: {len(php_files)/elapsed:.1f} files/sec
   Errors: {len(errors)}
""")
    
    # Check inheritance
    extends = graph_store.query("MATCH ()-[r:EXTENDS]->() RETURN count(r) as c")
    implements = graph_store.query("MATCH ()-[r:IMPLEMENTS]->() RETURN count(r) as c")
    
    print(f"🔗 Inheritance:")
    print(f"   EXTENDS: {extends[0]['c'] if extends else 0}")
    print(f"   IMPLEMENTS: {implements[0]['c'] if implements else 0}")
    
    # Check multi-labels with simpler query
    php_classes = graph_store.query("""
        MATCH (n:Symbol)
        WHERE n.kind = 'class' AND n._language = 'php'
        RETURN count(n) as c
    """)
    print(f"\n🏷️  PHP Classes: {php_classes[0]['c'] if php_classes else 0}")
    

if __name__ == '__main__':
    test_indexing()