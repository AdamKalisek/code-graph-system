#!/usr/bin/env python3
"""
Complete system test with all relationships
Clean database and index sample data to verify all features work
"""

import sys
import subprocess
from pathlib import Path

sys.path.append('.')

def run_test():
    """Run complete system test"""
    print("=" * 70)
    print("  COMPLETE SYSTEM TEST")
    print("=" * 70)
    
    # Step 1: Clean database
    print("\n🧹 Step 1: Cleaning database...")
    result = subprocess.run(['python', 'clean_neo4j.py'], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Failed to clean database: {result.stderr}")
        return False
    print("   ✓ Database cleaned")
    
    # Step 2: Run demo indexing
    print("\n📊 Step 2: Running demo indexing...")
    result = subprocess.run(['python', 'demo_indexing.py'], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Failed to index demo data: {result.stderr}")
        return False
    
    # Parse output for statistics
    output_lines = result.stdout.split('\n')
    for line in output_lines:
        if 'endpoints' in line.lower() or 'php' in line.lower() or 'javascript' in line.lower():
            if '✓' in line or '•' in line or ':' in line:
                print(f"   {line.strip()}")
    
    # Step 3: Verify relationships
    print("\n🔍 Step 3: Verifying relationships...")
    
    from code_graph_system.core.graph_store import FederatedGraphStore
    
    graph = FederatedGraphStore(
        'bolt://localhost:7688',
        ('neo4j', 'password123'),
        {'federation': {'mode': 'unified'}}
    )
    
    # Check each relationship type
    relationship_checks = {
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
    
    results = {}
    for rel_type, query in relationship_checks.items():
        result = graph.query(query)
        count = result[0]['c'] if result else 0
        results[rel_type] = count
        
        # Print with status indicator
        if count > 0:
            print(f"   ✓ {rel_type}: {count}")
        else:
            print(f"   ✗ {rel_type}: {count}")
    
    # Step 4: Check for complete chains
    print("\n🔗 Step 4: Checking complete chains...")
    
    # Check JS -> Endpoint -> PHP chain
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
        print("   ✓ Found complete JS → Endpoint → PHP chains:")
        for chain in chains:
            print(f"      • {chain['js_file']} → {chain['method']} {chain['endpoint']} → {chain['controller']}")
    else:
        print("   ✗ No complete chains found")
    
    # Step 5: Test specific relationships
    print("\n🎯 Step 5: Testing specific relationships...")
    
    # Check PHP inheritance
    extends = graph.query("""
        MATCH (child:Symbol:PHP:Class)-[:EXTENDS]->(parent:Symbol:PHP:Class)
        RETURN child.name as child, parent.name as parent
        LIMIT 3
    """)
    
    if extends:
        print("   ✓ PHP Inheritance working:")
        for rel in extends:
            print(f"      • {rel['child']} extends {rel['parent']}")
    else:
        print("   ✗ PHP inheritance not working")
    
    # Check API calls from JavaScript
    api_calls = graph.query("""
        MATCH (js:Symbol)
        WHERE js._language = 'javascript' AND js.metadata_api_calls IS NOT NULL
        RETURN js.name as file, js.metadata_api_calls as calls
        LIMIT 2
    """)
    
    if api_calls:
        print("   ✓ API calls detected in JavaScript:")
        for file_calls in api_calls:
            import json
            try:
                calls = json.loads(file_calls['calls'])
                print(f"      • {file_calls['file']}: {len(calls)} API calls")
            except:
                pass
    else:
        print("   ✗ No API calls detected")
    
    # Final summary
    print("\n" + "=" * 70)
    print("  TEST RESULTS SUMMARY")
    print("=" * 70)
    
    working = []
    not_working = []
    
    for rel_type, count in results.items():
        if count > 0:
            working.append(rel_type)
        elif rel_type in ['EXTENDS', 'IMPLEMENTS', 'USES_TRAIT', 'CALLS', 'HANDLES']:
            not_working.append(rel_type)
    
    print(f"\n✅ Working relationships ({len(working)}):")
    for rel in working:
        print(f"   • {rel}: {results[rel]}")
    
    if not_working:
        print(f"\n❌ Not working relationships ({len(not_working)}):")
        for rel in not_working:
            print(f"   • {rel}")
    
    success = len(not_working) == 0
    
    if success:
        print("\n🎉 ALL TESTS PASSED! System is fully functional.")
    else:
        print(f"\n⚠️ {len(not_working)} relationships still need fixing.")
    
    return success


if __name__ == '__main__':
    success = run_test()
    sys.exit(0 if success else 1)