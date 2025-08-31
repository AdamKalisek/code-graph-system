#!/usr/bin/env python3
"""
Complete EspoCRM Indexer with ALL Enhanced Parsers
Integrates all working parsers for comprehensive code graph
"""

import sys
import time
import logging
from pathlib import Path
from typing import List, Dict, Set
import json
import subprocess
import hashlib

sys.path.append('.')

from code_graph_system.core.graph_store import FederatedGraphStore
from code_graph_system.core.schema import Symbol, Relationship
from plugins.php.plugin import PHPLanguagePlugin
from plugins.javascript.enhanced_parser import JavaScriptEnhancedParser
from plugins.espocrm.formula_parser import FormulaDSLParser

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ComprehensiveEspoCRMIndexer:
    def __init__(self, espocrm_path: str, batch_size: int = 50):
        self.espocrm_path = Path(espocrm_path)
        self.batch_size = batch_size
        
        # Initialize graph store
        self.graph = FederatedGraphStore(
            uri='bolt://localhost:7688',
            auth=('neo4j', 'password123')
        )
        
        # Initialize parsers
        self.php_plugin = PHPLanguagePlugin()
        self.js_parser = JavaScriptEnhancedParser()
        self.formula_parser = FormulaDSLParser()
        
        # Track statistics
        self.stats = {
            'php_files': 0,
            'js_files': 0,
            'nodes': 0,
            'relationships': 0,
            'relationship_types': {}
        }
        
    def index_all(self):
        """Main indexing method"""
        logger.info("=" * 70)
        logger.info("COMPREHENSIVE ESPOCRM INDEXING WITH ALL PARSERS")
        logger.info("=" * 70)
        
        # Clean database first
        self._clean_database()
        
        # Create directory structure
        self._index_directories()
        
        # Index PHP files with enhanced parser
        self._index_php_files()
        
        # Index JavaScript files with API parser
        self._index_javascript_files()
        
        # Index QueryBuilder patterns
        self._index_querybuilder_patterns()
        
        # Index Formula DSL scripts
        self._index_formula_scripts()
        
        # Print final statistics
        self._print_statistics()
        
    def _clean_database(self):
        """Clean the database"""
        logger.info("\n🧹 Cleaning database...")
        try:
            self.graph.query("MATCH (n) DETACH DELETE n")
            logger.info("✅ Database cleaned")
        except Exception as e:
            logger.error(f"❌ Failed to clean database: {e}")
            
    def _index_directories(self):
        """Create directory hierarchy"""
        logger.info("\n📁 Creating directory structure...")
        
        nodes = []
        relationships = []
        dir_nodes = {}
        
        # Add root directory
        root_id = hashlib.md5(str(self.espocrm_path.name).encode()).hexdigest()
        root_node = Symbol(
            name=self.espocrm_path.name,
            qualified_name=self.espocrm_path.name,
            kind='directory',
            plugin_id='indexer'
        )
        root_node.id = root_id
        nodes.append(root_node)
        dir_nodes['.'] = root_id
        
        # Collect all directories
        for path in self.espocrm_path.rglob("*"):
            if path.is_dir() and not path.name.startswith('.') and path.name != '__pycache__':
                rel_path = path.relative_to(self.espocrm_path)
                dir_id = hashlib.md5(str(rel_path).encode()).hexdigest()
                
                node = Symbol(
                    name=path.name,
                    qualified_name=str(rel_path),
                    kind='directory',
                    plugin_id='indexer'
                )
                node.id = dir_id
                nodes.append(node)
                dir_nodes[str(rel_path)] = dir_id
                
        # Create CONTAINS relationships
        for path, node_id in dir_nodes.items():
            parent_path = str(Path(path).parent)
            if parent_path in dir_nodes and parent_path != path:
                rel = Relationship(
                    type='CONTAINS',
                    source_id=dir_nodes[parent_path],
                    target_id=node_id
                )
                relationships.append(rel)
                
        # Store in database
        self.graph.store_batch(nodes, relationships)
        logger.info(f"✅ Created {len(nodes)} directories, {len(relationships)} relationships")
        
    def _index_php_files(self):
        """Index PHP files with enhanced parser"""
        logger.info("\n🐘 Indexing PHP files...")
        
        php_files = list(self.espocrm_path.rglob("*.php"))
        logger.info(f"Found {len(php_files)} PHP files")
        
        for i in range(0, len(php_files), self.batch_size):
            batch = php_files[i:i+self.batch_size]
            self._process_php_batch(batch, i // self.batch_size + 1, 
                                   (len(php_files) + self.batch_size - 1) // self.batch_size)
                                   
    def _process_php_batch(self, files: List[Path], batch_num: int, total_batches: int):
        """Process a batch of PHP files"""
        logger.info(f"  Batch {batch_num}/{total_batches}: Processing {len(files)} files")
        
        all_nodes = []
        all_relationships = []
        
        for file_path in files:
            try:
                # Parse with enhanced parser
                result = self.php_plugin.parse_file(str(file_path))
                
                if result.errors:
                    logger.debug(f"    Parse errors in {file_path.name}: {result.errors}")
                    continue
                    
                # Create file node
                file_id = hashlib.md5(str(file_path).encode()).hexdigest()
                file_node = Symbol(
                    name=file_path.name,
                    qualified_name=str(file_path),
                    kind='file',
                    plugin_id='php'
                )
                file_node.id = file_id
                all_nodes.append(file_node)
                
                # Add file to directory relationship
                parent_dir = file_path.parent.relative_to(self.espocrm_path)
                dir_id = hashlib.md5(str(parent_dir).encode()).hexdigest()
                all_relationships.append(Relationship(
                    type='IN_DIRECTORY',
                    source_id=file_id,
                    target_id=dir_id
                ))
                
                # Add parsed nodes and relationships
                all_nodes.extend(result.nodes)
                all_relationships.extend(result.relationships)
                
                # Update stats
                self.stats['php_files'] += 1
                
            except Exception as e:
                logger.error(f"    Error processing {file_path.name}: {e}")
                
        # Create placeholder nodes for unresolved references
        node_ids = {node.id for node in all_nodes}
        placeholder_nodes = []
        
        for rel in all_relationships:
            if rel.target_id and rel.target_id.startswith('unresolved_'):
                if rel.target_id not in node_ids:
                    placeholder = Symbol(
                        name=rel.metadata.get('target_fqn', rel.target_id) if rel.metadata else rel.target_id,
                        qualified_name=rel.metadata.get('target_fqn', rel.target_id) if rel.metadata else rel.target_id,
                        kind='unresolved',
                        plugin_id='php'
                    )
                    placeholder.id = rel.target_id
                    placeholder_nodes.append(placeholder)
                    node_ids.add(rel.target_id)
                    
        all_nodes.extend(placeholder_nodes)
        
        # Store batch
        if all_nodes:
            self.graph.store_batch(all_nodes, all_relationships)
            self.stats['nodes'] += len(all_nodes)
            self.stats['relationships'] += len(all_relationships)
            
            # Count relationship types
            for rel in all_relationships:
                rel_type = rel.type
                self.stats['relationship_types'][rel_type] = \
                    self.stats['relationship_types'].get(rel_type, 0) + 1
                    
            logger.info(f"    ✅ Stored {len(all_nodes)} nodes, {len(all_relationships)} relationships")
            
    def _index_javascript_files(self):
        """Index JavaScript files with API parser"""
        logger.info("\n🌐 Indexing JavaScript files...")
        
        js_files = list(self.espocrm_path.rglob("*.js"))
        logger.info(f"Found {len(js_files)} JavaScript files")
        
        for i in range(0, len(js_files), self.batch_size):
            batch = js_files[i:i+self.batch_size]
            self._process_js_batch(batch, i // self.batch_size + 1,
                                 (len(js_files) + self.batch_size - 1) // self.batch_size)
                                 
    def _process_js_batch(self, files: List[Path], batch_num: int, total_batches: int):
        """Process a batch of JavaScript files"""
        logger.info(f"  Batch {batch_num}/{total_batches}: Processing {len(files)} files")
        
        all_nodes = []
        all_relationships = []
        
        for file_path in files:
            try:
                # Parse with enhanced JS parser
                result = self.js_parser.parse_file(str(file_path))
                
                if result.errors:
                    logger.debug(f"    Parse errors in {file_path.name}: {result.errors}")
                    continue
                
                # Add all nodes from parser
                all_nodes.extend(result.nodes)
                
                # Add file to directory relationship
                file_id = hashlib.md5(str(file_path).encode()).hexdigest()
                parent_dir = file_path.parent.relative_to(self.espocrm_path)
                dir_id = hashlib.md5(str(parent_dir).encode()).hexdigest()
                all_relationships.append(Relationship(
                    type='IN_DIRECTORY',
                    source_id=file_id,
                    target_id=dir_id
                ))
                
                # Add all relationships from parser
                all_relationships.extend(result.relationships)
                
                self.stats['js_files'] += 1
                
            except Exception as e:
                logger.debug(f"    Error processing {file_path.name}: {e}")
                
        # Store batch
        if all_nodes:
            self.graph.store_batch(all_nodes, all_relationships)
            self.stats['nodes'] += len(all_nodes)
            self.stats['relationships'] += len(all_relationships)
            
            for rel in all_relationships:
                rel_type = rel.type
                self.stats['relationship_types'][rel_type] = \
                    self.stats['relationship_types'].get(rel_type, 0) + 1
                    
            logger.info(f"    ✅ Stored {len(all_nodes)} nodes, {len(all_relationships)} relationships")
            
    def _index_querybuilder_patterns(self):
        """Index QueryBuilder patterns in PHP files"""
        logger.info("\n🔍 Indexing QueryBuilder patterns...")
        
        php_files = list(self.espocrm_path.rglob("*.php"))
        queries_found = 0
        
        for file_path in php_files:
            try:
                # Run QueryBuilder parser
                result = subprocess.run(
                    ['php', 'plugins/php/querybuilder_parser.php', str(file_path)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0 and result.stdout:
                    data = json.loads(result.stdout)
                    queries = data.get('queries', [])
                    
                    if queries:
                        nodes = []
                        relationships = []
                        file_id = hashlib.md5(str(file_path).encode()).hexdigest()
                        
                        for query in queries:
                            # Create query node
                            query_id = hashlib.md5(
                                f"{file_path}:{query['line']}:{json.dumps(query['chain'])}".encode()
                            ).hexdigest()
                            
                            node = Symbol(
                                name=f"Query_{'_'.join([m['method'] for m in query['chain'][:3]])}",
                                qualified_name=f"{file_path}:{query['line']}",
                                kind='query',
                                plugin_id='querybuilder'
                            )
                            node.id = query_id
                            node.metadata = query
                            nodes.append(node)
                            
                            relationships.append(Relationship(
                                type='HAS_QUERY',
                                source_id=file_id,
                                target_id=query_id
                            ))
                            
                            queries_found += 1
                            
                        if nodes:
                            self.graph.store_batch(nodes, relationships)
                            self.stats['nodes'] += len(nodes)
                            self.stats['relationships'] += len(relationships)
                            self.stats['relationship_types']['HAS_QUERY'] = \
                                self.stats['relationship_types'].get('HAS_QUERY', 0) + len(relationships)
                                
            except Exception as e:
                logger.debug(f"    Error parsing queries in {file_path.name}: {e}")
                
        logger.info(f"✅ Found {queries_found} QueryBuilder patterns")
        
    def _index_formula_scripts(self):
        """Index Formula DSL scripts"""
        logger.info("\n📝 Indexing Formula DSL scripts...")
        
        # Look for formula scripts in metadata and custom directories
        formula_locations = [
            self.espocrm_path / 'custom' / 'Espo' / 'Custom' / 'Resources' / 'metadata',
            self.espocrm_path / 'application' / 'Espo' / 'Resources' / 'metadata'
        ]
        
        formulas_found = 0
        
        for location in formula_locations:
            if not location.exists():
                continue
                
            for json_file in location.rglob("*.json"):
                try:
                    with open(json_file, 'r') as f:
                        data = json.load(f)
                        
                    # Look for formula fields in metadata
                    self._extract_formulas_from_metadata(data, json_file, formulas_found)
                    
                except Exception as e:
                    logger.debug(f"    Error reading {json_file}: {e}")
                    
        logger.info(f"✅ Found {formulas_found} Formula scripts")
        
    def _extract_formulas_from_metadata(self, data: dict, source_file: Path, counter: int):
        """Extract formula scripts from metadata"""
        if isinstance(data, dict):
            for key, value in data.items():
                if key in ['formula', 'beforeSaveFormula', 'afterSaveFormula']:
                    # Found a formula script
                    result = self.formula_parser.extract_operations(value)
                    
                    # Create formula node
                    formula_id = hashlib.md5(f"{source_file}:{key}:{value[:50]}".encode()).hexdigest()
                    node = Symbol(
                        name=f"Formula_{key}",
                        qualified_name=f"{source_file}:{key}",
                        kind='formula',
                        plugin_id='formula'
                    )
                    node.id = formula_id
                    node.metadata = result
                    
                    # Store
                    self.graph.store_batch([node], [])
                    self.stats['nodes'] += 1
                    counter += 1
                    
                elif isinstance(value, dict):
                    self._extract_formulas_from_metadata(value, source_file, counter)
                    
    def _print_statistics(self):
        """Print final statistics"""
        logger.info("\n" + "=" * 70)
        logger.info("📊 INDEXING COMPLETE - STATISTICS")
        logger.info("=" * 70)
        
        logger.info(f"\n📈 Totals:")
        logger.info(f"  PHP files indexed: {self.stats['php_files']}")
        logger.info(f"  JavaScript files indexed: {self.stats['js_files']}")
        logger.info(f"  Total nodes created: {self.stats['nodes']}")
        logger.info(f"  Total relationships created: {self.stats['relationships']}")
        
        logger.info(f"\n🔗 Relationship types:")
        for rel_type, count in sorted(self.stats['relationship_types'].items()):
            logger.info(f"  {rel_type}: {count}")
            
        # Query database for verification
        try:
            result = self.graph.query("""
                MATCH ()-[r]->()
                RETURN type(r) as relType, count(r) as count
                ORDER BY count DESC
                LIMIT 10
            """)
            
            logger.info(f"\n✅ Top relationships in database:")
            for record in result:
                logger.info(f"  {record['relType']}: {record['count']}")
                
        except Exception as e:
            logger.error(f"Failed to query database: {e}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Comprehensive EspoCRM Indexer')
    parser.add_argument('--path', type=str, 
                       default='/home/david/Work/Programming/espocrm',
                       help='Path to EspoCRM installation')
    parser.add_argument('--batch-size', type=int, default=50,
                       help='Batch size for processing')
    args = parser.parse_args()
    
    indexer = ComprehensiveEspoCRMIndexer(args.path, args.batch_size)
    indexer.index_all()

if __name__ == '__main__':
    main()