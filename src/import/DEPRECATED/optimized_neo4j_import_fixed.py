#!/usr/bin/env python3
"""
FIXED Optimized Neo4j Import from SQLite Database
Uses UNWIND for maximum performance with proper indexing
"""

import sqlite3
from neo4j import GraphDatabase
import time
from typing import Dict, List, Tuple
import logging
import hashlib

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
            # CRITICAL: Create indexes on ALL labels for id property
            indexes = [
                # Constraints (which create unique indexes)
                "CREATE CONSTRAINT symbol_id IF NOT EXISTS FOR (s:Symbol) REQUIRE s.id IS UNIQUE",
                "CREATE CONSTRAINT file_id IF NOT EXISTS FOR (f:File) REQUIRE f.id IS UNIQUE",
                "CREATE CONSTRAINT dir_id IF NOT EXISTS FOR (d:Directory) REQUIRE d.id IS UNIQUE",
                "CREATE CONSTRAINT php_class_id IF NOT EXISTS FOR (c:PHPClass) REQUIRE c.id IS UNIQUE",
                "CREATE CONSTRAINT php_interface_id IF NOT EXISTS FOR (i:PHPInterface) REQUIRE i.id IS UNIQUE",
                "CREATE CONSTRAINT php_trait_id IF NOT EXISTS FOR (t:PHPTrait) REQUIRE t.id IS UNIQUE",
                "CREATE CONSTRAINT php_method_id IF NOT EXISTS FOR (m:PHPMethod) REQUIRE m.id IS UNIQUE",
                "CREATE CONSTRAINT php_property_id IF NOT EXISTS FOR (p:PHPProperty) REQUIRE p.id IS UNIQUE",
                "CREATE CONSTRAINT php_constant_id IF NOT EXISTS FOR (c:PHPConstant) REQUIRE c.id IS UNIQUE",
                "CREATE CONSTRAINT php_function_id IF NOT EXISTS FOR (f:PHPFunction) REQUIRE f.id IS UNIQUE",
                "CREATE CONSTRAINT php_namespace_id IF NOT EXISTS FOR (n:PHPNamespace) REQUIRE n.id IS UNIQUE",
                "CREATE CONSTRAINT js_module_id IF NOT EXISTS FOR (m:JSModule) REQUIRE m.id IS UNIQUE",
                # Additional indexes for performance
                "CREATE INDEX symbol_name IF NOT EXISTS FOR (s:Symbol) ON (s.name)",
                "CREATE INDEX php_class_name IF NOT EXISTS FOR (c:PHPClass) ON (c.name)",
                "CREATE INDEX php_method_name IF NOT EXISTS FOR (m:PHPMethod) ON (m.name)",
            ]
            
            for index_query in indexes:
                try:
                    session.run(index_query)
                    index_name = index_query.split(' ')[2]
                    logger.info(f"  Created index/constraint: {index_name}")
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning(f"  Index/constraint issue: {e}")
    
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
        """FIXED: Import relationships with proper indexing"""
        logger.info("Importing relationships from SQLite...")
        import_start = time.time()
        
        conn = sqlite3.connect(self.sqlite_db)
        conn.row_factory = sqlite3.Row
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
        total_relationships = 0
        for rel_type, count in rel_counts:
            logger.info(f"  {rel_type}: {count:,}")
            total_relationships += count
        logger.info(f"Total relationships to import: {total_relationships:,}")
        
        with self.driver.session() as session:
            # Process each relationship type
            for rel_type, total_count in rel_counts:
                rel_start = time.time()
                logger.info(f"\nImporting {rel_type} relationships ({total_count:,} total)...")
                
                # Process in batches
                offset = 0
                failed_count = 0
                
                while offset < total_count:
                    # Get batch with source and target types
                    cursor.execute(f"""
                        SELECT 
                            sr.source_id, 
                            sr.target_id, 
                            sr.line_number, 
                            sr.column_number,
                            s1.type as source_type,
                            s2.type as target_type
                        FROM symbol_references sr
                        JOIN symbols s1 ON sr.source_id = s1.id
                        JOIN symbols s2 ON sr.target_id = s2.id
                        WHERE sr.reference_type = ?
                        LIMIT ? OFFSET ?
                    """, (rel_type, batch_size, offset))
                    
                    rows = cursor.fetchall()
                    if not rows:
                        break
                    
                    # Group by source and target label combinations for efficient queries
                    batches_by_labels = {}
                    for row in rows:
                        source_labels = self._get_label_for_type(row['source_type'], row['source_id'])
                        target_labels = self._get_label_for_type(row['target_type'], row['target_id'])
                        key = f"{source_labels}|{target_labels}"
                        
                        if key not in batches_by_labels:
                            batches_by_labels[key] = []
                        
                        batches_by_labels[key].append({
                            'source_id': row['source_id'],
                            'target_id': row['target_id'],
                            'line': row['line_number'],
                            'column': row['column_number']
                        })
                    
                    # Process each label combination separately
                    for label_key, batch in batches_by_labels.items():
                        source_label, target_label = label_key.split('|')
                        
                        # OPTIMIZED QUERY WITH LABELS
                        query = f"""
                        UNWIND $batch AS rel
                        MATCH (s:{source_label} {{id: rel.source_id}})
                        MATCH (t:{target_label} {{id: rel.target_id}})
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
                                logger.debug(f"  Only created {created}/{len(batch)} relationships")
                                
                        except Exception as e:
                            logger.error(f"  Batch failed for {rel_type} ({source_label}->{target_label}): {e}")
                            failed_count += len(batch)
                    
                    offset += batch_size
                    if offset % 5000 == 0:
                        logger.info(f"  Progress: {min(offset, total_count):,}/{total_count:,}")
                
                if failed_count > 0:
                    self.stats['failed_relationships'][rel_type] = failed_count
                    logger.warning(f"  Failed to create {failed_count} {rel_type} relationships")
                
                rel_time = time.time() - rel_start
                logger.info(f"  ✅ {rel_type} completed in {rel_time:.2f} seconds ({total_count/rel_time:.0f} relationships/sec)")
        
        conn.close()
        total_rel_time = time.time() - import_start
        logger.info(f"\n🎯 Total relationships created: {self.stats['relationships_created']:,} in {total_rel_time:.2f} seconds")
        logger.info(f"   Average speed: {self.stats['relationships_created']/total_rel_time:.0f} relationships/second")
        
        if self.stats['failed_relationships']:
            logger.warning("Failed relationships by type:")
            for rel_type, count in self.stats['failed_relationships'].items():
                logger.warning(f"  {rel_type}: {count}")
    
    def _get_label_for_type(self, node_type: str, node_id: str) -> str:
        """Get the primary Neo4j label for a node type"""
        if node_type == 'class':
            return 'PHPClass'
        elif node_type == 'interface':
            return 'PHPInterface'
        elif node_type == 'trait':
            return 'PHPTrait'
        elif node_type == 'method':
            return 'PHPMethod'
        elif node_type == 'function':
            return 'PHPFunction'
        elif node_type == 'property':
            return 'PHPProperty'
        elif node_type == 'constant':
            return 'PHPConstant'
        elif node_type == 'namespace':
            return 'PHPNamespace'
        elif node_type == 'file':
            return 'File'
        elif node_type == 'directory':
            return 'Directory'
        elif node_id.startswith('js_'):
            return 'JSModule'
        else:
            return 'Symbol'  # Fallback to generic Symbol
    
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
            for record in result:
                count = record['count']
                rel_type = record['type']
                total_rels += count
                print(f"  {rel_type}: {count:,}")
            
            # Check critical relationships
            print(f"\n✅ Summary:")
            print(f"  Total Nodes: {self.stats['nodes_created']:,}")
            print(f"  Total Relationships: {self.stats['relationships_created']:,}")
            
            # Test Service query
            print("\n🔍 Testing Service Query:")
            result = session.run("""
                MATCH (c:PHPClass)-[:DEFINES]->(m:PHPMethod)<-[r:CALLS]-()
                WHERE c.name CONTAINS 'Service'
                RETURN c.name as ServiceClass, 
                       m.name as Method,
                       count(r) as CallCount
                ORDER BY CallCount DESC
                LIMIT 5
            """)
            
            for record in result:
                print(f"  {record['ServiceClass']}.{record['Method']}() - {record['CallCount']} calls")
    
    def import_config_references(self):
        """Import configuration references from metadata parsing"""
        logger.info("Importing configuration references...")
        
        conn = sqlite3.connect(self.sqlite_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if config_references table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='config_references'
        """)
        if not cursor.fetchone():
            logger.info("No config_references table found, skipping...")
            return
        
        # Get config references
        cursor.execute("""
            SELECT config_file, config_key, class_name, reference_type
            FROM config_references
        """)
        references = cursor.fetchall()
        
        if not references:
            logger.info("No config references found")
            conn.close()
            return
        
        logger.info(f"Found {len(references)} configuration references to import")
        
        with self.driver.session() as session:
            # Create ConfigFile nodes
            config_files = {}
            for ref in references:
                config_file = ref['config_file']
                if config_file not in config_files:
                    # Create ConfigFile node
                    file_id = f"config_{hashlib.md5(config_file.encode()).hexdigest()}"
                    query = """
                    CREATE (n:ConfigFile:File)
                    SET n.id = $id, n.path = $path, n.type = 'json'
                    """
                    session.run(query, id=file_id, path=config_file)
                    config_files[config_file] = file_id
                    self.stats['nodes_created'] += 1
            
            # Create REGISTERED_IN relationships
            registered_count = 0
            for ref in references:
                file_id = config_files[ref['config_file']]
                class_name = ref['class_name']
                
                # Create relationship from class to config file
                query = """
                MATCH (c:PHPClass) WHERE c.name = $class_name
                MATCH (f:ConfigFile {id: $file_id})
                CREATE (c)-[r:REGISTERED_IN]->(f)
                SET r.config_key = $config_key, 
                    r.registration_type = $ref_type
                RETURN count(r) as created
                """
                result = session.run(query,
                    class_name=class_name,
                    file_id=file_id,
                    config_key=ref['config_key'],
                    ref_type=ref['reference_type']
                )
                
                created = result.single()['created']
                if created:
                    registered_count += created
                    self.stats['relationships_created'] += created
                    
                    # Mark authentication hooks specially
                    if ref['reference_type'] == 'AUTHENTICATION_HOOK':
                        mark_query = """
                        MATCH (c:PHPClass) WHERE c.name = $class_name
                        SET c.requires_registration = true,
                            c.registration_file = $config_file,
                            c.registration_key = $config_key
                        """
                        session.run(mark_query,
                            class_name=class_name,
                            config_file=ref['config_file'],
                            config_key=ref['config_key']
                        )
            
            logger.info(f"Created {len(config_files)} ConfigFile nodes")
            logger.info(f"Created {registered_count} REGISTERED_IN relationships")
        
        conn.close()
    
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
            
            # Import configuration references if available
            self.import_config_references()
            
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