"""
JavaScript Language Plugin for Universal Code Graph System.

Parses JavaScript files to extract:
- ES6 modules and imports
- Classes and methods
- Functions and arrow functions
- CommonJS and AMD modules
- React components
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
from uuid import UUID, uuid4

from code_graph_system.core.plugin_interface import ILanguagePlugin, ParseResult
from code_graph_system.core.schema import (
    CoreNode, Symbol, File, Module, Relationship
)


logger = logging.getLogger(__name__)


class JavaScriptPlugin(ILanguagePlugin):
    """JavaScript language plugin using Node.js parser"""
    
    def __init__(self):
        self.plugin_id = 'javascript'
        self.name = 'JavaScript Language Plugin'
        self.version = '1.0.0'
        self.parser_path = Path(__file__).parent / 'parser.js'
        
    def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize the plugin"""
        if not self.parser_path.exists():
            logger.error(f"Parser not found at {self.parser_path}")
            return False
            
        logger.info(f"Initialized {self.name} v{self.version}")
        return True
        
    def can_parse(self, file_path: str) -> bool:
        """Check if this plugin can parse the file"""
        extensions = ['.js', '.jsx', '.mjs', '.ts', '.tsx']
        return Path(file_path).suffix.lower() in extensions
        
    def parse_file(self, file_path: str) -> ParseResult:
        """Parse a JavaScript file"""
        if not self.can_parse(file_path):
            return ParseResult(
                success=False,
                nodes=[],
                relationships=[],
                errors=[f"Cannot parse file: {file_path}"],
                warnings=[]
            )
            
        try:
            # Call Node.js parser
            result = subprocess.run(
                ['node', str(self.parser_path), file_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return ParseResult(
                    success=False,
                    nodes=[],
                    relationships=[],
                    errors=[f"Parser error: {result.stderr}"],
                    warnings=[]
                )
                
            # Parse JSON output
            parser_output = json.loads(result.stdout)
            
            # Convert to our schema
            nodes, relationships = self._convert_parser_output(parser_output, file_path)
            
            return ParseResult(
                success=True,
                nodes=nodes,
                relationships=relationships,
                errors=[],
                warnings=parser_output.get('warnings', [])
            )
            
        except subprocess.TimeoutExpired:
            return ParseResult(
                success=False,
                nodes=[],
                relationships=[],
                errors=[f"Parser timeout for file: {file_path}"],
                warnings=[]
            )
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            return ParseResult(
                success=False,
                nodes=[],
                relationships=[],
                errors=[str(e)],
                warnings=[]
            )
            
    def _convert_parser_output(self, output: Dict[str, Any], file_path: str) -> tuple:
        """Convert parser output to our schema"""
        nodes = []
        relationships = []
        
        # Create file node
        file_node = File(
            id=uuid4(),
            type='File',
            name=Path(file_path).name,
            path=file_path,
            plugin_id=self.plugin_id,
            metadata={
                'language': 'javascript',
                'size': Path(file_path).stat().st_size if Path(file_path).exists() else 0
            }
        )
        nodes.append(file_node)
        
        # Create module node
        module_name = Path(file_path).stem
        module_node = Module(
            id=uuid4(),
            type='Module',
            name=module_name,
            qualified_name=file_path,
            plugin_id=self.plugin_id,
            metadata=output.get('module', {})
        )
        nodes.append(module_node)
        
        # Link file to module
        relationships.append(Relationship(
            source_id=file_node.id,
            target_id=module_node.id,
            type='CONTAINS_MODULE'
        ))
        
        # Process imports
        for imp in output.get('imports', []):
            import_node = Symbol(
                id=uuid4(),
                type='Import',
                name=imp.get('source', 'unknown'),
                qualified_name=f"import:{imp.get('source')}",
                kind='import',
                plugin_id=self.plugin_id,
                metadata=imp
            )
            nodes.append(import_node)
            
            relationships.append(Relationship(
                source_id=module_node.id,
                target_id=import_node.id,
                type='IMPORTS'
            ))
            
        # Process exports
        for exp in output.get('exports', []):
            export_node = Symbol(
                id=uuid4(),
                type='Export',
                name=exp.get('name', 'default'),
                qualified_name=f"{module_name}.{exp.get('name', 'default')}",
                kind='export',
                plugin_id=self.plugin_id,
                metadata=exp
            )
            nodes.append(export_node)
            
            relationships.append(Relationship(
                source_id=module_node.id,
                target_id=export_node.id,
                type='EXPORTS'
            ))
            
        # Process classes
        for cls in output.get('classes', []):
            class_node = Symbol(
                id=uuid4(),
                type='Class',
                name=cls.get('name', 'Anonymous'),
                qualified_name=f"{module_name}.{cls.get('name', 'Anonymous')}",
                kind='class',
                plugin_id=self.plugin_id,
                metadata=cls
            )
            nodes.append(class_node)
            
            relationships.append(Relationship(
                source_id=module_node.id,
                target_id=class_node.id,
                type='DEFINES_CLASS'
            ))
            
            # Handle extends
            if cls.get('extends'):
                relationships.append(Relationship(
                    source_id=class_node.id,
                    target_id=uuid4(),  # Would need to resolve
                    type='EXTENDS',
                    metadata={'parent': cls['extends']}
                ))
                
        # Process functions
        for func in output.get('functions', []):
            func_node = Symbol(
                id=uuid4(),
                type='Function',
                name=func.get('name', 'anonymous'),
                qualified_name=f"{module_name}.{func.get('name', 'anonymous')}",
                kind='function',
                plugin_id=self.plugin_id,
                metadata=func
            )
            nodes.append(func_node)
            
            relationships.append(Relationship(
                source_id=module_node.id,
                target_id=func_node.id,
                type='DEFINES_FUNCTION'
            ))
            
        return nodes, relationships
        
    def parse_string(self, content: str, file_name: str = None) -> ParseResult:
        """Parse JavaScript code from string"""
        # Could implement string parsing via temp file
        # For now, not implemented
        return ParseResult(
            success=False,
            nodes=[],
            relationships=[],
            errors=["String parsing not implemented"],
            warnings=[]
        )
        
    def get_metadata(self) -> Dict[str, Any]:
        """Get plugin metadata"""
        return {
            'id': self.plugin_id,
            'name': self.name,
            'version': self.version,
            'type': 'language',
            'language': 'javascript',
            'extensions': ['.js', '.jsx', '.mjs', '.ts', '.tsx'],
            'capabilities': [
                'es6_modules',
                'commonjs',
                'amd',
                'classes',
                'functions',
                'arrow_functions',
                'react_components'
            ]
        }
        
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate plugin configuration"""
        return True
        
    def cleanup(self) -> bool:
        """Cleanup plugin resources"""
        return True