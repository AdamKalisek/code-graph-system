#!/usr/bin/env python3
"""Import inheritance relationships to Neo4j using MCP in batches"""

import re

def load_cypher_file(file_path):
    """Load and parse Cypher statements"""
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    statements = []
    for line in lines:
        line = line.strip()
        if line and line.startswith('MATCH'):
            statements.append(line)
    return statements

def extract_ids_and_type(statement):
    """Extract source ID, target ID, and relationship type from Cypher statement"""
    # Pattern: MATCH (s {id: 'SOURCE'}), (t {id: 'TARGET'}) CREATE (s)-[:TYPE]->(t);
    pattern = r"MATCH \(s \{id: '([^']+)'\}\), \(t \{id: '([^']+)'\}\) CREATE \(s\)-\[:(\w+)\]->\(t\)"
    match = re.match(pattern, statement)
    if match:
        return match.group(1), match.group(2), match.group(3)
    return None, None, None

def main():
    # Load statements
    statements = load_cypher_file('inheritance.cypher')
    print(f"Found {len(statements)} inheritance relationships to import")
    
    # Group by relationship type
    extends = []
    implements = []
    uses_trait = []
    
    for stmt in statements:
        source_id, target_id, rel_type = extract_ids_and_type(stmt)
        if source_id and target_id:
            if rel_type == 'EXTENDS':
                extends.append((source_id, target_id))
            elif rel_type == 'IMPLEMENTS':
                implements.append((source_id, target_id))
            elif rel_type == 'USES_TRAIT':
                uses_trait.append((source_id, target_id))
    
    print(f"\nBreakdown:")
    print(f"  EXTENDS: {len(extends)}")
    print(f"  IMPLEMENTS: {len(implements)}")
    print(f"  USES_TRAIT: {len(uses_trait)}")
    
    # Write batch import files
    with open('extends_batch.cypher', 'w') as f:
        for source, target in extends:
            f.write(f"MATCH (s {{id: '{source}'}}), (t {{id: '{target}'}}) CREATE (s)-[:EXTENDS]->(t);\n")
    
    with open('implements_batch.cypher', 'w') as f:
        for source, target in implements:
            f.write(f"MATCH (s {{id: '{source}'}}), (t {{id: '{target}'}}) CREATE (s)-[:IMPLEMENTS]->(t);\n")
    
    with open('uses_trait_batch.cypher', 'w') as f:
        for source, target in uses_trait:
            f.write(f"MATCH (s {{id: '{source}'}}), (t {{id: '{target}'}}) CREATE (s)-[:USES_TRAIT]->(t);\n")
    
    print(f"\nCreated batch files:")
    print(f"  extends_batch.cypher ({len(extends)} relationships)")
    print(f"  implements_batch.cypher ({len(implements)} relationships)")
    print(f"  uses_trait_batch.cypher ({len(uses_trait)} relationships)")

if __name__ == "__main__":
    main()