#!/usr/bin/env python3
"""
OPTIMIZED Neo4j Bulk Importer using UNWIND
Maximum performance for large graphs - THE FINAL SOLUTION!
"""

import re
import json
import time
from neo4j import GraphDatabase
from pathlib import Path
from typing import List, Dict, Tuple

class BulkNeo4jImporter:
    """Ultra-fast Neo4j importer using UNWIND for bulk operations"""
    
    def __init__(self, uri="bolt://localhost:7688", user="neo4j", password="password123"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.nodes = []
        self.relationships = []
        self.stats = {
            'nodes_created': 0,
            'relationships_created': 0,
            'time_taken': 0
        }
        
    def parse_cypher_file(self, cypher_file: str):
        """Parse Cypher file into bulk-ready data structures"""
        print(f"📖 Parsing {cypher_file}...")
        
        with open(cypher_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Split into statements
        statements = content.strip().split('\n')
        
        for stmt in statements:
            stmt = stmt.strip()
            if not stmt or stmt.startswith('//'):
                continue
                
            if stmt.startswith('CREATE ('):
                self._parse_node(stmt)
            elif stmt.startswith('MATCH'):
                self._parse_relationship(stmt)
                
        print(f"📊 Parsed {len(self.nodes)} nodes and {len(self.relationships)} relationships")
        
    def _parse_node(self, statement: str):
        """Parse CREATE node statement"""
        # Pattern: CREATE (n:Label {prop1: 'value1', prop2: 'value2'})
        match = re.match(r"CREATE \([^:]+:(\w+)\s*({[^}]+})\)", statement)
        if match:
            label = match.group(1)
            props_str = match.group(2)
            
            # Parse properties - handle escaped quotes
            props = {}
            # Use a more robust property parser
            prop_pattern = r"(\w+):\s*'((?:[^'\\]|\\.)*)'"
            for prop_match in re.finditer(prop_pattern, props_str):
                key = prop_match.group(1)
                value = prop_match.group(2).replace("\\'", "'").replace("\\\\", "\\")
                props[key] = value
                
            self.nodes.append({
                'label': label,
                'properties': props
            })
            
    def _parse_relationship(self, statement: str):
        """Parse MATCH and CREATE relationship statement"""
        # Pattern: MATCH (s:Label {id: 'id1'}), (t:Label {id: 'id2'}) CREATE (s)-[:REL_TYPE]->(t)
        patterns = [
            # With labels
            r"MATCH \(s:?\w*\s*{id:\s*'([^']+)'}\),\s*\(t:?\w*\s*{id:\s*'([^']+)'}\)\s*CREATE \(s\)-\[:(\w+)\]->\(t\)",
            # Without labels
            r"MATCH \(s\s*{id:\s*'([^']+)'}\),\s*\(t\s*{id:\s*'([^']+)'}\)\s*CREATE \(s\)-\[:(\w+)\]->\(t\)",
        ]
        
        for pattern in patterns:
            match = re.match(pattern, statement)
            if match:
                self.relationships.append({
                    'source_id': match.group(1),
                    'target_id': match.group(2),
                    'type': match.group(3)
                })
                break
                
    def import_to_neo4j(self):
        """Import everything to Neo4j using bulk operations"""
        start_time = time.time()
        
        print("\n🚀 Starting Neo4j import...")
        
        # Create indexes first for performance
        self._create_indexes()
        
        # Import nodes in bulk
        self._bulk_create_nodes()
        
        # Import relationships in bulk
        self._bulk_create_relationships()
        
        self.stats['time_taken'] = time.time() - start_time
        
        print("\n✅ Import complete!")
        print(f"📊 Created {self.stats['nodes_created']} nodes")
        print(f"📊 Created {self.stats['relationships_created']} relationships")
        print(f"⏱️ Time taken: {self.stats['time_taken']:.2f} seconds")
        
    def _create_indexes(self):
        """Create indexes for better performance"""
        print("📑 Creating indexes...")
        
        with self.driver.session() as session:
            # Get unique labels
            labels = set(node['label'] for node in self.nodes)
            
            for label in labels:
                try:
                    # Create index on id property for each label
                    session.run(f"CREATE INDEX {label}_id IF NOT EXISTS FOR (n:{label}) ON (n.id)")
                except:
                    pass  # Index might already exist
                    
    def _bulk_create_nodes(self, batch_size=5000):
        """Create nodes in bulk using UNWIND"""
        print(f"📦 Creating {len(self.nodes)} nodes in batches of {batch_size}...")
        
        with self.driver.session() as session:
            # Group nodes by label for efficiency
            nodes_by_label = {}
            for node in self.nodes:
                label = node['label']
                if label not in nodes_by_label:
                    nodes_by_label[label] = []
                nodes_by_label[label].append(node['properties'])
            
            # Process each label group
            for label, properties_list in nodes_by_label.items():
                print(f"  Creating {len(properties_list)} {label} nodes...")
                
                # Process in batches
                for i in range(0, len(properties_list), batch_size):
                    batch = properties_list[i:i+batch_size]
                    
                    query = f"""
                    UNWIND $batch AS props
                    CREATE (n:{label})
                    SET n = props
                    """
                    
                    session.run(query, batch=batch)
                    self.stats['nodes_created'] += len(batch)
                    
                    if (i + batch_size) % 10000 == 0:
                        print(f"    Progress: {min(i+batch_size, len(properties_list))}/{len(properties_list)}")
                        
    def _bulk_create_relationships(self, batch_size=1000):
        """Create relationships in bulk using UNWIND"""
        print(f"🔗 Creating {len(self.relationships)} relationships...")
        
        with self.driver.session() as session:
            # Group relationships by type
            rels_by_type = {}
            for rel in self.relationships:
                rel_type = rel['type']
                if rel_type not in rels_by_type:
                    rels_by_type[rel_type] = []
                rels_by_type[rel_type].append({
                    'source_id': rel['source_id'],
                    'target_id': rel['target_id']
                })
            
            # Process each relationship type
            for rel_type, rels in rels_by_type.items():
                print(f"  Creating {len(rels)} {rel_type} relationships...")
                
                # Process in batches
                for i in range(0, len(rels), batch_size):
                    batch = rels[i:i+batch_size]
                    
                    query = f"""
                    UNWIND $batch AS rel
                    MATCH (s {{id: rel.source_id}})
                    MATCH (t {{id: rel.target_id}})
                    CREATE (s)-[r:{rel_type}]->(t)
                    """
                    
                    try:
                        session.run(query, batch=batch)
                        self.stats['relationships_created'] += len(batch)
                    except Exception as e:
                        print(f"    Warning: Some {rel_type} relationships failed: {e}")
                        
                    if (i + batch_size) % 5000 == 0:
                        print(f"    Progress: {min(i+batch_size, len(rels))}/{len(rels)}")
                        
    def verify_import(self):
        """Verify the import was successful"""
        print("\n🔍 Verifying import...")
        
        with self.driver.session() as session:
            # Count nodes
            result = session.run("MATCH (n) RETURN COUNT(n) as count")
            node_count = result.single()['count']
            
            # Count relationships
            result = session.run("MATCH ()-[r]->() RETURN COUNT(r) as count")
            rel_count = result.single()['count']
            
            # Get relationship distribution
            result = session.run("""
                MATCH ()-[r]->()
                RETURN TYPE(r) as type, COUNT(r) as count
                ORDER BY count DESC
                LIMIT 10
            """)
            
            print(f"\n📊 Graph Statistics:")
            print(f"  Total Nodes: {node_count:,}")
            print(f"  Total Relationships: {rel_count:,}")
            print(f"\n  Top Relationship Types:")
            for record in result:
                print(f"    {record['type']}: {record['count']:,}")
                
    def close(self):
        """Close the driver connection"""
        self.driver.close()


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Bulk import Cypher to Neo4j')
    parser.add_argument('cypher_file', help='Path to Cypher file')
    parser.add_argument('--uri', default='bolt://localhost:7688', help='Neo4j URI')
    parser.add_argument('--user', default='neo4j', help='Neo4j username')
    parser.add_argument('--password', default='password123', help='Neo4j password')
    parser.add_argument('--verify', action='store_true', help='Verify after import')
    
    args = parser.parse_args()
    
    importer = BulkNeo4jImporter(args.uri, args.user, args.password)
    
    try:
        # Parse the Cypher file
        importer.parse_cypher_file(args.cypher_file)
        
        # Import to Neo4j
        importer.import_to_neo4j()
        
        # Verify if requested
        if args.verify:
            importer.verify_import()
            
    finally:
        importer.close()


if __name__ == '__main__':
    main()