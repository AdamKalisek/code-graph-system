#!/usr/bin/env python3
"""
Resolve PHP inheritance relationships after indexing
Creates EXTENDS, IMPLEMENTS, and USES_TRAIT relationships
"""

import sys
sys.path.append('.')

from code_graph_system.core.graph_store import FederatedGraphStore


def resolve_php_relationships():
    """Create PHP inheritance relationships based on stored metadata"""
    
    print("🔗 Resolving PHP inheritance relationships...")
    
    # Connect to Neo4j
    graph = FederatedGraphStore(
        'bolt://localhost:7688',
        ('neo4j', 'password123'),
        {'federation': {'mode': 'unified'}}
    )
    
    counts = {
        'extends': 0,
        'implements': 0,
        'uses_trait': 0
    }
    
    # Process each PHP file's relationships
    from plugins.php.plugin import PHPLanguagePlugin
    from pathlib import Path
    
    php_plugin = PHPLanguagePlugin()
    php_plugin.initialize({})
    
    # Get PHP files that were indexed
    php_files = [
        'espocrm/application/Espo/Core/Entity.php',
        'espocrm/application/Espo/Entities/User.php',
        'espocrm/application/Espo/Modules/Crm/Entities/Lead.php',
        'espocrm/application/Espo/Modules/Crm/Entities/Account.php',
        'espocrm/application/Espo/Controllers/User.php',
        'espocrm/application/Espo/Modules/Crm/Controllers/Lead.php',
        'espocrm/application/Espo/Modules/Crm/Controllers/Account.php',
        'espocrm/application/Espo/Core/Controllers/Base.php',
        'espocrm/application/Espo/Core/Controllers/Record.php',
        'espocrm/application/Espo/Services/User.php',
        'espocrm/application/Espo/Modules/Crm/Services/Lead.php',
    ]
    
    for file_path in php_files:
        if not Path(file_path).exists():
            continue
            
        # Parse the file to get relationships
        result = php_plugin.parse_file(file_path)
        
        # Process relationships that have target_fqn
        for rel in result.relationships:
            if rel.type == 'EXTENDS' and hasattr(rel, 'metadata') and rel.metadata:
                target_fqn = rel.metadata.get('target_fqn')
                if target_fqn:
                    # Try to find the target node
                    target = graph.query("""
                        MATCH (t:Symbol:PHP)
                        WHERE t.qualified_name = $fqn OR t.fqn = $fqn
                        RETURN t.id as id
                        LIMIT 1
                    """, {'fqn': target_fqn})
                    
                    if target:
                        # Create the EXTENDS relationship
                        created = graph.graph.run("""
                            MATCH (c:Symbol {id: $source_id})
                            MATCH (p:Symbol {id: $target_id})
                            MERGE (c)-[r:EXTENDS]->(p)
                            RETURN count(r) as created
                        """, source_id=rel.source_id, target_id=target[0]['id']).data()
                        
                        if created and created[0]['created'] > 0:
                            counts['extends'] += 1
                            print(f"   ✓ EXTENDS: {rel.source_id[:8]}... -> {target_fqn}")
            
            elif rel.type == 'IMPLEMENTS' and hasattr(rel, 'metadata') and rel.metadata:
                target_fqn = rel.metadata.get('target_fqn')
                if target_fqn:
                    # Try to find the target interface
                    target = graph.query("""
                        MATCH (i:Symbol:PHP)
                        WHERE i.qualified_name = $fqn OR i.fqn = $fqn
                        RETURN i.id as id
                        LIMIT 1
                    """, {'fqn': target_fqn})
                    
                    if target:
                        # Create the IMPLEMENTS relationship
                        created = graph.graph.run("""
                            MATCH (c:Symbol {id: $source_id})
                            MATCH (i:Symbol {id: $target_id})
                            MERGE (c)-[r:IMPLEMENTS]->(i)
                            RETURN count(r) as created
                        """, source_id=rel.source_id, target_id=target[0]['id']).data()
                        
                        if created and created[0]['created'] > 0:
                            counts['implements'] += 1
                            print(f"   ✓ IMPLEMENTS: {rel.source_id[:8]}... -> {target_fqn}")
            
            elif rel.type == 'USES_TRAIT' and hasattr(rel, 'metadata') and rel.metadata:
                target_fqn = rel.metadata.get('target_fqn')
                if target_fqn:
                    # Try to find the target trait
                    target = graph.query("""
                        MATCH (t:Symbol:PHP)
                        WHERE t.qualified_name = $fqn OR t.fqn = $fqn
                        RETURN t.id as id
                        LIMIT 1
                    """, {'fqn': target_fqn})
                    
                    if target:
                        # Create the USES_TRAIT relationship
                        created = graph.graph.run("""
                            MATCH (c:Symbol {id: $source_id})
                            MATCH (t:Symbol {id: $target_id})
                            MERGE (c)-[r:USES_TRAIT]->(t)
                            RETURN count(r) as created
                        """, source_id=rel.source_id, target_id=target[0]['id']).data()
                        
                        if created and created[0]['created'] > 0:
                            counts['uses_trait'] += 1
                            print(f"   ✓ USES_TRAIT: {rel.source_id[:8]}... -> {target_fqn}")
    
    print("\n📊 Results:")
    print(f"   EXTENDS: {counts['extends']}")
    print(f"   IMPLEMENTS: {counts['implements']}")
    print(f"   USES_TRAIT: {counts['uses_trait']}")
    
    return counts


if __name__ == '__main__':
    resolve_php_relationships()