#!/usr/bin/env python3
"""
Direct Neo4j Import from SQLite Database
Imports the complete graph including all inheritance relationships
"""

import sqlite3
from neo4j import GraphDatabase
import time
from typing import Dict, List, Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DirectNeo4jImporter:
    """Import directly from SQLite to Neo4j"""
    
    def __init__(self, sqlite_db: str, neo4j_uri="bolt://localhost:7688", 
                 neo4j_user="neo4j", neo4j_password="password123"):
        self.sqlite_db = sqlite_db
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.stats = {
            'nodes_created': 0,
            'relationships_created': 0,
            'time_taken': 0
        }
        
    def clear_neo4j(self):
        """Clear all data from Neo4j"""
        logger.info("Clearing Neo4j database...")
        with self.driver.session() as session:
            result = session.run("MATCH (n) DETACH DELETE n")
            summary = result.consume()
            logger.info(f"Deleted {summary.counters.nodes_deleted} nodes and {summary.counters.relationships_deleted} relationships")
    
    def create_indexes(self):
        """Create indexes for better performance"""
        logger.info("Creating indexes...")
        with self.driver.session() as session:
            indexes = [
                "CREATE INDEX symbol_id IF NOT EXISTS FOR (s:Symbol) ON (s.id)",
                "CREATE INDEX file_id IF NOT EXISTS FOR (f:File) ON (f.id)",
                "CREATE INDEX dir_id IF NOT EXISTS FOR (d:Directory) ON (d.id)",
                "CREATE INDEX php_class IF NOT EXISTS FOR (c:PHPClass) ON (c.name)",
                "CREATE INDEX js_module IF NOT EXISTS FOR (m:JSModule) ON (m.name)"
            ]
            for index in indexes:
                session.run(index)
    
    def import_nodes(self):
        """Import all nodes from SQLite to Neo4j"""
        logger.info("Importing nodes from SQLite...")
        
        conn = sqlite3.connect(self.sqlite_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Import symbols as nodes
        cursor.execute("SELECT * FROM symbols")
        symbols = cursor.fetchall()
        
        logger.info(f"Found {len(symbols)} symbols to import")
        
        with self.driver.session() as session:
            # Batch import symbols
            batch = []
            for symbol in symbols:
                # Determine labels based on type and ID prefix
                labels = []
                symbol_type = symbol['type']
                symbol_id = symbol['id']
                
                # Primary label based on type
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
                    else:
                        labels.append('JSSymbol')
                else:
                    labels.append('PHPSymbol')
                
                # Build properties
                props = {
                    'id': symbol['id'],
                    'name': symbol['name'],
                    'type': symbol['type'],
                    'file_path': symbol['file_path'],
                    'line_number': symbol['line_number']
                }
                
                # Add optional properties
                if symbol['namespace']:
                    props['namespace'] = symbol['namespace']
                if symbol['visibility']:
                    props['visibility'] = symbol['visibility']
                if symbol['is_static']:
                    props['is_static'] = symbol['is_static']
                if symbol['is_abstract']:
                    props['is_abstract'] = symbol['is_abstract']
                if symbol['is_final']:
                    props['is_final'] = symbol['is_final']
                if symbol['return_type']:
                    props['return_type'] = symbol['return_type']
                if symbol['extends']:
                    props['extends'] = symbol['extends']
                
                batch.append({'labels': labels, 'props': props})
                
                # Import in batches
                if len(batch) >= 1000:
                    self._create_nodes_batch(session, batch)
                    batch = []
            
            # Import remaining
            if batch:
                self._create_nodes_batch(session, batch)
        
        conn.close()
        logger.info(f"Created {self.stats['nodes_created']} nodes")
    
    def _create_nodes_batch(self, session, batch):
        """Create a batch of nodes"""
        # Group by label combination for efficiency
        by_labels = {}
        for item in batch:
            label_key = ':'.join(item['labels'])
            if label_key not in by_labels:
                by_labels[label_key] = []
            by_labels[label_key].append(item['props'])
        
        for labels, props_list in by_labels.items():
            query = f"""
            UNWIND $batch AS props
            CREATE (n:{labels})
            SET n = props
            """
            session.run(query, batch=props_list)
            self.stats['nodes_created'] += len(props_list)
    
    def import_relationships(self):
        """Import all relationships from SQLite to Neo4j"""
        logger.info("Importing relationships from SQLite...")
        
        conn = sqlite3.connect(self.sqlite_db)
        cursor = conn.cursor()
        
        # Get all relationships
        cursor.execute("SELECT * FROM symbol_references")
        references = cursor.fetchall()
        
        logger.info(f"Found {len(references)} relationships to import")
        
        # Group by type
        by_type = {}
        for ref in references:
            # Columns: id, source_id, target_id, reference_type, line_number, column_number
            rel_type = ref[3]  # reference_type column (4th column)
            if rel_type not in by_type:
                by_type[rel_type] = []
            by_type[rel_type].append({
                'source_id': ref[1],  # source_id (2nd column)
                'target_id': ref[2],  # target_id (3rd column)
                'line': ref[4],       # line_number (5th column)
                'column': ref[5]      # column_number (6th column)
            })
        
        with self.driver.session() as session:
            for rel_type, rels in by_type.items():
                logger.info(f"  Importing {len(rels)} {rel_type} relationships...")
                
                # Import in batches
                batch_size = 500
                for i in range(0, len(rels), batch_size):
                    batch = rels[i:i+batch_size]
                    
                    query = f"""
                    UNWIND $batch AS rel
                    MATCH (s {{id: rel.source_id}})
                    MATCH (t {{id: rel.target_id}})
                    CREATE (s)-[r:{rel_type}]->(t)
                    SET r.line = rel.line, r.column = rel.column
                    """
                    
                    try:
                        result = session.run(query, batch=batch)
                        summary = result.consume()
                        self.stats['relationships_created'] += summary.counters.relationships_created
                    except Exception as e:
                        logger.warning(f"Failed batch of {rel_type} relationships: {e}")
                        # Try one by one for failed batch
                        failed = 0
                        for rel in batch:
                            try:
                                single_query = f"""
                                MATCH (s {{id: $source_id}})
                                MATCH (t {{id: $target_id}})
                                CREATE (s)-[r:{rel_type}]->(t)
                                SET r.line = $line, r.column = $column
                                """
                                result = session.run(single_query, 
                                          source_id=rel['source_id'],
                                          target_id=rel['target_id'],
                                          line=rel['line'],
                                          column=rel['column'])
                                summary = result.consume()
                                self.stats['relationships_created'] += summary.counters.relationships_created
                            except Exception as e2:
                                failed += 1
                                if failed <= 3:  # Only log first few failures
                                    logger.debug(f"Failed {rel_type}: {rel['source_id']} -> {rel['target_id']}: {e2}")
                        if failed > 0:
                            logger.warning(f"  Failed to create {failed}/{len(batch)} {rel_type} relationships")
        
        conn.close()
        logger.info(f"Created {self.stats['relationships_created']} relationships")
    
    def verify_import(self):
        """Verify the import was successful"""
        logger.info("\nVerifying import...")
        
        with self.driver.session() as session:
            # Count nodes
            result = session.run("MATCH (n) RETURN COUNT(n) as count")
            node_count = result.single()['count']
            
            # Count relationships
            result = session.run("MATCH ()-[r]->() RETURN COUNT(r) as count")
            rel_count = result.single()['count']
            
            # Get relationship type counts
            result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as type, COUNT(r) as count
                ORDER BY count DESC
                LIMIT 20
            """)
            
            print(f"\n📊 Graph Statistics:")
            print(f"  Total Nodes: {node_count:,}")
            print(f"  Total Relationships: {rel_count:,}")
            print(f"\n  Relationship Types:")
            for record in result:
                print(f"    {record['type']}: {record['count']:,}")
            
            # Check for wrong relationships
            result = session.run("""
                MATCH (c:PHPClass)-[r]->(d:Directory)
                RETURN COUNT(r) as count
            """)
            wrong_count = result.single()['count']
            if wrong_count > 0:
                logger.warning(f"⚠️  Found {wrong_count} classes with relationships to directories!")
            else:
                logger.info("✅ No classes pointing to directories (correct!)")
            
            # Check inheritance relationships
            result = session.run("""
                MATCH ()-[r:EXTENDS|IMPLEMENTS|USES_TRAIT]->()
                RETURN type(r) as type, COUNT(r) as count
            """)
            print(f"\n  Inheritance Relationships:")
            for record in result:
                print(f"    {record['type']}: {record['count']}")
    
    def run(self):
        """Run the complete import process"""
        start_time = time.time()
        
        try:
            self.clear_neo4j()
            self.create_indexes()
            self.import_nodes()
            self.import_relationships()
            self.verify_import()
            
            self.stats['time_taken'] = time.time() - start_time
            
            print(f"\n✅ Import Complete!")
            print(f"  Time taken: {self.stats['time_taken']:.2f} seconds")
            print(f"  Nodes created: {self.stats['nodes_created']:,}")
            print(f"  Relationships created: {self.stats['relationships_created']:,}")
            
        except Exception as e:
            logger.error(f"Import failed: {e}")
            raise
        finally:
            self.driver.close()


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Direct import from SQLite to Neo4j')
    parser.add_argument('--db', default='data/espocrm_complete.db', help='SQLite database path')
    parser.add_argument('--uri', default='bolt://localhost:7688', help='Neo4j URI')
    parser.add_argument('--user', default='neo4j', help='Neo4j username')
    parser.add_argument('--password', default='password123', help='Neo4j password')
    
    args = parser.parse_args()
    
    importer = DirectNeo4jImporter(args.db, args.uri, args.user, args.password)
    importer.run()


if __name__ == '__main__':
    main()