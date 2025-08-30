#!/usr/bin/env python3
"""
Complete EspoCRM Indexing with AST Parsers and Cross-Language Linking
"""

import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.append('.')

from code_graph_system.core.graph_store import FederatedGraphStore
from code_graph_system.core.schema import Symbol, Relationship
from plugins.php.plugin import PHPLanguagePlugin
from plugins.javascript.tree_sitter_parser import JavaScriptParser
from plugins.espocrm.route_parser import EspoCRMRouteParser
from plugins.espocrm.cross_linker import CrossLinker
import json
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def index_metadata_optimized(graph):
    """Index all metadata JSON files - OPTIMIZED with batching."""
    print("\n📄 Indexing metadata...")
    nodes = []
    relationships = []
    count = 0
    
    # Stream metadata files instead of loading all at once
    metadata_paths = [
        'espocrm/application/Espo/Resources/metadata/',
        'espocrm/custom/Espo/Custom/Resources/metadata/'
    ]
    
    for base_path in metadata_paths:
        if Path(base_path).exists():
            for f in Path(base_path).rglob('*.json'):
                try:
                    content = f.read_text(encoding='utf-8', errors='ignore')
                    metadata_node = Symbol(
                        name=f.name,
                        qualified_name=str(f),
                        kind='metadata',
                        plugin_id='metadata',
                        metadata=json.loads(content)
                    )
                    nodes.append(metadata_node)
                    count += 1
                    
                    # Batch store every 100 nodes
                    if len(nodes) >= 100:
                        n, r = graph.store_batch(nodes, relationships)
                        nodes = []
                        print(f"   Processed {count} metadata files...")
                except Exception as e:
                    logger.warning(f"Error processing metadata file {f}: {e}")
    
    # Store remaining nodes
    if nodes:
        n, r = graph.store_batch(nodes, relationships)
    
    print(f"   Created {count} metadata nodes total")

def create_directory_structure(graph, base_path):
    """Create all directory nodes efficiently using os.walk - OPTIMIZED."""
    import os
    print(f"   Building directory structure for {base_path}...")
    
    dir_nodes = []
    dir_relationships = []
    seen_dirs = set()
    
    # Use os.walk for efficient traversal - avoids loading all files
    for root, dirs, files in os.walk(base_path):
        root_path = Path(root)
        
        # Skip if already processed
        if str(root_path) in seen_dirs:
            continue
            
        seen_dirs.add(str(root_path))
        
        # Create node for this directory
        dir_node = Symbol(
            name=root_path.name if root_path.name else 'espocrm',
            qualified_name=str(root_path),
            kind='directory',
            plugin_id='filesystem'
        )
        dir_nodes.append(dir_node)
        
        # Create parent relationship if not root
        parent_path = root_path.parent
        if str(parent_path) != str(root_path) and str(parent_path) in seen_dirs:
            parent_node = Symbol(
                name=parent_path.name if parent_path.name else 'espocrm',
                qualified_name=str(parent_path),
                kind='directory',
                plugin_id='filesystem'
            )
            dir_relationships.append(Relationship(
                source_id=parent_node.id,
                target_id=dir_node.id,
                type='CONTAINS'
            ))
    
    # Single batch operation for all directories
    if dir_nodes:
        n, r = graph.store_batch(dir_nodes, dir_relationships)
        print(f"   Created {n} directory nodes, {r} relationships in single batch")
        return n, r
    return 0, 0


def process_files_streaming(graph, base_path, pattern, parser, language, batch_size=100):
    """Process files using generator pattern for memory efficiency."""
    batch = []
    batch_nodes = []
    batch_rels = []
    file_count = 0
    total_nodes = 0
    total_rels = 0
    
    # Count files first for progress reporting
    total_files = sum(1 for _ in Path(base_path).rglob(pattern))
    print(f"   Found {total_files} {pattern} files")
    
    # Stream files instead of loading all into memory
    for file_path in Path(base_path).rglob(pattern):
        batch.append(file_path)
        file_count += 1
        
        if len(batch) >= batch_size:
            # Process batch
            for fp in batch:
                try:
                    if hasattr(parser, 'parse_file'):
                        result = parser.parse_file(str(fp))
                    else:
                        result = parser.parse(str(fp))
                        
                    if not result.errors:
                        batch_nodes.extend(result.nodes)
                        batch_rels.extend(result.relationships)
                except Exception as e:
                    logger.warning(f"Failed to parse {fp}: {e}")
            
            # Store batch
            if batch_nodes:
                n, r = graph.store_batch(batch_nodes, batch_rels, language)
                total_nodes += n
                total_rels += r
                batch_nodes = []
                batch_rels = []
            
            # Progress indicator
            if file_count % 500 == 0 or file_count == total_files:
                print(f"   Progress: {file_count}/{total_files} files processed")
            batch = []
    
    # Process remaining files
    if batch:
        for fp in batch:
            try:
                if hasattr(parser, 'parse_file'):
                    result = parser.parse_file(str(fp))
                else:
                    result = parser.parse(str(fp))
                    
                if not result.errors:
                    batch_nodes.extend(result.nodes)
                    batch_rels.extend(result.relationships)
            except Exception as e:
                logger.warning(f"Failed to parse {fp}: {e}")
        
        if batch_nodes:
            n, r = graph.store_batch(batch_nodes, batch_rels, language)
            total_nodes += n
            total_rels += r
            print(f"   Progress: {file_count}/{total_files} files processed")
    
    return total_nodes, total_rels


