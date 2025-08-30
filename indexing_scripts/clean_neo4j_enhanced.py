#!/usr/bin/env python3
"""
Enhanced Neo4j Database Cleaner
- Removes all nodes and relationships
- Cleans up indexes and constraints
- Provides logging
- Offers batch deletion for large databases
"""

import sys
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime

sys.path.append('.')

from code_graph_system.core.graph_store import FederatedGraphStore

def setup_logging(log_level='INFO'):
    """Setup logging configuration."""
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = log_dir / f'neo4j_clean_{timestamp}.log'
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def clean_database(batch_size=10000, clean_schema=False, force=False):
    """
    Remove all nodes and relationships from Neo4j
    
    Args:
        batch_size: Number of nodes to delete per batch (for large databases)
        clean_schema: Whether to also drop indexes and constraints
        force: Skip confirmation prompt
    """
    logger = setup_logging()
    
    print("=" * 70)
    print("  ENHANCED NEO4J DATABASE CLEANUP")
    print("=" * 70)
    print(f"  Started: {datetime.now()}")
    print(f"  Batch size: {batch_size}")
    print(f"  Clean schema: {clean_schema}")
    print("=" * 70)
    
    logger.info("Starting Neo4j database cleanup")
    
    try:
        # Connect to Neo4j
        print("\n🔌 Connecting to Neo4j...")
        logger.info("Connecting to Neo4j at bolt://localhost:7688")
        
        graph = FederatedGraphStore(
            'bolt://localhost:7688',
            ('neo4j', 'password123'),
            {'federation': {'mode': 'unified'}}
        )
        logger.info("Successfully connected to Neo4j")
        
        # Count existing data
        print("\n📊 Current database state:")
        node_count = graph.query("MATCH (n) RETURN count(n) as count")[0]['count']
        rel_count = graph.query("MATCH ()-[r]->() RETURN count(r) as count")[0]['count']
        
        # Get index and constraint count if cleaning schema
        if clean_schema:
            indexes = graph.query("SHOW INDEXES")
            constraints = graph.query("SHOW CONSTRAINTS")
            index_count = len(indexes) if indexes else 0
            constraint_count = len(constraints) if constraints else 0
            
            print(f"   Nodes: {node_count:,}")
            print(f"   Relationships: {rel_count:,}")
            print(f"   Indexes: {index_count}")
            print(f"   Constraints: {constraint_count}")
            
            logger.info(f"Database state: {node_count} nodes, {rel_count} relationships, "
                       f"{index_count} indexes, {constraint_count} constraints")
        else:
            print(f"   Nodes: {node_count:,}")
            print(f"   Relationships: {rel_count:,}")
            logger.info(f"Database state: {node_count} nodes, {rel_count} relationships")
        
        if node_count == 0 and rel_count == 0:
            print("\n✅ Database is already empty!")
            logger.info("Database is already empty, nothing to clean")
            return
        
        # Confirmation prompt (unless forced)
        if not force:
            print(f"\n⚠️  WARNING: This will delete {node_count:,} nodes and {rel_count:,} relationships!")
            response = input("Are you sure you want to continue? (yes/no): ")
            if response.lower() != 'yes':
                print("❌ Cleanup cancelled")
                logger.info("Cleanup cancelled by user")
                return
        
        # Clean nodes and relationships
        print("\n🧹 Cleaning database...")
        start_time = time.time()
        
        if node_count > batch_size:
            # Batch deletion for large databases
            print(f"   Large database detected, using batch deletion...")
            logger.info(f"Using batch deletion with batch size {batch_size}")
            
            deleted = 0
            while True:
                # Delete nodes in batches
                result = graph.graph.run(
                    f"MATCH (n) WITH n LIMIT {batch_size} DETACH DELETE n RETURN count(n) as deleted"
                ).data()
                
                batch_deleted = result[0]['deleted'] if result else 0
                if batch_deleted == 0:
                    break
                    
                deleted += batch_deleted
                logger.debug(f"Deleted batch: {batch_deleted} nodes")
                print(f"   Deleted {deleted:,}/{node_count:,} nodes ({deleted*100/node_count:.1f}%)")
                
                # Small delay to avoid overwhelming the database
                if deleted < node_count:
                    time.sleep(0.1)
        else:
            # Single deletion for small databases
            logger.info("Using single deletion query")
            graph.graph.run("MATCH (n) DETACH DELETE n")
        
        # Clean schema if requested
        if clean_schema:
            print("\n🔧 Cleaning schema...")
            logger.info("Cleaning indexes and constraints")
            
            # Drop all indexes
            if indexes:
                for index in indexes:
                    try:
                        index_name = index.get('name', '')
                        if index_name:
                            graph.graph.run(f"DROP INDEX {index_name}")
                            logger.debug(f"Dropped index: {index_name}")
                    except Exception as e:
                        logger.warning(f"Failed to drop index: {e}")
            
            # Drop all constraints
            if constraints:
                for constraint in constraints:
                    try:
                        constraint_name = constraint.get('name', '')
                        if constraint_name:
                            graph.graph.run(f"DROP CONSTRAINT {constraint_name}")
                            logger.debug(f"Dropped constraint: {constraint_name}")
                    except Exception as e:
                        logger.warning(f"Failed to drop constraint: {e}")
        
        # Verify cleanup
        print("\n✅ Verifying cleanup...")
        node_count = graph.query("MATCH (n) RETURN count(n) as count")[0]['count']
        rel_count = graph.query("MATCH ()-[r]->() RETURN count(r) as count")[0]['count']
        
        elapsed = time.time() - start_time
        
        print(f"\n📊 Final database state:")
        print(f"   Nodes: {node_count}")
        print(f"   Relationships: {rel_count}")
        print(f"   Time taken: {elapsed:.1f} seconds")
        
        logger.info(f"Cleanup completed in {elapsed:.1f} seconds")
        logger.info(f"Final state: {node_count} nodes, {rel_count} relationships")
        
        if node_count == 0 and rel_count == 0:
            print("\n🎯 Database successfully cleaned! Ready for fresh indexing!")
            logger.info("Database successfully cleaned")
        else:
            print("\n⚠️  Warning: Some data may remain in the database")
            logger.warning(f"Cleanup incomplete: {node_count} nodes, {rel_count} relationships remain")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        print(f"\n❌ Error: {e}")
        print("\nMake sure Neo4j is running:")
        print("  ./run_neo4j.sh")
        sys.exit(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Clean Neo4j database')
    parser.add_argument('--batch-size', type=int, default=10000,
                        help='Batch size for deletion (default: 10000)')
    parser.add_argument('--clean-schema', action='store_true',
                        help='Also drop indexes and constraints')
    parser.add_argument('--force', action='store_true',
                        help='Skip confirmation prompt')
    parser.add_argument('--log-level', type=str, default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Logging level (default: INFO)')
    
    args = parser.parse_args()
    
    # Set log level
    if args.log_level:
        logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))
    
    clean_database(
        batch_size=args.batch_size,
        clean_schema=args.clean_schema,
        force=args.force
    )