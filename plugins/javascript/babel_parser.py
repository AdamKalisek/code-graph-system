#!/usr/bin/env python3
"""
Babel-based JavaScript/TypeScript parser wrapper
Uses Node.js subprocess to leverage @babel/parser for accurate parsing
"""

import json
import subprocess
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from code_graph_system.core.schema import Symbol, Relationship, SourceLocation
from code_graph_system.core.plugin_interface import ParseResult


class BabelParser:
    """JavaScript/TypeScript parser using Babel AST"""
    
    def __init__(self):
        self.parser_script = Path(__file__).parent / 'babel_parser_fixed.js'
        if not self.parser_script.exists():
            raise FileNotFoundError(f"Babel parser script not found: {self.parser_script}")
        
        # Test Node.js availability
        try:
            result = subprocess.run(['node', '--version'], capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError("Node.js is not available")
        except FileNotFoundError:
            raise RuntimeError("Node.js is not installed")
    
    def parse_file(self, file_path: str) -> ParseResult:
        """Parse a JavaScript/TypeScript file"""
        try:
            # Call Node.js parser
            result = subprocess.run(
                ['node', str(self.parser_script), file_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return ParseResult(
                    file_path=file_path,
                    nodes=[],
                    relationships=[],
                    errors=[f"Parser failed: {result.stderr}"]
                )
            
            # Parse JSON output
            data = json.loads(result.stdout)
            
            # Convert to Schema objects
            nodes = []
            relationships = []
            
            for node_data in data.get('nodes', []):
                node = self._create_symbol(node_data, file_path)
                nodes.append(node)
            
            for rel_data in data.get('relationships', []):
                rel = Relationship(
                    type=rel_data['type'],
                    source_id=rel_data['source_id'],
                    target_id=rel_data['target_id'],
                    metadata=rel_data.get('metadata', {})
                )
                relationships.append(rel)
            
            return ParseResult(
                file_path=file_path,
                nodes=nodes,
                relationships=relationships,
                errors=data.get('errors', [])
            )
            
        except subprocess.TimeoutExpired:
            return ParseResult(
                file_path=file_path,
                nodes=[],
                relationships=[],
                errors=[f"Parser timeout for {file_path}"]
            )
        except Exception as e:
            return ParseResult(
                file_path=file_path,
                nodes=[],
                relationships=[],
                errors=[f"Parse error: {str(e)}"]
            )
    
    def _create_symbol(self, data: Dict, file_path: str) -> Symbol:
        """Create Symbol from parsed data"""
        symbol = Symbol(
            name=data['name'],
            qualified_name=data['qualified_name'],
            kind=data['kind'],
            plugin_id='javascript'
        )
        
        symbol.id = data['id']
        
        # Set metadata with language tag
        metadata = data.get('metadata', {})
        metadata['_language'] = 'javascript'
        symbol.metadata = metadata
        
        # Set location
        loc = data.get('location', {})
        symbol.location = SourceLocation(
            file_path=file_path,
            start_line=loc.get('start_line', 0),
            start_column=0,
            end_line=loc.get('end_line', 0),
            end_column=0
        )
        
        return symbol
    
    def parse_directory(self, directory: str, extensions: List[str] = None) -> List[ParseResult]:
        """Parse all JavaScript/TypeScript files in a directory"""
        if extensions is None:
            extensions = ['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs']
        
        results = []
        path = Path(directory)
        
        for ext in extensions:
            for file_path in path.rglob(f'*{ext}'):
                # Skip node_modules and other common exclusions
                if any(part in file_path.parts for part in ['node_modules', '.git', 'dist', 'build']):
                    continue
                
                result = self.parse_file(str(file_path))
                results.append(result)
        
        return results


# For backward compatibility with existing code
JavaScriptParser = BabelParser