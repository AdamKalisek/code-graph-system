#!/usr/bin/env python3
"""
Add configuration references directly to Neo4j using MCP.
"""

import sqlite3
import logging

def add_config_references_via_mcp(db_path: str):
    """Add configuration references using MCP Neo4j tool."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all authentication hook registrations
    cursor.execute("""
        SELECT DISTINCT config_file, config_key, class_name 
        FROM config_references
        WHERE reference_type = 'AUTHENTICATION_HOOK'
    """)
    
    hooks = cursor.fetchall()
    logging.info(f"Found {len(hooks)} authentication hooks to add to Neo4j")
    
    # Create Cypher queries to add the registration information
    cypher_queries = []
    
    # First, create ConfigFile nodes
    config_files = set()
    for config_file, _, _ in hooks:
        config_files.add(config_file)
    
    for config_file in config_files:
        query = f"""
        MERGE (f:ConfigFile {{path: '{config_file}', type: 'json'}})
        """
        cypher_queries.append(query)
    
    # Then create REGISTERED_IN relationships
    for config_file, config_key, class_name in hooks:
        # Escape backslashes for Neo4j
        class_name_escaped = class_name.replace('\\', '\\\\')
        query = f"""
        MATCH (c:PHPClass {{name: '{class_name_escaped}'}})
        MATCH (f:ConfigFile {{path: '{config_file}'}})
        MERGE (c)-[:REGISTERED_IN {{config_key: '{config_key}', registration_type: 'AUTHENTICATION_HOOK'}}]->(f)
        SET c.requires_registration = true,
            c.registration_file = '{config_file}',
            c.registration_key = '{config_key}'
        """
        cypher_queries.append(query)
    
    # Add relationship from Manager to hooks
    for _, config_key, class_name in hooks:
        class_name_escaped = class_name.replace('\\', '\\\\')
        query = f"""
        MATCH (m:PHPClass {{name: 'Espo\\\\Core\\\\Authentication\\\\Hook\\\\Manager'}})
        MATCH (h:PHPClass {{name: '{class_name_escaped}'}})
        MERGE (m)-[:LOADS_VIA_CONFIG {{config_key: '{config_key}', mechanism: 'metadata'}}]->(h)
        """
        cypher_queries.append(query)
    
    # Mark methods that use dynamic loading
    query = """
    MATCH (m:PHPMethod)
    WHERE m.class_name = 'Espo\\\\Core\\\\Authentication\\\\Hook\\\\Manager'
    AND m.name IN ['getHookClassNameList', 'getBeforeLoginHookList', 'getOnLoginHookList']
    SET m.uses_dynamic_loading = true,
        m.loading_mechanism = 'metadata_config'
    """
    cypher_queries.append(query)
    
    conn.close()
    
    # Output all queries for manual execution
    print("# Configuration Reference Import Queries for Neo4j\n")
    print("# Execute these queries in Neo4j to add configuration references:\n")
    
    for i, query in enumerate(cypher_queries, 1):
        print(f"// Query {i}")
        print(query.strip())
        print(";")
        print()
    
    print(f"\n# Total: {len(cypher_queries)} queries to execute")
    
    # Also save to file
    with open('add_config_refs.cypher', 'w') as f:
        f.write("// Configuration Reference Import Queries\n\n")
        for query in cypher_queries:
            f.write(query.strip() + ";\n\n")
    
    print(f"\n✅ Queries saved to: add_config_refs.cypher")
    print("You can now:")
    print("1. Copy and paste the queries above into Neo4j Browser")
    print("2. Or run: cat add_config_refs.cypher | cypher-shell")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    add_config_references_via_mcp('data/espocrm_fixed.db')