def index_complete_optimized():
    print("=" * 70)
    print("  OPTIMIZED ESPOCRM INDEXING")
    print("=" * 70)
    start_time = time.time()
    print(f"  Started: {datetime.now()}")
    
    # Initialize
    graph = FederatedGraphStore(
        'bolt://localhost:7688',
        ('neo4j', 'password123'),
        {'federation': {'mode': 'unified'}}
    )
    
    # Clear
    print("\n🧹 Clearing graph...")
    graph.graph.run("MATCH (n) DETACH DELETE n")
    
    # Create directory structure ONCE for entire codebase
    print("\n📁 Creating directory structure (ONCE)...")
    dir_start = time.time()
    create_directory_structure(graph, 'espocrm')
    print(f"   Directory creation took: {time.time() - dir_start:.2f} seconds")
    
    # Index metadata with batching
    index_metadata_optimized(graph)
    
    # Index endpoints first
    print("\n📡 Indexing endpoints...")
    parser = EspoCRMRouteParser('espocrm')
    endpoints, rels = parser.parse_all_routes()
    if endpoints:
        n, r = graph.store_batch(endpoints, rels)
        print(f"   Created {n} endpoints, {r} relationships")
    
    # Index PHP files with streaming
    print("\n🐘 Indexing PHP files (STREAMING)...")
    php_start = time.time()
    php_plugin = PHPLanguagePlugin()
    php_plugin.initialize({})
    
    # Process with streaming - no memory spike
    php_nodes, php_rels = process_files_streaming(graph, 'espocrm', '*.php', php_plugin, 'php', batch_size=100)
    print(f"   PHP indexing took: {time.time() - php_start:.2f} seconds")
    print(f"   Created {php_nodes} nodes, {php_rels} relationships")
    
    # Index JavaScript files with streaming
    print("\n🌐 Indexing JavaScript files (STREAMING)...")
    js_start = time.time()
    js_parser = JavaScriptParser()
    
    # Process with streaming - no memory spike
    js_nodes, js_rels = process_files_streaming(graph, 'espocrm/client', '*.js', js_parser, 'javascript', batch_size=100)
    print(f"   JavaScript indexing took: {time.time() - js_start:.2f} seconds")
    print(f"   Created {js_nodes} nodes, {js_rels} relationships")
    
    # Cross-link
    print("\n🔗 Cross-linking...")
    linker = CrossLinker(graph)
    links = linker.link_all()
    
    # Report
    print("\n" + "=" * 70)
    print("  RESULTS")
    print("=" * 70)
    
    stats = {
        'PHP Classes': graph.query("MATCH (n:Symbol) WHERE n.kind='class' AND n._language='php' RETURN count(n) as c"),
        'JS Functions': graph.query("MATCH (n:Symbol) WHERE n.kind='function' AND n._language='javascript' RETURN count(n) as c"),
        'Endpoints': graph.query("MATCH (n:Endpoint) RETURN count(n) as c"),
        'EXTENDS': graph.query("MATCH ()-[r:EXTENDS]->() RETURN count(r) as c"),
        'CALLS': graph.query("MATCH ()-[r:CALLS]->() RETURN count(r) as c")
    }
    
    for key, result in stats.items():
        count = result[0]['c'] if result else 0
        print(f"{key}: {count}")
    
    # Final timing
    total_time = time.time() - start_time
    print("\n" + "=" * 70)
    print(f"  PERFORMANCE SUMMARY")
    print("=" * 70)
    # Count files for final stats
    total_php_files = sum(1 for _ in Path('espocrm').rglob('*.php'))
    total_js_files = sum(1 for _ in Path('espocrm/client').rglob('*.js'))
    total_files = total_php_files + total_js_files
    
    print(f"Total execution time: {total_time:.2f} seconds ({total_time/60:.1f} minutes)")
    print(f"Files processed: {total_files}")
    print(f"Average time per file: {total_time/total_files:.3f} seconds" if total_files > 0 else "No files processed")
    print("\n✅ Optimized indexing complete!")


if __name__ == '__main__':
    # Run the optimized version
    index_complete_optimized()
