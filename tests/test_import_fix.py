#!/usr/bin/env python3
"""Test import fix"""

import sys
sys.path.append('.')

from plugins.javascript.tree_sitter_parser import JavaScriptParser

parser = JavaScriptParser()

# Test simple file with imports
test_content = """
import BaseRecordView from 'views/record/base';
import ViewRecordHelper from 'view-record-helper';
"""

# Create temp file
with open('test_import.js', 'w') as f:
    f.write(test_content)

result = parser.parse_file('test_import.js')

print("Parsing result:")
print("-" * 50)
print(f"Nodes: {len(result.nodes)}")
for node in result.nodes:
    print(f"  {node.kind}: {node.name} (id={node.id[:8]}...)")
    
print("\nRelationships: ")
for rel in result.relationships:
    print(f"  {rel.type}: {rel.source_id[:8]}... -> {rel.target_id[:8]}...")