#!/usr/bin/env python3
"""
Optimized Neo4j Import from SQLite Database
Uses UNWIND for maximum performance with proper error handling
"""

import sqlite3
from neo4j import GraphDatabase
import time
from typing import Dict, List, Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class OptimizedNeo4jImporter:
    """Optimized import from SQLite to Neo4j"""
    
    def __init__(self, sqlite_db: str, neo4j_uri="bolt://localhost:7688", 
                 neo4j_user="neo4j", neo4j_password="password123"):
        self.sqlite_db = sqlite_db
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.stats = {
            'nodes_created': 0,
            'relationships_created': 0,
            'failed_relationships': {},
            'time_taken': 0
        }
        
    def clear_neo4j(self):
        """Clear all data from Neo4j"""
        logger.info("Clearing Neo4j database...")
        with self.driver.session() as session:
            # Delete in batches to avoid memory issues
            while True:
                result = session.run("""
                    MATCH (n) 
                    WITH n LIMIT 10000
                    DETACH DELETE n
                    RETURN COUNT(n) as deleted
                """)
                deleted = result.single()['deleted']
                if deleted == 0:
                    break
                logger.info(f"  Deleted {deleted} nodes...")
    
    def create_constraints_and_indexes(self):
        """Create constraints and indexes for better performance"""
        logger.info("Creating constraints and indexes...")
        with self.driver.session() as session:
            constraints = [
                # Unique constraints ensure node uniqueness and create indexes
                "CREATE CONSTRAINT symbol_id IF NOT EXISTS FOR (s:Symbol) REQUIRE s.id IS UNIQUE",
                "CREATE CONSTRAINT file_id IF NOT EXISTS FOR (f:File) REQUIRE f.id IS UNIQUE",
                "CREATE CONSTRAINT dir_id IF NOT EXISTS FOR (d:Directory) REQUIRE d.id IS UNIQUE",
                "CREATE CONSTRAINT php_class_id IF NOT EXISTS FOR (c:PHPClass) REQUIRE c.id IS UNIQUE",
                "CREATE CONSTRAINT php_interface_id IF NOT EXISTS FOR (i:PHPInterface) REQUIRE i.id IS UNIQUE",
                "CREATE CONSTRAINT php_trait_id IF NOT EXISTS FOR (t:PHPTrait) REQUIRE t.id IS UNIQUE",
                "CREATE CONSTRAINT js_module_id IF NOT EXISTS FOR (m:JSModule) REQUIRE m.id IS UNIQUE",
            ]
            
            for constraint in constraints:
                try:
                    session.run(constraint)
                    logger.info(f"  Created: {constraint.split(' ')[2]}")
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning(f"  Constraint issue: {e}")
    
    def import_nodes_optimized(self, batch_size=10000):
        """Import all nodes from SQLite to Neo4j with optimal batching"""
        logger.info("Importing nodes from SQLite...")
        
        conn = sqlite3.connect(self.sqlite_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get total count
        cursor.execute("SELECT COUNT(*) as count FROM symbols")
        total = cursor.fetchone()['count']
        logger.info(f"Total symbols to import: {total:,}")
        
        # Import in chunks
        offset = 0
        with self.driver.session() as session:
            while offset < total:
                cursor.execute(f"SELECT * FROM symbols LIMIT {batch_size} OFFSET {offset}")
                symbols = cursor.fetchall()
                
                if not symbols:
                    break
                
                # Group by label combination for efficiency
                nodes_by_labels = {}
                for symbol in symbols:
                    labels = self._get_labels(symbol)
                    label_key = ':'.join(labels)
                    
                    if label_key not in nodes_by_labels:
                        nodes_by_labels[label_key] = []
                    
                    props = self._get_node_props(symbol)
                    nodes_by_labels[label_key].append(props)
                
                # Import each label group
                for labels, props_list in nodes_by_labels.items():
                    query = f"""
                    UNWIND $batch AS props
                    CREATE (n:{labels})
                    SET n = props
                    """
                    session.run(query, batch=props_list)
                    self.stats['nodes_created'] += len(props_list)
                
                offset += batch_size
                logger.info(f"  Progress: {min(offset, total):,}/{total:,} nodes")
        
        conn.close()
        logger.info(f"Created {self.stats['nodes_created']:,} nodes")
    
    def _get_labels(self, symbol) -> List[str]:
        """Determine labels for a symbol"""
        labels = ['Symbol']  # Base label for all
        symbol_type = symbol['type']
        symbol_id = symbol['id']
        
        if symbol_type == 'class':
            labels.append('PHPClass')
        elif symbol_type == 'interface':
            labels.append('PHPInterface')
        elif symbol_type == 'trait':
            labels.append('PHPTrait')
        elif symbol_type == 'method':
            labels.append('PHPMethod')
        elif symbol_type == 'function':
            labels.append('PHPFunction')
        elif symbol_type == 'property':
            labels.append('PHPProperty')
        elif symbol_type == 'constant':
            labels.append('PHPConstant')
        elif symbol_type == 'namespace':
            labels.append('PHPNamespace')
        elif symbol_type == 'file':
            labels.append('File')
        elif symbol_type == 'directory':
            labels.append('Directory')
        elif symbol_id.startswith('js_'):
            if symbol_type == 'module':
                labels.append('JSModule')
            elif symbol_type == 'function':
                labels.append('JSFunction')
            elif symbol_type == 'class':
                labels.append('JSClass')
            else:
                labels.append('JSSymbol')
        else:
            labels.append('PHPSymbol')
        
        return labels
    
    def _get_node_props(self, symbol) -> Dict:
        """Build properties for a node"""
        props = {
            'id': symbol['id'],
            'name': symbol['name'],
            'type': symbol['type']
        }
        
        # Add all non-null properties
        optional_fields = ['file_path', 'line_number', 'namespace', 'visibility',
                          'is_static', 'is_abstract', 'is_final', 'return_type',
                          'extends', 'implements']
        
        for field in optional_fields:
            if symbol[field] is not None:
                props[field] = symbol[field]
        
        return props
    
    def import_relationships_optimized(self, batch_size=5000):
        """Import relationships with optimal batching and error handling"""
        logger.info("Importing relationships from SQLite...")
        
        conn = sqlite3.connect(self.sqlite_db)
        cursor = conn.cursor()
        
        # Get relationship counts by type
        cursor.execute("""
            SELECT reference_type, COUNT(*) as count
            FROM symbol_references
            GROUP BY reference_type
            ORDER BY count DESC
        """)
        rel_counts = cursor.fetchall()
        
        logger.info("Relationship distribution:")
        for rel_type, count in rel_counts:
            logger.info(f"  {rel_type}: {count:,}")
        
        with self.driver.session() as session:
            # Process each relationship type
            for rel_type, total_count in rel_counts:
                logger.info(f"\nImporting {rel_type} relationships...")
                
                # Process in batches
                offset = 0
                failed_count = 0
                
                while offset < total_count:
                    cursor.execute(f"""
                        SELECT source_id, target_id, line_number, column_number
                        FROM symbol_references
                        WHERE reference_type = ?
                        LIMIT ? OFFSET ?
                    """, (rel_type, batch_size, offset))
                    
                    batch = [{'source_id': row[0], 'target_id': row[1], 
                             'line': row[2], 'column': row[3]} 
                            for row in cursor.fetchall()]
                    
                    if not batch:
                        break
                    
                    # Use UNWIND for batch creation
                    query = f"""
                    UNWIND $batch AS rel
                    MATCH (s {{id: rel.source_id}})
                    MATCH (t {{id: rel.target_id}})
                    CREATE (s)-[r:{rel_type}]->(t)
                    SET r.line = rel.line, r.column = rel.column
                    RETURN COUNT(r) as created
                    """
                    
                    try:
                        result = session.run(query, batch=batch)
                        created = result.single()['created']
                        self.stats['relationships_created'] += created
                        
                        if created < len(batch):
                            failed_count += (len(batch) - created)
                            logger.warning(f"  Only created {created}/{len(batch)} relationships")
                            
                    except Exception as e:
                        logger.error(f"  Batch failed for {rel_type}: {e}")
                        failed_count += len(batch)
                        
                        # Try smaller batches on failure
                        if batch_size > 100:
                            self._retry_failed_batch(session, rel_type, batch)
                    
                    offset += batch_size
                    if offset % 10000 == 0:
                        logger.info(f"  Progress: {min(offset, total_count):,}/{total_count:,}")
                
                if failed_count > 0:
                    self.stats['failed_relationships'][rel_type] = failed_count
                    logger.warning(f"  Failed to create {failed_count} {rel_type} relationships")
        
        conn.close()
        logger.info(f"\nTotal relationships created: {self.stats['relationships_created']:,}")
        
        if self.stats['failed_relationships']:
            logger.warning("Failed relationships by type:")
            for rel_type, count in self.stats['failed_relationships'].items():
                logger.warning(f"  {rel_type}: {count}")
    
    def _retry_failed_batch(self, session, rel_type: str, batch: List[Dict]):
        """Retry failed batch with smaller chunks"""
        logger.debug(f"  Retrying {len(batch)} {rel_type} relationships in smaller chunks...")
        
        chunk_size = 100
        created = 0
        
        for i in range(0, len(batch), chunk_size):
            chunk = batch[i:i+chunk_size]
            query = f"""
            UNWIND $batch AS rel
            MATCH (s {{id: rel.source_id}})
            MATCH (t {{id: rel.target_id}})
            CREATE (s)-[r:{rel_type}]->(t)
            SET r.line = rel.line, r.column = rel.column
            RETURN COUNT(r) as created
            """
            
            try:
                result = session.run(query, batch=chunk)
                chunk_created = result.single()['created']
                self.stats['relationships_created'] += chunk_created
                created += chunk_created
            except:
                pass  # Skip this chunk
        
        logger.debug(f"  Retry recovered {created}/{len(batch)} relationships")
    
    def verify_import(self):
        """Verify the import was successful"""
        logger.info("\n" + "="*60)
        logger.info("VERIFICATION RESULTS")
        logger.info("="*60)
        
        with self.driver.session() as session:
            # Count nodes by label
            result = session.run("""
                MATCH (n)
                UNWIND labels(n) AS label
                WITH label
                WHERE label <> 'Symbol'
                RETURN label, COUNT(*) as count
                ORDER BY count DESC
            """)
            
            print("\n📊 Node Distribution:")
            total_nodes = 0
            for record in result:
                count = record['count']
                total_nodes += count
                print(f"  {record['label']}: {count:,}")
            
            # Count relationships by type
            result = session.run("""
                MATCH ()-[r]->()
                RETURN TYPE(r) as type, COUNT(r) as count
                ORDER BY count DESC
            """)
            
            print(f"\n📈 Relationship Distribution:")
            total_rels = 0
            inheritance_rels = 0
            for record in result:
                count = record['count']
                rel_type = record['type']
                total_rels += count
                if rel_type in ['EXTENDS', 'IMPLEMENTS', 'USES_TRAIT']:
                    inheritance_rels += count
                print(f"  {rel_type}: {count:,}")
            
            # Check critical relationships
            print(f"\n✅ Summary:")
            print(f"  Total Nodes: {self.stats['nodes_created']:,}")
            print(f"  Total Relationships: {self.stats['relationships_created']:,}")
            print(f"  Inheritance Relationships: {inheritance_rels:,}")
            
            # Sample queries
            print("\n🔍 Sample Queries:")
            
            # Find a class with inheritance
            result = session.run("""
                MATCH (c:PHPClass)-[:EXTENDS]->(p:PHPClass)
                RETURN c.name as child, p.name as parent
                LIMIT 5
            """)
            
            print("\n  Class Inheritance Examples:")
            for record in result:
                print(f"    {record['child']} extends {record['parent']}")
            
            # Find interfaces
            result = session.run("""
                MATCH (c:PHPClass)-[:IMPLEMENTS]->(i:PHPInterface)
                RETURN c.name as class, i.name as interface
                LIMIT 5
            """)
            
            print("\n  Interface Implementation Examples:")
            for record in result:
                print(f"    {record['class']} implements {record['interface']}")
    
    def run(self):
        """Run the complete import process"""
        start_time = time.time()
        
        try:
            logger.info("Starting optimized Neo4j import...")
            
            # Clear and prepare database
            self.clear_neo4j()
            self.create_constraints_and_indexes()
            
            # Import data
            self.import_nodes_optimized(batch_size=10000)
            self.import_relationships_optimized(batch_size=5000)
            
            # Verify
            self.verify_import()
            
            self.stats['time_taken'] = time.time() - start_time
            
            print(f"\n" + "="*60)
            print("✅ IMPORT COMPLETE!")
            print("="*60)
            print(f"⏱️  Time taken: {self.stats['time_taken']:.2f} seconds")
            print(f"📦 Nodes created: {self.stats['nodes_created']:,}")
            print(f"🔗 Relationships created: {self.stats['relationships_created']:,}")
            
            if self.stats['failed_relationships']:
                print(f"⚠️  Failed relationships: {sum(self.stats['failed_relationships'].values()):,}")
            
        except Exception as e:
            logger.error(f"Import failed: {e}")
            raise
        finally:
            self.driver.close()


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Optimized Neo4j import from SQLite')
    parser.add_argument('--db', default='data/espocrm_complete.db', help='SQLite database path')
    parser.add_argument('--uri', default='bolt://localhost:7688', help='Neo4j URI')
    parser.add_argument('--user', default='neo4j', help='Neo4j username')
    parser.add_argument('--password', default='password123', help='Neo4j password')
    
    args = parser.parse_args()
    
    importer = OptimizedNeo4jImporter(args.db, args.uri, args.user, args.password)
    importer.run()


if __name__ == '__main__':
    main()