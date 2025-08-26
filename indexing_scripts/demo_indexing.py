#!/usr/bin/env python3
"""
Demo indexing for verification
Indexes a small subset of EspoCRM to demonstrate all relationship types
"""

import sys
import time
from pathlib import Path

sys.path.append('.')

from code_graph_system.core.graph_store import FederatedGraphStore
from plugins.php.plugin import PHPLanguagePlugin
from plugins.javascript.babel_parser import BabelParser
from plugins.espocrm.route_parser import EspoCRMRouteParser
from plugins.espocrm.cross_linker import CrossLinker


def index_demo_data():
    """Index sample data for demonstration"""
    print("=" * 70)
    print("  DEMO INDEXING FOR VERIFICATION")
    print("=" * 70)
    print("\n📝 This will index:")
    print("  • API Endpoints from routes.json")
    print("  • Core PHP classes (User, Lead, Account entities)")
    print("  • Sample JavaScript files with API calls")
    print("  • Cross-language relationships")
    print()
    
    # Connect to Neo4j
    print("🔌 Connecting to Neo4j...")
    graph = FederatedGraphStore(
        'bolt://localhost:7688',
        ('neo4j', 'password123'),
        {'federation': {'mode': 'unified'}}
    )
    
    # Statistics
    stats = {
        'endpoints': 0,
        'php_files': 0,
        'js_files': 0,
        'relationships': {
            'EXTENDS': 0,
            'IMPLEMENTS': 0,
            'USES_TRAIT': 0,
            'CALLS': 0,
            'HANDLES': 0
        }
    }
    
    # Phase 1: Index API Endpoints
    print("\n📡 PHASE 1: Indexing API Endpoints...")
    parser = EspoCRMRouteParser('espocrm')
    endpoints, rels = parser.parse_all_routes()
    stats['endpoints'] = len(endpoints)
    if endpoints:
        n, r = graph.store_batch(endpoints, rels)
        print(f"   ✓ Created {len(endpoints)} endpoints")
    
    # Phase 2: Index sample PHP files
    print("\n🐘 PHASE 2: Indexing PHP Classes...")
    php_plugin = PHPLanguagePlugin()
    php_plugin.initialize({})
    
    # Select key PHP files to demonstrate relationships
    php_files = [
        # Base/Parent classes (index these first!)
        'espocrm/application/Espo/Core/ORM/Entity.php',
        'espocrm/application/Espo/Entities/Person.php',
        'espocrm/application/Espo/Core/Controllers/Base.php',
        'espocrm/application/Espo/Core/Controllers/Record.php',
        'espocrm/application/Espo/Core/Services/Base.php',
        
        # Core entities that have inheritance
        'espocrm/application/Espo/Core/Entity.php',
        'espocrm/application/Espo/Entities/User.php',
        'espocrm/application/Espo/Modules/Crm/Entities/Lead.php',
        'espocrm/application/Espo/Modules/Crm/Entities/Account.php',
        'espocrm/application/Espo/Modules/Crm/Entities/Contact.php',
        
        # Controllers that handle endpoints
        'espocrm/application/Espo/Controllers/User.php',
        'espocrm/application/Espo/Modules/Crm/Controllers/Lead.php',
        'espocrm/application/Espo/Modules/Crm/Controllers/Account.php',
        
        # Services
        'espocrm/application/Espo/Services/User.php',
        'espocrm/application/Espo/Modules/Crm/Services/Lead.php',
        
        # Traits to demonstrate USES_TRAIT
        'espocrm/application/Espo/Core/ORM/Entity/Relations.php',
        'espocrm/application/Espo/Core/ORM/Entity/Links.php',
    ]
    
    print(f"   Indexing {len(php_files)} key PHP files...")
    for file_path in php_files:
        if Path(file_path).exists():
            try:
                result = php_plugin.parse_file(file_path)
                if result.nodes:
                    graph.store_batch(result.nodes, result.relationships, 'php')
                    stats['php_files'] += 1
                    print(f"   ✓ {Path(file_path).name}")
            except Exception as e:
                print(f"   ✗ {Path(file_path).name}: {e}")
    
    # Phase 3: Index sample JavaScript files
    print("\n🌐 PHASE 3: Indexing JavaScript Files...")
    js_parser = BabelParser()
    
    # Select JS files that make API calls
    js_files = [
        'espocrm/client/src/views/user/detail.js',
        'espocrm/client/src/views/user/list.js',
        'espocrm/client/modules/crm/src/views/lead/detail.js',
        'espocrm/client/modules/crm/src/views/lead/list.js',
        'espocrm/client/modules/crm/src/views/account/detail.js',
        'espocrm/client/src/app.js',
        'espocrm/client/src/ajax.js',
        'espocrm/client/src/model.js',
        'espocrm/client/src/collection.js',
    ]
    
    print(f"   Indexing {len(js_files)} key JavaScript files...")
    for file_path in js_files:
        if Path(file_path).exists():
            try:
                result = js_parser.parse_file(file_path)
                if result.nodes:
                    graph.store_batch(result.nodes, result.relationships, 'javascript')
                    stats['js_files'] += 1
                    
                    # Check for API calls
                    api_count = 0
                    for node in result.nodes:
                        if hasattr(node, 'metadata') and node.metadata and 'api_calls' in node.metadata:
                            import json
                            api_calls = json.loads(node.metadata['api_calls'])
                            api_count = len(api_calls)
                    
                    status = f"✓ {Path(file_path).name}"
                    if api_count > 0:
                        status += f" ({api_count} API calls)"
                    print(f"   {status}")
            except Exception as e:
                print(f"   ✗ {Path(file_path).name}: {e}")
    
    # Phase 4: Create cross-language links
    print("\n🔗 PHASE 4: Creating Cross-Language Links...")
    linker = CrossLinker(graph)
    
    js_to_endpoints = linker.link_js_to_endpoints()
    print(f"   ✓ Created {js_to_endpoints} JS→Endpoint CALLS relationships")
    stats['relationships']['CALLS'] = js_to_endpoints
    
    endpoints_to_php = linker.link_endpoints_to_controllers()
    print(f"   ✓ Created {endpoints_to_php} Endpoint→PHP HANDLES relationships")
    stats['relationships']['HANDLES'] = endpoints_to_php
    
    resolved = linker.resolve_inheritance()
    print(f"   ✓ Resolved {resolved} inheritance relationships")
    
    # Phase 5: Count final relationships
    print("\n📊 PHASE 5: Verification Statistics...")
    
    # Count each relationship type
    rel_queries = {
        'EXTENDS': "MATCH ()-[r:EXTENDS]->() RETURN count(r) as c",
        'IMPLEMENTS': "MATCH ()-[r:IMPLEMENTS]->() RETURN count(r) as c",
        'USES_TRAIT': "MATCH ()-[r:USES_TRAIT]->() RETURN count(r) as c",
        'CALLS': "MATCH ()-[r:CALLS]->() RETURN count(r) as c",
        'HANDLES': "MATCH ()-[r:HANDLES]->() RETURN count(r) as c",
        'HAS_METHOD': "MATCH ()-[r:HAS_METHOD]->() RETURN count(r) as c",
        'HAS_PROPERTY': "MATCH ()-[r:HAS_PROPERTY]->() RETURN count(r) as c",
        'IMPORTS': "MATCH ()-[r:IMPORTS]->() RETURN count(r) as c",
        'EXPORTS': "MATCH ()-[r:EXPORTS]->() RETURN count(r) as c",
        'DEFINED_IN': "MATCH ()-[r:DEFINED_IN]->() RETURN count(r) as c",
    }
    
    print("\n🔍 Relationship Counts:")
    for rel_type, query in rel_queries.items():
        result = graph.query(query)
        count = result[0]['c'] if result else 0
        if count > 0:
            stats['relationships'][rel_type] = count
            print(f"   {rel_type}: {count}")
    
    # Count node types
    print("\n📦 Node Type Counts:")
    node_queries = {
        'PHP Classes': "MATCH (n:Symbol) WHERE n._language = 'php' AND n.kind = 'class' RETURN count(n) as c",
        'PHP Methods': "MATCH (n:Symbol) WHERE n._language = 'php' AND n.kind = 'method' RETURN count(n) as c",
        'PHP Traits': "MATCH (n:Symbol) WHERE n._language = 'php' AND n.kind = 'trait' RETURN count(n) as c",
        'JS Files': "MATCH (n:Symbol) WHERE n._language = 'javascript' AND n.kind = 'file' RETURN count(n) as c",
        'JS Functions': "MATCH (n:Symbol) WHERE n._language = 'javascript' AND n.kind = 'function' RETURN count(n) as c",
        'API Endpoints': "MATCH (n:Endpoint) RETURN count(n) as c",
    }
    
    for label, query in node_queries.items():
        result = graph.query(query)
        count = result[0]['c'] if result else 0
        if count > 0:
            print(f"   {label}: {count}")
    
    # Show sample complete chains
    print("\n✨ Sample Complete Chains (JS → Endpoint → PHP):")
    chains = graph.query("""
        MATCH (js:Symbol)-[:CALLS]->(e:Endpoint)<-[:HANDLES]-(php:Symbol)
        WHERE js._language = 'javascript' AND php._language = 'php'
        RETURN 
            js.qualified_name as js_file,
            e.method as method,
            e.path as endpoint,
            php.qualified_name as controller
        LIMIT 3
    """)
    
    if chains:
        for chain in chains:
            print(f"\n   JavaScript: {chain['js_file']}")
            print(f"   → API Call: {chain['method']} {chain['endpoint']}")
            print(f"   → PHP Controller: {chain['controller']}")
    else:
        print("   No complete chains found. Check if API calls were detected.")
    
    print("\n" + "=" * 70)
    print("  ✅ DEMO INDEXING COMPLETE")
    print("=" * 70)
    print(f"""
Summary:
  • Endpoints indexed: {stats['endpoints']}
  • PHP files indexed: {stats['php_files']}
  • JavaScript files indexed: {stats['js_files']}
  • Total relationships: {sum(stats['relationships'].values())}
""")
    
    return stats


if __name__ == '__main__':
    index_demo_data()