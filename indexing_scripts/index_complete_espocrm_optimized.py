#!/usr/bin/env python3
"""
Optimized Complete EspoCRM Indexing with AST Parsers and Cross-Language Linking
Performance improvements:
- Cached directory nodes to avoid recreation
- Batch processing for database operations
- Generator-based file iteration
- Configurable batch sizes
- Better progress tracking
- File logging with rotation
"""

import sys
import time
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
from typing import Generator, Set, List, Tuple
from collections import defaultdict

sys.path.append('.')

from code_graph_system.core.graph_store import FederatedGraphStore
from code_graph_system.core.schema import Symbol, Relationship
from plugins.php.plugin import PHPLanguagePlugin
from plugins.javascript.tree_sitter_parser import JavaScriptParser
from plugins.espocrm.route_parser import EspoCRMRouteParser
from plugins.espocrm.cross_linker import CrossLinker
import json

def setup_logging(log_file='indexing.log', log_level='INFO'):
    """Setup logging configuration with file rotation."""
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / log_file
    
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_formatter = logging.Formatter(
        '%(levelname)s - %(message)s'
    )
    
    # Setup root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # File handler with rotation (10MB max, keep 5 backups)
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Console handler for important messages
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logger

class OptimizedIndexer:
    def __init__(self, graph, batch_size=100):
        self.graph = graph
        self.batch_size = batch_size
        self.directory_cache = set()  # Track created directories
        self.directory_nodes = {}  # Store directory nodes for file linking
        self.pending_nodes = []
        self.pending_relationships = []
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def flush_batch(self, force=False):
        """Flush pending nodes and relationships to database."""
        if force or len(self.pending_nodes) >= self.batch_size:
            if self.pending_nodes or self.pending_relationships:
                self.logger.debug(f"Flushing batch: {len(self.pending_nodes)} nodes, {len(self.pending_relationships)} relationships")
                n, r = self.graph.store_batch(self.pending_nodes, self.pending_relationships)
                self.pending_nodes = []
                self.pending_relationships = []
                self.logger.debug(f"Batch stored: {n} nodes, {r} relationships")
                return n, r
        return 0, 0
    
    def create_directory_hierarchy(self, file_paths: List[Path]):
        """Pre-create all directory nodes for a set of files with proper relationships."""
        self.logger.info("Creating directory hierarchy...")
        print("   Creating directory hierarchy...")
        
        # Collect all unique directories
        all_dirs = set()
        for file_path in file_paths:
            current = file_path.parent
            while current != current.parent and str(current) != '.':
                all_dirs.add(current)
                current = current.parent
        
        # Sort directories by depth (parent directories first)
        sorted_dirs = sorted(all_dirs, key=lambda p: len(p.parts))
        
        nodes = []
        relationships = []
        
        # Create all directory nodes first
        for dir_path in sorted_dirs:
            if str(dir_path) not in self.directory_cache:
                dir_node = Symbol(
                    name=dir_path.name,
                    qualified_name=str(dir_path),
                    kind='directory',
                    plugin_id='filesystem'
                )
                nodes.append(dir_node)
                self.directory_cache.add(str(dir_path))
                self.directory_nodes[str(dir_path)] = dir_node
            else:
                # Directory already exists, but we need it in directory_nodes for file linking
                # Try to find it in our cache or create a reference node
                if str(dir_path) not in self.directory_nodes:
                    # Create a reference node (won't be stored again, just for linking)
                    dir_node = Symbol(
                        name=dir_path.name,
                        qualified_name=str(dir_path),
                        kind='directory',
                        plugin_id='filesystem'
                    )
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
        
        if nodes:
            n, r = self.graph.store_batch(nodes, relationships)
            self.logger.info(f"Created {n} directory nodes, {r} relationships")
            print(f"   Created {n} directory nodes, {r} relationships")
        
        return nodes, relationships  # Return for file linking
    
    def create_file_directory_relationships(self, file_nodes: List, file_paths: List[Path]):
        """Create IN_DIRECTORY relationships for files."""
        relationships = []
        
        # Debug logging
        self.logger.info(f"Creating file-to-directory relationships for {len(file_nodes)} files")
        self.logger.info(f"Directory nodes available: {len(getattr(self, 'directory_nodes', {}))}")
        
        if not hasattr(self, 'directory_nodes'):
            self.logger.error("No directory_nodes attribute found!")
            return relationships
            
        if not self.directory_nodes:
            self.logger.error("directory_nodes is empty!")
            return relationships
        
        # Log first few directory paths for debugging
        sample_dirs = list(self.directory_nodes.keys())[:5]
        self.logger.info(f"Sample directory paths in cache: {sample_dirs}")
        
        for file_node, file_path in zip(file_nodes, file_paths):
            parent_dir = str(file_path.parent)
            
            # Debug each lookup
            if parent_dir in self.directory_nodes:
                dir_node = self.directory_nodes[parent_dir]
                relationships.append(Relationship(
                    source_id=file_node.id,
                    target_id=dir_node.id,
                    type='IN_DIRECTORY'
                ))
                self.logger.debug(f"✓ Linked {file_path.name} to {parent_dir}")
            else:
                self.logger.warning(f"✗ Directory not found for {file_path.name}: '{parent_dir}'")
                self.logger.warning(f"  Available dirs starting with same prefix: {[d for d in self.directory_nodes.keys() if d.startswith(parent_dir[:20])][:3]}")
        
        self.logger.info(f"Created {len(relationships)} file-to-directory relationships")
            
        return relationships
    
    def index_metadata(self):
        """Index all metadata JSON files with batching."""
        self.logger.info("Starting metadata indexing")
        print("\n📄 Indexing metadata...")
        nodes = []
        relationships = []
        
        metadata_paths = [
            'espocrm/application/Espo/Resources/metadata/',
            'espocrm/custom/Espo/Custom/Resources/metadata/'
        ]
        
        total_processed = 0
        for base_path in metadata_paths:
            base = Path(base_path)
            if not base.exists():
                continue
                
            for f in base.rglob('*.json'):
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
                    total_processed += 1
                    
                    # Batch processing
                    if len(nodes) >= self.batch_size:
                        n, r = self.graph.store_batch(nodes, relationships)
                        print(f"   Batch: Created {n} metadata nodes")
                        nodes = []
                        
                except Exception as e:
                    self.logger.error(f"Error processing metadata file {f}: {e}")
                    print(f"   Error processing {f}: {e}")
        
        # Flush remaining
        if nodes:
            n, r = self.graph.store_batch(nodes, relationships)
            print(f"   Final batch: Created {n} metadata nodes")
        
        self.logger.info(f"Total metadata files processed: {total_processed}")
        print(f"   Total metadata files processed: {total_processed}")
    
    def process_files_batch(self, files: List[Path], parser, language: str):
        """Process a batch of files with a given parser."""
        from code_graph_system.core.schema import File as FileNode
        
        batch_nodes = []
        batch_relationships = []
        file_nodes = []
        errors = 0
        
        for f in files:
            # Create File node
            file_node = FileNode(
                path=str(f),
                name=f.name,
                language=language,
                plugin_id=language
            )
            file_nodes.append(file_node)
            batch_nodes.append(file_node)
            
            try:
                result = parser.parse_file(str(f))
                if not result.errors:
                    # Add parsed symbols
                    batch_nodes.extend(result.nodes)
                    batch_relationships.extend(result.relationships)
                    
                    # Create DEFINED_IN relationships for symbols to file
                    for symbol in result.nodes:
                        if hasattr(symbol, 'id'):
                            batch_relationships.append(Relationship(
                                source_id=symbol.id,
                                target_id=file_node.id,
                                type='DEFINED_IN'
                            ))
                else:
                    self.logger.debug(f"Parse errors in {f}: {result.errors}")
                    errors += 1
            except Exception as e:
                self.logger.debug(f"Failed to parse {f}: {e}")
                errors += 1
        
        # Create file-to-directory relationships
        file_dir_relationships = self.create_file_directory_relationships(file_nodes, files)
        batch_relationships.extend(file_dir_relationships)
        
        if errors:
            self.logger.debug(f"Batch had {errors} failed files out of {len(files)}")
        
        if batch_nodes:
            n, r = self.graph.store_batch(batch_nodes, batch_relationships, language)
            return n, r
        return 0, 0
    
    def index_php_files(self):
        """Index PHP files with batching and progress tracking."""
        self.logger.info("Starting PHP file indexing")
        print("\n🐘 Indexing PHP files...")
        php_plugin = PHPLanguagePlugin()
        php_plugin.initialize({})
        
        # Get all PHP files
        php_files = list(Path('espocrm').rglob('*.php'))
        total_files = len(php_files)
        self.logger.info(f"Found {total_files} PHP files to index")
        print(f"   Found {total_files} PHP files")
        
        if not php_files:
            return
        
        # Pre-create directory structure
        self.create_directory_hierarchy(php_files)
        
        # Process in batches
        total_nodes = 0
        total_relationships = 0
        batch = []
        
        start_time = time.time()
        for i, f in enumerate(php_files, 1):
            batch.append(f)
            
            if len(batch) >= self.batch_size or i == total_files:
                batch_num = (i - 1) // self.batch_size + 1
                total_batches = (total_files + self.batch_size - 1) // self.batch_size
                self.logger.info(f"Processing PHP batch {batch_num}/{total_batches} ({len(batch)} files)")
                n, r = self.process_files_batch(batch, php_plugin, 'php')
                total_nodes += n
                total_relationships += r
                self.logger.info(f"Batch {batch_num} completed: {n} nodes, {r} relationships")
                batch = []
                
                # Progress reporting
                if i % 100 == 0 or i == total_files:
                    elapsed = time.time() - start_time
                    rate = i / elapsed if elapsed > 0 else 0
                    eta = (total_files - i) / rate if rate > 0 else 0
                    self.logger.info(f"PHP Progress: {i}/{total_files} ({i*100/total_files:.1f}%) - {rate:.0f} files/sec - ETA: {eta:.0f}s")
                    print(f"   Progress: {i}/{total_files} ({i*100/total_files:.1f}%) "
                          f"- {rate:.0f} files/sec - ETA: {eta:.0f}s")
        
        self.logger.info(f"Indexing completed: {total_nodes} nodes, {total_relationships} relationships")
        print(f"   Completed: {total_nodes} nodes, {total_relationships} relationships")
    
    def index_javascript_files(self):
        """Index JavaScript files with batching and progress tracking."""
        self.logger.info("Starting JavaScript file indexing")
        print("\n🌐 Indexing JavaScript files...")
        js_parser = JavaScriptParser()
        
        # Get all JS files
        js_files = list(Path('espocrm/client').rglob('*.js'))
        total_files = len(js_files)
        self.logger.info(f"Found {total_files} JavaScript files to index")
        print(f"   Found {total_files} JavaScript files")
        
        if not js_files:
            return
        
        # Pre-create directory structure
        self.create_directory_hierarchy(js_files)
        
        # Process in batches
        total_nodes = 0
        total_relationships = 0
        batch = []
        
        start_time = time.time()
        for i, f in enumerate(js_files, 1):
            batch.append(f)
            
            if len(batch) >= self.batch_size or i == total_files:
                batch_num = (i - 1) // self.batch_size + 1
                total_batches = (total_files + self.batch_size - 1) // self.batch_size
                self.logger.info(f"Processing JS batch {batch_num}/{total_batches} ({len(batch)} files)")
                n, r = self.process_files_batch(batch, js_parser, 'javascript')
                total_nodes += n
                total_relationships += r
                self.logger.info(f"Batch {batch_num} completed: {n} nodes, {r} relationships")
                batch = []
                
                # Progress reporting
                if i % 100 == 0 or i == total_files:
                    elapsed = time.time() - start_time
                    rate = i / elapsed if elapsed > 0 else 0
                    eta = (total_files - i) / rate if rate > 0 else 0
                    self.logger.info(f"PHP Progress: {i}/{total_files} ({i*100/total_files:.1f}%) - {rate:.0f} files/sec - ETA: {eta:.0f}s")
                    print(f"   Progress: {i}/{total_files} ({i*100/total_files:.1f}%) "
                          f"- {rate:.0f} files/sec - ETA: {eta:.0f}s")
        
        self.logger.info(f"Indexing completed: {total_nodes} nodes, {total_relationships} relationships")
        print(f"   Completed: {total_nodes} nodes, {total_relationships} relationships")


