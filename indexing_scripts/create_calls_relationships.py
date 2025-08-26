#!/usr/bin/env python3
"""
Create CALLS relationships from JavaScript to Endpoints
"""

import sys
import json
from pathlib import Path

sys.path.append('.')

from code_graph_system.core.graph_store import FederatedGraphStore
from plugins.espocrm.cross_linker import CrossLinker

def create_calls_relationships():
    """Create CALLS relationships"""
    print("=" * 70)
    print("  CREATING CALLS RELATIONSHIPS")
    print("=" * 70)
    
    # Connect to Neo4j
    print("🔌 Connecting to Neo4j...")
    graph = FederatedGraphStore(
        'bolt://localhost:7688',
        ('neo4j', 'password123'),
        {'federation': {'mode': 'unified'}}
    )
    
    # Run cross-linker
    print("🔗 Running cross-linker...")
    linker = CrossLinker(graph)
    
    # Link JavaScript API calls to endpoints
    js_to_endpoints = linker.link_js_to_endpoints()
    print(f"✅ Created {js_to_endpoints} JS->Endpoint CALLS relationships")
    
    # Link endpoints to PHP controllers
    endpoints_to_php = linker.link_endpoints_to_controllers()
    print(f"✅ Created {endpoints_to_php} Endpoint->Controller HANDLES relationships")
    
    # Resolve inheritance
    resolved = linker.resolve_inheritance()
    print(f"✅ Resolved {resolved} inheritance relationships")
    
    # Verify
    print("\n📊 Verification:")
    print("-" * 40)
    
    # Check CALLS relationships
    result = graph.query("""
        MATCH (js:Symbol)-[r:CALLS]->(e:Endpoint)
        WHERE js._language = 'javascript'
        RETURN count(r) as count
    """)
    calls_count = result[0]['count'] if result else 0
    print(f"CALLS relationships: {calls_count}")
    
    # Show sample connections
    if calls_count > 0:
        samples = graph.query("""
            MATCH (js:Symbol)-[r:CALLS]->(e:Endpoint)<-[:HANDLES]-(php:Symbol)
            WHERE js._language = 'javascript' AND php._language = 'php'
            RETURN 
                js.qualified_name as js_file,
                e.path as endpoint,
                php.qualified_name as controller
            LIMIT 5
        """)
        
        if samples:
            print("\n✨ Sample JavaScript → Endpoint → PHP chains:")
            for sample in samples:
                print(f"   • {sample['js_file']}")
                print(f"     → {sample['endpoint']}")
                print(f"     → {sample['controller']}")
                print()
    
    return calls_count

if __name__ == '__main__':
    create_calls_relationships()