#!/usr/bin/env python3
"""
Fast relationship importer for Neo4j
Imports only the relationships, assuming nodes are already loaded
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neo4j import GraphDatabase
import yaml
import sqlite3
from datetime import datetime
import logging
from collections import defaultdict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/relationships_import.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class RelationshipImporter:
    def __init__(self, config_path: str = "memory.yaml"):
        self.config = self._load_config(config_path)
        self.driver = None
        self.batch_size = 1000

    def _load_config(self, config_path: str) -> dict:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def connect(self):
        neo4j_config = self.config.get('neo4j', {})
        uri = neo4j_config.get('uri', 'bolt://localhost:7687')
        username = neo4j_config.get('username', 'neo4j')
        password = neo4j_config.get('password', 'password')

        logger.info(f"Connecting to Neo4j at {uri}...")
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        self.driver.verify_connectivity()
        logger.info("Connected successfully")

    def import_relationships(self, db_path: str):
        """Import relationships with progress tracking."""
        logger.info(f"Loading relationships from {db_path}...")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get total count
        cursor.execute("SELECT COUNT(*) FROM symbol_references")
        total = cursor.fetchone()[0]
        logger.info(f"Total relationships to import: {total:,}")

        # Get relationships grouped by type
        cursor.execute("""
            SELECT reference_type, COUNT(*) as cnt
            FROM symbol_references
            GROUP BY reference_type
            ORDER BY cnt DESC
        """)
        rel_types = cursor.fetchall()

        logger.info("Relationship distribution:")
        for rel_type, count in rel_types:
            logger.info(f"  {rel_type}: {count:,}")

        start_time = datetime.now()
        imported = 0
        failed = 0

        # Import each relationship type separately for better performance
        for rel_type, type_count in rel_types:
            logger.info(f"\nImporting {rel_type} relationships ({type_count:,} total)...")

            cursor.execute("""
                SELECT source_id, target_id
                FROM symbol_references
                WHERE reference_type = ?
            """, (rel_type,))

            batch = []
            type_imported = 0
            type_failed = 0

            for row in cursor:
                batch.append({
                    'source_id': row[0],
                    'target_id': row[1]
                })

                if len(batch) >= self.batch_size:
                    success, fail = self._create_relationships_batch(rel_type, batch)
                    type_imported += success
                    type_failed += fail
                    imported += success
                    failed += fail

                    if type_imported % 5000 == 0:
                        logger.info(f"  Progress: {type_imported:,}/{type_count:,} ({100*type_imported/type_count:.1f}%)")

                    batch = []

            # Process remaining batch
            if batch:
                success, fail = self._create_relationships_batch(rel_type, batch)
                type_imported += success
                type_failed += fail
                imported += success
                failed += fail

            logger.info(f"  Completed {rel_type}: {type_imported:,} created, {type_failed:,} failed")

        conn.close()

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"\nImport complete!")
        logger.info(f"  Total time: {elapsed:.2f} seconds")
        logger.info(f"  Successfully imported: {imported:,} relationships")
        logger.info(f"  Failed: {failed:,} relationships")
        logger.info(f"  Success rate: {100*imported/(imported+failed):.1f}%")

    def _create_relationships_batch(self, rel_type: str, relationships: list) -> tuple:
        """Create a batch of relationships. Returns (success_count, fail_count)."""
        with self.driver.session() as session:
            # Try optimized query first
            query = f"""
                UNWIND $rels as rel
                MATCH (s {{id: rel.source_id}})
                MATCH (t {{id: rel.target_id}})
                CREATE (s)-[r:{rel_type}]->(t)
                RETURN count(r) as created
            """

            try:
                result = session.run(query, rels=relationships)
                created = result.single()['created']
                return (created, len(relationships) - created)
            except Exception as e:
                # If batch fails, try individual relationships
                success = 0
                for rel in relationships:
                    try:
                        query = f"""
                            MATCH (s {{id: $source_id}})
                            MATCH (t {{id: $target_id}})
                            CREATE (s)-[:{rel_type}]->(t)
                        """
                        session.run(query, source_id=rel['source_id'], target_id=rel['target_id'])
                        success += 1
                    except:
                        pass

                return (success, len(relationships) - success)

    def verify(self):
        """Verify the import."""
        with self.driver.session() as session:
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            total = result.single()['count']
            logger.info(f"\nVerification: {total:,} relationships in Neo4j")

            result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as type, count(*) as count
                ORDER BY count DESC
                LIMIT 10
            """)
            logger.info("Top relationship types:")
            for record in result:
                logger.info(f"  {record['type']}: {record['count']:,}")

    def close(self):
        if self.driver:
            self.driver.close()


def main():
    importer = RelationshipImporter()

    try:
        importer.connect()
        importer.import_relationships('data/espocrm.db')
        importer.verify()
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1
    finally:
        importer.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())