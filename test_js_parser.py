#!/usr/bin/env python3
"""
Test JavaScript parser with EspoCRM frontend files
"""

import sys
from pathlib import Path

sys.path.append('.')

from plugins.javascript.tree_sitter_parser import JavaScriptParser


def test_parser():
    """Test JavaScript parser with EspoCRM files"""
    print("=" * 70)
    print("  TESTING JAVASCRIPT PARSER")
    print("=" * 70)
    
    parser = JavaScriptParser()
    
    # Find some JavaScript files in EspoCRM
    espocrm_path = Path('espocrm')
    js_files = list(espocrm_path.glob('client/src/**/*.js'))[:5]
    
    if not js_files:
        print("❌ No JavaScript files found in espocrm/client/src/")
        return
        
    print(f"\n📂 Found {len(list(espocrm_path.glob('client/src/**/*.js')))} JS files in client/src/")
    print(f"   Testing with first 5 files...")
    
    for js_file in js_files:
        print(f"\n📄 Parsing: {js_file}")
        
        try:
            result = parser.parse_file(str(js_file))
            
            if result.errors:
                print(f"   ❌ Errors: {result.errors}")
                continue
                
            # Analyze content
            imports = [n for n in result.nodes if n.kind == 'import']
            exports = [n for n in result.nodes if n.kind == 'export']
            classes = [n for n in result.nodes if n.kind == 'class']
            functions = [n for n in result.nodes if n.kind == 'function']
            backbone = [n for n in result.nodes if 'backbone' in n.kind]
            
            print(f"   ✅ Parsed successfully")
            print(f"      Imports: {len(imports)}")
            print(f"      Exports: {len(exports)}")
            print(f"      Classes: {len(classes)}")
            print(f"      Functions: {len(functions)}")
            print(f"      Backbone: {len(backbone)}")
            
            # Check for API calls
            file_node = [n for n in result.nodes if n.kind == 'file'][0]
            if file_node and 'api_calls' in file_node.metadata:
                api_calls = file_node.metadata['api_calls']
                print(f"      API calls: {len(api_calls)}")
                if api_calls:
                    print(f"         Sample: {api_calls[0]['url']} ({api_calls[0]['method']})")
                    
            # Show sample import
            if imports:
                imp = imports[0]
                print(f"      Sample import: {imp.name}")
                if imp.metadata.get('items'):
                    print(f"         Items: {imp.metadata['items']}")
                    
            # Show sample Backbone component
            if backbone:
                comp = backbone[0]
                print(f"      Backbone component: {comp.name} ({comp.kind})")
                if 'properties' in comp.metadata:
                    props = comp.metadata['properties'][:3]
                    print(f"         Properties: {props}")
                    
        except Exception as e:
            print(f"   ❌ Parse error: {e}")
            

def test_specific_view():
    """Test parsing a specific Backbone view"""
    print("\n" + "=" * 70)
    print("  TESTING BACKBONE VIEW PARSING")
    print("=" * 70)
    
    parser = JavaScriptParser()
    
    # Look for a view file
    view_files = list(Path('espocrm').glob('client/src/views/**/*.js'))[:3]
    
    for view_file in view_files:
        print(f"\n📄 Parsing view: {view_file}")
        
        try:
            result = parser.parse_file(str(view_file))
            
            if result.errors:
                print(f"   ❌ Errors: {result.errors}")
                continue
                
            # Find Backbone components
            backbone = [n for n in result.nodes if 'backbone' in n.kind]
            
            if backbone:
                for comp in backbone:
                    print(f"   ✅ Found {comp.kind}: {comp.name}")
                    if 'properties' in comp.metadata:
                        print(f"      Properties: {comp.metadata['properties'][:5]}")
            else:
                print(f"   ⚠️  No Backbone components found")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            

def test_api_detection():
    """Test API call detection"""
    print("\n" + "=" * 70)
    print("  TESTING API CALL DETECTION")
    print("=" * 70)
    
    parser = JavaScriptParser()
    
    # Create test content with API calls
    test_content = """
    // Test API calls
    fetch('/api/v1/Lead')
        .then(response => response.json());
        
    $.ajax({
        url: '/api/v1/Account',
        method: 'POST',
        data: data
    });
    
    axios.get('/api/v1/Contact')
        .then(response => {
            console.log(response.data);
        });
    """
    
    # Write to temp file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
        f.write(test_content)
        temp_file = f.name
        
    try:
        result = parser.parse_file(temp_file)
        
        if result.errors:
            print(f"❌ Errors: {result.errors}")
        else:
            file_node = [n for n in result.nodes if n.kind == 'file'][0]
            if 'api_calls' in file_node.metadata:
                api_calls = file_node.metadata['api_calls']
                print(f"✅ Found {len(api_calls)} API calls:")
                for call in api_calls:
                    print(f"   - {call['function']}('{call['url']}') [{call['method']}]")
            else:
                print("❌ No API calls detected")
    finally:
        Path(temp_file).unlink()


if __name__ == '__main__':
    test_parser()
    test_specific_view()
    test_api_detection()
    
    print("\n" + "=" * 70)
    print("  TEST COMPLETE")
    print("=" * 70)