#!/usr/bin/env python3
"""
Test the new Nikic PHP parser with EspoCRM files
"""

import sys
import json
from pathlib import Path

sys.path.append('.')

from plugins.php.nikic_parser import NikicPHPParser


def test_parser():
    """Test the Nikic PHP parser"""
    print("=" * 70)
    print("  TESTING NIKIC PHP PARSER")
    print("=" * 70)
    
    parser = NikicPHPParser()
    
    # Test with a complex EspoCRM file
    test_file = 'espocrm/application/Espo/Core/Application.php'
    
    if not Path(test_file).exists():
        print(f"❌ Test file not found: {test_file}")
        return False
        
    print(f"\n📄 Testing with: {test_file}")
    
    # Parse the file
    result = parser.parse_file(test_file)
    
    if result.errors:
        print(f"❌ Parser errors: {result.errors}")
        return False
        
    print(f"✅ Parsed successfully!")
    print(f"   Nodes: {len(result.nodes)}")
    print(f"   Relationships: {len(result.relationships)}")
    
    # Analyze parsed content
    classes = [n for n in result.nodes if n.kind == 'class']
    methods = [n for n in result.nodes if n.kind == 'method']
    properties = [n for n in result.nodes if n.kind == 'property']
    interfaces = [n for n in result.nodes if n.kind == 'interface']
    traits = [n for n in result.nodes if n.kind == 'trait']
    
    print(f"\n📊 Parsed symbols:")
    print(f"   Classes: {len(classes)}")
    print(f"   Methods: {len(methods)}")
    print(f"   Properties: {len(properties)}")
    print(f"   Interfaces: {len(interfaces)}")
    print(f"   Traits: {len(traits)}")
    
    # Show sample class with FQN
    if classes:
        cls = classes[0]
        print(f"\n📦 Sample class:")
        print(f"   Name: {cls.name}")
        print(f"   FQN: {cls.qualified_name}")
        print(f"   Labels: {cls.get_labels()}")
        if cls.metadata:
            print(f"   Namespace: {cls.metadata.get('namespace', 'N/A')}")
            
    # Check for inheritance relationships
    extends_rels = [r for r in result.relationships if r.type == 'EXTENDS']
    implements_rels = [r for r in result.relationships if r.type == 'IMPLEMENTS']
    uses_trait_rels = [r for r in result.relationships if r.type == 'USES_TRAIT']
    
    print(f"\n🔗 Relationships:")
    print(f"   EXTENDS: {len(extends_rels)}")
    print(f"   IMPLEMENTS: {len(implements_rels)}")
    print(f"   USES_TRAIT: {len(uses_trait_rels)}")
    
    # Show sample inheritance
    if extends_rels:
        rel = extends_rels[0]
        if rel.metadata and 'target_fqn' in rel.metadata:
            print(f"\n   Sample inheritance:")
            print(f"   Target FQN: {rel.metadata['target_fqn']}")
            
    return True


def test_multi_file():
    """Test parser with multiple files"""
    print("\n" + "=" * 70)
    print("  TESTING MULTIPLE FILES")
    print("=" * 70)
    
    parser = NikicPHPParser()
    
    test_files = [
        'espocrm/application/Espo/Core/Application.php',
        'espocrm/application/Espo/Core/Container.php',
        'espocrm/application/Espo/Entities/User.php'
    ]
    
    for file_path in test_files:
        if not Path(file_path).exists():
            print(f"⚠️  Skipping {file_path} (not found)")
            continue
            
        print(f"\n📄 Parsing: {file_path}")
        result = parser.parse_file(file_path)
        
        if result.errors:
            print(f"   ❌ Errors: {result.errors}")
        else:
            classes = [n for n in result.nodes if n.kind == 'class']
            if classes:
                print(f"   ✅ Found class: {classes[0].qualified_name}")
                print(f"      Labels: {classes[0].get_labels()}")
                

def test_ast_script_directly():
    """Test the PHP AST parser script directly"""
    print("\n" + "=" * 70)
    print("  TESTING PHP AST SCRIPT DIRECTLY")
    print("=" * 70)
    
    import subprocess
    
    test_file = 'espocrm/application/Espo/Core/Application.php'
    
    if not Path(test_file).exists():
        print(f"❌ Test file not found: {test_file}")
        return
        
    result = subprocess.run(
        ['php', 'plugins/php/ast_parser.php', test_file],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"❌ Script failed: {result.stderr}")
        return
        
    try:
        data = json.loads(result.stdout)
        print(f"✅ Script output valid JSON")
        print(f"   Nodes: {len(data.get('nodes', []))}")
        print(f"   Relationships: {len(data.get('relationships', []))}")
        
        # Show sample node
        if data.get('nodes'):
            node = data['nodes'][0]
            print(f"\n   Sample node:")
            print(f"   Name: {node.get('name')}")
            print(f"   FQN: {node.get('fqn')}")
            print(f"   Kind: {node.get('kind')}")
            
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        print(f"Output: {result.stdout[:500]}")


if __name__ == '__main__':
    # Test AST script directly first
    test_ast_script_directly()
    
    # Test parser wrapper
    success = test_parser()
    
    if success:
        # Test multiple files
        test_multi_file()
        
    print("\n" + "=" * 70)
    print("  TEST COMPLETE")
    print("=" * 70)