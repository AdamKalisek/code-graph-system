#!/usr/bin/env python3
"""Test JavaScript parser on single file"""

import sys
sys.path.append('.')

from plugins.javascript.tree_sitter_parser import JavaScriptParser

# Test on a single JS file
parser = JavaScriptParser()
test_file = 'espocrm/client/src/views/record/detail.js'

print(f"Testing parser on: {test_file}")
print("-" * 50)

try:
    result = parser.parse_file(test_file)
    
    print(f"✅ Parsing successful!")
    print(f"   Nodes: {len(result.nodes)}")
    print(f"   Relationships: {len(result.relationships)}")
    print(f"   Errors: {len(result.errors)}")
    
    # Show what was extracted
    if result.nodes:
        print("\nExtracted symbols:")
        for node in result.nodes[:5]:  # First 5
            print(f"   - {node.kind}: {node.name}")
            if hasattr(node, 'metadata') and node.metadata:
                if 'api_calls' in node.metadata:
                    print(f"     API calls detected!")
    
    if result.errors:
        print("\nErrors:")
        for err in result.errors[:3]:
            print(f"   - {err}")
            
except Exception as e:
    print(f"❌ Parser failed: {e}")
    import traceback
    traceback.print_exc()