def index_complete_optimized(batch_size=100, log_level='INFO'):
    """Main indexing function with optimizations."""
    # Setup logging
    logger = setup_logging('espocrm_indexing.log', log_level)
    logger.info("="*70)
    logger.info("Starting optimized EspoCRM indexing")
    logger.info(f"Batch size: {batch_size}, Log level: {log_level}")
    
    print("=" * 70)
    print("  OPTIMIZED COMPLETE ESPOCRM INDEXING")
    print("=" * 70)
    print(f"  Started: {datetime.now()}")
    print(f"  Batch size: {batch_size}")
    print(f"  Log file: logs/espocrm_indexing.log")
    
    overall_start = time.time()
    
    # Initialize
    logger.info("Connecting to Neo4j database...")
    try:
        graph = FederatedGraphStore(
            'bolt://localhost:7688',
            ('neo4j', 'password123'),
            {'federation': {'mode': 'unified'}}
        )
        logger.info("Successfully connected to Neo4j")
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")
        print(f"\n❌ Error: Failed to connect to database: {e}")
        return
    
    # Clear
    logger.info("Clearing existing graph data...")
    print("\n🧹 Clearing graph...")
    try:
        graph.graph.run("MATCH (n) DETACH DELETE n")
        logger.info("Graph cleared successfully")
    except Exception as e:
        logger.error(f"Failed to clear graph: {e}")
        print(f"\n❌ Error clearing graph: {e}")
    
    # Create optimized indexer
    indexer = OptimizedIndexer(graph, batch_size)
    
    # Index metadata
    indexer.index_metadata()
    
    # Index endpoints
    logger.info("Starting endpoint indexing...")
    print("\n📡 Indexing endpoints...")
    try:
        parser = EspoCRMRouteParser('espocrm')
        endpoints, rels = parser.parse_all_routes()
        if endpoints:
            n, r = graph.store_batch(endpoints, rels)
            logger.info(f"Created {n} endpoints, {r} relationships")
            print(f"   Created {n} endpoints, {r} relationships")
    except Exception as e:
        logger.error(f"Failed to index endpoints: {e}")
        print(f"   Error indexing endpoints: {e}")
    
    # Index PHP files
    indexer.index_php_files()
    
    # Index JavaScript files
    indexer.index_javascript_files()
    
    # Cross-link
    logger.info("Starting cross-linking...")
    print("\n🔗 Cross-linking...")
    try:
        linker = CrossLinker(graph)
        links = linker.link_all()
        # link_all() returns an integer count, not a list
        if isinstance(links, int):
            logger.info(f"Created {links} cross-language links")
            print(f"   Created {links} cross-language links")
        else:
            logger.info(f"Created {len(links)} cross-language links")
            print(f"   Created {len(links)} cross-language links")
    except Exception as e:
        logger.error(f"Failed to cross-link: {e}")
        print(f"   Error cross-linking: {e}")
    
    # Report
    logger.info("Generating statistics...")
    print("\n" + "=" * 70)
    print("  RESULTS")
    print("=" * 70)
    
    try:
        stats = {
            'PHP Classes': graph.query("MATCH (n:Symbol) WHERE n.kind='class' AND n._language='php' RETURN count(n) as c"),
            'JS Functions': graph.query("MATCH (n:Symbol) WHERE n.kind='function' AND n._language='javascript' RETURN count(n) as c"),
            'Endpoints': graph.query("MATCH (n:Endpoint) RETURN count(n) as c"),
            'Directories': graph.query("MATCH (n:Symbol) WHERE n.kind='directory' RETURN count(n) as c"),
            'EXTENDS': graph.query("MATCH ()-[r:EXTENDS]->() RETURN count(r) as c"),
            'CALLS': graph.query("MATCH ()-[r:CALLS]->() RETURN count(r) as c"),
            'CONTAINS': graph.query("MATCH ()-[r:CONTAINS]->() RETURN count(r) as c")
        }
        
        for key, result in stats.items():
            count = result[0]['c'] if result else 0
            logger.info(f"{key}: {count}")
            print(f"  {key}: {count}")
    except Exception as e:
        logger.error(f"Failed to generate statistics: {e}")
        print(f"  Error generating statistics: {e}")
    
    elapsed = time.time() - overall_start
    logger.info(f"Indexing completed in {elapsed:.1f} seconds")
    print(f"\n⏱️  Total time: {elapsed:.1f} seconds")
    print(f"📝 Log file: logs/espocrm_indexing.log")
    print("✅ Complete!")


if __name__ == '__main__':
    # Allow batch size and log level to be passed as command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Optimized EspoCRM Indexing')
    parser.add_argument('--batch-size', type=int, default=100,
                        help='Batch size for database operations (default: 100)')
    parser.add_argument('--log-level', type=str, default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Logging level (default: INFO)')
    args = parser.parse_args()
    
    index_complete_optimized(args.batch_size, args.log_level)