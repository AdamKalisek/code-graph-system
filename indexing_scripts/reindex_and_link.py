#!/usr/bin/env python3
"""
Clean JavaScript nodes and re-index with improved API detection
"""

import sys
sys.path.append('.')

from code_graph_system.core.graph_store import FederatedGraphStore
from plugins.espocrm.cross_linker import CrossLinker

# Execute index_javascript
print("🔄 Re-indexing JavaScript with improved API detection...")
import index_javascript
stats = index_javascript.index_javascript()

print("\n🔗 Creating cross-language links...")

# Connect to Neo4j
graph = FederatedGraphStore(
    'bolt://localhost:7688',
    ('neo4j', 'password123'),
    {'federation': {'mode': 'unified'}}
)

# Run cross-linker
linker = CrossLinker(graph)
js_to_endpoints = linker.link_js_to_endpoints()
print(f"✅ Created {js_to_endpoints} JS->Endpoint CALLS relationships")

# Verify
print("\n📊 Final Verification:")
print("-" * 40)

# Relationship counts
rel_types = {
    'CALLS': "MATCH (js:Symbol)-[r:CALLS]->(e:Endpoint) WHERE js._language = 'javascript' RETURN count(r) as c",
    'HANDLES': "MATCH (php:Symbol)-[r:HANDLES]->(e:Endpoint) WHERE php._language = 'php' RETURN count(r) as c",
    'EXTENDS': "MATCH ()-[r:EXTENDS]->() RETURN count(r) as c",
    'IMPLEMENTS': "MATCH ()-[r:IMPLEMENTS]->() RETURN count(r) as c",
    'USES_TRAIT': "MATCH ()-[r:USES_TRAIT]->() RETURN count(r) as c"
}

for rel_type, query in rel_types.items():
    result = graph.query(query)
    count = result[0]['c'] if result else 0
    print(f"{rel_type}: {count}")

# Show complete chains
print("\n✨ Complete JavaScript → Endpoint → PHP chains:")
chains = graph.query("""
    MATCH (js:Symbol)-[:CALLS]->(e:Endpoint)<-[:HANDLES]-(php:Symbol)
    WHERE js._language = 'javascript' AND php._language = 'php'
    RETURN 
        js.qualified_name as js_file,
        e.method as method,
        e.path as endpoint,
        php.qualified_name as controller
    LIMIT 5
""")

if chains:
    for chain in chains:
        print(f"\n  {chain['js_file']}")
        print(f"    ↓ {chain['method']} {chain['endpoint']}")
        print(f"    ↓ {chain['controller']}")
else:
    print("  No complete chains found yet.")

print("\n✅ JavaScript parsing and linking complete!")