#!/usr/bin/env python3
"""
Neo4j Database Cleaner Tool
Safely cleans all data from Neo4j database while preserving the database structure.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neo4j import GraphDatabase
import yaml
from typing import Dict, Any
import argparse
from datetime import datetime


class Neo4jCleaner:
    def __init__(self, config_path: str = "memory.yaml"):
        self.config = self._load_config(config_path)
        self.driver = None

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config

    def connect(self):
        """Connect to Neo4j database."""
        neo4j_config = self.config.get('neo4j', {})
        uri = neo4j_config.get('uri', 'bolt://localhost:7687')
        username = neo4j_config.get('username', 'neo4j')
        password = neo4j_config.get('password', 'password')

        print(f"Connecting to Neo4j at {uri}...")
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        self.driver.verify_connectivity()
        print("✓ Connected successfully")

    def get_statistics(self) -> Dict[str, int]:
        """Get current database statistics."""
        stats = {}
        with self.driver.session() as session:
            # Count nodes
            result = session.run("MATCH (n) RETURN count(n) as count")
            stats['total_nodes'] = result.single()['count']

            # Count relationships
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            stats['total_relationships'] = result.single()['count']

            # Count by node labels
            result = session.run("""
                MATCH (n)
                UNWIND labels(n) as label
                RETURN label, count(*) as count
                ORDER BY count DESC
            """)
            stats['nodes_by_label'] = {record['label']: record['count'] for record in result}

            # Count by relationship types
            result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as type, count(*) as count
                ORDER BY count DESC
            """)
            stats['relationships_by_type'] = {record['type']: record['count'] for record in result}

        return stats

    def clean_database(self, batch_size: int = 10000):
        """Clean all data from the database in batches."""
        print("\n⚠️  WARNING: This will delete ALL data from the Neo4j database!")

        # Show current statistics
        stats = self.get_statistics()
        print(f"\nCurrent database statistics:")
        print(f"  Total nodes: {stats['total_nodes']:,}")
        print(f"  Total relationships: {stats['total_relationships']:,}")

        if stats['nodes_by_label']:
            print("\n  Nodes by label:")
            for label, count in stats['nodes_by_label'].items():
                print(f"    {label}: {count:,}")

        if stats['relationships_by_type']:
            print("\n  Relationships by type:")
            for rel_type, count in stats['relationships_by_type'].items():
                print(f"    {rel_type}: {count:,}")

        if stats['total_nodes'] == 0:
            print("\n✓ Database is already empty")
            return

        # Confirm deletion
        response = input("\nAre you sure you want to delete all this data? (yes/no): ")
        if response.lower() != 'yes':
            print("Operation cancelled")
            return

        print(f"\nCleaning database (batch size: {batch_size})...")
        start_time = datetime.now()

        with self.driver.session() as session:
            # First, delete all relationships in batches
            if stats['total_relationships'] > 0:
                print("  Deleting relationships...")
                deleted_rels = 0
                while True:
                    result = session.run(f"""
                        MATCH ()-[r]->()
                        WITH r LIMIT {batch_size}
                        DELETE r
                        RETURN count(r) as deleted
                    """)
                    batch_deleted = result.single()['deleted']
                    if batch_deleted == 0:
                        break
                    deleted_rels += batch_deleted
                    print(f"    Deleted {deleted_rels:,} / {stats['total_relationships']:,} relationships", end='\r')
                print(f"  ✓ Deleted {deleted_rels:,} relationships total                    ")

            # Then delete all nodes in batches
            if stats['total_nodes'] > 0:
                print("  Deleting nodes...")
                deleted_nodes = 0
                while True:
                    result = session.run(f"""
                        MATCH (n)
                        WITH n LIMIT {batch_size}
                        DETACH DELETE n
                        RETURN count(n) as deleted
                    """)
                    batch_deleted = result.single()['deleted']
                    if batch_deleted == 0:
                        break
                    deleted_nodes += batch_deleted
                    print(f"    Deleted {deleted_nodes:,} / {stats['total_nodes']:,} nodes", end='\r')
                print(f"  ✓ Deleted {deleted_nodes:,} nodes total                    ")

            # Drop all indexes and constraints (optional)
            print("  Checking indexes and constraints...")
            result = session.run("SHOW INDEXES")
            indexes = list(result)
            if indexes:
                print(f"    Found {len(indexes)} indexes (keeping them)")

            result = session.run("SHOW CONSTRAINTS")
            constraints = list(result)
            if constraints:
                print(f"    Found {len(constraints)} constraints (keeping them)")

        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\n✓ Database cleaned successfully in {elapsed:.2f} seconds")

        # Verify cleaning
        final_stats = self.get_statistics()
        print(f"\nFinal verification:")
        print(f"  Nodes remaining: {final_stats['total_nodes']}")
        print(f"  Relationships remaining: {final_stats['total_relationships']}")

    def close(self):
        """Close database connection."""
        if self.driver:
            self.driver.close()
            print("Connection closed")


def main():
    parser = argparse.ArgumentParser(description='Clean Neo4j database')
    parser.add_argument('--config', default='memory.yaml', help='Path to configuration file')
    parser.add_argument('--batch-size', type=int, default=10000, help='Batch size for deletion')
    parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')
    args = parser.parse_args()

    cleaner = Neo4jCleaner(args.config)

    try:
        cleaner.connect()

        if args.force:
            print("Force mode enabled - skipping confirmation")
            # Temporarily override input
            import builtins
            original_input = builtins.input
            builtins.input = lambda _: "yes"
            cleaner.clean_database(args.batch_size)
            builtins.input = original_input
        else:
            cleaner.clean_database(args.batch_size)

    except Exception as e:
        print(f"Error: {e}")
        return 1
    finally:
        cleaner.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())