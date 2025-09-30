#!/usr/bin/env python3
"""
Fast Cypher-based import - generates optimized Cypher for direct execution
"""

import sqlite3
import time
from pathlib import Path

def generate_optimized_cypher(db_path: str, output_file: str = "optimized_import.cypher"):
    """Generate optimized Cypher statements for bulk import"""
    
    print("Generating optimized Cypher import file...")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    with open(output_file, 'w') as f:
        # Clear database
        f.write("// Clear existing data\n")
        f.write("MATCH (n) DETACH DELETE n;\n\n")
        
        # Create constraints
        f.write("// Create constraints for performance\n")
        f.write("CREATE CONSTRAINT IF NOT EXISTS FOR (s:Symbol) REQUIRE s.id IS UNIQUE;\n")
        f.write("CREATE CONSTRAINT IF NOT EXISTS FOR (f:File) REQUIRE f.id IS UNIQUE;\n")
        f.write("CREATE CONSTRAINT IF NOT EXISTS FOR (d:Directory) REQUIRE d.id IS UNIQUE;\n\n")
        
        # Get all symbols and group by type
        print("  Processing nodes...")
        cursor.execute("SELECT * FROM symbols")
        symbols = cursor.fetchall()
        
        # Group symbols by label combination
        nodes_by_label = {}
        for symbol in symbols:
            labels = []
            symbol_type = symbol['type']
            symbol_id = symbol['id']
            
            # Determine labels
            if symbol_type == 'class':
                labels = ['Symbol', 'PHPClass']
            elif symbol_type == 'interface':
                labels = ['Symbol', 'PHPInterface']
            elif symbol_type == 'trait':
                labels = ['Symbol', 'PHPTrait']
            elif symbol_type == 'method':
                labels = ['Symbol', 'PHPMethod']
            elif symbol_type == 'property':
                labels = ['Symbol', 'PHPProperty']
            elif symbol_type == 'function':
                labels = ['Symbol', 'PHPFunction']
            elif symbol_type == 'file':
                labels = ['File']
            elif symbol_type == 'directory':
                labels = ['Directory']
            elif symbol_id.startswith('js_'):
                if symbol_type == 'module':
                    labels = ['Symbol', 'JSModule']
                else:
                    labels = ['Symbol', 'JSSymbol']
            else:
                labels = ['Symbol', 'PHPSymbol']
            
            label_key = ':'.join(labels)
            if label_key not in nodes_by_label:
                nodes_by_label[label_key] = []
            
            # Build properties - escape quotes
            props = {
                'id': symbol['id'],
                'name': symbol['name'].replace("'", "\\'") if symbol['name'] else '',
                'type': symbol['type']
            }
            
            # Add non-null properties
            for field in ['file_path', 'line_number', 'namespace', 'visibility']:
                if symbol[field] is not None:
                    value = str(symbol[field])
                    if isinstance(symbol[field], str):
                        value = value.replace("'", "\\'")
                    props[field] = value
            
            nodes_by_label[label_key].append(props)
        
        # Write node creation in batches
        f.write("// Create nodes in batches\n")
        for labels, nodes in nodes_by_label.items():
            print(f"    Writing {len(nodes)} {labels} nodes...")
            
            # Use UNWIND for batch creation
            f.write(f"// Create {labels} nodes ({len(nodes)} total)\n")
            f.write("UNWIND [\n")
            
            for i, props in enumerate(nodes):
                prop_str = ', '.join([f"{k}: '{v}'" for k, v in props.items()])
                f.write(f"  {{{prop_str}}}")
                if i < len(nodes) - 1:
                    f.write(",")
                f.write("\n")
            
            f.write(f"] AS props\n")
            f.write(f"CREATE (n:{labels})\n")
            f.write("SET n = props;\n\n")
        
        print(f"  Wrote {len(symbols)} nodes")
        
        # Get relationships and group by type
        print("  Processing relationships...")
        cursor.execute("""
            SELECT reference_type, COUNT(*) as count
            FROM symbol_references
            GROUP BY reference_type
            ORDER BY count DESC
        """)
        rel_types = cursor.fetchall()
        
        # Process each relationship type
        total_rels = 0
        for rel_type, count in rel_types:
            print(f"    Writing {count} {rel_type} relationships...")
            
            cursor.execute("""
                SELECT source_id, target_id, line_number, column_number
                FROM symbol_references
                WHERE reference_type = ?
            """, (rel_type,))
            
            relationships = cursor.fetchall()
            
            # Write in batches of 1000
            batch_size = 1000
            for batch_start in range(0, len(relationships), batch_size):
                batch = relationships[batch_start:batch_start + batch_size]
                
                f.write(f"// Create {rel_type} relationships (batch {batch_start//batch_size + 1})\n")
                f.write("UNWIND [\n")
                
                for i, rel in enumerate(batch):
                    f.write(f"  {{source: '{rel[0]}', target: '{rel[1]}', line: {rel[2]}, col: {rel[3]}}}")
                    if i < len(batch) - 1:
                        f.write(",")
                    f.write("\n")
                
                f.write("] AS rel\n")
                f.write("MATCH (s {id: rel.source})\n")
                f.write("MATCH (t {id: rel.target})\n")
                f.write(f"CREATE (s)-[r:{rel_type}]->(t)\n")
                f.write("SET r.line = rel.line, r.column = rel.col;\n\n")
            
            total_rels += count
        
        print(f"  Wrote {total_rels} relationships")
        
        # Add verification queries
        f.write("// Verification queries\n")
        f.write("MATCH (n) RETURN COUNT(n) as total_nodes;\n")
        f.write("MATCH ()-[r]->() RETURN TYPE(r) as type, COUNT(r) as count ORDER BY count DESC;\n")
    
    conn.close()
    print(f"\n✅ Generated {output_file}")
    print(f"   Nodes: {len(symbols)}")
    print(f"   Relationships: {total_rels}")
    print("\nTo import to Neo4j:")
    print(f"  cat {output_file} | cypher-shell -u neo4j -p password123 --address bolt://localhost:7688")
    
    return output_file

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate optimized Cypher import')
    parser.add_argument('--db', default='data/espocrm_complete.db', help='SQLite database')
    parser.add_argument('--output', default='optimized_import.cypher', help='Output Cypher file')
    
    args = parser.parse_args()
    generate_optimized_cypher(args.db, args.output)

if __name__ == '__main__':
    main()