#!/usr/bin/env python3
"""
Ultra-Fast Neo4j Import Tool - Implements advanced optimization strategies
Supports multiple import modes based on use case
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import csv
import yaml
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from neo4j import AsyncGraphDatabase, GraphDatabase
from neo4j.exceptions import TransientError, ClientError
import argparse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UltraFastNeo4jImporter:
    """Ultra-fast Neo4j importer with multiple optimization strategies"""

    def __init__(self, config_path: str = "memory.yaml"):
        self.config = self._load_config(config_path)
        self.neo4j_config = self.config.get('neo4j', {})
        self.uri = self.neo4j_config.get('uri', 'bolt://localhost:7687')
        self.username = self.neo4j_config.get('username', 'neo4j')
        self.password = self.neo4j_config.get('password', 'password')
        self.driver = None
        self.async_driver = None

        # Optimized batch sizes based on GPT-5 recommendations
        self.node_batch_size = 50000  # Increased from 5000
        self.rel_batch_size = 20000   # Optimized for relationships
        self.parallel_workers = 8      # Parallel execution

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def export_to_csv_for_admin_import(self, db_path: str, output_dir: str = "neo4j_import"):
        """
        Export SQLite data to CSV format optimized for neo4j-admin import
        This is the FASTEST method (5-30x faster than API)
        """
        logger.info("Exporting to CSV for neo4j-admin import (fastest method)...")

        Path(output_dir).mkdir(exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Export nodes grouped by type
        node_files = self._export_nodes_to_csv(cursor, output_dir)

        # Export relationships
        rel_files = self._export_relationships_to_csv(cursor, output_dir)

        # Generate import script
        self._generate_admin_import_script(node_files, rel_files, output_dir)

        conn.close()

        logger.info(f"✅ CSV export complete. Files in {output_dir}/")
        logger.info("To import (FASTEST method):")
        logger.info(f"  chmod +x {output_dir}/admin_import.sh")
        logger.info(f"  ./{output_dir}/admin_import.sh")

    def _export_nodes_to_csv(self, cursor, output_dir: str) -> List[str]:
        """Export nodes to CSV files grouped by type"""
        node_files = []

        # Group symbols by type for optimal import
        type_groups = {
            'PHPClass': "type = 'class'",
            'PHPInterface': "type = 'interface'",
            'PHPTrait': "type = 'trait'",
            'PHPMethod': "type = 'method'",
            'PHPFunction': "type = 'function'",
            'PHPProperty': "type = 'property'",
            'JSModule': "id LIKE 'js_%' AND type = 'module'",
            'File': "type = 'file'",
            'Directory': "type = 'directory'"
        }

        for label, condition in type_groups.items():
            query = f"""
                SELECT id, name, type, file_path, line_number, namespace, visibility, metadata
                FROM symbols
                WHERE {condition}
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            if not rows:
                continue

            filename = f"{output_dir}/nodes_{label.lower()}.csv"
            node_files.append(filename)

            with open(filename, 'w', newline='') as csvfile:
                # Header with :ID for neo4j-admin
                fieldnames = ['id:ID', 'name', 'type', 'file_path', 'line_number:int',
                            'namespace', 'visibility', ':LABEL']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for row in rows:
                    writer.writerow({
                        'id:ID': row['id'],
                        'name': row['name'] or '',
                        'type': row['type'],
                        'file_path': row['file_path'] or '',
                        'line_number:int': row['line_number'] or 0,
                        'namespace': row['namespace'] or '',
                        'visibility': row['visibility'] or '',
                        ':LABEL': f'Symbol;{label}'
                    })

            logger.info(f"  Exported {len(rows)} {label} nodes to {filename}")

        return node_files

    def _export_relationships_to_csv(self, cursor, output_dir: str) -> List[str]:
        """Export relationships to CSV files grouped by type"""
        rel_files = []

        cursor.execute("""
            SELECT DISTINCT reference_type
            FROM symbol_references
            ORDER BY reference_type
        """)
        rel_types = [row[0] for row in cursor.fetchall()]

        for rel_type in rel_types:
            cursor.execute("""
                SELECT source_id, target_id, line_number, column_number
                FROM symbol_references
                WHERE reference_type = ?
            """, (rel_type,))

            rows = cursor.fetchall()
            if not rows:
                continue

            filename = f"{output_dir}/rels_{rel_type.lower()}.csv"
            rel_files.append(filename)

            with open(filename, 'w', newline='') as csvfile:
                fieldnames = [':START_ID', ':END_ID', 'line:int', 'column:int', ':TYPE']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for row in rows:
                    writer.writerow({
                        ':START_ID': row[0],
                        ':END_ID': row[1],
                        'line:int': row[2] or 0,
                        'column:int': row[3] or 0,
                        ':TYPE': rel_type
                    })

            logger.info(f"  Exported {len(rows)} {rel_type} relationships")

        return rel_files

    def _generate_admin_import_script(self, node_files: List[str], rel_files: List[str], output_dir: str):
        """Generate shell script for neo4j-admin import"""
        script_path = f"{output_dir}/admin_import.sh"

        with open(script_path, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write("# Ultra-fast Neo4j admin import script\n")
            f.write("# This is 5-30x faster than API-based imports\n\n")

            f.write("DATABASE=neo4j\n")
            f.write("NEO4J_HOME=/var/lib/neo4j\n\n")

            f.write("echo 'Stopping Neo4j for offline import...'\n")
            f.write("sudo systemctl stop neo4j\n\n")

            f.write("echo 'Running neo4j-admin import...'\n")
            f.write("sudo -u neo4j neo4j-admin database import full \\\n")
            f.write(f"  --database=$DATABASE \\\n")
            f.write("  --id-type=STRING \\\n")

            # Add node files
            for nf in node_files:
                f.write(f"  --nodes={nf} \\\n")

            # Add relationship files
            for rf in rel_files:
                f.write(f"  --relationships={rf} \\\n")

            f.write("  --overwrite-destination=true\n\n")

            f.write("echo 'Starting Neo4j...'\n")
            f.write("sudo systemctl start neo4j\n\n")

            f.write("echo 'Waiting for Neo4j to be ready...'\n")
            f.write("sleep 10\n\n")

            f.write("echo 'Creating indexes and constraints...'\n")
            f.write("cypher-shell -u $NEO4J_USER -p $NEO4J_PASSWORD <<EOF\n")
            f.write("CREATE CONSTRAINT IF NOT EXISTS FOR (s:Symbol) REQUIRE s.id IS UNIQUE;\n")
            f.write("CREATE INDEX IF NOT EXISTS FOR (s:Symbol) ON (s.name);\n")
            f.write("CREATE INDEX IF NOT EXISTS FOR (s:Symbol) ON (s.type);\n")
            f.write("CREATE INDEX IF NOT EXISTS FOR (s:Symbol) ON (s.file_path);\n")
            f.write("CALL db.stats.collect();\n")
            f.write("EOF\n\n")

            f.write("echo '✅ Import complete!'\n")

        os.chmod(script_path, 0o755)
        logger.info(f"  Generated import script: {script_path}")

    async def import_with_apoc_parallel(self, db_path: str):
        """
        Import using APOC parallel iterate for online imports (2-6x faster)
        Database stays online during import
        """
        logger.info("Starting APOC parallel import (online, 2-6x faster)...")

        if not self.async_driver:
            self.async_driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password),
                max_connection_pool_size=32  # Increased pool size
            )

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        async with self.async_driver.session() as session:
            # Check for APOC
            try:
                await session.run("RETURN apoc.version()")
            except:
                logger.error("APOC not installed! Install from: https://neo4j.com/labs/apoc/")
                return

            # Clear database
            await self._clear_database_async(session)

            # Create constraints first
            await self._create_constraints_async(session)

            # Import nodes with APOC parallel
            await self._import_nodes_apoc_parallel(session, cursor)

            # Import relationships with APOC parallel
            await self._import_relationships_apoc_parallel(session, cursor)

            # Collect statistics (Neo4j 5.x requires section parameter)
            try:
                await session.run("CALL db.stats.collect('QUERIES')")
            except:
                pass  # Ignore if stats collection fails

        conn.close()
        logger.info("✅ APOC parallel import complete")

    async def _import_nodes_apoc_parallel(self, session, cursor):
        """Import nodes using APOC parallel iterate"""
        logger.info("Importing nodes with APOC parallel...")

        cursor.execute("SELECT * FROM symbols")
        all_symbols = cursor.fetchall()

        # Group by type for better performance
        nodes_by_type = {}
        for symbol in all_symbols:
            symbol_type = symbol['type']
            if symbol_type not in nodes_by_type:
                nodes_by_type[symbol_type] = []

            nodes_by_type[symbol_type].append({
                'id': symbol['id'],
                'name': symbol['name'] or '',
                'type': symbol['type'],
                'file_path': symbol['file_path'] or '',
                'line_number': symbol['line_number'] or 0,
                'namespace': symbol['namespace'] or '',
                'visibility': symbol['visibility'] or ''
            })

        # Import each type in parallel
        for symbol_type, nodes in nodes_by_type.items():
            label = self._get_label_for_type(symbol_type)

            # Use APOC periodic iterate with parallel execution
            query = """
                CALL apoc.periodic.iterate(
                    'UNWIND $nodes AS node RETURN node',
                    'CREATE (n:Symbol:%s) SET n = node',
                    {batchSize: $batchSize, parallel: true, concurrency: $concurrency, params: {nodes: $nodes}}
                ) YIELD batches, total, errorMessages
                RETURN batches, total, errorMessages
            """ % label

            result = await session.run(
                query,
                nodes=nodes,
                batchSize=self.node_batch_size,
                concurrency=self.parallel_workers
            )

            stats = await result.single()
            logger.info(f"  Created {stats['total']} {label} nodes in {stats['batches']} batches")

            if stats['errorMessages']:
                logger.error(f"  Errors: {stats['errorMessages']}")

    async def _import_relationships_apoc_parallel(self, session, cursor):
        """Import relationships using APOC parallel iterate"""
        logger.info("Importing relationships with APOC parallel...")

        cursor.execute("""
            SELECT reference_type, COUNT(*) as count
            FROM symbol_references
            GROUP BY reference_type
        """)
        rel_types = cursor.fetchall()

        for rel_type, count in rel_types:
            cursor.execute("""
                SELECT source_id, target_id, line_number, column_number
                FROM symbol_references
                WHERE reference_type = ?
            """, (rel_type,))

            rels = [
                {
                    'source': row[0],
                    'target': row[1],
                    'line': row[2] or 0,
                    'column': row[3] or 0
                }
                for row in cursor.fetchall()
            ]

            # Use APOC for parallel relationship creation
            query = """
                CALL apoc.periodic.iterate(
                    'UNWIND $rels AS rel RETURN rel',
                    'MATCH (s:Symbol {id: rel.source}), (t:Symbol {id: rel.target})
                     CREATE (s)-[r:%s {line: rel.line, column: rel.column}]->(t)',
                    {batchSize: $batchSize, parallel: true, concurrency: $concurrency, params: {rels: $rels}}
                ) YIELD batches, total, errorMessages
                RETURN batches, total, errorMessages
            """ % rel_type

            result = await session.run(
                query,
                rels=rels,
                batchSize=self.rel_batch_size,
                concurrency=max(4, self.parallel_workers // 2)  # Less concurrency for relationships
            )

            stats = await result.single()
            logger.info(f"  Created {stats['total']} {rel_type} relationships in {stats['batches']} batches")

    def import_with_parallel_bolt(self, db_path: str):
        """
        Optimized Bolt import with parallel workers (2-4x faster)
        Uses async driver with pipelining and large batches
        """
        logger.info("Starting parallel Bolt import (2-4x faster than basic)...")

        asyncio.run(self._import_with_parallel_bolt_async(db_path))

    async def _import_with_parallel_bolt_async(self, db_path: str):
        """Async implementation of parallel Bolt import"""

        if not self.async_driver:
            self.async_driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password),
                max_connection_pool_size=32,
                connection_acquisition_timeout=60.0
            )

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Clear and prepare database
        async with self.async_driver.session() as session:
            await self._clear_database_async(session)
            await self._create_constraints_async(session)

        # Get all data
        cursor.execute("SELECT * FROM symbols")
        all_symbols = list(cursor.fetchall())

        cursor.execute("SELECT * FROM symbol_references")
        all_relationships = list(cursor.fetchall())

        conn.close()

        # Partition data for parallel processing
        symbol_chunks = self._partition_data(all_symbols, self.parallel_workers)
        # Use fewer, larger partitions for relationships to lower contention but
        # still cover the entire dataset. Previously we sliced the partitions
        # which unintentionally dropped roughly half of the relationships.
        rel_worker_count = max(1, self.parallel_workers // 2)
        rel_chunks = self._partition_data(all_relationships, rel_worker_count)

        # Cache the valid symbol ids so we can cheaply filter out relationships
        # that reference nodes we failed to import. This prevents
        # Neo.ClientError.Statement.EntityNotFound errors once we start
        # creating relationships.
        valid_symbol_ids = {
            row['id'] for row in all_symbols
            if row['id']
        }
        missing_ids = len(all_symbols) - len(valid_symbol_ids)
        if missing_ids:
            logger.warning(
                f"Detected {missing_ids} symbols without ids in SQLite export; "
                "relationships pointing to them will be skipped"
            )

        # Import nodes in parallel
        logger.info(f"Importing {len(all_symbols)} nodes with {self.parallel_workers} workers...")
        node_tasks = [
            self._import_node_chunk(chunk, worker_id)
            for worker_id, chunk in enumerate(symbol_chunks)
        ]
        await asyncio.gather(*node_tasks)

        # Import relationships in parallel (with less concurrency to avoid lock contention)
        logger.info(f"Importing {len(all_relationships)} relationships...")
        rel_tasks = [
            self._import_relationship_chunk(chunk, worker_id, valid_symbol_ids)
            for worker_id, chunk in enumerate(rel_chunks)
        ]
        await asyncio.gather(*rel_tasks)

        # Collect statistics
        async with self.async_driver.session() as session:
            try:
                await session.run("CALL db.stats.collect('QUERIES')")
            except:
                pass  # Ignore if stats collection fails

        logger.info("✅ Parallel Bolt import complete")

    def _partition_data(self, data: List, num_partitions: int) -> List[List]:
        """Partition data for parallel processing"""
        chunk_size = len(data) // num_partitions + 1
        return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]

    async def _import_node_chunk(self, symbols: List, worker_id: int):
        """Import a chunk of nodes"""
        async with self.async_driver.session() as session:
            # Group by type
            by_type = {}
            for symbol in symbols:
                label = self._get_label_for_type(dict(symbol)['type'])
                if label not in by_type:
                    by_type[label] = []

                props = {
                    'id': symbol['id'],
                    'name': symbol['name'] or '',
                    'type': symbol['type'],
                    'file_path': symbol['file_path'] or '',
                    'line_number': symbol['line_number'] or 0,
                    'namespace': symbol['namespace'] or '',
                    'visibility': symbol['visibility'] or ''
                }
                by_type[label].append(props)

            # Import each type
            for label, nodes in by_type.items():
                # Process in batches
                for i in range(0, len(nodes), self.node_batch_size):
                    batch = nodes[i:i + self.node_batch_size]

                    query = f"""
                        UNWIND $batch AS props
                        CREATE (n:Symbol:{label})
                        SET n = props
                    """

                    await session.run(query, batch=batch)

                    if i % (self.node_batch_size * 5) == 0:
                        logger.info(f"  Worker {worker_id}: Imported {i}/{len(nodes)} {label} nodes")

    async def _import_relationship_chunk(
        self,
        relationships: List,
        worker_id: int,
        valid_symbol_ids: set[str]
    ):
        """Import a chunk of relationships"""
        async with self.async_driver.session() as session:
            # Group by type
            by_type = {}
            skipped = 0
            for rel in relationships:
                rel_type = rel['reference_type']
                if rel_type not in by_type:
                    by_type[rel_type] = []

                if rel['source_id'] not in valid_symbol_ids or rel['target_id'] not in valid_symbol_ids:
                    skipped += 1
                    continue

                by_type[rel_type].append({
                    'source': rel['source_id'],
                    'target': rel['target_id'],
                    'line': rel['line_number'] or 0,
                    'column': rel['column_number'] or 0
                })

            if skipped:
                logger.warning(
                    f"  Worker {worker_id}: Skipped {skipped} relationships with missing nodes"
                )

            # Import each type
            for rel_type, rels in by_type.items():
                # Process in smaller batches for relationships
                for i in range(0, len(rels), self.rel_batch_size):
                    batch = rels[i:i + self.rel_batch_size]

                    query = f"""
                        UNWIND $batch AS rel
                        MATCH (s:Symbol {{id: rel.source}})
                        MATCH (t:Symbol {{id: rel.target}})
                        CREATE (s)-[r:{rel_type}]->(t)
                        SET r.line = rel.line, r.column = rel.column
                    """

                    try:
                        async def work(tx, batch):
                            result = await tx.run(query, batch=batch)
                            await result.consume()

                        await session.execute_write(work, batch=batch)
                    except TransientError as e:
                        logger.warning(
                            f"  Worker {worker_id}: Deadlock retry exhausted for {rel_type}: {e}")
                    except ClientError as e:
                        logger.warning(
                            f"  Worker {worker_id}: Client error while creating {rel_type}: {e}")
                    except Exception as e:
                        logger.warning(
                            f"  Worker {worker_id}: Failed batch for {rel_type}: {e}")

    def _get_label_for_type(self, symbol_type: str) -> str:
        """Map symbol type to Neo4j label"""
        type_map = {
            'class': 'PHPClass',
            'interface': 'PHPInterface',
            'trait': 'PHPTrait',
            'method': 'PHPMethod',
            'function': 'PHPFunction',
            'property': 'PHPProperty',
            'constant': 'PHPConstant',
            'namespace': 'PHPNamespace',
            'file': 'File',
            'directory': 'Directory',
            'module': 'JSModule'
        }
        return type_map.get(symbol_type, 'PHPSymbol')

    async def _clear_database_async(self, session):
        """Clear database in batches"""
        logger.info("Clearing database...")
        while True:
            result = await session.run("""
                MATCH (n)
                WITH n LIMIT 50000
                DETACH DELETE n
                RETURN COUNT(n) as deleted
            """)
            deleted = (await result.single())['deleted']
            if deleted == 0:
                break
            logger.info(f"  Deleted {deleted} nodes...")

    async def _create_constraints_async(self, session):
        """Create constraints and indexes"""
        logger.info("Creating constraints and indexes...")

        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Symbol) REQUIRE s.id IS UNIQUE",
            "CREATE INDEX IF NOT EXISTS FOR (s:Symbol) ON (s.name)",
            "CREATE INDEX IF NOT EXISTS FOR (s:Symbol) ON (s.type)",
            "CREATE INDEX IF NOT EXISTS FOR (s:Symbol) ON (s.file_path)",
            "CREATE INDEX IF NOT EXISTS FOR (f:File) ON (f.path)",
            "CREATE INDEX IF NOT EXISTS FOR (d:Directory) ON (d.path)"
        ]

        for constraint in constraints:
            try:
                await session.run(constraint)
                logger.info(f"  ✓ {constraint.split('FOR')[1].split('ON')[0].strip()}")
            except Exception as e:
                if "already exists" not in str(e).lower():
                    logger.warning(f"  ⚠ {e}")

    def generate_memory_optimized_config(self, output_file: str = "neo4j_optimized.conf"):
        """Generate optimized Neo4j configuration for bulk imports"""
        logger.info(f"Generating optimized Neo4j configuration...")

        config = """# Optimized Neo4j Configuration for Bulk Imports
# Based on GPT-5 recommendations for maximum performance

# Memory Settings
server.memory.heap.initial_size=16G
server.memory.heap.max_size=32G
server.memory.pagecache.size=48G  # Adjust based on available RAM

# Transaction and Checkpoint Settings (for bulk load)
server.checkpoint.interval.time=1h  # Reduced frequency during import
server.checkpoint.iops.limit=0      # Unlimited IOPS for fast storage
server.tx_log.rotation.size=1G      # Larger transaction logs
server.tx_log.preallocate=true      # Pre-allocate for performance

# Query Logging (disable during import)
server.logs.query.enabled=false
server.logs.query.threshold=0

# Network Settings
server.bolt.thread_pool_min_size=10
server.bolt.thread_pool_max_size=400
server.bolt.thread_pool_keep_alive=5m

# Additional Performance Settings
dbms.memory.transaction.total.max=2G
dbms.relationship_grouping_threshold=1
metrics.enabled=false  # Disable metrics during import

# OS-level optimizations (apply these to your system):
# - Disable swap: sudo swapoff -a
# - Disable transparent huge pages
# - Use XFS or ext4 filesystem with noatime mount option
# - Ensure adequate file descriptors: ulimit -n 65536
"""

        with open(output_file, 'w') as f:
            f.write(config)

        logger.info(f"  Generated: {output_file}")
        logger.info("  Apply with: sudo cp neo4j_optimized.conf /etc/neo4j/neo4j.conf")
        logger.info("  Then restart: sudo systemctl restart neo4j")

    def close(self):
        """Close all connections"""
        if self.driver:
            self.driver.close()
        if self.async_driver:
            asyncio.run(self.async_driver.close())


