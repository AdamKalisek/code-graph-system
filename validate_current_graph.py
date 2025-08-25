#!/usr/bin/env python3
"""
Validate current graph content and structure
Shows what's actually in the Neo4j database
"""

import sys
sys.path.append('.')

from code_graph_system.core.graph_store import FederatedGraphStore


def validate_graph():
    """Validate and report on current graph content"""
    print("="*70)
    print("  CURRENT GRAPH VALIDATION")
    print("="*70)
    
    # Connect to Neo4j
    graph_store = FederatedGraphStore(
        'bolt://localhost:7688',
        ('neo4j', 'password123'),
        {'federation': {'mode': 'unified'}}
    )
    
    # 1. Overall statistics
    print("\n📊 OVERALL STATISTICS:")
    stats = graph_store.get_statistics()
    print(f"  Total nodes: {stats['total_nodes']:,}")
    print(f"  Total relationships: {stats['total_relationships']:,}")
    
    # 2. Node types breakdown
    print("\n📦 NODE TYPES:")
    for node_type, count in sorted(stats.get('node_types', {}).items(), key=lambda x: x[1], reverse=True):
        print(f"  {node_type}: {count:,}")
    
    # 3. Relationship types
    print("\n🔗 RELATIONSHIP TYPES:")
    for rel_type, count in sorted(stats.get('relationship_types', {}).items(), key=lambda x: x[1], reverse=True):
        print(f"  {rel_type}: {count:,}")
    
    # 4. Language distribution
    print("\n🌐 LANGUAGE DISTRIBUTION:")
    for lang, count in sorted(stats.get('languages', {}).items(), key=lambda x: x[1], reverse=True):
        print(f"  {lang}: {count:,}")
    
    # 5. File types
    print("\n📄 FILE TYPES:")
    file_query = """
        MATCH (n:Symbol {kind: 'file'})
        RETURN n.name as name
        LIMIT 10000
    """
    files = graph_store.query(file_query)
    
    extensions = {}
    for file in files:
        name = file['name']
        if '.' in name:
            ext = name.split('.')[-1]
            extensions[ext] = extensions.get(ext, 0) + 1
    
    for ext, count in sorted(extensions.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  .{ext}: {count:,}")
    
    # 6. PHP Classes
    print("\n🐘 PHP CLASSES:")
    php_query = """
        MATCH (c:Symbol {kind: 'class', _language: 'php'})
        RETURN count(c) as count
    """
    php_classes = graph_store.query(php_query)
    print(f"  Total PHP classes: {php_classes[0]['count'] if php_classes else 0}")
    
    # Sample classes
    sample_query = """
        MATCH (c:Symbol {kind: 'class', _language: 'php'})
        RETURN c.name as name, c.qualified_name as fqcn
        LIMIT 5
    """
    samples = graph_store.query(sample_query)
    if samples:
        print("  Sample classes:")
        for s in samples:
            print(f"    - {s['name']} ({s['fqcn']})")
    
    # 7. Directories
    print("\n📁 DIRECTORY STRUCTURE:")
    dir_query = """
        MATCH (d:Symbol {kind: 'directory'})
        RETURN count(d) as count
    """
    dirs = graph_store.query(dir_query)
    print(f"  Total directories: {dirs[0]['count'] if dirs else 0}")
    
    # Top-level directories
    top_dirs = """
        MATCH (d:Symbol {kind: 'directory'})
        WHERE d.qualified_name STARTS WITH 'espocrm/'
        AND NOT d.qualified_name CONTAINS '//'
        RETURN d.name as name
        LIMIT 10
    """
    top = graph_store.query(top_dirs)
    if top:
        print("  Top-level directories:")
        for t in top[:5]:
            print(f"    - {t['name']}")
    
    # 8. Metadata JSON
    print("\n📋 METADATA JSON FILES:")
    meta_query = """
        MATCH (m:Symbol {kind: 'metadata'})
        RETURN count(m) as count
    """
    meta = graph_store.query(meta_query)
    print(f"  Total metadata files: {meta[0]['count'] if meta else 0}")
    
    # 9. JavaScript files
    print("\n🌐 JAVASCRIPT FILES:")
    js_query = """
        MATCH (j:Symbol {_language: 'javascript'})
        RETURN count(j) as count
    """
    js = graph_store.query(js_query)
    print(f"  Total JS nodes: {js[0]['count'] if js else 0}")
    
    # 10. Check for cross-references
    print("\n🔄 CROSS-LANGUAGE REFERENCES:")
    
    # Check EXTENDS relationships
    extends_query = """
        MATCH ()-[r:EXTENDS]->()
        RETURN count(r) as count
    """
    extends = graph_store.query(extends_query)
    print(f"  EXTENDS relationships: {extends[0]['count'] if extends else 0}")
    
    # Check IMPLEMENTS relationships
    implements_query = """
        MATCH ()-[r:IMPLEMENTS_INTERFACE]->()
        RETURN count(r) as count
    """
    implements = graph_store.query(implements_query)
    print(f"  IMPLEMENTS relationships: {implements[0]['count'] if implements else 0}")
    
    # 11. Sample complex query
    print("\n🔍 SAMPLE COMPLEX QUERIES:")
    
    # Classes with most methods
    complex_query = """
        MATCH (c:Symbol {kind: 'class'})-[:HAS_METHOD]->(m)
        RETURN c.name as class, count(m) as method_count
        ORDER BY method_count DESC
        LIMIT 5
    """
    complex_results = graph_store.query(complex_query)
    if complex_results:
        print("  Classes with most methods:")
        for r in complex_results:
            print(f"    - {r['class']}: {r['method_count']} methods")
    
    # Files with most classes
    file_class_query = """
        MATCH (f:Symbol {kind: 'file'})-[:DEFINED_IN]-(c:Symbol {kind: 'class'})
        RETURN f.name as file, count(c) as class_count
        ORDER BY class_count DESC
        LIMIT 5
    """
    file_classes = graph_store.query(file_class_query)
    if file_classes:
        print("\n  Files with most classes:")
        for r in file_classes:
            print(f"    - {r['file']}: {r['class_count']} classes")
    
    print("\n" + "="*70)
    print("  VALIDATION COMPLETE")
    print("="*70)
    
    # Summary
    print("\n📝 SUMMARY:")
    if stats['total_nodes'] > 25000:
        print("  ✅ Full EspoCRM indexed successfully")
    else:
        print("  ⚠️  Partial indexing detected")
    
    if extends[0]['count'] if extends else 0 > 0:
        print("  ✅ Inheritance relationships exist")
    else:
        print("  ❌ No inheritance relationships (EXTENDS not resolved)")
    
    if dirs[0]['count'] if dirs else 0 > 2000:
        print("  ✅ Complete filesystem structure")
    else:
        print("  ⚠️  Incomplete filesystem structure")
    
    print("\n🎯 NEXT STEPS:")
    print("  1. Implement AST-based PHP parser for accurate inheritance")
    print("  2. Add JavaScript parser for frontend coverage")
    print("  3. Create Endpoint nodes for API mapping")
    print("  4. Resolve EXTENDS/IMPLEMENTS relationships")


if __name__ == '__main__':
    validate_graph()