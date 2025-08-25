#!/usr/bin/env python3
"""
Test the new PHP AST parser
"""

import sys
from pathlib import Path
sys.path.append('.')

from plugins.php.ast_parser_simple import SimplePHPParser

def test_parser():
    print("Testing Improved PHP Parser")
    print("=" * 50)
    
    parser = SimplePHPParser()
    
    # Test with Container.php
    test_file = 'espocrm/application/Espo/Core/Container.php'
    
    if Path(test_file).exists():
        print(f"\nParsing: {test_file}")
        result = parser.parse_file(test_file)
        
        print(f"\nParse Results:")
        print(f"  Success: {len(result.errors) == 0}")
        print(f"  Nodes: {len(result.nodes)}")
        print(f"  Relationships: {len(result.relationships)}")
        
        if result.errors:
            print(f"\nErrors:")
            for error in result.errors:
                print(f"  - {error}")
        
        # Show breakdown by type
        node_types = {}
        for node in result.nodes:
            kind = node.kind
            node_types[kind] = node_types.get(kind, 0) + 1
        
        print(f"\nNode Types:")
        for kind, count in sorted(node_types.items()):
            print(f"  {kind}: {count}")
        
        # Show classes found
        classes = [n for n in result.nodes if n.kind == 'class']
        if classes:
            print(f"\nClasses Found:")
            for cls in classes:
                print(f"  - {cls.name} ({cls.qualified_name})")
        
        # Show methods found
        methods = [n for n in result.nodes if n.kind == 'method']
        if methods:
            print(f"\nMethods Found ({len(methods)} total):")
            for method in methods[:10]:  # Show first 10
                print(f"  - {method.name}")
                
        # Show properties found
        properties = [n for n in result.nodes if n.kind == 'property']
        if properties:
            print(f"\nProperties Found ({len(properties)} total):")
            for prop in properties[:10]:  # Show first 10
                print(f"  - {prop.name}")
    else:
        print(f"File not found: {test_file}")

if __name__ == '__main__':
    test_parser()