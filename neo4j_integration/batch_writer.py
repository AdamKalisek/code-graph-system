"""Neo4j Batch Writer - Efficiently writes Symbol Table data to Neo4j"""

import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging
from neo4j import GraphDatabase, Transaction
import time

from symbol_table import SymbolTable

logger = logging.getLogger(__name__)


@dataclass
class Neo4jConfig:
    """Neo4j connection configuration"""
    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: str = "password"
    database: str = "neo4j"
    batch_size: int = 1000
    max_retries: int = 3


class Neo4jBatchWriter:
    """Writes Symbol Table data to Neo4j in batches"""
    
    def __init__(self, symbol_table: SymbolTable, config: Neo4jConfig):
        self.symbol_table = symbol_table
        self.config = config
        self.driver = None
        self.stats = {
            'nodes_created': 0,
            'relationships_created': 0,
            'nodes_updated': 0,
            'errors': 0,
            'duration': 0
        }
    
    def connect(self) -> None:
        """Connect to Neo4j"""
        logger.info(f"Connecting to Neo4j at {self.config.uri}")
        self.driver = GraphDatabase.driver(
            self.config.uri,
            auth=(self.config.username, self.config.password)
        )
        
        # Test connection
        with self.driver.session(database=self.config.database) as session:
            result = session.run("RETURN 1")
            result.single()
        
        logger.info("Connected to Neo4j successfully")
    
    def close(self) -> None:
        """Close Neo4j connection"""
        if self.driver:
            self.driver.close()
            logger.info("Disconnected from Neo4j")
    
    def export_to_neo4j(self) -> Dict[str, Any]:
        """Export all Symbol Table data to Neo4j"""
        if not self.driver:
            self.connect()
        
        start_time = time.time()
        
        try:
            # Clear existing data (optional)
            if self._should_clear_existing():
                self._clear_database()
            
            # Create constraints and indexes
            self._create_constraints_and_indexes()
            
            # Export nodes and relationships
            nodes, edges = self.symbol_table.export_to_neo4j_format()
            
            logger.info(f"Exporting {len(nodes)} nodes and {len(edges)} relationships to Neo4j")
            
            # Write nodes in batches
            self._write_nodes_batch(nodes)
            
            # Write relationships in batches
            self._write_relationships_batch(edges)
            
            # Create additional indexes for performance
            self._create_additional_indexes()
            
            self.stats['duration'] = time.time() - start_time
            
            logger.info(f"Export complete: {self.stats}")
            
            return self.stats
            
        except Exception as e:
            logger.error(f"Error exporting to Neo4j: {e}")
            raise
    
    def _should_clear_existing(self) -> bool:
        """Check if we should clear existing data"""
        # Could be configured or check for existing data
        return False
    
    def _clear_database(self) -> None:
        """Clear all nodes and relationships"""
        logger.warning("Clearing existing Neo4j data")
        
        with self.driver.session(database=self.config.database) as session:
            session.run("MATCH (n) DETACH DELETE n")
        
        logger.info("Database cleared")
    
    def _create_constraints_and_indexes(self) -> None:
        """Create constraints and indexes for performance"""
        logger.info("Creating constraints and indexes")
        
        constraints = [
            # Unique constraint on symbol ID
            """
            CREATE CONSTRAINT symbol_id_unique IF NOT EXISTS
            FOR (s:Symbol) REQUIRE s.id IS UNIQUE
            """,
            
            # Indexes for common queries
            """
            CREATE INDEX symbol_name_index IF NOT EXISTS
            FOR (s:Symbol) ON (s.name)
            """,
            """
            CREATE INDEX symbol_type_index IF NOT EXISTS
            FOR (s:Symbol) ON (s.type)
            """,
            """
            CREATE INDEX symbol_namespace_index IF NOT EXISTS
            FOR (s:Symbol) ON (s.namespace)
            """,
            """
            CREATE INDEX symbol_file_index IF NOT EXISTS
            FOR (s:Symbol) ON (s.file_path)
            """,
            """
            CREATE INDEX symbol_composite_index IF NOT EXISTS
            FOR (s:Symbol) ON (s.type, s.namespace)
            """
        ]
        
        with self.driver.session(database=self.config.database) as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                except Exception as e:
                    # Index might already exist
                    logger.debug(f"Constraint/index creation note: {e}")
    
    def _write_nodes_batch(self, nodes: List[Dict[str, Any]]) -> None:
        """Write nodes to Neo4j in batches"""
        logger.info(f"Writing {len(nodes)} nodes in batches of {self.config.batch_size}")
        
        with self.driver.session(database=self.config.database) as session:
            for i in range(0, len(nodes), self.config.batch_size):
                batch = nodes[i:i + self.config.batch_size]
                
                # Use UNWIND for batch insert
                query = """
                UNWIND $nodes AS node
                MERGE (s:Symbol {id: node.id})
                SET s += node
                """
                
                try:
                    result = session.run(query, nodes=batch)
                    summary = result.consume()
                    self.stats['nodes_created'] += summary.counters.nodes_created
                    self.stats['nodes_updated'] += summary.counters.properties_set
                    
                    if (i + self.config.batch_size) % 10000 == 0:
                        logger.info(f"Processed {i + self.config.batch_size} nodes")
                        
                except Exception as e:
                    logger.error(f"Error writing node batch {i}: {e}")
                    self.stats['errors'] += 1
                    
                    # Try individual inserts for this batch
                    self._write_nodes_individually(batch, session)
    
    def _write_nodes_individually(self, nodes: List[Dict[str, Any]], session) -> None:
        """Fallback to write nodes individually if batch fails"""
        for node in nodes:
            try:
                query = """
                MERGE (s:Symbol {id: $id})
                SET s += $props
                """
                session.run(query, id=node['id'], props=node)
                self.stats['nodes_created'] += 1
            except Exception as e:
                logger.error(f"Error writing node {node.get('id')}: {e}")
                self.stats['errors'] += 1
    
    def _write_relationships_batch(self, edges: List[Dict[str, Any]]) -> None:
        """Write relationships to Neo4j in batches"""
        logger.info(f"Writing {len(edges)} relationships in batches of {self.config.batch_size}")
        
        # Group edges by type for more efficient queries
        edges_by_type = {}
        for edge in edges:
            edge_type = edge['type']
            if edge_type not in edges_by_type:
                edges_by_type[edge_type] = []
            edges_by_type[edge_type].append(edge)
        
        with self.driver.session(database=self.config.database) as session:
            for edge_type, typed_edges in edges_by_type.items():
                logger.info(f"Writing {len(typed_edges)} {edge_type} relationships")
                
                for i in range(0, len(typed_edges), self.config.batch_size):
                    batch = typed_edges[i:i + self.config.batch_size]
                    
                    # Dynamic relationship type
                    query = f"""
                    UNWIND $edges AS edge
                    MATCH (source:Symbol {{id: edge.source_id}})
                    MATCH (target:Symbol {{id: edge.target_id}})
                    MERGE (source)-[r:{edge_type}]->(target)
                    SET r.line_number = edge.line_number,
                        r.column_number = edge.column_number,
                        r.context = edge.context
                    """
                    
                    try:
                        result = session.run(query, edges=batch)
                        summary = result.consume()
                        self.stats['relationships_created'] += summary.counters.relationships_created
                        
                    except Exception as e:
                        logger.error(f"Error writing relationship batch {i} of type {edge_type}: {e}")
                        self.stats['errors'] += 1
                        
                        # Try individual inserts
                        self._write_relationships_individually(batch, edge_type, session)
    
    def _write_relationships_individually(self, edges: List[Dict[str, Any]], 
                                         edge_type: str, session) -> None:
        """Fallback to write relationships individually if batch fails"""
        for edge in edges:
            try:
                query = f"""
                MATCH (source:Symbol {{id: $source_id}})
                MATCH (target:Symbol {{id: $target_id}})
                MERGE (source)-[r:{edge_type}]->(target)
                SET r.line_number = $line_number,
                    r.column_number = $column_number,
                    r.context = $context
                """
                session.run(
                    query,
                    source_id=edge['source_id'],
                    target_id=edge['target_id'],
                    line_number=edge.get('line_number'),
                    column_number=edge.get('column_number'),
                    context=edge.get('context')
                )
                self.stats['relationships_created'] += 1
            except Exception as e:
                logger.error(f"Error writing relationship {edge}: {e}")
                self.stats['errors'] += 1
    
    def _create_additional_indexes(self) -> None:
        """Create additional indexes for query performance"""
        logger.info("Creating additional indexes for query performance")
        
        # Create fulltext index for searching
        fulltext_index = """
        CREATE FULLTEXT INDEX symbol_search IF NOT EXISTS
        FOR (s:Symbol)
        ON EACH [s.name, s.namespace]
        """
        
        with self.driver.session(database=self.config.database) as session:
            try:
                session.run(fulltext_index)
            except Exception as e:
                logger.debug(f"Fulltext index note: {e}")
    
    def run_query(self, cypher: str, parameters: Dict[str, Any] = None) -> List[Dict]:
        """Run a Cypher query and return results"""
        if not self.driver:
            self.connect()
        
        with self.driver.session(database=self.config.database) as session:
            result = session.run(cypher, parameters or {})
            return [dict(record) for record in result]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics"""
        stats_queries = {
            'total_nodes': "MATCH (n) RETURN count(n) as count",
            'total_relationships': "MATCH ()-[r]->() RETURN count(r) as count",
            'nodes_by_type': """
                MATCH (n:Symbol)
                RETURN n.type as type, count(n) as count
                ORDER BY count DESC
            """,
            'relationships_by_type': """
                MATCH ()-[r]->()
                RETURN type(r) as type, count(r) as count
                ORDER BY count DESC
            """,
            'files_indexed': """
                MATCH (n:Symbol)
                RETURN count(DISTINCT n.file_path) as count
            """
        }
        
        stats = {}
        for key, query in stats_queries.items():
            try:
                result = self.run_query(query)
                if key in ['nodes_by_type', 'relationships_by_type']:
                    stats[key] = {r['type']: r['count'] for r in result}
                else:
                    stats[key] = result[0]['count'] if result else 0
            except Exception as e:
                logger.error(f"Error getting {key}: {e}")
                stats[key] = "Error"
        
        return stats