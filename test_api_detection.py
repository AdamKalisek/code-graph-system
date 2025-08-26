#!/usr/bin/env python3
"""Test API call detection"""

import sys
import json
sys.path.append('.')

from plugins.javascript.tree_sitter_parser import JavaScriptParser

# Test file with API calls
test_content = """
// Test API calls
function loadUser(userId) {
    fetch('/api/v1/User/' + userId)
        .then(res => res.json())
        .then(data => console.log(data));
    
    $.ajax({
        url: '/api/v1/Lead',
        method: 'POST',
        data: {name: 'Test'}
    });
    
    axios.get('/api/v1/Account')
        .then(response => console.log(response));
}
"""

# Write test file
with open('test_api.js', 'w') as f:
    f.write(test_content)

# Parse it
parser = JavaScriptParser()
result = parser.parse_file('test_api.js')

print("Parsing results:")
print("-" * 50)
print(f"Nodes: {len(result.nodes)}")
print(f"Relationships: {len(result.relationships)}")

# Check for API calls in metadata
for node in result.nodes:
    print(f"\nNode: {node.name} ({node.kind})")
    if hasattr(node, 'metadata') and node.metadata:
        print(f"  Has metadata: {list(node.metadata.keys())}")
        if 'api_calls' in node.metadata:
            api_calls = node.metadata['api_calls']
            if isinstance(api_calls, str):
                api_calls = json.loads(api_calls)
            print(f"  API calls detected: {len(api_calls)}")
            for call in api_calls:
                print(f"    - {call['method']} {call['url']} (line {call['line']})")