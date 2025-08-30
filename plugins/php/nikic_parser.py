#!/usr/bin/env python3
"""
AST-based PHP parser using nikic/PHP-Parser
Provides accurate FQN resolution and inheritance tracking
"""

import subprocess
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any
from code_graph_system.core.schema import Symbol, Relationship, SourceLocation
from code_graph_system.core.plugin_interface import ParseResult


class NikicPHPParser:
    """PHP parser using nikic/PHP-Parser for accurate AST parsing"""
    
    def __init__(self):
        # Use enhanced parser with relationship extraction
        self.parser_script = Path(__file__).parent / 'ast_parser_enhanced.php'
        if not self.parser_script.exists():
            # Fallback to basic parser if enhanced not found
            self.parser_script = Path(__file__).parent / 'ast_parser.php'
        if not self.parser_script.exists():
            raise FileNotFoundError(f"PHP parser script not found: {self.parser_script}")
            
    def parse_file(self, file_path: str) -> ParseResult:
        """Parse PHP file using nikic/PHP-Parser"""
        try:
            # Call PHP script
            result = subprocess.run(
                ['php', str(self.parser_script), file_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return ParseResult(
                    file_path=file_path,
                    nodes=[],
                    relationships=[],
                    errors=[f"PHP parser failed: {result.stderr}"]
                )
                
            # Parse JSON output
            try:
                ast_data = json.loads(result.stdout)
            except json.JSONDecodeError as e:
                return ParseResult(
                    file_path=file_path,
                    nodes=[],
                    relationships=[],
                    errors=[f"Invalid JSON from parser: {e}"]
                )
                
            # Check for errors
            if 'error' in ast_data:
                return ParseResult(
                    file_path=file_path,
                    nodes=[],
                    relationships=[],
                    errors=[ast_data['error']]
                )
                
            return self._convert_ast_to_nodes(ast_data, file_path)
            
        except subprocess.TimeoutExpired:
            return ParseResult(
                file_path=file_path,
                nodes=[],
                relationships=[],
                errors=[f"Parser timeout for file: {file_path}"]
            )
        except Exception as e:
            return ParseResult(
                file_path=file_path,
                nodes=[],
                relationships=[],
                errors=[f"Parser error: {str(e)}"]
            )
            
    def _convert_ast_to_nodes(self, ast_data: Dict, file_path: str) -> ParseResult:
        """Convert AST data to Symbol nodes and relationships"""
        nodes = []
        relationships = []
        
        # Create file node
        file_id = self._generate_id(file_path)
        file_node = Symbol(
            name=Path(file_path).name,
            qualified_name=file_path,
            kind='file',
            plugin_id='php'
        )
        file_node.id = file_id
        file_node.location = SourceLocation(
            file_path=file_path,
            start_line=1,
            start_column=0,
            end_line=1,
            end_column=0
        )
        nodes.append(file_node)
        
        # Process AST nodes
        for node_data in ast_data.get('nodes', []):
            symbol = self._create_symbol(node_data)
            nodes.append(symbol)
            
            # Add DEFINED_IN relationship
            relationships.append(Relationship(
                type='DEFINED_IN',
                source_id=symbol.id,
                target_id=file_id
            ))
            
        # Process relationships
        for rel_data in ast_data.get('relationships', []):
            try:
                # Skip if missing required fields
                if 'target_id' not in rel_data:
                    if 'target_fqn' in rel_data:
                        # For unresolved references (like external interfaces), create a placeholder target_id
                        rel_data['target_id'] = f"unresolved_{rel_data['target_fqn'].replace('\\', '_').replace('::', '_')}"
                    else:
                        continue
                
                # Skip if missing source_id
                if 'source_id' not in rel_data:
                    continue
                
                rel = Relationship(
                    type=rel_data['type'],
                    source_id=rel_data['source_id'],
                    target_id=rel_data['target_id']
                )
                
                # Store target FQN for unresolved references
                if 'target_fqn' in rel_data:
                    rel.metadata = {'target_fqn': rel_data['target_fqn']}
                    
                relationships.append(rel)
            except KeyError as e:
                print(f"Warning: Skipping relationship due to missing field: {e}")
                print(f"Relationship data: {rel_data}")
                continue
            
        return ParseResult(
            file_path=file_path,
            nodes=nodes,
            relationships=relationships,
            errors=[]
        )
        
    def _create_symbol(self, node_data: Dict) -> Symbol:
        """Create Symbol from node data"""
        symbol = Symbol(
            name=node_data['name'],
            qualified_name=node_data.get('fqn', node_data.get('qualified_name', '')),
            kind=node_data['kind'],
            plugin_id='php'
        )
        
        # Set ID
        symbol.id = node_data['id']
        
        # Set location
        if 'file_path' in node_data and 'line' in node_data:
            symbol.location = SourceLocation(
                file_path=node_data['file_path'],
                start_line=node_data['line'],
                start_column=0,
                end_line=node_data['line'],
                end_column=0
            )
            
        # Set metadata
        metadata = {}
        
        # Add visibility
        if 'visibility' in node_data:
            metadata['visibility'] = node_data['visibility']
            
        # Add modifiers
        for modifier in ['is_static', 'is_abstract', 'is_final', 'is_readonly']:
            if modifier in node_data and node_data[modifier]:
                metadata[modifier] = True
                
        # Add namespace
        if 'namespace' in node_data:
            metadata['namespace'] = node_data['namespace']
            
        # Add type information
        if 'return_type' in node_data and node_data['return_type']:
            metadata['return_type'] = node_data['return_type']
        if 'type' in node_data and node_data['type']:
            metadata['type'] = node_data['type']
            
        if metadata:
            symbol.metadata = metadata
            
        return symbol
        
    def _generate_id(self, content: str) -> str:
        """Generate unique ID"""
        return hashlib.md5(content.encode()).hexdigest()