def main():
    parser = argparse.ArgumentParser(
        description='Ultra-fast Neo4j import with multiple optimization strategies',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Import Methods (from fastest to flexible):
  1. --admin-export   : Export to CSV for neo4j-admin (5-30x faster, offline)
  2. --apoc-parallel  : Use APOC parallel iterate (2-6x faster, online)
  3. --bolt-parallel  : Optimized Bolt with parallelism (2-4x faster, online)

Examples:
  # Fastest - neo4j-admin import (requires restart)
  %(prog)s --admin-export --db data/espocrm_complete.db

  # Fast online import with APOC
  %(prog)s --apoc-parallel --db data/espocrm_complete.db

  # Parallel Bolt import (no APOC required)
  %(prog)s --bolt-parallel --db data/espocrm_complete.db

  # Generate optimized Neo4j config
  %(prog)s --generate-config
        """
    )

    parser.add_argument('--config', default='memory.yaml', help='Configuration file')
    parser.add_argument('--db', help='SQLite database path')

    # Import methods
    parser.add_argument('--admin-export', action='store_true',
                       help='Export to CSV for neo4j-admin import (fastest, 5-30x)')
    parser.add_argument('--apoc-parallel', action='store_true',
                       help='Use APOC parallel iterate (2-6x faster, online)')
    parser.add_argument('--bolt-parallel', action='store_true',
                       help='Optimized Bolt with parallelism (2-4x faster)')

    # Additional options
    parser.add_argument('--generate-config', action='store_true',
                       help='Generate optimized Neo4j configuration')
    parser.add_argument('--workers', type=int, default=8,
                       help='Number of parallel workers (default: 8)')
    parser.add_argument('--node-batch', type=int, default=50000,
                       help='Node batch size (default: 50000)')
    parser.add_argument('--rel-batch', type=int, default=20000,
                       help='Relationship batch size (default: 20000)')

    args = parser.parse_args()

    if args.generate_config:
        importer = UltraFastNeo4jImporter(args.config)
        importer.generate_memory_optimized_config()
        return 0

    if not args.db:
        # Try to get from config
        importer = UltraFastNeo4jImporter(args.config)
        storage = importer.config.get('storage', {})
        args.db = storage.get('sqlite', 'data/espocrm_complete.db')

    if not Path(args.db).exists():
        logger.error(f"Database not found: {args.db}")
        return 1

    importer = UltraFastNeo4jImporter(args.config)
    importer.parallel_workers = args.workers
    importer.node_batch_size = args.node_batch
    importer.rel_batch_size = args.rel_batch

    try:
        start_time = datetime.now()

        if args.admin_export:
            importer.export_to_csv_for_admin_import(args.db)

        elif args.apoc_parallel:
            asyncio.run(importer.import_with_apoc_parallel(args.db))

        elif args.bolt_parallel:
            importer.import_with_parallel_bolt(args.db)

        else:
            # Default to bolt parallel
            logger.info("No method specified, using parallel Bolt import...")
            importer.import_with_parallel_bolt(args.db)

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"⏱️ Total time: {elapsed:.2f} seconds")

    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        importer.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
