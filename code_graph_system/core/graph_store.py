"""
Federated Graph Store for the Universal Code Graph System.

Manages multiple language-specific graphs in Neo4j.
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
import pandas as pd
from py2neo import Graph, Node, Relationship as Neo4jRelationship, NodeMatcher
from py2neo.bulk import create_nodes, create_relationships
import csv

from .schema import CoreNode, Relationship


logger = logging.getLogger(__name__)


class FederatedGraphStore:
    """Manages multiple language-specific graphs in Neo4j"""
    
    def __init__(self, uri: str, auth: Tuple[str, str], config: Dict[str, Any] = None):
        """
        Initialize the federated graph store.
        
        Args:
            uri: Neo4j connection URI (e.g., bolt://localhost:7688)
            auth: Tuple of (username, password)
            config: Optional configuration dictionary
        """
        self.uri = uri
        self.auth = auth
        self.config = config or {}
        
        # Connect to Neo4j
        try:
            self.graph = Graph(uri, auth=auth)
            logger.info(f"Connected to Neo4j at {uri}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise
            
        # Track language-specific databases
        self.language_graphs: Dict[str, str] = {}
        
        # Federation mode: 'unified' or 'per-language'
        self.federation_mode = self.config.get('federation', {}).get('mode', 'per-language')
        
        # Initialize schema
        self._initialize_schema()
        
    def _initialize_schema(self):
        """Initialize graph schema with indexes and constraints"""
        try:
            # Core indexes
            self.graph.run("""
                CREATE INDEX file_path IF NOT EXISTS
                FOR (f:File) ON (f.path)
            """)
            
            self.graph.run("""
                CREATE INDEX symbol_qualified_name IF NOT EXISTS
                FOR (s:Symbol) ON (s.qualified_name)
            """)
            
            self.graph.run("""
                CREATE INDEX node_id IF NOT EXISTS
                FOR (n:Node) ON (n.id)
            """)
            
            # Constraints
            self.graph.run("""
                CREATE CONSTRAINT unique_file_path IF NOT EXISTS
                FOR (f:File) REQUIRE f.path IS UNIQUE
            """)
            
            logger.info("Graph schema initialized")
            
        except Exception as e:
            logger.warning(f"Schema initialization warning: {e}")
            
    def _flatten_dict(self, data: Dict[str, Any], prefix: str = '') -> Dict[str, Any]:
        """
        Flatten nested dictionaries for Neo4j storage.
        
        Args:
            data: Dictionary to flatten
            prefix: Prefix for nested keys
            
        Returns:
            Flattened dictionary with primitive values only
        """
        flattened = {}
        
        for key, value in data.items():
            new_key = f"{prefix}_{key}" if prefix else key
            
            if isinstance(value, dict):
                # Recursively flatten nested dictionaries
                flattened.update(self._flatten_dict(value, new_key))
            elif isinstance(value, list):
                # Convert lists to JSON strings if they contain complex objects
                if value and isinstance(value[0], (dict, list)):
                    flattened[new_key] = json.dumps(value)
                else:
                    flattened[new_key] = value
            elif value is not None:
                # Store primitive values directly
                flattened[new_key] = str(value) if not isinstance(value, (str, int, float, bool)) else value
                
        return flattened
    
    def store_nodes(self, nodes: List[CoreNode], language: str = None) -> int:
        """
        Store nodes in the graph using bulk ingestion with UNWIND and multi-labels.
        
        Args:
            nodes: List of nodes to store
            language: Optional language for federation
            
        Returns:
            Number of nodes stored
        """
        if not nodes:
            return 0
            
        # Group nodes by their label set for efficient bulk operations
        nodes_by_labels = {}
        for node in nodes:
            data = node.to_dict()
            # Add language tag if using unified mode
            if self.federation_mode == 'unified' and language:
                data['_language'] = language
            
            # Get multi-labels if node supports it
            if hasattr(node, 'get_labels'):
                labels = node.get_labels()
                label_key = ':'.join(labels)
            else:
                # Fallback to single label
                node_type = data.get('type', 'Node')
                label_key = node_type
                labels = [node_type]
            
            if label_key not in nodes_by_labels:
                nodes_by_labels[label_key] = {'labels': labels, 'nodes': []}
            
            # Flatten properties for Neo4j
            flattened_props = self._flatten_dict(data)
            nodes_by_labels[label_key]['nodes'].append(flattened_props)
        
        # Bulk create nodes using UNWIND with multi-labels
        total_created = 0
        try:
            for label_key, data in nodes_by_labels.items():
                labels_str = ':'.join(data['labels'])
                node_list = data['nodes']
                
                # Use UNWIND for bulk operations with multi-labels
                query = f"""
                    UNWIND $nodes AS node_data
                    MERGE (n:{labels_str} {{id: node_data.id}})
                    SET n += node_data
                    RETURN count(n) as created
                """
                
                result = self.graph.run(query, nodes=node_list).data()
                if result:
                    total_created += result[0].get('created', 0)
                    
            logger.info(f"Stored {total_created} nodes using bulk ingestion with multi-labels")
            return total_created
            
        except Exception as e:
            logger.error(f"Failed to store nodes: {e}")
            return 0
            
    def store_relationships(self, relationships: List[Relationship]) -> int:
        """
        Store relationships in the graph using bulk ingestion with UNWIND.
        
        Args:
            relationships: List of relationships to store
            
        Returns:
            Number of relationships stored
        """
        if not relationships:
            return 0
            
        # Group relationships by type for efficient bulk operations
        rels_by_type = {}
        for rel in relationships:
            rel_type = rel.type
            if rel_type not in rels_by_type:
                rels_by_type[rel_type] = []
            
            properties = rel.to_dict()
            properties.pop('source_id', None)
            properties.pop('target_id', None)
            properties.pop('type', None)
            
            # Flatten the properties for Neo4j storage
            flattened_props = self._flatten_dict(properties)
            
            rels_by_type[rel_type].append({
                'source_id': str(rel.source_id),
                'target_id': str(rel.target_id),
                'properties': flattened_props
            })
        
        # Bulk create relationships using UNWIND
        total_created = 0
        for rel_type, rel_list in rels_by_type.items():
            try:
                # Use UNWIND for bulk operations (100-1000x faster)
                query = f"""
                    UNWIND $rels AS rel_data
                    MATCH (a {{id: rel_data.source_id}})
                    MATCH (b {{id: rel_data.target_id}})
                    MERGE (a)-[r:{rel_type}]->(b)
                    SET r += rel_data.properties
                    RETURN count(r) as created
                """
                
                result = self.graph.run(query, rels=rel_list).data()
                if result:
                    total_created += result[0].get('created', 0)
                    
            except Exception as e:
                logger.warning(f"Failed to create {rel_type} relationships: {e}")
                
        logger.info(f"Stored {total_created} relationships using bulk ingestion")
        return total_created
        
    def store_batch(self, nodes: List[CoreNode], relationships: List[Relationship], 
                   language: str = None) -> Tuple[int, int]:
        """
        Store a batch of nodes and relationships.
        
        Args:
            nodes: List of nodes
            relationships: List of relationships
            language: Optional language for federation
            
        Returns:
            Tuple of (nodes_stored, relationships_stored)
        """
        nodes_stored = self.store_nodes(nodes, language)
        relationships_stored = self.store_relationships(relationships)
        
        return nodes_stored, relationships_stored
        
    def query(self, cypher: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Execute a Cypher query.
        
        Args:
            cypher: Cypher query string
            params: Query parameters
            
        Returns:
            Query results as list of dictionaries
        """
        try:
            result = self.graph.run(cypher, params or {})
            return result.data()
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return []
            
    def query_language(self, language: str, cypher: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Query within a specific language subgraph.
        
        Args:
            language: Language to query
            cypher: Cypher query string
            params: Query parameters
            
        Returns:
            Query results
        """
        if self.federation_mode == 'unified':
            # Add language filter to query
            filtered_cypher = cypher.replace('MATCH', f"MATCH (n {{_language: '{language}'}})")
            return self.query(filtered_cypher, params)
        else:
            # Query specific database (future implementation)
            return self.query(cypher, params)
            
    def get_node_by_id(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get a node by its ID"""
        result = self.query(
            "MATCH (n {id: $id}) RETURN n",
            {'id': node_id}
        )
        return result[0]['n'] if result else None
        
    def get_node_relationships(self, node_id: str, direction: str = 'both') -> List[Dict[str, Any]]:
        """Get all relationships for a node"""
        if direction == 'outgoing':
            query = "MATCH (n {id: $id})-[r]->(m) RETURN r, m"
        elif direction == 'incoming':
            query = "MATCH (n {id: $id})<-[r]-(m) RETURN r, m"
        else:
            query = "MATCH (n {id: $id})-[r]-(m) RETURN r, m"
            
        return self.query(query, {'id': node_id})
        
    def delete_node(self, node_id: str) -> bool:
        """Delete a node and its relationships"""
        try:
            self.graph.run(
                "MATCH (n {id: $id}) DETACH DELETE n",
                {'id': node_id}
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete node {node_id}: {e}")
            return False
            
    def clear_language_graph(self, language: str) -> bool:
        """Clear all nodes and relationships for a language"""
        try:
            if self.federation_mode == 'unified':
                self.graph.run(
                    "MATCH (n {_language: $language}) DETACH DELETE n",
                    {'language': language}
                )
            else:
                self.graph.run("MATCH (n) DETACH DELETE n")
                
            logger.info(f"Cleared graph for language: {language}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear language graph: {e}")
            return False
            
    def export_csv(self, output_dir: str, language: str = None):
        """
        Export graph to CSV files for backup or analysis.
        
        Args:
            output_dir: Directory to save CSV files
            language: Optional language filter
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Export nodes
        if language and self.federation_mode == 'unified':
            nodes_query = "MATCH (n {_language: $language}) RETURN n"
            params = {'language': language}
        else:
            nodes_query = "MATCH (n) RETURN n"
            params = {}
            
        nodes_result = self.query(nodes_query, params)
        
        if nodes_result:
            # Convert to DataFrame
            nodes_df = pd.DataFrame([n['n'] for n in nodes_result])
            nodes_df.to_csv(output_path / 'nodes.csv', index=False)
            logger.info(f"Exported {len(nodes_df)} nodes to CSV")
            
        # Export relationships
        if language and self.federation_mode == 'unified':
            rels_query = """
                MATCH (n {_language: $language})-[r]-(m {_language: $language})
                RETURN n.id as source, type(r) as type, m.id as target, properties(r) as props
            """
        else:
            rels_query = """
                MATCH (n)-[r]-(m)
                RETURN n.id as source, type(r) as type, m.id as target, properties(r) as props
            """
            
        rels_result = self.query(rels_query, params)
        
        if rels_result:
            rels_df = pd.DataFrame(rels_result)
            rels_df.to_csv(output_path / 'relationships.csv', index=False)
            logger.info(f"Exported {len(rels_df)} relationships to CSV")
            
    def import_csv(self, csv_dir: str):
        """
        Import graph from CSV files.
        
        Args:
            csv_dir: Directory containing CSV files
        """
        csv_path = Path(csv_dir)
        
        # Import nodes
        nodes_file = csv_path / 'nodes.csv'
        if nodes_file.exists():
            nodes_df = pd.read_csv(nodes_file)
            
            for _, row in nodes_df.iterrows():
                node_dict = row.to_dict()
                node_type = node_dict.get('type', 'Node')
                
                query = f"""
                    MERGE (n:{node_type} {{id: $id}})
                    SET n += $properties
                """
                
                self.graph.run(query, id=node_dict['id'], properties=node_dict)
                
            logger.info(f"Imported {len(nodes_df)} nodes from CSV")
            
        # Import relationships
        rels_file = csv_path / 'relationships.csv'
        if rels_file.exists():
            rels_df = pd.read_csv(rels_file)
            
            for _, row in rels_df.iterrows():
                query = f"""
                    MATCH (a {{id: $source}})
                    MATCH (b {{id: $target}})
                    MERGE (a)-[r:{row['type']}]->(b)
                """
                
                self.graph.run(
                    query,
                    source=row['source'],
                    target=row['target']
                )
                
            logger.info(f"Imported {len(rels_df)} relationships from CSV")
            
    def get_statistics(self) -> Dict[str, Any]:
        """Get graph statistics"""
        stats = {}
        
        # Node counts by type
        node_types = self.query("""
            MATCH (n)
            RETURN labels(n)[0] as type, count(n) as count
            ORDER BY count DESC
        """)
        stats['node_types'] = {item['type']: item['count'] for item in node_types}
        
        # Relationship counts by type
        rel_types = self.query("""
            MATCH ()-[r]->()
            RETURN type(r) as type, count(r) as count
            ORDER BY count DESC
        """)
        stats['relationship_types'] = {item['type']: item['count'] for item in rel_types}
        
        # Total counts
        stats['total_nodes'] = sum(stats['node_types'].values())
        stats['total_relationships'] = sum(stats['relationship_types'].values())
        
        # Language distribution (if federated)
        if self.federation_mode == 'unified':
            languages = self.query("""
                MATCH (n)
                WHERE n._language IS NOT NULL
                RETURN n._language as language, count(n) as count
            """)
            stats['languages'] = {item['language']: item['count'] for item in languages}
            
        return stats