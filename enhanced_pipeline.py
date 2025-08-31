#!/usr/bin/env python3
"""Enhanced Code Graph Pipeline - Complete implementation with Symbol Table"""

import argparse
import logging
import sys
from pathlib import Path
import time
import json

from symbol_table import SymbolTable
from parsers.php_enhanced import PHPSymbolCollector
from parsers.php_reference_resolver import PHPReferenceResolver
from plugins.framework.laravel_plugin import LaravelPlugin
from neo4j_integration.batch_writer import Neo4jBatchWriter, Neo4jConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EnhancedCodeGraphPipeline:
    """Complete pipeline for building enhanced code graph"""
    
    def __init__(self, project_path: str, db_path: str = ".cache/symbols.db"):
        self.project_path = Path(project_path)
        self.db_path = db_path
        self.symbol_table = SymbolTable(db_path)
        self.stats = {}
        
    def run_full_pipeline(self, neo4j_config: Neo4jConfig = None) -> Dict:
        """Run the complete pipeline"""
        logger.info(f"Starting enhanced code graph pipeline for {self.project_path}")
        start_time = time.time()
        
        try:
            # Pass 1: Symbol Collection
            logger.info("=" * 60)
            logger.info("PASS 1: Symbol Collection")
            logger.info("=" * 60)
            self._run_symbol_collection()
            
            # Pass 2: Reference Resolution
            logger.info("=" * 60)
            logger.info("PASS 2: Reference Resolution")
            logger.info("=" * 60)
            self._run_reference_resolution()
            
            # Pass 3: Framework Analysis (if applicable)
            logger.info("=" * 60)
            logger.info("PASS 3: Framework Analysis")
            logger.info("=" * 60)
            self._run_framework_analysis()
            
            # Export to Neo4j
            if neo4j_config:
                logger.info("=" * 60)
                logger.info("EXPORT: Writing to Neo4j")
                logger.info("=" * 60)
                self._export_to_neo4j(neo4j_config)
            
            # Calculate final statistics
            self.stats['total_duration'] = time.time() - start_time
            self.stats['symbol_table'] = self.symbol_table.get_stats()
            
            logger.info("=" * 60)
            logger.info("Pipeline complete!")
            logger.info(f"Total time: {self.stats['total_duration']:.2f} seconds")
            logger.info(f"Statistics: {json.dumps(self.stats, indent=2)}")
            
            return self.stats
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            raise
        
    def _run_symbol_collection(self) -> None:
        """Pass 1: Collect all symbols"""
        start_time = time.time()
        
        collector = PHPSymbolCollector(self.symbol_table)
        collector.parse_directory(str(self.project_path))
        
        self.stats['pass1_duration'] = time.time() - start_time
        
        stats = self.symbol_table.get_stats()
        logger.info(f"Pass 1 complete in {self.stats['pass1_duration']:.2f}s")
        logger.info(f"Collected {stats['total_symbols']} symbols from {stats['files_parsed']} files")
        
    def _run_reference_resolution(self) -> None:
        """Pass 2: Resolve all references"""
        start_time = time.time()
        
        resolver = PHPReferenceResolver(self.symbol_table)
        resolver.resolve_directory(str(self.project_path))
        
        self.stats['pass2_duration'] = time.time() - start_time
        
        stats = self.symbol_table.get_stats()
        logger.info(f"Pass 2 complete in {self.stats['pass2_duration']:.2f}s")
        logger.info(f"Resolved {stats['total_references']} references")
        
        # Report unresolved references
        unresolved = resolver.resolver.get_unresolved_report()
        if unresolved:
            total_unresolved = sum(len(refs) for refs in unresolved.values())
            logger.warning(f"Found {total_unresolved} unresolved references")
            self.stats['unresolved_references'] = unresolved
    
    def _run_framework_analysis(self) -> None:
        """Pass 3: Analyze framework-specific patterns"""
        start_time = time.time()
        
        # Check if it's a Laravel project
        if self._is_laravel_project():
            logger.info("Detected Laravel project - running framework analysis")
            
            laravel_plugin = LaravelPlugin(self.symbol_table)
            laravel_plugin.analyze_project(str(self.project_path))
            
            self.stats['framework'] = 'Laravel'
            self.stats['pass3_duration'] = time.time() - start_time
            
            logger.info(f"Pass 3 complete in {self.stats['pass3_duration']:.2f}s")
            logger.info(f"Analyzed Laravel patterns")
        else:
            logger.info("No framework detected - skipping Pass 3")
            self.stats['framework'] = None
            self.stats['pass3_duration'] = 0
    
    def _is_laravel_project(self) -> bool:
        """Check if this is a Laravel project"""
        markers = [
            'artisan',
            'composer.json',
            'app/Http/Kernel.php'
        ]
        
        for marker in markers:
            if not (self.project_path / marker).exists():
                return False
        
        # Check composer.json
        composer_file = self.project_path / 'composer.json'
        try:
            with open(composer_file) as f:
                composer = json.load(f)
                require = composer.get('require', {})
                return 'laravel/framework' in require
        except:
            return False
    
    def _export_to_neo4j(self, config: Neo4jConfig) -> None:
        """Export to Neo4j database"""
        start_time = time.time()
        
        writer = Neo4jBatchWriter(self.symbol_table, config)
        
        try:
            writer.connect()
            export_stats = writer.export_to_neo4j()
            
            self.stats['neo4j_export'] = export_stats
            self.stats['export_duration'] = time.time() - start_time
            
            # Get Neo4j statistics
            neo4j_stats = writer.get_statistics()
            self.stats['neo4j_stats'] = neo4j_stats
            
            logger.info(f"Export complete in {self.stats['export_duration']:.2f}s")
            logger.info(f"Created {export_stats['nodes_created']} nodes and {export_stats['relationships_created']} relationships")
            
        finally:
            writer.close()
    
    def query_code_graph(self, query: str) -> List[Dict]:
        """Query the code graph using natural language"""
        # This would integrate with the query engine
        # For now, return a placeholder
        logger.info(f"Query: {query}")
        
        # Example queries that could be translated to Cypher
        example_queries = {
            "how is email sent": """
                MATCH path = (route:Symbol)-[:ROUTES_TO_METHOD]->(method:Symbol)-[:CALLS*1..5]->(target:Symbol)
                WHERE route.metadata.laravel_type = 'route' 
                AND (target.name CONTAINS 'mail' OR target.name CONTAINS 'email')
                RETURN path
                LIMIT 10
            """,
            "what extends Model": """
                MATCH (class:Symbol {type: 'class'})-[:EXTENDS]->(parent:Symbol)
                WHERE parent.name CONTAINS 'Model'
                RETURN class.name, class.file_path
            """,
            "find all controllers": """
                MATCH (controller:Symbol {type: 'class'})
                WHERE controller.name CONTAINS 'Controller'
                RETURN controller.name, controller.file_path
            """
        }
        
        return []


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Enhanced Code Graph Pipeline')
    parser.add_argument('project_path', help='Path to the project to analyze')
    parser.add_argument('--db-path', default='.cache/symbols.db', help='Path to symbol table database')
    parser.add_argument('--neo4j-uri', default='bolt://localhost:7687', help='Neo4j URI')
    parser.add_argument('--neo4j-user', default='neo4j', help='Neo4j username')
    parser.add_argument('--neo4j-password', default='password', help='Neo4j password')
    parser.add_argument('--neo4j-database', default='neo4j', help='Neo4j database')
    parser.add_argument('--batch-size', type=int, default=1000, help='Batch size for Neo4j writes')
    parser.add_argument('--skip-neo4j', action='store_true', help='Skip Neo4j export')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create pipeline
    pipeline = EnhancedCodeGraphPipeline(args.project_path, args.db_path)
    
    # Configure Neo4j if not skipped
    neo4j_config = None
    if not args.skip_neo4j:
        neo4j_config = Neo4jConfig(
            uri=args.neo4j_uri,
            username=args.neo4j_user,
            password=args.neo4j_password,
            database=args.neo4j_database,
            batch_size=args.batch_size
        )
    
    # Run pipeline
    try:
        stats = pipeline.run_full_pipeline(neo4j_config)
        
        # Save statistics to file
        stats_file = Path('.cache/pipeline_stats.json')
        stats_file.parent.mkdir(exist_ok=True)
        with open(stats_file, 'w') as f:
            json.dump(stats, f, indent=2, default=str)
        
        logger.info(f"Statistics saved to {stats_file}")
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()