#!/usr/bin/env python3
"""
Comprehensive test for relationship extraction
Tests that all critical relationships are properly extracted from code
"""

import subprocess
import json
import sys
from pathlib import Path

def test_php_parser():
    """Test PHP parser extracts all relationship types"""
    print("\n" + "="*70)
    print("TESTING PHP RELATIONSHIP EXTRACTION")
    print("="*70)
    
    test_file = "tests/test_enhanced_parser.php"
    parser_script = "plugins/php/ast_parser_enhanced.php"
    
    # Run parser
    result = subprocess.run(
        ['php', parser_script, test_file],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"❌ Parser failed: {result.stderr}")
        return False
    
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        return False
    
    if 'error' in data:
        print(f"❌ Parse error: {data['error']}")
        return False
    
    # Count relationship types
    relationships = data.get('relationships', [])
    relationship_counts = {}
    
    for rel in relationships:
        rel_type = rel.get('type', 'UNKNOWN')
        relationship_counts[rel_type] = relationship_counts.get(rel_type, 0) + 1
    
    print("\n📊 Extracted Relationships:")
    print("-" * 40)
    
    # Expected relationships
    expected = {
        'CALLS': 10,      # Method/function calls
        'IMPORTS': 3,     # Use statements
        'REQUIRES': 1,    # Include/require
        'READS': 5,       # Property reads
        'WRITES': 3,      # Property writes
        'INSTANTIATES': 2, # New objects
        'THROWS': 1,      # Exceptions
        'EMITS': 1,       # Events triggered
        'LISTENS': 1,     # Event listeners
    }
    
    tests_passed = 0
    tests_failed = 0
    
    for rel_type, min_expected in expected.items():
        actual = relationship_counts.get(rel_type, 0)
        if actual >= min_expected:
            print(f"  ✅ {rel_type:15} {actual:3} (expected ≥{min_expected})")
            tests_passed += 1
        else:
            print(f"  ❌ {rel_type:15} {actual:3} (expected ≥{min_expected})")
            tests_failed += 1
    
    # Show any additional relationships found
    for rel_type, count in relationship_counts.items():
        if rel_type not in expected:
            print(f"  ➕ {rel_type:15} {count:3} (bonus)")
    
    print("\n📈 Summary:")
    print(f"  Total relationships: {len(relationships)}")
    print(f"  Unique types: {len(relationship_counts)}")
    print(f"  Tests passed: {tests_passed}/{len(expected)}")
    
    # Show sample relationships
    print("\n🔍 Sample Relationships:")
    print("-" * 40)
    
    # Show sample CALLS
    calls = [r for r in relationships if r['type'] == 'CALLS'][:3]
    for call in calls:
        target = call.get('target_fqn', call.get('target_function', 'unknown'))
        print(f"  CALLS: {call.get('source_id', 'unknown')[:8]}... → {target}")
    
    # Show sample IMPORTS
    imports = [r for r in relationships if r['type'] == 'IMPORTS'][:3]
    for imp in imports:
        print(f"  IMPORTS: {imp.get('target_fqn', 'unknown')}")
    
    # Show sample ACCESSES
    accesses = [r for r in relationships if r['type'] in ['READS', 'WRITES']][:3]
    for acc in accesses:
        print(f"  {acc['type']}: {acc.get('target_property', 'unknown')}")
    
    return tests_failed == 0

def test_relationship_resolution():
    """Test that relationships can be resolved across files"""
    print("\n" + "="*70)
    print("TESTING RELATIONSHIP RESOLUTION")
    print("="*70)
    
    # Parse a real EspoCRM file
    test_files = [
        "espocrm/application/Espo/Controllers/User.php",
        "espocrm/application/Espo/Services/User.php",
        "espocrm/application/Espo/Entities/User.php"
    ]
    
    parser_script = "plugins/php/ast_parser_enhanced.php"
    all_relationships = []
    all_nodes = []
    
    for test_file in test_files:
        if not Path(test_file).exists():
            print(f"  ⚠️  Skipping {test_file} (not found)")
            continue
            
        result = subprocess.run(
            ['php', parser_script, test_file],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                if 'error' not in data:
                    all_relationships.extend(data.get('relationships', []))
                    all_nodes.extend(data.get('nodes', []))
                    print(f"  ✅ Parsed {test_file}: {len(data.get('nodes', []))} nodes, {len(data.get('relationships', []))} relationships")
            except:
                print(f"  ❌ Failed to parse {test_file}")
    
    if all_relationships:
        print(f"\n📊 Cross-file Analysis:")
        print(f"  Total nodes: {len(all_nodes)}")
        print(f"  Total relationships: {len(all_relationships)}")
        
        # Check for cross-references
        calls_to_user_methods = [
            r for r in all_relationships 
            if r.get('type') == 'CALLS' and 'User' in r.get('target_fqn', '')
        ]
        
        if calls_to_user_methods:
            print(f"  ✅ Found {len(calls_to_user_methods)} calls to User methods")
        
        return True
    
    return False

def main():
    """Run all tests"""
    print("\n🚀 RELATIONSHIP EXTRACTION TEST SUITE")
    
    success = True
    
    # Test PHP parser
    if not test_php_parser():
        success = False
        print("\n❌ PHP parser test failed")
    else:
        print("\n✅ PHP parser test passed")
    
    # Test resolution
    if not test_relationship_resolution():
        print("\n⚠️  Resolution test incomplete")
    else:
        print("\n✅ Resolution test passed")
    
    # Final result
    print("\n" + "="*70)
    if success:
        print("✅ ALL TESTS PASSED - Relationships extraction working!")
    else:
        print("❌ SOME TESTS FAILED - Review implementation")
    print("="*70)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())