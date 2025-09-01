#!/usr/bin/env python3
"""
Final Neo4j Export for Complete EspoCRM Code Graph
"""

import sqlite3
import json
import sys

def export_to_neo4j():
    """Export complete code graph to Neo4j"""
    
    # Connect to database
    conn = sqlite3.connect('.cache/complete_espocrm.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all symbols
    symbols = cursor.execute("SELECT * FROM symbols").fetchall()
    references = cursor.execute("SELECT * FROM symbol_references").fetchall()
    
    print(f"Exporting {len(symbols)} symbols and {len(references)} references to Neo4j")
    
    # Create Cypher export file
    with open('espocrm_complete_graph.cypher', 'w') as f:
        # Clear database
        f.write("// Clear existing data\n")
        f.write("MATCH (n) DETACH DELETE n;\n\n")
        
        # Create indexes for performance
        f.write("// Create indexes\n")
        f.write("CREATE INDEX symbol_id IF NOT EXISTS FOR (s:Symbol) ON (s.id);\n")
        f.write("CREATE INDEX class_name IF NOT EXISTS FOR (c:Class) ON (c.name);\n")
        f.write("CREATE INDEX method_name IF NOT EXISTS FOR (m:Method) ON (m.name);\n")
        f.write("CREATE INDEX function_name IF NOT EXISTS FOR (f:Function) ON (f.name);\n\n")
        
        # Create nodes
        f.write("// Create nodes\n")
        for symbol in symbols:
            # Determine node labels based on type
            symbol_type = symbol['type']
            labels = ['Symbol']
            
            if symbol_type == 'class':
                labels.append('Class')
            elif symbol_type == 'method':
                labels.append('Method')
            elif symbol_type == 'function':
                labels.append('Function')
            elif symbol_type == 'property':
                labels.append('Property')
            elif symbol_type == 'constant':
                labels.append('Constant')
            elif symbol_type == 'trait':
                labels.append('Trait')
            elif symbol_type == 'interface':
                labels.append('Interface')
            elif symbol_type == 'namespace':
                labels.append('Namespace')
            elif symbol_type and symbol_type.startswith('js_'):
                labels.append('JavaScript')
                labels.append(symbol_type.replace('js_', '').title())
            
            # Build properties
            props = {
                'id': symbol['id'],
                'name': symbol['name'],
                'type': symbol_type,
                'file': symbol['file_path'],
            }
            
            if symbol['line_number']:
                props['line'] = symbol['line_number']
            
            if symbol['namespace']:
                props['namespace'] = symbol['namespace']
                
            # Create node
            labels_str = ':'.join(labels)
            props_str = ', '.join([f'{k}: {json.dumps(v)}' for k, v in props.items()])
            f.write(f"CREATE (:{labels_str} {{{props_str}}});\n")
        
        f.write("\n// Create relationships\n")
        
        # Create relationships
        relationship_count = {}
        for ref in references:
            rel_type = ref['reference_type'].replace('-', '_').upper()
            relationship_count[rel_type] = relationship_count.get(rel_type, 0) + 1
            
            f.write(f"MATCH (s:Symbol {{id: '{ref['source_id']}'}}), ")
            f.write(f"(t:Symbol {{id: '{ref['target_id']}'}}) ")
            f.write(f"CREATE (s)-[:{rel_type}]->(t);\n")
        
        # Add statistics as comments
        f.write("\n// Statistics\n")
        f.write(f"// Total Symbols: {len(symbols)}\n")
        f.write(f"// Total References: {len(references)}\n")
        f.write("// Relationship Types:\n")
        for rel_type, count in sorted(relationship_count.items(), key=lambda x: x[1], reverse=True):
            f.write(f"//   {rel_type}: {count}\n")
    
    conn.close()
    
    print("✅ Created espocrm_complete_graph.cypher")
    print("\nTo import into Neo4j:")
    print("  1. Start Neo4j: neo4j start")
    print("  2. Import: cat espocrm_complete_graph.cypher | cypher-shell -u neo4j -p your_password")
    print("  3. Open browser: http://localhost:7474")
    print("\nSample queries:")
    print("  - All classes: MATCH (c:Class) RETURN c LIMIT 50")
    print("  - Inheritance: MATCH (c:Class)-[:EXTENDS]->(p:Class) RETURN c, p")
    print("  - Method calls: MATCH (m:Method)-[:CALLS]->(t:Method) RETURN m, t LIMIT 100")
    print("  - Return types: MATCH (m:Method)-[:RETURNS]->(t:Class) RETURN m, t LIMIT 50")

if __name__ == "__main__":
    export_to_neo4j()