#!/usr/bin/env python3
"""
Complete rebuild and validation of the Universal Code Graph System.
This script:
1. Cleans the entire graph
2. Rebuilds from scratch
3. Validates against actual files
4. Checks all relationships
5. Verifies metadata
"""

import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple

sys.path.append('.')

from code_graph_system.core.graph_store import FederatedGraphStore
from plugins.php.plugin import PHPLanguagePlugin


def print_header(text: str):
    """Print a formatted header"""
    print(f"\n{'='*70}")
    print(f"  {text}")
    print('='*70)


def print_section(text: str):
    """Print a section header"""
    print(f"\n>>> {text}")
    print('-'*50)


class GraphValidator:
    """Validates that the graph accurately represents the codebase"""
    
    def __init__(self, graph_store: FederatedGraphStore):
        self.graph_store = graph_store
        self.validation_errors = []
        self.validation_warnings = []
        
    def validate_file_node(self, file_path: str) -> bool:
        """Validate that a file node exists and has correct properties"""
        print(f"\n🔍 Validating file node: {file_path}")
        
        # Check if file exists on disk
        if not Path(file_path).exists():
            self.validation_errors.append(f"File does not exist on disk: {file_path}")
            print(f"   ❌ File not found on disk")
            return False
            
        # Check if file node exists in graph
        result = self.graph_store.query("""
            MATCH (f:File {path: $path})
            RETURN f
        """, {'path': file_path})
        
        if not result:
            self.validation_errors.append(f"File node not in graph: {file_path}")
            print(f"   ❌ File node not found in graph")
            return False
            
        file_node = result[0]['f']
        print(f"   ✅ File node exists in graph")
        
        # Validate file properties
        actual_size = Path(file_path).stat().st_size
        node_size = file_node.get('size', 0)
        
        if abs(actual_size - node_size) > 100:  # Allow small difference
            self.validation_warnings.append(
                f"File size mismatch for {file_path}: actual={actual_size}, node={node_size}"
            )
            print(f"   ⚠️  File size mismatch")
            
        return True
        
    def validate_class_in_file(self, file_path: str, class_name: str) -> bool:
        """Validate that a class found in the graph actually exists in the file"""
        print(f"\n🔍 Validating class '{class_name}' in {Path(file_path).name}")
        
        # Read the actual file
        try:
            with open(file_path, 'r') as f:
                content = f.read()
        except Exception as e:
            self.validation_errors.append(f"Cannot read file {file_path}: {e}")
            return False
            
        # Check if class exists in file (simple check)
        import re
        class_pattern = rf'class\s+{re.escape(class_name)}'
        if not re.search(class_pattern, content):
            self.validation_errors.append(
                f"Class '{class_name}' not found in file {file_path}"
            )
            print(f"   ❌ Class '{class_name}' not found in actual file")
            return False
            
        print(f"   ✅ Class '{class_name}' exists in file")
        
        # Check if class node exists in graph
        result = self.graph_store.query("""
            MATCH (c:Symbol {name: $name, kind: 'class'})
            RETURN c
        """, {'name': class_name})
        
        if not result:
            self.validation_errors.append(f"Class node '{class_name}' not in graph")
            print(f"   ❌ Class node not found in graph")
            return False
            
        print(f"   ✅ Class node exists in graph")
        return True
        
    def validate_relationships(self, class_name: str) -> Dict[str, Any]:
        """Validate relationships for a class"""
        print(f"\n🔍 Validating relationships for class '{class_name}'")
        
        # Get all relationships for the class
        result = self.graph_store.query("""
            MATCH (c:Symbol {name: $name, kind: 'class'})
            OPTIONAL MATCH (c)-[r]->(t)
            RETURN type(r) as rel_type, collect(t.name) as targets
        """, {'name': class_name})
        
        relationships = {}
        if result:
            for row in result:
                if row['rel_type']:
                    relationships[row['rel_type']] = row['targets']
                    
        print(f"   Found relationships: {list(relationships.keys())}")
        return relationships
        
    def validate_metadata(self) -> bool:
        """Check if metadata is properly stored"""
        print(f"\n🔍 Validating metadata storage")
        
        # Check for nodes with metadata
        result = self.graph_store.query("""
            MATCH (n)
            WHERE n.metadata IS NOT NULL OR 
                  n.metadata_namespace IS NOT NULL OR
                  n.metadata_file_path IS NOT NULL
            RETURN count(n) as count
        """)
        
        metadata_count = result[0]['count'] if result else 0
        
        if metadata_count > 0:
            print(f"   ✅ Found {metadata_count} nodes with metadata")
            
            # Sample some metadata
            sample = self.graph_store.query("""
                MATCH (n)
                WHERE n.metadata_file_path IS NOT NULL
                RETURN n.name as name, n.metadata_file_path as file_path
                LIMIT 3
            """)
            
            if sample:
                print(f"   Sample metadata:")
                for s in sample:
                    print(f"     • {s['name']}: {s['file_path']}")
                    
            return True
        else:
            self.validation_warnings.append("No metadata found in graph")
            print(f"   ⚠️  No metadata found")
            return False
            
    def generate_report(self) -> Dict[str, Any]:
        """Generate validation report"""
        return {
            'errors': self.validation_errors,
            'warnings': self.validation_warnings,
            'error_count': len(self.validation_errors),
            'warning_count': len(self.validation_warnings),
            'success': len(self.validation_errors) == 0
        }


