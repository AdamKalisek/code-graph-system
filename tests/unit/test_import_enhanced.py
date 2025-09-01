#!/usr/bin/env python3
"""
Enhanced EspoCRM Import Script with Progressive Testing
Uses the new Symbol Table architecture for complete edge detection
"""

import argparse
import sys
import time
import logging
import json
import psutil
import os
from pathlib import Path
from typing import Dict, List, Any
import shutil

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from enhanced_pipeline import EnhancedCodeGraphPipeline
from neo4j_integration.batch_writer import Neo4jConfig
from symbol_table import SymbolTable

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ProgressiveTestImporter:
    """Progressive test importer with monitoring"""
    
    def __init__(self, espocrm_path: str):
        self.espocrm_path = Path(espocrm_path)
        self.test_batches_dir = Path('test_batches')
        self.stats_history = []
        
        # Neo4j configuration
        self.neo4j_config = Neo4jConfig(
            uri='bolt://localhost:7688',
            username='neo4j',
            password='password123',
            batch_size=1000
        )
        
    def create_test_batches(self) -> Dict[str, Path]:
        """Create test batches of increasing size"""
        logger.info("Creating test batches...")
        
        # Clean and create test batch directory
        if self.test_batches_dir.exists():
            shutil.rmtree(self.test_batches_dir)
        self.test_batches_dir.mkdir()
        
        batches = {}
        
        # Tiny batch: Authentication module (10-20 files)
        tiny_src = self.espocrm_path / 'application/Espo/Core/Authentication'
        if tiny_src.exists():
            tiny_dst = self.test_batches_dir / 'tiny'
            shutil.copytree(tiny_src, tiny_dst)
            batches['tiny'] = tiny_dst
            file_count = len(list(tiny_dst.rglob('*.php')))
            logger.info(f"  Tiny batch: {file_count} PHP files")
        
        # Small batch: Core module (100+ files)
        small_src = self.espocrm_path / 'application/Espo/Core'
        if small_src.exists():
            small_dst = self.test_batches_dir / 'small'
            # Copy first 100 PHP files
            small_dst.mkdir()
            php_files = list(small_src.rglob('*.php'))[:100]
            for file in php_files:
                rel_path = file.relative_to(small_src)
                dst_file = small_dst / rel_path
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, dst_file)
            batches['small'] = small_dst
            logger.info(f"  Small batch: {len(php_files)} PHP files")
        
        # Medium batch: All Core modules (500+ files)
        medium_src = self.espocrm_path / 'application/Espo'
        if medium_src.exists():
            medium_dst = self.test_batches_dir / 'medium'
            # Copy first 500 PHP files
            medium_dst.mkdir()
            php_files = list(medium_src.rglob('*.php'))[:500]
            for file in php_files:
                rel_path = file.relative_to(medium_src)
                dst_file = medium_dst / rel_path
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, dst_file)
            batches['medium'] = medium_dst
            logger.info(f"  Medium batch: {len(php_files)} PHP files")
        
        # Large batch: Full application directory
        large_src = self.espocrm_path / 'application'
        if large_src.exists():
            batches['large'] = large_src  # Use directly, don't copy
            file_count = len(list(large_src.rglob('*.php')))
            logger.info(f"  Large batch: {file_count} PHP files (using source)")
        
        return batches
    
    def clean_environment(self):
        """Clean Neo4j and Symbol Table cache"""
        logger.info("Cleaning environment...")
        
        # Clean Neo4j
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            self.neo4j_config.uri,
            auth=(self.neo4j_config.username, self.neo4j_config.password)
        )
        
        with driver.session() as session:
            result = session.run("MATCH (n) DETACH DELETE n")
            summary = result.consume()
            logger.info(f"  Deleted {summary.counters.nodes_deleted} nodes and {summary.counters.relationships_deleted} relationships")
        
        driver.close()
        
        # Clean Symbol Table cache
        cache_dir = Path('.cache')
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
            logger.info("  Cleaned Symbol Table cache")
        
    def monitor_resources(self) -> Dict[str, Any]:
        """Monitor system resources"""
        process = psutil.Process(os.getpid())
        
        return {
            'memory_mb': process.memory_info().rss / 1024 / 1024,
            'cpu_percent': process.cpu_percent(),
            'open_files': len(process.open_files()),
            'threads': process.num_threads()
        }
    
    def test_batch(self, name: str, path: Path) -> Dict[str, Any]:
        """Test a single batch with monitoring"""
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing {name.upper()} batch: {path}")
        logger.info(f"{'='*60}")
        
        # Record initial state
        start_time = time.time()
        start_resources = self.monitor_resources()
        
        # Clean Symbol Table for fresh test
        cache_db = Path('.cache/symbols.db')
        if cache_db.exists():
            cache_db.unlink()
        
        # Run pipeline
        pipeline = EnhancedCodeGraphPipeline(
            str(path),
            db_path=f'.cache/symbols_{name}.db'
        )
        
        try:
            stats = pipeline.run_full_pipeline(self.neo4j_config)
            
            # Add resource monitoring
            end_resources = self.monitor_resources()
            stats['resources'] = {
                'memory_delta_mb': end_resources['memory_mb'] - start_resources['memory_mb'],
                'peak_memory_mb': end_resources['memory_mb'],
                'cpu_average': end_resources['cpu_percent'],
                'duration': time.time() - start_time
            }
            
            # Validate results
            stats['validation'] = self.validate_import(stats)
            
            logger.info(f"\n✅ {name.upper()} batch completed successfully!")
            self.print_batch_stats(name, stats)
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ {name.upper()} batch failed: {e}")
            import traceback
            traceback.print_exc()
            return {'error': str(e)}
    
    def validate_import(self, stats: Dict) -> Dict[str, bool]:
        """Validate import quality"""
        validation = {}
        
        # Check symbol collection
        validation['symbols_collected'] = stats.get('symbol_table', {}).get('total_symbols', 0) > 0
        
        # Check reference resolution
        total_refs = stats.get('symbol_table', {}).get('total_references', 0)
        validation['references_resolved'] = total_refs > 0
        
        # Check unresolved rate
        unresolved = stats.get('unresolved_references', {})
        total_unresolved = sum(len(refs) for refs in unresolved.values()) if unresolved else 0
        unresolved_rate = (total_unresolved / max(total_refs, 1)) * 100 if total_refs > 0 else 0
        validation['low_unresolved_rate'] = unresolved_rate < 10
        
        # Check Neo4j export
        if 'neo4j_stats' in stats:
            validation['neo4j_export_success'] = stats['neo4j_stats'].get('total_nodes', 0) > 0
        
        # Check performance
        if 'resources' in stats:
            validation['memory_efficient'] = stats['resources']['memory_delta_mb'] < 500
            validation['fast_processing'] = stats['resources']['duration'] < 60
        
        return validation
    
    def print_batch_stats(self, name: str, stats: Dict):
        """Print formatted statistics for a batch"""
        print(f"\n📊 {name.upper()} Batch Statistics:")
        print("─" * 50)
        
        if 'symbol_table' in stats:
            st = stats['symbol_table']
            print(f"  Symbols collected: {st.get('total_symbols', 0):,}")
            print(f"  References found: {st.get('total_references', 0):,}")
            print(f"  Files parsed: {st.get('files_parsed', 0):,}")
            
            # Symbol breakdown
            if any(k.startswith('type_') for k in st):
                print("\n  Symbol Types:")
                for key, value in st.items():
                    if key.startswith('type_'):
                        symbol_type = key.replace('type_', '')
                        print(f"    {symbol_type}: {value:,}")
        
        if 'neo4j_stats' in stats:
            neo = stats['neo4j_stats']
            print(f"\n  Neo4j Export:")
            print(f"    Total nodes: {neo.get('total_nodes', 0):,}")
            print(f"    Total relationships: {neo.get('total_relationships', 0):,}")
            
            # Relationship breakdown
            if 'relationships_by_type' in neo:
                print("\n  Relationship Types:")
                for rel_type, count in neo['relationships_by_type'].items():
                    print(f"    {rel_type}: {count:,}")
        
        if 'resources' in stats:
            res = stats['resources']
            print(f"\n  Performance:")
            print(f"    Duration: {res['duration']:.2f} seconds")
            print(f"    Memory used: {res['memory_delta_mb']:.2f} MB")
            print(f"    Peak memory: {res['peak_memory_mb']:.2f} MB")
            
            # Calculate rates
            if stats.get('symbol_table', {}).get('files_parsed', 0) > 0:
                files_per_sec = stats['symbol_table']['files_parsed'] / res['duration']
                print(f"    Files/second: {files_per_sec:.2f}")
        
        if 'validation' in stats:
            val = stats['validation']
            print(f"\n  Validation:")
            for check, passed in val.items():
                status = "✅" if passed else "❌"
                print(f"    {status} {check.replace('_', ' ').title()}")
        
        print("─" * 50)
    
    def query_test_results(self):
        """Run test queries to validate the graph"""
        logger.info("\n🔍 Running validation queries...")
        
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            self.neo4j_config.uri,
            auth=(self.neo4j_config.username, self.neo4j_config.password)
        )
        
        queries = [
            ("Total nodes", "MATCH (n) RETURN count(n) as count"),
            ("Total relationships", "MATCH ()-[r]->() RETURN count(r) as count"),
            ("Classes extending others", "MATCH (c)-[:EXTENDS]->() RETURN count(c) as count"),
            ("Interfaces implemented", "MATCH ()-[:IMPLEMENTS]->() RETURN count(*) as count"),
            ("Method calls", "MATCH ()-[:CALLS]->() RETURN count(*) as count"),
            ("Class instantiations", "MATCH ()-[:INSTANTIATES]->() RETURN count(*) as count"),
            ("Namespace imports", "MATCH ()-[:IMPORTS]->() RETURN count(*) as count"),
        ]
        
        with driver.session() as session:
            for name, query in queries:
                result = session.run(query)
                count = result.single()['count']
                logger.info(f"  {name}: {count:,}")
        
        driver.close()
    
    def run_progressive_test(self):
        """Run the complete progressive test"""
        logger.info("🚀 Starting Progressive Test Import")
        logger.info("=" * 60)
        
        # Clean environment
        self.clean_environment()
        
        # Create test batches
        batches = self.create_test_batches()
        
        if not batches:
            logger.error("No test batches could be created!")
            return
        
        # Test each batch progressively
        results = {}
        for name in ['tiny', 'small', 'medium']:
            if name in batches:
                results[name] = self.test_batch(name, batches[name])
                
                # Query test after each batch
                self.query_test_results()
                
                # Wait between batches
                time.sleep(2)
        
        # Print summary
        self.print_summary(results)
        
        # Save results to file
        results_file = Path('test_results.json')
        with open(results_file, 'w') as f:
            # Convert non-serializable objects
            clean_results = json.dumps(results, default=str, indent=2)
            f.write(clean_results)
        logger.info(f"\n📝 Results saved to {results_file}")
    
    def print_summary(self, results: Dict):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("📈 PROGRESSIVE TEST SUMMARY")
        print("=" * 60)
        
        for batch_name, stats in results.items():
            if 'error' in stats:
                print(f"\n{batch_name.upper()}: ❌ FAILED - {stats['error']}")
            else:
                validation = stats.get('validation', {})
                all_passed = all(validation.values()) if validation else False
                status = "✅ PASSED" if all_passed else "⚠️ PARTIAL"
                
                print(f"\n{batch_name.upper()}: {status}")
                if 'symbol_table' in stats:
                    print(f"  Symbols: {stats['symbol_table'].get('total_symbols', 0):,}")
                    print(f"  References: {stats['symbol_table'].get('total_references', 0):,}")
                if 'resources' in stats:
                    print(f"  Time: {stats['resources']['duration']:.2f}s")
                    print(f"  Memory: {stats['resources']['memory_delta_mb']:.2f}MB")
        
        print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(description='Progressive test import for EspoCRM')
    parser.add_argument('espocrm_path', help='Path to EspoCRM installation')
    parser.add_argument('--batch', choices=['tiny', 'small', 'medium', 'large'],
                       help='Test only a specific batch')
    parser.add_argument('--skip-clean', action='store_true',
                       help='Skip cleaning the database')
    
    args = parser.parse_args()
    
    # Verify path exists
    if not Path(args.espocrm_path).exists():
        logger.error(f"Path does not exist: {args.espocrm_path}")
        sys.exit(1)
    
    # Run tests
    tester = ProgressiveTestImporter(args.espocrm_path)
    
    if args.batch:
        # Test single batch
        if not args.skip_clean:
            tester.clean_environment()
        
        batches = tester.create_test_batches()
        if args.batch in batches:
            stats = tester.test_batch(args.batch, batches[args.batch])
            tester.query_test_results()
            tester.print_batch_stats(args.batch, stats)
        else:
            logger.error(f"Batch '{args.batch}' not available")
    else:
        # Run full progressive test
        tester.run_progressive_test()


if __name__ == '__main__':
    main()