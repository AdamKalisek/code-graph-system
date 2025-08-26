#!/usr/bin/env python3
"""
Re-index EspoCRM with AST-based PHP parser and multi-label support
Shows inheritance relationships and accurate FQNs
"""

import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.append('.')

from code_graph_system.core.graph_store import FederatedGraphStore
from plugins.php.plugin import PHPLanguagePlugin


def reindex_espocrm():
    """Re-index EspoCRM with new AST parser"""
    print("=" * 70)
    print("  RE-INDEXING ESPOCRM WITH AST PARSER")
    print("=" * 70)
    print(f"  Started: {datetime.now()}")
    
    # Connect to Neo4j
    print("\n🔌 Connecting to Neo4j...")
    graph_store = FederatedGraphStore(
        'bolt://localhost:7688',
        ('neo4j', 'password123'),
        {'federation': {'mode': 'unified'}}
    )
    
    # Clear existing data
    print("🧹 Clearing existing graph...")
    graph_store.graph.run("MATCH (n) DETACH DELETE n")
    
    # Initialize PHP plugin (will use NikicPHPParser)
    print("📦 Initializing PHP plugin with AST parser...")
    php_plugin = PHPLanguagePlugin()
    php_plugin.initialize({})
    
    # Find all PHP files
    espocrm_path = Path('espocrm')
    php_files = list(espocrm_path.rglob('*.php'))
    print(f"\n📂 Found {len(php_files)} PHP files")
    
    # Process files in batches
    batch_size = 50
    total_nodes = 0
    total_relationships = 0
    errors = []
    
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
                    errors.extend(result.errors)
                    
            except Exception as e:
                errors.append(f"Error parsing {file_path}: {e}")
                
        # Store batch
        if batch_nodes:
            n, r = graph_store.store_batch(batch_nodes, batch_relationships, 'php')
            total_nodes += n
            total_relationships += r
            
        # Progress report
        if (i + batch_size) % 500 == 0:
            elapsed = time.time() - start_time
            rate = (i + batch_size) / elapsed
            print(f"  Progress: {i + batch_size}/{len(php_files)} files ({rate:.1f} files/sec)")
            
    elapsed = time.time() - start_time
    
    print("\n" + "=" * 70)
    print("  INDEXING COMPLETE")
    print("=" * 70)
    
    print(f"""
📊 Statistics:
   Files processed: {len(php_files)}
   Nodes created: {total_nodes}
   Relationships: {total_relationships}
   Errors: {len(errors)}
   Time: {elapsed:.2f} seconds
   Rate: {len(php_files)/elapsed:.1f} files/sec
""")
    
    # Query to verify inheritance
    print("\n🔍 Verifying inheritance relationships...")
    
    extends_query = """
        MATCH ()-[r:EXTENDS]->()
        RETURN count(r) as count
    """
    extends = graph_store.query(extends_query)
    print(f"   EXTENDS relationships: {extends[0]['count'] if extends else 0}")
    
    implements_query = """
        MATCH ()-[r:IMPLEMENTS]->()
        RETURN count(r) as count
    """
    implements = graph_store.query(implements_query)
    print(f"   IMPLEMENTS relationships: {implements[0]['count'] if implements else 0}")
    
    uses_trait_query = """
        MATCH ()-[r:USES_TRAIT]->()
        RETURN count(r) as count
    """
    uses_trait = graph_store.query(uses_trait_query)
    print(f"   USES_TRAIT relationships: {uses_trait[0]['count'] if uses_trait else 0}")
    
    # Sample inheritance chain
    print("\n📈 Sample inheritance chain:")
    inheritance_query = """
        MATCH (c:Class)-[:EXTENDS]->(p)
        RETURN c.qualified_name as child, p.qualified_name as parent
        LIMIT 5
    """
    inheritance = graph_store.query(inheritance_query)
    if inheritance:
        for rel in inheritance:
            print(f"   {rel.get('child', 'Unknown')} extends {rel.get('parent', 'Unknown')}")
    else:
        print("   No inheritance found (may need to resolve unresolved references)")
        
    # Check multi-labels
    print("\n🏷️  Checking multi-label support:")
    label_query = """
        MATCH (n:Symbol:PHP:Class)
        RETURN count(n) as count
    """
    multi_label = graph_store.query(label_query)
    if multi_label and multi_label[0]['count'] > 0:
        print(f"   ✅ Multi-labels working: {multi_label[0]['count']} PHP Classes")
    else:
        # Fallback check
        fallback_query = """
            MATCH (n:Symbol)
            WHERE n._language = 'php' AND n.kind = 'class'
            RETURN count(n) as count
        """
        fallback = graph_store.query(fallback_query)
        print(f"   ⚠️  Multi-labels not applied, using properties: {fallback[0]['count'] if fallback else 0} PHP Classes")
        
    # Sample FQNs
    print("\n📛 Sample FQNs (Fully Qualified Names):")
    fqn_query = """
        MATCH (c:Symbol {kind: 'class'})
        WHERE c.qualified_name CONTAINS '\\\\'
        RETURN c.qualified_name as fqn
        LIMIT 10
    """
    fqns = graph_store.query(fqn_query)
    if fqns:
        for f in fqns[:5]:
            print(f"   {f['fqn']}")
    else:
        print("   No namespaced classes found")
        
    if errors:
        print(f"\n⚠️  {len(errors)} errors encountered (showing first 5):")
        for error in errors[:5]:
            print(f"   - {error}")
            

if __name__ == '__main__':
    reindex_espocrm()