def clean_graph(graph_store: FederatedGraphStore) -> bool:
    """Completely clean the graph database"""
    print_section("CLEANING GRAPH DATABASE")
    
    try:
        # Delete all nodes and relationships
        graph_store.graph.run("MATCH (n) DETACH DELETE n")
        print("✅ Deleted all nodes and relationships")
        
        # Verify cleanup
        result = graph_store.query("MATCH (n) RETURN count(n) as count")
        count = result[0]['count'] if result else 0
        
        if count == 0:
            print("✅ Graph is completely clean")
            return True
        else:
            print(f"❌ Graph still has {count} nodes")
            return False
            
    except Exception as e:
        print(f"❌ Error cleaning graph: {e}")
        return False


def rebuild_graph(graph_store: FederatedGraphStore, php_plugin: PHPLanguagePlugin) -> Dict[str, int]:
    """Rebuild the entire graph from scratch"""
    print_section("REBUILDING GRAPH FROM SCRATCH")
    
    stats = {
        'files_processed': 0,
        'total_nodes': 0,
        'total_relationships': 0,
        'classes_found': 0,
        'errors': 0
    }
    
    # List of files to process
    test_files = [
        'espocrm/application/Espo/Core/Container.php',
        'espocrm/application/Espo/Core/Application.php',
        'espocrm/application/Espo/Core/HookManager.php',
        'espocrm/application/Espo/Core/InjectableFactory.php',
        'espocrm/application/Espo/Core/ApplicationUser.php',
    ]
    
    for file_path in test_files:
        if not Path(file_path).exists():
            print(f"⚠️  Skipping non-existent file: {file_path}")
            stats['errors'] += 1
            continue
            
        print(f"\n📝 Processing: {Path(file_path).name}")
        
        try:
            # Parse the file
            result = php_plugin.parse_file(file_path)
            
            # Count classes
            classes = [n for n in result.nodes if hasattr(n, 'kind') and n.kind == 'class']
            stats['classes_found'] += len(classes)
            
            if classes:
                print(f"   Found classes: {', '.join([c.name for c in classes])}")
            
            # Store in graph
            nodes_stored, rels_stored = graph_store.store_batch(
                result.nodes,
                result.relationships,
                'php'
            )
            
            stats['total_nodes'] += nodes_stored
            stats['total_relationships'] += rels_stored
            stats['files_processed'] += 1
            
            print(f"   Stored: {nodes_stored} nodes, {rels_stored} relationships")
            
        except Exception as e:
            print(f"   ❌ Error processing file: {e}")
            stats['errors'] += 1
            
    return stats


