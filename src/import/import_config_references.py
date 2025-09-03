#!/usr/bin/env python3
"""
Import configuration references to Neo4j to capture runtime behavior
that's invisible to static code analysis.
"""

import sqlite3
from py2neo import Graph, Node, Relationship
import logging
from typing import List, Dict

class ConfigReferenceImporter:
    """Import configuration references from SQLite to Neo4j."""
    
    def __init__(self, db_path: str, neo4j_uri: str = "bolt://localhost:7688"):
        self.db_path = db_path
        # Use no authentication for local Neo4j
        self.graph = Graph(neo4j_uri)
        self.logger = logging.getLogger(__name__)
        
    def import_config_references(self):
        """Import all configuration references to Neo4j."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all config references
        cursor.execute("""
            SELECT config_file, config_key, class_name, reference_type
            FROM config_references
        """)
        
        references = cursor.fetchall()
        self.logger.info(f"Found {len(references)} configuration references to import")
        
        # Create ConfigFile nodes and REGISTERED_IN relationships
        tx = self.graph.begin()
        config_files = {}
        
        for config_file, config_key, class_name, ref_type in references:
            # Create or get ConfigFile node
            if config_file not in config_files:
                config_node = Node("ConfigFile", path=config_file, type="json")
                tx.create(config_node)
                config_files[config_file] = config_node
            else:
                config_node = config_files[config_file]
                
            # Find the PHP class node
            class_query = """
                MATCH (c:PHPClass {name: $class_name})
                RETURN c
                LIMIT 1
            """
            result = self.graph.run(class_query, class_name=class_name).data()
            
            if result:
                class_node = result[0]['c']
                
                # Create REGISTERED_IN relationship
                rel = Relationship(
                    class_node,
                    "REGISTERED_IN",
                    config_node,
                    config_key=config_key,
                    registration_type=ref_type
                )
                tx.create(rel)
                
                # For authentication hooks, also create a special marker
                if ref_type == 'AUTHENTICATION_HOOK':
                    class_node['requires_registration'] = True
                    class_node['registration_file'] = config_file
                    class_node['registration_key'] = config_key
                    tx.push(class_node)
                    
        tx.commit()
        self.logger.info(f"Created {len(config_files)} ConfigFile nodes")
        
        # Create validation queries
        self._create_validation_queries()
        
        conn.close()
        
    def _create_validation_queries(self):
        """Create Neo4j queries to validate hook registration."""
        
        # Query 1: Find orphaned authentication hooks
        orphaned_query = """
            MATCH (c:PHPClass)-[:IMPLEMENTS]->(i:PHPInterface)
            WHERE i.name IN [
                'Espo\\\\Core\\\\Authentication\\\\Hook\\\\BeforeLogin',
                'Espo\\\\Core\\\\Authentication\\\\Hook\\\\OnLogin'
            ]
            AND NOT EXISTS((c)-[:REGISTERED_IN]->(:ConfigFile))
            RETURN c.name as orphaned_hook, i.name as implements
        """
        
        result = self.graph.run(orphaned_query).data()
        if result:
            self.logger.warning(f"⚠️  Found {len(result)} ORPHANED authentication hooks:")
            for row in result:
                self.logger.warning(f"  - {row['orphaned_hook']} implements {row['implements']}")
                
        # Query 2: Find properly registered hooks
        registered_query = """
            MATCH (c:PHPClass)-[r:REGISTERED_IN]->(f:ConfigFile)
            WHERE r.registration_type = 'AUTHENTICATION_HOOK'
            RETURN c.name as hook, r.config_key as hook_type, f.path as config_file
        """
        
        result = self.graph.run(registered_query).data()
        if result:
            self.logger.info(f"✅ Found {len(result)} properly registered authentication hooks")
            
    def add_configuration_edges(self):
        """Add edges from configuration consumers to configured classes."""
        
        # Link Authentication Manager to registered hooks
        query = """
            MATCH (manager:PHPClass {name: 'Espo\\\\Core\\\\Authentication\\\\Hook\\\\Manager'})
            MATCH (hook:PHPClass)-[r:REGISTERED_IN]->(f:ConfigFile)
            WHERE r.registration_type = 'AUTHENTICATION_HOOK'
            CREATE (manager)-[:LOADS_VIA_CONFIG {
                config_file: f.path,
                config_key: r.config_key
            }]->(hook)
        """
        
        self.graph.run(query)
        self.logger.info("Added LOADS_VIA_CONFIG relationships")
        
        # Mark methods that use metadata loading
        query = """
            MATCH (m:PHPMethod)
            WHERE m.class_name = 'Espo\\\\Core\\\\Authentication\\\\Hook\\\\Manager'
            AND m.name IN ['getHookClassNameList', 'getBeforeLoginHookList', 'getOnLoginHookList']
            SET m.uses_dynamic_loading = true,
                m.loading_mechanism = 'metadata_config'
        """
        
        self.graph.run(query)
        self.logger.info("Marked methods using dynamic loading")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Import config references to Neo4j')
    parser.add_argument('--db', required=True, help='Path to SQLite database')
    parser.add_argument('--neo4j', default='bolt://localhost:7688', help='Neo4j connection URI')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    importer = ConfigReferenceImporter(args.db, args.neo4j)
    importer.import_config_references()
    importer.add_configuration_edges()
    
    print("\n✅ Configuration references imported to Neo4j")
    print("You can now query:")
    print("  - (c:PHPClass)-[:REGISTERED_IN]->(f:ConfigFile)")
    print("  - (manager)-[:LOADS_VIA_CONFIG]->(hook)")
    print("  - Classes with {requires_registration: true}")


if __name__ == '__main__':
    main()