#!/usr/bin/env python3
"""
FULL EspoCRM Indexing with All Fixes Applied
Indexes entire codebase with proper connection detection
"""

import sys
import time
import logging
from pathlib import Path
from datetime import datetime

sys.path.append('.')

from code_graph_system.core.graph_store import FederatedGraphStore
from plugins.php.plugin import PHPLanguagePlugin
from plugins.javascript.tree_sitter_parser import JavaScriptParser
from plugins.espocrm.route_parser import EspoCRMRouteParser
from plugins.espocrm.cross_linker import CrossLinker

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def index_full_espocrm():
    """Run FULL indexing of entire EspoCRM codebase"""
    print("=" * 70)
    print("  FULL ESPOCRM INDEXING")
    print("=" * 70)
    print(f"  Started: {datetime.now()}")
    print("  With all O3-recommended fixes applied")
    print()
    
    # Statistics
    stats = {
        'php_files': 0,
        'js_files': 0,
        'endpoints': 0,
        'nodes': 0,
        'relationships': 0,
        'errors': []
    }
    
    # Initialize graph store
    print("🔌 Connecting to Neo4j...")
    graph = FederatedGraphStore(
        'bolt://localhost:7688',
        ('neo4j', 'password123'),
        {'federation': {'mode': 'unified'}}
    )
    
    # Clear database
    print("🧹 Clearing existing graph...")
    graph.graph.run("MATCH (n) DETACH DELETE n")
    
    # Phase 1: Index Endpoints
    print("\n📡 PHASE 1: Indexing API Endpoints")
    print("-" * 40)
    parser = EspoCRMRouteParser('espocrm')
    endpoints, rels = parser.parse_all_routes()
    stats['endpoints'] = len(endpoints)
    if endpoints:
        n, r = graph.store_batch(endpoints, rels)
        stats['nodes'] += n
        stats['relationships'] += r
    print(f"✅ Created {len(endpoints)} endpoints")
    
    # Phase 2: Index PHP Backend
    print("\n🐘 PHASE 2: Indexing PHP Backend")
    print("-" * 40)
    php_plugin = PHPLanguagePlugin()
    php_plugin.initialize({})
    
    # Find all PHP files
    php_files = list(Path('espocrm').rglob('*.php'))
    # Exclude vendor and tests
    php_files = [f for f in php_files if 'vendor' not in str(f) and 'tests' not in str(f)]
    stats['php_files'] = len(php_files)
    print(f"📂 Found {len(php_files)} PHP files")
    
    # Process in batches
    batch_size = 100
    start_time = time.time()
    
    for i in range(0, len(php_files), batch_size):
        batch = php_files[i:i+batch_size]
        batch_nodes = []
        batch_relationships = []
        
        for file_path in batch:
            try:
                result = php_plugin.parse_file(str(file_path))
                if len(result.errors) == 0:
                    batch_nodes.extend(result.nodes)
                    batch_relationships.extend(result.relationships)
                else:
                    stats['errors'].extend(result.errors)
            except Exception as e:
                stats['errors'].append(f"PHP error in {file_path}: {e}")
        
        # Store batch
        if batch_nodes:
            n, r = graph.store_batch(batch_nodes, batch_relationships, 'php')
            stats['nodes'] += n
            stats['relationships'] += r
        
        # Progress
        if (i + batch_size) % 500 == 0:
            elapsed = time.time() - start_time
            rate = (i + batch_size) / elapsed
            eta = (len(php_files) - i - batch_size) / rate
            print(f"   Progress: {i + batch_size}/{len(php_files)} ({rate:.1f} files/sec, ETA: {eta:.0f}s)")
    
    elapsed = time.time() - start_time
    print(f"✅ Indexed {len(php_files)} PHP files in {elapsed:.1f}s")
    
    # Phase 3: Index JavaScript Frontend
    print("\n🌐 PHASE 3: Indexing JavaScript Frontend")
    print("-" * 40)
    js_parser = JavaScriptParser()
    
    # Find JavaScript files
    js_files = []
    for pattern in ['*.js', '*.jsx']:
        js_files.extend(list(Path('espocrm/client').rglob(pattern)))
    # Exclude node_modules
    js_files = [f for f in js_files if 'node_modules' not in str(f)]
    stats['js_files'] = len(js_files)
    print(f"📂 Found {len(js_files)} JavaScript files")
    
    # Process JavaScript files
    start_time = time.time()
    
    for i in range(0, len(js_files), batch_size):
        batch = js_files[i:i+batch_size]
        batch_nodes = []
        batch_relationships = []
        
        for file_path in batch:
            try:
                result = js_parser.parse_file(str(file_path))
                if len(result.errors) == 0:
                    batch_nodes.extend(result.nodes)
                    batch_relationships.extend(result.relationships)
                else:
                    stats['errors'].extend(result.errors)
            except Exception as e:
                stats['errors'].append(f"JS error in {file_path}: {e}")
        
        # Store batch
        if batch_nodes:
            n, r = graph.store_batch(batch_nodes, batch_relationships, 'javascript')
            stats['nodes'] += n
            stats['relationships'] += r
        
        # Progress
        if (i + batch_size) % 200 == 0:
            elapsed = time.time() - start_time
            rate = (i + batch_size) / elapsed
            eta = (len(js_files) - i - batch_size) / rate
            print(f"   Progress: {i + batch_size}/{len(js_files)} ({rate:.1f} files/sec, ETA: {eta:.0f}s)")
    
    elapsed = time.time() - start_time
    print(f"✅ Indexed {len(js_files)} JavaScript files in {elapsed:.1f}s")
    
    # Phase 4: Cross-Language Linking
    print("\n🔗 PHASE 4: Cross-Language Linking")
    print("-" * 40)
    linker = CrossLinker(graph)
    links = linker.link_all()
    stats['relationships'] += links
    print(f"✅ Created {links} cross-language relationships")
    
    # Phase 5: Verification
    print("\n📊 PHASE 5: Verification")
    print("=" * 70)
    
    # Query all relationship types
    rel_types = [
        'EXTENDS', 'IMPLEMENTS', 'USES_TRAIT', 'CALLS', 'HANDLES',
        'IMPORTS', 'EXPORTS', 'HAS_METHOD', 'HAS_PROPERTY', 'DEFINED_IN'
    ]
    
    print("\n🔗 Relationship Statistics:")
    for rel_type in rel_types:
        result = graph.query(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as c")
        count = result[0]['c'] if result else 0
        if count > 0:
            print(f"   {rel_type}: {count}")
    
    # Node statistics
    print("\n📦 Node Statistics:")
    node_queries = {
        'PHP Classes': "MATCH (n:Symbol) WHERE n._language = 'php' AND n.kind = 'class' RETURN count(n) as c",
        'PHP Methods': "MATCH (n:Symbol) WHERE n._language = 'php' AND n.kind = 'method' RETURN count(n) as c",
        'PHP Traits': "MATCH (n:Symbol) WHERE n._language = 'php' AND n.kind = 'trait' RETURN count(n) as c",
        'PHP Interfaces': "MATCH (n:Symbol) WHERE n._language = 'php' AND n.kind = 'interface' RETURN count(n) as c",
        'JS Functions': "MATCH (n:Symbol) WHERE n._language = 'javascript' AND n.kind = 'function' RETURN count(n) as c",
        'JS Classes': "MATCH (n:Symbol) WHERE n._language = 'javascript' AND n.kind = 'class' RETURN count(n) as c",
        'API Endpoints': "MATCH (n:Endpoint) RETURN count(n) as c"
    }
    
    for label, query in node_queries.items():
        result = graph.query(query)
        count = result[0]['c'] if result else 0
        if count > 0:
            print(f"   {label}: {count}")
    
    # Sample connections
    print("\n✨ Sample Cross-Language Connections:")
    
    # JS -> Endpoint -> PHP
    full_chain = graph.query("""
        MATCH (js:Symbol)-[:CALLS]->(e:Endpoint)<-[:HANDLES]-(php:Symbol)
        WHERE js._language = 'javascript' AND php._language = 'php'
        RETURN js.qualified_name as js_file, e.path as endpoint, php.qualified_name as controller
        LIMIT 3
    """)
    
    if full_chain:
        print("\n   JavaScript → Endpoint → PHP Controller:")
        for chain in full_chain:
            print(f"   • {chain['js_file']} → {chain['endpoint']} → {chain['controller']}")
    
    # Inheritance examples
    inheritance = graph.query("""
        MATCH (c:Symbol)-[:EXTENDS]->(p:Symbol)
        WHERE c._language = 'php'
        RETURN c.qualified_name as child, p.qualified_name as parent
        LIMIT 3
    """)
    
    if inheritance:
        print("\n   PHP Inheritance:")
        for rel in inheritance:
            print(f"   • {rel['child']} extends {rel['parent']}")
    
    # Trait usage
    traits = graph.query("""
        MATCH (c:Symbol)-[:USES_TRAIT]->(t:Symbol)
        RETURN c.qualified_name as class, t.qualified_name as trait
        LIMIT 3
    """)
    
    if traits:
        print("\n   PHP Trait Usage:")
        for rel in traits:
            print(f"   • {rel['class']} uses {rel['trait']}")
    
    # Final statistics
    print("\n" + "=" * 70)
    print("  INDEXING COMPLETE")
    print("=" * 70)
    print(f"""
📈 Final Statistics:
   PHP files: {stats['php_files']}
   JavaScript files: {stats['js_files']}
   API endpoints: {stats['endpoints']}
   Total nodes: {stats['nodes']}
   Total relationships: {stats['relationships']}
   Errors: {len(stats['errors'])}
   
✅ Full EspoCRM code graph created successfully!
   You can now trace from frontend JavaScript through
   API endpoints to backend PHP controllers and entities.
""")
    
    if stats['errors']:
        print(f"\n⚠️ {len(stats['errors'])} errors occurred (showing first 5):")
        for error in stats['errors'][:5]:
            print(f"   - {error[:100]}...")


if __name__ == '__main__':
    index_full_espocrm()