#!/usr/bin/env python3
"""
Performance test for bulk ingestion improvements
"""

import sys
import time
from pathlib import Path
sys.path.append('.')

from code_graph_system.core.graph_store import FederatedGraphStore
from plugins.php.plugin import PHPLanguagePlugin


def test_performance():
    """Test parsing and storage performance"""
    print("Performance Test - Bulk Ingestion")
    print("=" * 50)
    
    # Connect to Neo4j
    graph_store = FederatedGraphStore(
        'bolt://localhost:7688',
        ('neo4j', 'password123'),
        {'federation': {'mode': 'unified'}}
    )
    
    # Clear graph
    graph_store.graph.run("MATCH (n) DETACH DELETE n")
    
    # Initialize PHP plugin
    php_plugin = PHPLanguagePlugin()
    php_plugin.initialize({})
    
    # Test files
    test_files = []
    espo_dir = Path('espocrm/application/Espo')
    
    # Find PHP files
    for php_file in espo_dir.rglob('*.php'):
        test_files.append(str(php_file))
        if len(test_files) >= 50:  # Test with 50 files
            break
    
    print(f"\nTesting with {len(test_files)} PHP files")
    
    total_nodes = 0
    total_relationships = 0
    
    # Start timing
    start_time = time.time()
    parse_time = 0
    store_time = 0
    
    for i, file_path in enumerate(test_files):
        # Parse file
        parse_start = time.time()
        result = php_plugin.parse_file(file_path)
        parse_time += time.time() - parse_start
        
        # Store in graph
        store_start = time.time()
        n, r = graph_store.store_batch(
            result.nodes,
            result.relationships,
            'php'
        )
        store_time += time.time() - store_start
        
        total_nodes += n
        total_relationships += r
        
        if (i + 1) % 10 == 0:
            print(f"  Processed {i + 1} files...")
    
    total_time = time.time() - start_time
    
    # Print results
    print(f"\n📊 Performance Results:")
    print(f"  Total files: {len(test_files)}")
    print(f"  Total nodes: {total_nodes}")
    print(f"  Total relationships: {total_relationships}")
    print(f"\n⏱️ Timing:")
    print(f"  Total time: {total_time:.2f} seconds")
    print(f"  Parse time: {parse_time:.2f} seconds ({parse_time/total_time*100:.1f}%)")
    print(f"  Store time: {store_time:.2f} seconds ({store_time/total_time*100:.1f}%)")
    print(f"\n📈 Performance:")
    print(f"  Files/second: {len(test_files)/total_time:.1f}")
    print(f"  Nodes/second: {total_nodes/store_time:.1f}")
    print(f"  Relationships/second: {total_relationships/store_time:.1f}")
    
    # Get final statistics
    stats = graph_store.get_statistics()
    print(f"\n📊 Graph Statistics:")
    print(f"  Total nodes in graph: {stats['total_nodes']}")
    print(f"  Total relationships in graph: {stats['total_relationships']}")
    
    print("\n✅ Performance test complete!")


if __name__ == '__main__':
    test_performance()