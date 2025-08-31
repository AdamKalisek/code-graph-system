#!/usr/bin/env python3
"""Test tree-sitter query syntax"""

import tree_sitter
from tree_sitter import Language, Parser
import tree_sitter_javascript as tsjs

# Create parser
parser = Parser(Language(tsjs.language()))

# Test code
code = """
class UserView extends BaseView {
    constructor() {
        super();
    }
    render() {
        return this;
    }
}
"""

tree = parser.parse(bytes(code, 'utf8'))

# Try simple query
query_str = """
(class_declaration
  name: (identifier) @class_name
) @class
"""

query = parser.language.query(query_str)
captures = query.captures(tree.root_node)

print(f"Found {len(captures)} captures")
for capture in captures:
    print(f"  Capture: {capture}")

# Print tree structure to understand it
def print_tree(node, indent=0):
    print("  " * indent + f"{node.type}")
    for child in node.children:
        print_tree(child, indent + 1)

print("\nTree structure:")
print_tree(tree.root_node)