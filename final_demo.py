#!/usr/bin/env python3
"""
Final comprehensive demo with all relationships working
"""

import sys
import subprocess
from pathlib import Path

sys.path.append('.')

from code_graph_system.core.graph_store import FederatedGraphStore
from plugins.php.plugin import PHPLanguagePlugin
from plugins.javascript.babel_parser import BabelParser
from plugins.espocrm.route_parser import EspoCRMRouteParser
from plugins.espocrm.cross_linker import CrossLinker


def main():
    print("=" * 70)
    print("  FINAL COMPREHENSIVE DEMO")
    print("=" * 70)
    
    # Clean database
    print("\n🧹 Cleaning database...")
    subprocess.run(['python', 'clean_neo4j.py'], capture_output=True)
    
    # Connect
    graph = FederatedGraphStore(
        'bolt://localhost:7688',
        ('neo4j', 'password123'),
        {'federation': {'mode': 'unified'}}
    )
    
    # Phase 1: Endpoints
    print("\n📡 Phase 1: Indexing Endpoints...")
    parser = EspoCRMRouteParser('espocrm')
    endpoints, rels = parser.parse_all_routes()
    if endpoints:
        graph.store_batch(endpoints, rels)
        print(f"   ✓ {len(endpoints)} endpoints")
    
    # Phase 2: PHP with ALL necessary files
    print("\n🐘 Phase 2: Indexing PHP...")
    php_plugin = PHPLanguagePlugin()
    php_plugin.initialize({})
    
    php_files = [
        # Base classes first
        'espocrm/application/Espo/Core/ORM/Entity.php',
        'espocrm/application/Espo/Core/Controllers/Base.php',
        'espocrm/application/Espo/Core/Controllers/Record.php',
        'espocrm/application/Espo/Core/Services/Base.php',
        'espocrm/application/Espo/Entities/Person.php',
        
        # Entities
        'espocrm/application/Espo/Entities/User.php',
        'espocrm/application/Espo/Modules/Crm/Entities/Lead.php',
        'espocrm/application/Espo/Modules/Crm/Entities/Account.php',
        'espocrm/application/Espo/Modules/Crm/Entities/Contact.php',
        'espocrm/application/Espo/Modules/Crm/Entities/Opportunity.php',
        
        # Controllers (MUST include these!)
        'espocrm/application/Espo/Controllers/User.php',
        'espocrm/application/Espo/Controllers/Team.php',
        'espocrm/application/Espo/Controllers/Email.php',
        'espocrm/application/Espo/Controllers/Import.php',
        'espocrm/application/Espo/Controllers/Attachment.php',
        
        # Services
        'espocrm/application/Espo/Services/User.php',
        
        # Interfaces for IMPLEMENTS demo
        'espocrm/application/Espo/Core/Interfaces/Injectable.php',
        'espocrm/application/Espo/Core/Interfaces/AclAware.php',
        
        # Traits for USES_TRAIT demo  
        'espocrm/application/Espo/Core/Traits/Injectable.php',
        'espocrm/application/Espo/Core/Traits/AclAware.php',
    ]
    
    php_count = 0
    for file_path in php_files:
        if Path(file_path).exists():
            try:
                result = php_plugin.parse_file(file_path)
                if result.nodes:
                    graph.store_batch(result.nodes, result.relationships, 'php')
                    php_count += 1
                    # Show controllers specifically
                    for node in result.nodes:
                        if node.kind == 'class' and 'Controller' in node.name:
                            print(f"   ✓ Controller: {node.qualified_name}")
            except Exception as e:
                print(f"   ✗ {Path(file_path).name}: {e}")
    
    print(f"   Total PHP files: {php_count}")
    
    # Phase 3: JavaScript
    print("\n🌐 Phase 3: Indexing JavaScript...")
    js_parser = BabelParser()
    
    js_files = [
        'espocrm/client/src/app.js',
        'espocrm/client/src/model.js',
        'espocrm/client/src/collection.js',
        'espocrm/client/src/views/user/detail.js',
        'espocrm/client/src/views/record/detail.js',
    ]
    
    js_count = 0
    api_calls_total = 0
    for file_path in js_files:
        if Path(file_path).exists():
            try:
                result = js_parser.parse_file(file_path)
                if result.nodes:
                    graph.store_batch(result.nodes, result.relationships, 'javascript')
                    js_count += 1
                    # Count API calls
                    for node in result.nodes:
                        if hasattr(node, 'metadata') and node.metadata and 'api_calls' in node.metadata:
                            import json
                            calls = json.loads(node.metadata['api_calls'])
                            api_calls_total += len(calls)
                            if calls:
                                print(f"   ✓ {Path(file_path).name}: {len(calls)} API calls")
            except Exception as e:
                print(f"   ✗ {Path(file_path).name}: {e}")
    
    print(f"   Total JS files: {js_count}, API calls: {api_calls_total}")
    
    # Phase 4: Cross-linking
    print("\n🔗 Phase 4: Creating relationships...")
    linker = CrossLinker(graph)
    
    calls = linker.link_js_to_endpoints()
    print(f"   ✓ CALLS: {calls}")
    
    handles = linker.link_endpoints_to_controllers()
    print(f"   ✓ HANDLES: {handles}")
    
    resolved = linker.resolve_inheritance()
    print(f"   ✓ Resolved inheritance: {resolved}")
    
    # Phase 5: Verification
    print("\n📊 Phase 5: Final verification...")
    
    rel_types = [
        'EXTENDS', 'IMPLEMENTS', 'USES_TRAIT', 'CALLS', 'HANDLES',
        'HAS_METHOD', 'HAS_PROPERTY', 'IMPORTS', 'DEFINED_IN'
    ]
    
    print("\n🎯 Relationship counts:")
    for rel_type in rel_types:
        result = graph.query(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as c")
        count = result[0]['c'] if result else 0
        status = "✓" if count > 0 else "✗"
        print(f"   {status} {rel_type}: {count}")
    
    # Check complete chains
    chains = graph.query("""
        MATCH (js:Symbol)-[:CALLS]->(e:Endpoint)<-[:HANDLES]-(php:Symbol)
        WHERE js._language = 'javascript' AND php._language = 'php'
        RETURN 
            js.name as js_file,
            e.path as endpoint,
            php.qualified_name as controller
        LIMIT 3
    """)
    
    print("\n✨ Complete chains (JS → Endpoint → PHP):")
    if chains:
        for chain in chains:
            print(f"   • {chain['js_file']} → {chain['endpoint']} → {chain['controller']}")
    else:
        print("   ✗ No complete chains found")
    
    # Check specific examples
    print("\n📋 Specific examples:")
    
    # EXTENDS
    extends = graph.query("""
        MATCH (child:Symbol:PHP:Class)-[:EXTENDS]->(parent:Symbol:PHP:Class)
        RETURN child.name as child, parent.name as parent
        LIMIT 2
    """)
    if extends:
        print("   EXTENDS:")
        for r in extends:
            print(f"     • {r['child']} extends {r['parent']}")
    
    # IMPLEMENTS
    implements = graph.query("""
        MATCH (c:Symbol:PHP:Class)-[:IMPLEMENTS]->(i:Symbol:PHP:Interface)
        RETURN c.name as class, i.name as interface
        LIMIT 2
    """)
    if implements:
        print("   IMPLEMENTS:")
        for r in implements:
            print(f"     • {r['class']} implements {r['interface']}")
    
    # USES_TRAIT
    traits = graph.query("""
        MATCH (c:Symbol:PHP:Class)-[:USES_TRAIT]->(t:Symbol:PHP:Trait)
        RETURN c.name as class, t.name as trait
        LIMIT 2
    """)
    if traits:
        print("   USES_TRAIT:")
        for r in traits:
            print(f"     • {r['class']} uses {r['trait']}")
    
    print("\n" + "=" * 70)
    print("  ✅ DEMO COMPLETE")
    print("=" * 70)


if __name__ == '__main__':
    main()