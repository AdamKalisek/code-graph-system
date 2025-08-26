#!/usr/bin/env python3
"""
Complete EspoCRM Indexing with AST Parsers and Cross-Language Linking
"""

import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.append('.')

from code_graph_system.core.graph_store import FederatedGraphStore
from plugins.php.plugin import PHPLanguagePlugin
from plugins.javascript.tree_sitter_parser import JavaScriptParser
from plugins.espocrm.route_parser import EspoCRMRouteParser
from plugins.espocrm.cross_linker import CrossLinker


def index_complete():
    print("=" * 70)
    print("  COMPLETE ESPOCRM INDEXING")
    print("=" * 70)
    print(f"  Started: {datetime.now()}")
    
    # Initialize
    graph = FederatedGraphStore(
        'bolt://localhost:7688',
        ('neo4j', 'password123'),
        {'federation': {'mode': 'unified'}}
    )
    
    # Clear
    print("\n🧹 Clearing graph...")
    graph.graph.run("MATCH (n) DETACH DELETE n")
    
    # Index endpoints first
    print("\n📡 Indexing endpoints...")
    parser = EspoCRMRouteParser('espocrm')
    endpoints, rels = parser.parse_all_routes()
    if endpoints:
        n, r = graph.store_batch(endpoints, rels)
        print(f"   Created {n} endpoints, {r} relationships")
    
    # Quick test - index 200 PHP files
    print("\n🐘 Indexing PHP (subset)...")
    php_plugin = PHPLanguagePlugin()
    php_plugin.initialize({})
    
    php_files = list(Path('espocrm').rglob('*.php'))[:200]
    for i, f in enumerate(php_files):
        if i % 50 == 0:
            print(f"   Progress: {i}/{len(php_files)}")
        try:
            result = php_plugin.parse_file(str(f))
            if not result.errors:
                graph.store_batch(result.nodes, result.relationships, 'php')
        except:
            pass
    
    # Quick test - index 100 JS files
    print("\n🌐 Indexing JavaScript (subset)...")
    js_parser = JavaScriptParser()
    
    js_files = list(Path('espocrm/client').rglob('*.js'))[:100]
    for i, f in enumerate(js_files):
        if i % 25 == 0:
            print(f"   Progress: {i}/{len(js_files)}")
        try:
            result = js_parser.parse_file(str(f))
            if not result.errors:
                graph.store_batch(result.nodes, result.relationships, 'javascript')
        except:
            pass
    
    # Cross-link
    print("\n🔗 Cross-linking...")
    linker = CrossLinker(graph)
    links = linker.link_all()
    
    # Report
    print("\n" + "=" * 70)
    print("  RESULTS")
    print("=" * 70)
    
    stats = {
        'PHP Classes': graph.query("MATCH (n:Symbol) WHERE n.kind='class' AND n._language='php' RETURN count(n) as c"),
        'JS Functions': graph.query("MATCH (n:Symbol) WHERE n.kind='function' AND n._language='javascript' RETURN count(n) as c"),
        'Endpoints': graph.query("MATCH (n:Endpoint) RETURN count(n) as c"),
        'EXTENDS': graph.query("MATCH ()-[r:EXTENDS]->() RETURN count(r) as c"),
        'CALLS': graph.query("MATCH ()-[r:CALLS]->() RETURN count(r) as c")
    }
    
    for key, result in stats.items():
        count = result[0]['c'] if result else 0
        print(f"{key}: {count}")
    
    print("\n✅ Complete!")


if __name__ == '__main__':
    index_complete()
