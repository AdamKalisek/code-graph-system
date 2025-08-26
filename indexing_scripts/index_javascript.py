#!/usr/bin/env python3
"""
JavaScript-only indexing with optimizations
"""

import sys
import time
import logging
from pathlib import Path
from datetime import datetime
import json

sys.path.append('.')

from code_graph_system.core.graph_store import FederatedGraphStore
from plugins.javascript.tree_sitter_parser import JavaScriptParser

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def index_javascript():
    """Index only JavaScript files with better error handling"""
    print("=" * 70)
    print("  JAVASCRIPT INDEXING")
    print("=" * 70)
    print(f"  Started: {datetime.now()}")
    print()
    
    # Statistics
    stats = {
        'files': 0,
        'nodes': 0,
        'relationships': 0,
        'api_calls': 0,
        'errors': [],
        'failed_files': []
    }
    
    # Initialize graph store
    print("🔌 Connecting to Neo4j...")
    graph = FederatedGraphStore(
        'bolt://localhost:7688',
        ('neo4j', 'password123'),
        {'federation': {'mode': 'unified'}}
    )
    
    # Initialize parser
    print("🌐 Initializing JavaScript parser...")
    js_parser = JavaScriptParser()
    
    # Find JavaScript files
    js_files = []
    for pattern in ['*.js', '*.jsx']:
        js_files.extend(list(Path('espocrm/client').rglob(pattern)))
    # Exclude node_modules
    js_files = [f for f in js_files if 'node_modules' not in str(f)]
    stats['files'] = len(js_files)
    print(f"📂 Found {len(js_files)} JavaScript files")
    
    # Process files one by one with error handling
    batch_size = 50
    start_time = time.time()
    
    for i in range(0, len(js_files), batch_size):
        batch = js_files[i:i+batch_size]
        batch_nodes = []
        batch_relationships = []
        
        for file_path in batch:
            try:
                result = js_parser.parse_file(str(file_path))
                
                if len(result.errors) == 0:
                    batch_nodes.extend(result.nodes)
                    batch_relationships.extend(result.relationships)
                    
                    # Count API calls
                    for node in result.nodes:
                        if hasattr(node, 'metadata') and node.metadata:
                            if 'api_calls' in node.metadata:
                                api_data = node.metadata.get('api_calls')
                                if api_data:
                                    try:
                                        if isinstance(api_data, str):
                                            api_calls = json.loads(api_data)
                                        else:
                                            api_calls = api_data
                                        stats['api_calls'] += len(api_calls)
                                    except:
                                        pass
                else:
                    stats['errors'].extend(result.errors)
                    stats['failed_files'].append(str(file_path))
                    
            except Exception as e:
                error_msg = f"Failed to parse {file_path}: {e}"
                stats['errors'].append(error_msg)
                stats['failed_files'].append(str(file_path))
                logger.debug(error_msg)
                continue
        
        # Store batch
        if batch_nodes:
            try:
                n, r = graph.store_batch(batch_nodes, batch_relationships, 'javascript')
                stats['nodes'] += n
                stats['relationships'] += r
            except Exception as e:
                logger.error(f"Failed to store batch: {e}")
        
        # Progress update
        current = min(i + batch_size, len(js_files))
        elapsed = time.time() - start_time
        if elapsed > 0:
            rate = current / elapsed
            eta = (len(js_files) - current) / rate if rate > 0 else 0
            print(f"   Progress: {current}/{len(js_files)} files " +
                  f"({rate:.1f} files/sec, ETA: {eta:.0f}s) " +
                  f"[API calls found: {stats['api_calls']}]")
    
    elapsed = time.time() - start_time
    print(f"✅ Indexed {len(js_files)} JavaScript files in {elapsed:.1f}s")
    
    # Summary
    print("\n" + "=" * 70)
    print("  JAVASCRIPT INDEXING COMPLETE")
    print("=" * 70)
    print(f"""
📈 Final Statistics:
   Files processed: {stats['files']}
   Failed files: {len(stats['failed_files'])}
   Nodes created: {stats['nodes']}
   Relationships created: {stats['relationships']}
   API calls detected: {stats['api_calls']}
   Errors: {len(stats['errors'])}
   Time: {elapsed:.1f} seconds
   Rate: {len(js_files)/elapsed:.1f} files/sec
""")
    
    if stats['failed_files']:
        print(f"⚠️ Failed to parse {len(stats['failed_files'])} files:")
        for f in stats['failed_files'][:5]:
            print(f"   - {f}")
        if len(stats['failed_files']) > 5:
            print(f"   ... and {len(stats['failed_files'])-5} more")
    
    return stats


if __name__ == '__main__':
    index_javascript()