#!/usr/bin/env python3
"""
FINAL COMPLETE IMPORT - Ensures Neo4j has EVERYTHING needed to answer queries
"""

import sqlite3
from neo4j import GraphDatabase
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FinalCompleteImporter:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            "bolt://localhost:7688", 
            auth=("neo4j", "password123")
        )
        self.sqlite_db = "data/espocrm_complete.db"
    
    def run_complete_import(self):
        """Execute complete import to Neo4j"""
        start = time.time()
        logger.info("Starting FINAL COMPLETE import...")
        
        # Clear database
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            logger.info("Cleared database")
        
        conn = sqlite3.connect(self.sqlite_db)
        cursor = conn.cursor()
        
        # 1. Import ALL nodes with proper labels
        logger.info("Importing ALL nodes...")
        with self.driver.session() as session:
            cursor.execute("SELECT * FROM symbols")
            
            batch = []
            count = 0
            for row in cursor.fetchall():
                # Determine labels based on type and ID
                symbol_id = row[0]
                symbol_type = row[2]
                
                if symbol_type == 'class':
                    labels = 'Symbol:PHPClass'
                elif symbol_type == 'method':
                    labels = 'Symbol:PHPMethod'
                elif symbol_type == 'interface':
                    labels = 'Symbol:PHPInterface'
                elif symbol_type == 'trait':
                    labels = 'Symbol:PHPTrait'
                elif symbol_type == 'function':
                    labels = 'Symbol:PHPFunction'
                elif symbol_type == 'property':
                    labels = 'Symbol:PHPProperty'
                elif symbol_type == 'file':
                    labels = 'File'
                elif symbol_type == 'directory':
                    labels = 'Directory'
                elif symbol_id.startswith('js_'):
                    labels = 'Symbol:JSSymbol'
                else:
                    labels = 'Symbol'
                
                batch.append({
                    'labels': labels,
                    'props': {
                        'id': symbol_id,
                        'name': row[1] or '',
                        'type': symbol_type or '',
                        'file_path': row[3] or '',
                        'line_number': row[4] or 0,
                        'namespace': row[7] or ''
                    }
                })
                
                # Process in batches of 5000
                if len(batch) >= 5000:
                    self._create_nodes_batch(session, batch)
                    count += len(batch)
                    logger.info(f"  Created {count} nodes...")
                    batch = []
            
            # Process remaining
            if batch:
                self._create_nodes_batch(session, batch)
                count += len(batch)
            
            logger.info(f"Created {count} total nodes")
        
        # 2. Import ALL relationships, especially inheritance
        logger.info("Importing ALL relationships...")
        
        # Get relationship counts
        cursor.execute("""
            SELECT reference_type, COUNT(*) 
            FROM symbol_references 
            GROUP BY reference_type 
            ORDER BY COUNT(*) DESC
        """)
        rel_types = cursor.fetchall()
        
        with self.driver.session() as session:
            total_rels = 0
            
            # Process CRITICAL relationships first
            critical_types = ['EXTENDS', 'IMPLEMENTS', 'USES_TRAIT']
            
            for rel_type in critical_types:
                cursor.execute("""
                    SELECT source_id, target_id, line_number, column_number
                    FROM symbol_references
                    WHERE reference_type = ?
                """, (rel_type,))
                
                rels = cursor.fetchall()
                if rels:
                    logger.info(f"  Importing {len(rels)} {rel_type} relationships...")
                    created = self._create_relationships_batch(session, rel_type, rels)
                    total_rels += created
                    logger.info(f"    Created {created} {rel_type} relationships")
            
            # Process other relationships
            for rel_type, count in rel_types:
                if rel_type not in critical_types:
                    logger.info(f"  Importing {count} {rel_type} relationships...")
                    
                    cursor.execute("""
                        SELECT source_id, target_id, line_number, column_number
                        FROM symbol_references
                        WHERE reference_type = ?
                        LIMIT 10000
                    """, (rel_type,))
                    
                    rels = cursor.fetchall()
                    if rels:
                        created = self._create_relationships_batch(session, rel_type, rels)
                        total_rels += created
            
            logger.info(f"Created {total_rels} total relationships")
        
        conn.close()
        
        elapsed = time.time() - start
        logger.info(f"IMPORT COMPLETE in {elapsed:.1f} seconds!")
        
        # Verify critical data
        self._verify_import()
    
    def _create_nodes_batch(self, session, batch):
        """Create nodes by label groups"""
        # Group by labels
        by_labels = {}
        for item in batch:
            labels = item['labels']
            if labels not in by_labels:
                by_labels[labels] = []
            by_labels[labels].append(item['props'])
        
        # Create each group
        for labels, props_list in by_labels.items():
            query = f"""
                UNWIND $batch AS props
                CREATE (n:{labels})
                SET n = props
            """
            session.run(query, batch=props_list)
    
    def _create_relationships_batch(self, session, rel_type, relationships):
        """Create relationships in batches"""
        batch_size = 1000
        created = 0
        
        for i in range(0, len(relationships), batch_size):
            batch = relationships[i:i+batch_size]
            
            rel_data = [
                {
                    'source': rel[0],
                    'target': rel[1],
                    'line': rel[2],
                    'col': rel[3]
                }
                for rel in batch
            ]
            
            query = f"""
                UNWIND $batch AS rel
                MATCH (s {{id: rel.source}})
                MATCH (t {{id: rel.target}})
                CREATE (s)-[r:{rel_type}]->(t)
                SET r.line = rel.line, r.column = rel.col
                RETURN COUNT(r) as created
            """
            
            try:
                result = session.run(query, batch=rel_data)
                created += result.single()['created']
            except Exception as e:
                logger.warning(f"Failed batch for {rel_type}: {e}")
        
        return created
    
    def _verify_import(self):
        """Verify the import succeeded"""
        logger.info("\n" + "="*60)
        logger.info("VERIFICATION")
        logger.info("="*60)
        
        with self.driver.session() as session:
            # Check nodes
            result = session.run("MATCH (n) RETURN COUNT(n) as count")
            nodes = result.single()['count']
            logger.info(f"Total nodes: {nodes}")
            
            # Check relationships
            result = session.run("""
                MATCH ()-[r]->()
                RETURN TYPE(r) as type, COUNT(r) as count
                ORDER BY count DESC
                LIMIT 10
            """)
            
            logger.info("Relationships:")
            for record in result:
                logger.info(f"  {record['type']}: {record['count']}")
            
            # Test email query
            result = session.run("""
                MATCH (n)
                WHERE toLower(n.name) CONTAINS 'email' 
                   OR toLower(n.name) CONTAINS 'send'
                RETURN n.type as type, n.name as name, n.file_path as path
                LIMIT 5
            """)
            
            logger.info("\nTest query 'email/send':")
            for record in result:
                logger.info(f"  {record['type']}: {record['name']}")


if __name__ == '__main__':
    importer = FinalCompleteImporter()
    importer.run_complete_import()