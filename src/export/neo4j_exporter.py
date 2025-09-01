#!/usr/bin/env python3
"""Export complete EspoCRM graph to Neo4j including FILES and DIRECTORIES"""

import sqlite3
import hashlib
from pathlib import Path
from collections import defaultdict

def generate_id(text):
    """Generate consistent ID for any text"""
    return hashlib.md5(text.encode()).hexdigest()

def export_to_neo4j_with_files():
    """Export complete graph including file system structure"""
    
    # Connect to SQLite
    conn = sqlite3.connect('.cache/complete_espocrm.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Track directories and files
    directories = set()
    files = {}  # file_path -> file_id
    file_symbols = defaultdict(list)  # file_path -> [symbol_ids]
    
    print("=== Exporting Complete Graph with File System ===")
    
    # Get all symbols with their files
    cursor.execute("""
        SELECT id, name, type, file_path, line_number, namespace
        FROM symbols
    """)
    
    symbols = cursor.fetchall()
    print(f"Found {len(symbols)} symbols")
    
    # Output file
    with open('espocrm_complete_with_files.cypher', 'w') as f:
        f.write("// EspoCRM Complete Graph with File System\n")
        f.write("// Clean database first\n")
        f.write("MATCH (n) DETACH DELETE n;\n\n")
        
        # Create indexes
        f.write("// Create indexes\n")
        f.write("CREATE INDEX IF NOT EXISTS FOR (d:Directory) ON (d.path);\n")
        f.write("CREATE INDEX IF NOT EXISTS FOR (f:File) ON (f.path);\n")
        f.write("CREATE INDEX IF NOT EXISTS FOR (f:File) ON (f.id);\n")
        f.write("CREATE INDEX IF NOT EXISTS FOR (n:Namespace) ON (n.id);\n")
        f.write("CREATE INDEX IF NOT EXISTS FOR (c:Class) ON (c.id);\n")
        f.write("CREATE INDEX IF NOT EXISTS FOR (m:Method) ON (m.id);\n")
        f.write("CREATE INDEX IF NOT EXISTS FOR (p:Property) ON (p.id);\n")
        f.write("CREATE INDEX IF NOT EXISTS FOR (c:Constant) ON (c.id);\n")
        f.write("CREATE INDEX IF NOT EXISTS FOR (i:Interface) ON (i.id);\n")
        f.write("CREATE INDEX IF NOT EXISTS FOR (t:Trait) ON (t.id);\n")
        f.write("CREATE INDEX IF NOT EXISTS FOR (f:Function) ON (f.id);\n\n")
        
        # Process symbols and collect file/directory info
        print("\nProcessing symbols and files...")
        for row in symbols:
            symbol_id = row['id']
            name = row['name']
            symbol_type = row['type']
            file_path = row['file_path']
            line = row['line_number']
            namespace = row['namespace']
            if file_path:
                # Clean file path
                file_path = file_path.replace('espocrm/', '')
                
                # Generate file ID
                file_id = generate_id(file_path)
                files[file_path] = file_id
                file_symbols[file_path].append(symbol_id)
                
                # Extract directory structure
                parts = file_path.split('/')
                for i in range(1, len(parts)):
                    dir_path = '/'.join(parts[:i])
                    directories.add(dir_path)
        
        print(f"Found {len(directories)} directories")
        print(f"Found {len(files)} files")
        
        # Create DIRECTORY nodes
        f.write("// Directory nodes\n")
        created_dirs = {}
        for dir_path in sorted(directories):
            dir_id = generate_id(dir_path)
            created_dirs[dir_path] = dir_id
            
            dir_name = dir_path.split('/')[-1] if '/' in dir_path else dir_path
            parent_path = '/'.join(dir_path.split('/')[:-1]) if '/' in dir_path else None
            
            f.write(f"CREATE (:Directory {{id: '{dir_id}', path: '{dir_path}', name: '{dir_name}'}});\n")
        
        # Create FILE nodes
        f.write("\n// File nodes\n")
        for file_path, file_id in sorted(files.items()):
            file_name = file_path.split('/')[-1]
            extension = file_name.split('.')[-1] if '.' in file_name else ''
            
            # Escape single quotes and backslashes in file paths
            safe_path = file_path.replace("\\", "\\\\").replace("'", "\\'")
            safe_name = file_name.replace("\\", "\\\\").replace("'", "\\'")
            
            f.write(f"CREATE (:File {{id: '{file_id}', path: '{safe_path}', name: '{safe_name}', extension: '{extension}'}});\n")
        
        # Create Symbol nodes (without Symbol: prefix)
        f.write("\n// Symbol nodes\n")
        for row in symbols:
            symbol_id = row['id']
            name = row['name']
            symbol_type = row['type']
            file_path = row['file_path']
            line = row['line_number']
            namespace = row['namespace']
            
            # Determine the label based on type
            label_map = {
                'class': 'Class',
                'interface': 'Interface',
                'trait': 'Trait',
                'method': 'Method',
                'function': 'Function',
                'property': 'Property',
                'constant': 'Constant',
                'namespace': 'Namespace'
            }
            
            label = label_map.get(symbol_type, 'Symbol')
            
            # Escape single quotes and backslashes
            safe_name = name.replace("\\", "\\\\").replace("'", "\\'") if name else ''
            safe_file = file_path.replace("\\", "\\\\").replace("'", "\\'") if file_path else ''
            safe_namespace = namespace.replace("\\", "\\\\").replace("'", "\\'") if namespace else ''
            
            # Build properties
            props = [
                f"id: '{symbol_id}'",
                f"name: '{safe_name}'",
                f"type: '{symbol_type}'"
            ]
            
            if file_path:
                props.append(f"file: '{safe_file}'")
            if line:
                props.append(f"line: {line}")
            if namespace:
                props.append(f"namespace: '{safe_namespace}'")
            
            f.write(f"CREATE (:{label} {{{', '.join(props)}}});\n")
        
        # Create CONTAINS relationships (Directory -> Directory)
        f.write("\n// Directory CONTAINS Directory relationships\n")
        for dir_path in sorted(directories):
            if '/' in dir_path:
                parent_path = '/'.join(dir_path.split('/')[:-1])
                if parent_path in created_dirs:
                    parent_id = created_dirs[parent_path]
                    child_id = created_dirs[dir_path]
                    f.write(f"MATCH (p:Directory {{id: '{parent_id}'}}), (c:Directory {{id: '{child_id}'}}) CREATE (p)-[:CONTAINS]->(c);\n")
        
        # Create CONTAINS relationships (Directory -> File)
        f.write("\n// Directory CONTAINS File relationships\n")
        for file_path, file_id in sorted(files.items()):
            if '/' in file_path:
                dir_path = '/'.join(file_path.split('/')[:-1])
                if dir_path in created_dirs:
                    dir_id = created_dirs[dir_path]
                    f.write(f"MATCH (d:Directory {{id: '{dir_id}'}}), (f:File {{id: '{file_id}'}}) CREATE (d)-[:CONTAINS]->(f);\n")
        
        # Create DEFINES relationships (File -> Symbol)
        f.write("\n// File DEFINES Symbol relationships\n")
        for file_path, symbol_ids in file_symbols.items():
            file_id = files[file_path]
            for symbol_id in symbol_ids:
                f.write(f"MATCH (f:File {{id: '{file_id}'}}), (s {{id: '{symbol_id}'}}) CREATE (f)-[:DEFINES]->(s);\n")
        
        # Get all references (edges between symbols)
        f.write("\n// Symbol relationships\n")
        cursor.execute("""
            SELECT source_id, target_id, reference_type
            FROM symbol_references
        """)
        
        references = cursor.fetchall()
        print(f"Found {len(references)} references")
        
        for source_id, target_id, ref_type in references:
            f.write(f"MATCH (s {{id: '{source_id}'}}), (t {{id: '{target_id}'}}) CREATE (s)-[:{ref_type}]->(t);\n")
    
    conn.close()
    
    print(f"\n✅ Export complete!")
    print(f"   Directories: {len(directories)}")
    print(f"   Files: {len(files)}")
    print(f"   Symbols: {len(symbols)}")
    print(f"   References: {len(references)}")
    print(f"\nSaved to: espocrm_complete_with_files.cypher")

if __name__ == "__main__":
    export_to_neo4j_with_files()