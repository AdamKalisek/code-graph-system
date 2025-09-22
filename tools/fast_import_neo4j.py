#!/usr/bin/env python3
"""
Fast Neo4j Import Tool
Optimized import using batch operations and proper indexing
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neo4j import GraphDatabase
import yaml
import sqlite3
import json
from typing import Dict, Any, List
import argparse
from datetime import datetime
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/neo4j_import.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class FastNeo4jImporter:
    def __init__(self, config_path: str = "memory.yaml"):
        self.config = self._load_config(config_path)
        self.driver = None
        self.batch_size = 5000

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

        logger.info(f"Connecting to Neo4j at {uri}...")
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        self.driver.verify_connectivity()
        logger.info("✓ Connected successfully")

    def create_indexes(self):
        """Create indexes for better performance."""
        logger.info("Creating indexes...")
        with self.driver.session() as session:
            indexes = [
                "CREATE INDEX IF NOT EXISTS FOR (n:File) ON (n.path)",
                "CREATE INDEX IF NOT EXISTS FOR (n:Directory) ON (n.path)",
                "CREATE INDEX IF NOT EXISTS FOR (n:PHPClass) ON (n.name)",
                "CREATE INDEX IF NOT EXISTS FOR (n:PHPMethod) ON (n.name)",
                "CREATE INDEX IF NOT EXISTS FOR (n:PHPSymbol) ON (n.id)",
                "CREATE INDEX IF NOT EXISTS FOR (n:JSSymbol) ON (n.id)",
                "CREATE INDEX IF NOT EXISTS FOR (n:JSModule) ON (n.path)",
            ]
            for index_query in indexes:
                try:
                    session.run(index_query)
                    logger.info(f"  ✓ {index_query.split('(n:')[1].split(')')[0]} index")
                except Exception as e:
                    logger.warning(f"  ⚠ Index may already exist: {e}")

    def import_from_sqlite(self, db_path: str):
        """Import data from SQLite database to Neo4j."""
        if not Path(db_path).exists():
            logger.error(f"Database {db_path} not found")
            return

        logger.info(f"Starting import from {db_path}...")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        start_time = datetime.now()

        # Import symbols as nodes
        logger.info("Phase 1: Importing symbols as nodes...")
        cursor.execute("""
            SELECT id, name, type, file_path, line_number, namespace, metadata
            FROM symbols
        """)

        symbols = []
        for row in cursor.fetchall():
            metadata = json.loads(row['metadata']) if row['metadata'] else {}

            # Determine node label based on type
            label = self._get_node_label(row['type'])

            symbol = {
                'id': row['id'],
                'name': row['name'] or 'unnamed',
                'type': row['type'],
                'file': row['file_path'] or '',
                'line': row['line_number'] or 0,
                'namespace': row['namespace'] or ''
            }

            # Add metadata fields
            for key, value in metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    symbol[key] = value

            symbols.append((label, symbol))

            if len(symbols) >= self.batch_size:
                self._batch_create_nodes(symbols)
                symbols = []

        if symbols:
            self._batch_create_nodes(symbols)

        # Import file structure
        logger.info("Phase 2: Importing file structure...")
        cursor.execute("""
            SELECT DISTINCT file_path
            FROM symbols
            WHERE file_path IS NOT NULL
        """)

        files = []
        dirs_seen = set()

        for row in cursor.fetchall():
            file_path = row['file_path']
            files.append({
                'path': file_path,
                'name': Path(file_path).name
            })

            # Add directory hierarchy
            parts = Path(file_path).parts[:-1]
            for i in range(len(parts)):
                dir_path = '/'.join(parts[:i+1])
                if dir_path not in dirs_seen:
                    dirs_seen.add(dir_path)

            if len(files) >= self.batch_size:
                self._batch_create_files(files)
                files = []

        if files:
            self._batch_create_files(files)

        # Create directories
        if dirs_seen:
            self._batch_create_directories(list(dirs_seen))

        # Import references as relationships
        logger.info("Phase 3: Importing relationships...")
        cursor.execute("""
            SELECT source_id, target_id, reference_type
            FROM symbol_references
        """)

        relationships = []
        for row in cursor.fetchall():
            relationships.append({
                'source_id': row['source_id'],
                'target_id': row['target_id'],
                'type': row['reference_type']
            })

            if len(relationships) >= self.batch_size:
                self._batch_create_relationships(relationships)
                relationships = []

        if relationships:
            self._batch_create_relationships(relationships)

        conn.close()

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"✓ Import completed in {elapsed:.2f} seconds")

    def _get_node_label(self, symbol_type: str) -> str:
        """Map symbol type to Neo4j node label."""
        type_map = {
            'class': 'PHPClass',
            'method': 'PHPMethod',
            'function': 'PHPFunction',
            'property': 'PHPProperty',
            'constant': 'PHPConstant',
            'interface': 'PHPInterface',
            'trait': 'PHPTrait',
            'namespace': 'PHPNamespace',
            'js_module': 'JSModule',
            'js_class': 'JSClass',
            'js_function': 'JSFunction',
            'js_method': 'JSMethod',
            'js_variable': 'JSVariable',
        }
        return type_map.get(symbol_type, 'PHPSymbol')

    def _batch_create_nodes(self, symbols: List[tuple]):
        """Create nodes in batches."""
        # Group by label
        by_label = {}
        for label, props in symbols:
            if label not in by_label:
                by_label[label] = []
            by_label[label].append(props)

        with self.driver.session() as session:
            for label, nodes in by_label.items():
                query = f"""
                    UNWIND $nodes as node
                    CREATE (n:{label})
                    SET n = node
                """
                session.run(query, nodes=nodes)
                logger.info(f"  Created {len(nodes)} {label} nodes")

    def _batch_create_files(self, files: List[Dict]):
        """Create file nodes in batch."""
        with self.driver.session() as session:
            query = """
                UNWIND $files as file
                CREATE (n:File {path: file.path, name: file.name})
            """
            session.run(query, files=files)
            logger.info(f"  Created {len(files)} File nodes")

    def _batch_create_directories(self, directories: List[str]):
        """Create directory nodes in batch."""
        dirs_data = [{'path': d, 'name': Path(d).name} for d in directories]
        with self.driver.session() as session:
            query = """
                UNWIND $dirs as dir
                CREATE (n:Directory {path: dir.path, name: dir.name})
            """
            session.run(query, dirs=dirs_data)
            logger.info(f"  Created {len(dirs_data)} Directory nodes")

    def _batch_create_relationships(self, relationships: List[Dict]):
        """Create relationships in batches."""
        # Group by type
        by_type = {}
        for rel in relationships:
            rel_type = rel['type']
            if rel_type not in by_type:
                by_type[rel_type] = []
            by_type[rel_type].append(rel)

        with self.driver.session() as session:
            for rel_type, rels in by_type.items():
                query = f"""
                    UNWIND $rels as rel
                    MATCH (s) WHERE s.id = rel.source_id
                    MATCH (t) WHERE t.id = rel.target_id
                    CREATE (s)-[r:{rel_type}]->(t)
                """
                try:
                    session.run(query, rels=rels)
                    logger.info(f"  Created {len(rels)} {rel_type} relationships")
                except Exception as e:
                    logger.error(f"  Error creating {rel_type}: {e}")

    def verify_import(self):
        """Verify the import results."""
        logger.info("📊 Import Verification:")
        with self.driver.session() as session:
            # Count nodes
            result = session.run("MATCH (n) RETURN count(n) as count")
            total_nodes = result.single()['count']
            logger.info(f"  Total nodes: {total_nodes:,}")

            # Count by label
            result = session.run("""
                MATCH (n)
                RETURN DISTINCT labels(n) as labels, count(*) as count
                ORDER BY count DESC
                LIMIT 10
            """)
            logger.info("  Node distribution:")
            for record in result:
                logger.info(f"    {record['labels']}: {record['count']:,}")

            # Count relationships
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            total_rels = result.single()['count']
            logger.info(f"  Total relationships: {total_rels:,}")

            # Count by type
            result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as type, count(*) as count
                ORDER BY count DESC
                LIMIT 10
            """)
            logger.info("  Relationship distribution:")
            for record in result:
                logger.info(f"    {record['type']}: {record['count']:,}")

    def close(self):
        """Close database connection."""
        if self.driver:
            self.driver.close()


def main():
    parser = argparse.ArgumentParser(description='Fast Neo4j import from SQLite')
    parser.add_argument('--config', default='memory.yaml', help='Path to configuration file')
    parser.add_argument('--db', help='SQLite database path (overrides config)')
    parser.add_argument('--clean', action='store_true', help='Clean Neo4j before import')
    args = parser.parse_args()

    importer = FastNeo4jImporter(args.config)

    try:
        importer.connect()

        if args.clean:
            logger.info("Cleaning database first...")
            from clean_neo4j import Neo4jCleaner
            cleaner = Neo4jCleaner(args.config)
            cleaner.driver = importer.driver
            cleaner.clean_database(batch_size=1000)

        importer.create_indexes()

        # Determine database path
        db_path = args.db
        if not db_path:
            storage = importer.config.get('storage', {})
            db_path = storage.get('sqlite', 'data/espocrm.db')

        importer.import_from_sqlite(db_path)
        importer.verify_import()

    except Exception as e:
        logger.error(f"Error: {e}")
        return 1
    finally:
        importer.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())