def check_php_parser_output(file_path: str) -> Dict[str, Any]:
    """Check what the PHP parser actually outputs"""
    print_section(f"PHP PARSER OUTPUT FOR {Path(file_path).name}")
    
    try:
        # Run the PHP parser directly
        result = subprocess.run(
            ['php', 'plugins/php/parser.php', file_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            print(f"❌ Parser error: {result.stderr}")
            return {}
            
        # Parse JSON output
        parser_output = json.loads(result.stdout)
        
        # Display parsed data
        print(f"File: {parser_output.get('file')}")
        print(f"Classes found: {len(parser_output.get('classes', []))}")
        
        for cls in parser_output.get('classes', []):
            print(f"\n  Class: {cls['name']}")
            print(f"    Type: {cls['type']}")
            print(f"    Namespace: {cls.get('namespace', 'none')}")
            print(f"    FQCN: {cls['fqcn']}")
            print(f"    Extends: {cls.get('extends', 'none')}")
            print(f"    Implements: {', '.join(cls.get('implements', []))}")
            print(f"    Methods: {len(cls.get('methods', []))}")
            print(f"    Properties: {len(cls.get('properties', []))}")
            
            # Show some methods
            for method in cls.get('methods', [])[:3]:
                print(f"      Method: {method['name']} ({method['visibility']})")
                
        return parser_output
        
    except Exception as e:
        print(f"❌ Error running parser: {e}")
        return {}


def check_filesystem_representation() -> None:
    """Check if we have filesystem representation in the graph"""
    print_section("CHECKING FILESYSTEM REPRESENTATION")
    
    # Check for metadata JSONs
    metadata_files = list(Path('espocrm/application/Espo/Resources/metadata').glob('**/*.json')) if \
                    Path('espocrm/application/Espo/Resources/metadata').exists() else []
    
    print(f"Found {len(metadata_files)} metadata JSON files")
    
    if metadata_files:
        print("\nSample metadata files:")
        for mf in metadata_files[:5]:
            print(f"  • {mf.relative_to('espocrm')}")
            
    # Check directory structure
    print("\n📁 Directory Structure:")
    espo_path = Path('espocrm')
    if espo_path.exists():
        for item in sorted(espo_path.glob('application/Espo/*'))[:10]:
            if item.is_dir():
                print(f"  📁 {item.name}/")
                # Show subdirectories
                for subitem in sorted(item.glob('*'))[:3]:
                    print(f"     {'📁' if subitem.is_dir() else '📄'} {subitem.name}")


def compare_file_with_graph(file_path: str, graph_store: FederatedGraphStore) -> None:
    """Compare actual file content with graph representation"""
    print_section(f"COMPARING FILE WITH GRAPH: {Path(file_path).name}")
    
    # Read the actual file
    print("\n📄 ACTUAL FILE CONTENT:")
    with open(file_path, 'r') as f:
        lines = f.readlines()
        
    # Find key elements in the file
    classes_in_file = []
    methods_in_file = []
    properties_in_file = []
    
    import re
    for i, line in enumerate(lines, 1):
        # Find classes
        if match := re.search(r'class\s+(\w+)', line):
            classes_in_file.append((match.group(1), i))
            print(f"  Line {i:4}: class {match.group(1)}")
            
        # Find methods
        if match := re.search(r'(?:public|private|protected)\s+function\s+(\w+)', line):
            methods_in_file.append((match.group(1), i))
            if len(methods_in_file) <= 5:  # Show first 5
                print(f"  Line {i:4}: method {match.group(1)}")
                
        # Find properties
        if match := re.search(r'(?:public|private|protected)\s+(?:static\s+)?(?:\??\w+\s+)?\$(\w+)', line):
            properties_in_file.append((match.group(1), i))
            if len(properties_in_file) <= 5:  # Show first 5
                print(f"  Line {i:4}: property ${match.group(1)}")
                
    print(f"\n  Total: {len(classes_in_file)} classes, {len(methods_in_file)} methods, {len(properties_in_file)} properties")
    
    # Now check what's in the graph
    print("\n📊 GRAPH REPRESENTATION:")
    
    # Get all symbols from this file
    result = graph_store.query("""
        MATCH (n:Symbol)
        WHERE n.metadata_file_path = $path
        RETURN n.name as name, n.kind as kind, n.type as type
        ORDER BY n.kind, n.name
    """, {'path': file_path})
    
    if result:
        graph_classes = [r for r in result if r['kind'] == 'class']
        graph_props = [r for r in result if r['kind'] == 'property']
        graph_methods = [r for r in result if r['kind'] == 'method']
        
        print(f"  Classes in graph: {', '.join([c['name'] for c in graph_classes])}")
        print(f"  Properties in graph: {len(graph_props)}")
        print(f"  Methods in graph: {len(graph_methods)}")
        
        # Compare
        print("\n🔍 COMPARISON:")
        
        file_class_names = {c[0] for c in classes_in_file}
        graph_class_names = {c['name'] for c in graph_classes}
        
        if file_class_names == graph_class_names:
            print(f"  ✅ Classes match perfectly")
        else:
            missing_in_graph = file_class_names - graph_class_names
            extra_in_graph = graph_class_names - file_class_names
            
            if missing_in_graph:
                print(f"  ❌ Missing in graph: {missing_in_graph}")
            if extra_in_graph:
                print(f"  ❌ Extra in graph: {extra_in_graph}")
                
        # Check relationships
        print("\n🔗 RELATIONSHIPS IN GRAPH:")
        for cls_name in graph_class_names:
            result = graph_store.query("""
                MATCH (c:Symbol {name: $name, kind: 'class'})-[r]->(t)
                RETURN type(r) as rel_type, count(t) as count
                ORDER BY count DESC
            """, {'name': cls_name})
            
            if result:
                print(f"  {cls_name}:")
                for rel in result:
                    if rel['rel_type']:
                        print(f"    → {rel['rel_type']}: {rel['count']}")
    else:
        print("  ❌ No symbols found in graph for this file")


def main():
    print_header("UNIVERSAL CODE GRAPH SYSTEM - COMPLETE VALIDATION")
    print(f"Started at: {datetime.now().isoformat()}")
    
    # 1. Connect to Neo4j
    print_section("CONNECTING TO NEO4J")
    try:
        graph_store = FederatedGraphStore(
            'bolt://localhost:7688',
            ('neo4j', 'password123'),
            {'federation': {'mode': 'unified'}}
        )
        print("✅ Connected to Neo4j")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        return
        
    # 2. Clean the graph
    if not clean_graph(graph_store):
        print("❌ Failed to clean graph, aborting")
        return
        
    # 3. Initialize PHP plugin
    print_section("INITIALIZING PHP PLUGIN")
    php_plugin = PHPLanguagePlugin()
    php_plugin.initialize({})
    print("✅ PHP plugin initialized")
    
    # 4. Check parser output for a sample file
    sample_file = 'espocrm/application/Espo/Core/Container.php'
    if Path(sample_file).exists():
        parser_output = check_php_parser_output(sample_file)
    
    # 5. Rebuild the graph
    rebuild_stats = rebuild_graph(graph_store, php_plugin)
    
    print_section("REBUILD STATISTICS")
    for key, value in rebuild_stats.items():
        print(f"  {key}: {value}")
        
    # 6. Validate the graph
    print_header("VALIDATION PHASE")
    validator = GraphValidator(graph_store)
    
    # Validate specific file and class
    validator.validate_file_node('espocrm/application/Espo/Core/Container.php')
    validator.validate_class_in_file('espocrm/application/Espo/Core/Container.php', 'Container')
    
    # Validate relationships
    relationships = validator.validate_relationships('Container')
    
    # Validate metadata
    validator.validate_metadata()
    
    # 7. Check filesystem representation
    check_filesystem_representation()
    
    # 8. Deep comparison for Container.php
    compare_file_with_graph('espocrm/application/Espo/Core/Container.php', graph_store)
    
    # 9. Generate validation report
    print_header("VALIDATION REPORT")
    report = validator.generate_report()
    
    print(f"\n📊 Summary:")
    print(f"  Errors: {report['error_count']}")
    print(f"  Warnings: {report['warning_count']}")
    print(f"  Success: {'✅ Yes' if report['success'] else '❌ No'}")
    
    if report['errors']:
        print(f"\n❌ Errors found:")
        for error in report['errors']:
            print(f"  • {error}")
            
    if report['warnings']:
        print(f"\n⚠️  Warnings:")
        for warning in report['warnings']:
            print(f"  • {warning}")
            
    # 10. Final graph statistics
    print_header("FINAL GRAPH STATE")
    stats = graph_store.get_statistics()
    print(f"  Total nodes: {stats['total_nodes']}")
    print(f"  Total relationships: {stats['total_relationships']}")
    
    if stats.get('node_types'):
        print(f"\n  Node types:")
        for node_type, count in stats['node_types'].items():
            print(f"    {node_type}: {count}")
            
    print(f"\n✅ Validation complete at {datetime.now().isoformat()}")


if __name__ == '__main__':
    main()