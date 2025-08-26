#!/usr/bin/env python3
"""Test Babel parser"""

import sys
import json
sys.path.append('.')

from plugins.javascript.babel_parser import BabelParser

# Test file with various constructs
test_content = """
// Test API calls with different patterns
import axios from 'axios';
import { fetchUser } from './api';

const API_BASE = '/api/v1';

async function loadUser(userId) {
    // Simple fetch
    const res1 = await fetch('/api/v1/User/' + userId);
    
    // Template literal
    const res2 = await fetch(`${API_BASE}/User/${userId}`);
    
    // $.ajax with object
    $.ajax({
        url: '/api/v1/Lead',
        method: 'POST',
        data: {name: 'Test'}
    });
    
    // axios methods
    await axios.get('/api/v1/Account');
    await axios.post('/api/v1/Account', data);
    
    // Complex Ajax call
    Espo.Ajax.postRequest('Layout/action/resetToDefault', {
        scope: this.scope,
        name: this.name
    });
}

class UserManager {
    constructor() {
        this.users = [];
    }
    
    async loadAll() {
        return fetch('/api/v1/User');
    }
}

export default UserManager;
"""

# Write test file
with open('test_babel.js', 'w') as f:
    f.write(test_content)

# Parse it
parser = BabelParser()
result = parser.parse_file('test_babel.js')

print("Babel Parser Results:")
print("=" * 50)
print(f"✅ Nodes: {len(result.nodes)}")
print(f"✅ Relationships: {len(result.relationships)}")
print(f"⚠️ Errors: {len(result.errors)}")

if result.errors:
    print("\nErrors:")
    for err in result.errors:
        print(f"  - {err}")

print("\nNodes extracted:")
for node in result.nodes:
    print(f"  • {node.kind}: {node.name}")
    if node.metadata and 'api_calls' in node.metadata:
        api_calls = json.loads(node.metadata['api_calls'])
        print(f"    API calls: {len(api_calls)}")
        for call in api_calls:
            print(f"      - {call['method']} {call['url']} (line {call['line']})")

print("\nRelationships:")
for rel in result.relationships:
    print(f"  • {rel.type}: {rel.source_id[:8]}... → {rel.target_id[:8]}...")