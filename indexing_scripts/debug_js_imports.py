#!/usr/bin/env python3
"""Debug JavaScript import parsing"""

import tree_sitter_javascript as tjs
from tree_sitter import Language, Parser

# Create test content
test_js = """
import BaseRecordView from 'views/record/base';
import ViewRecordHelper from 'view-record-helper';
import {inject} from 'di';
const axios = require('axios');
"""

# Setup parser
JS_LANGUAGE = Language(tjs.language())
parser = Parser(JS_LANGUAGE)

# Parse
tree = parser.parse(bytes(test_js, "utf8"))

def print_tree(node, source, indent=0):
    """Print AST tree"""
    text = source[node.start_byte:node.end_byte].decode('utf8')
    if len(text) > 50:
        text = text[:50] + "..."
    print(" " * indent + f"{node.type}: '{text}'")
    
    for child in node.children:
        print_tree(child, source, indent + 2)

print("AST Structure:")
print("-" * 50)
print_tree(tree.root_node, bytes(test_js, "utf8"))

print("\n\nImport Statement Analysis:")
print("-" * 50)

for node in tree.root_node.children:
    if node.type == 'import_statement':
        print(f"\nImport at line {node.start_point[0] + 1}:")
        
        # Get source
        source_node = node.child_by_field_name('source')
        if source_node:
            from_text = test_js[source_node.start_byte:source_node.end_byte]
            print(f"  Raw source: '{from_text}'")
            
            # Strip quotes
            from_path = from_text.strip('"\'')
            print(f"  Cleaned path: '{from_path}'")
            
        # Get import clause
        import_clause = None
        for child in node.children:
            if child.type == 'import_clause':
                import_clause = child
                break
                
        if import_clause:
            print(f"  Import clause type: {import_clause.type}")
            for child in import_clause.children:
                text = test_js[child.start_byte:child.end_byte]
                print(f"    - {child.type}: '{text}'")