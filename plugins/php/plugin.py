"""
PHP Language Plugin for Code Graph System

Provides PHP parsing and analysis capabilities.
"""

import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Iterator, Optional
import hashlib
import logging

# Add parent directories to path for imports
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from code_graph_system.core.plugin_interface import (
    ILanguagePlugin, PluginMetadata, PluginType,
    PluginCapability, ParseResult
)
from code_graph_system.core.schema import (
    CoreNode, Symbol, Relationship, File,
    SourceLocation, Visibility
)


logger = logging.getLogger(__name__)


class PHPLanguagePlugin(ILanguagePlugin):
    """PHP language support plugin"""
    
    def __init__(self):
        self.config = {}
        self.parser_script = Path(__file__).parent / 'parser.php'
        
    def get_metadata(self) -> PluginMetadata:
        """Return plugin metadata"""
        return PluginMetadata(
            id='php-language',
            name='PHP Language Support',
            version='1.0.0',
            author='Code Graph System',
            description='PHP language parsing and analysis support',
            type=PluginType.LANGUAGE,
            capabilities=[PluginCapability.PARSE, PluginCapability.ANALYZE],
            supported_languages=['php'],
            supported_extensions=['.php', '.php3', '.php4', '.php5', '.php7', '.phtml', '.inc'],
            namespace='php'
        )
        
    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize plugin with configuration"""
        self.config = config
        
        # Check if PHP is available
        try:
            result = subprocess.run(['php', '--version'], capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError("PHP not found in PATH")
            logger.info(f"PHP available: {result.stdout.split('\\n')[0]}")
        except FileNotFoundError:
            raise RuntimeError("PHP not found. Please install PHP >= 7.4")
            
    def can_handle(self, file_path: str) -> bool:
        """Check if plugin can handle this file"""
        extensions = self.get_metadata().supported_extensions
        return any(file_path.endswith(ext) for ext in extensions)
        
    def get_namespace(self) -> str:
        """Return plugin namespace"""
        return 'php'
        
    def get_schema_extensions(self) -> Dict[str, Any]:
        """Return custom node and relationship types"""
        return {
            'nodes': {
                'PHPClass': {
                    'extends': 'Symbol',
                    'properties': {
                        'namespace': 'string',
                        'is_abstract': 'boolean',
                        'is_final': 'boolean',
                        'is_interface': 'boolean',
                        'traits': 'array'
                    }
                },
                'PHPTrait': {
                    'extends': 'Symbol',
                    'properties': {
                        'namespace': 'string'
                    }
                },
                'PHPInterface': {
                    'extends': 'Symbol',
                    'properties': {
                        'namespace': 'string'
                    }
                },
                'PHPMethod': {
                    'extends': 'Symbol',
                    'properties': {
                        'class_name': 'string',
                        'visibility': 'string',
                        'is_static': 'boolean',
                        'is_abstract': 'boolean',
                        'is_final': 'boolean',
                        'parameters': 'array',
                        'return_type': 'string'
                    }
                },
                'PHPProperty': {
                    'extends': 'Symbol',
                    'properties': {
                        'class_name': 'string',
                        'visibility': 'string',
                        'is_static': 'boolean',
                        'type': 'string',
                        'default_value': 'string'
                    }
                }
            },
            'relationships': {
                'USES_TRAIT': {
                    'from': 'PHPClass',
                    'to': 'PHPTrait'
                },
                'IMPLEMENTS_INTERFACE': {
                    'from': 'PHPClass',
                    'to': 'PHPInterface'
                },
                'HAS_METHOD': {
                    'from': 'PHPClass',
                    'to': 'PHPMethod'
                },
                'HAS_PROPERTY': {
                    'from': 'PHPClass',
                    'to': 'PHPProperty'
                }
            }
        }
        
    def parse_file(self, file_path: str) -> ParseResult:
        """Parse a PHP file and return results"""
        nodes = []
        relationships = []
        errors = []
        warnings = []
        
        try:
            # Calculate file hash
            with open(file_path, 'rb') as f:
                content = f.read()
                file_hash = hashlib.sha256(content).hexdigest()
                
            # Create file node
            file_node = File(
                path=file_path,
                language='php',
                hash=file_hash,
                size=len(content)
            )
            nodes.append(file_node)
            
            # Call PHP parser
            if self.parser_script.exists():
                result = subprocess.run(
                    ['php', str(self.parser_script), file_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode != 0:
                    errors.append(f"Parser error: {result.stderr}")
                else:
                    # Parse JSON output
                    try:
                        parser_output = json.loads(result.stdout)
                        
                        # Process classes
                        for class_data in parser_output.get('classes', []):
                            class_node = self._create_class_node(class_data, file_path)
                            nodes.append(class_node)
                            
                            # Create relationships
                            if class_data.get('extends'):
                                rel = Relationship(
                                    type='EXTENDS',
                                    source_id=class_node.id,
                                    target_id=None,  # Will be resolved later
                                    metadata={'target_name': class_data['extends']}
                                )
                                relationships.append(rel)
                                
                            for interface in class_data.get('implements', []):
                                rel = Relationship(
                                    type='IMPLEMENTS_INTERFACE',
                                    source_id=class_node.id,
                                    target_id=None,  # Will be resolved later
                                    metadata={'target_name': interface}
                                )
                                relationships.append(rel)
                                
                            # Process methods
                            for method_data in class_data.get('methods', []):
                                method_node = self._create_method_node(method_data, class_data)
                                nodes.append(method_node)
                                
                                rel = Relationship(
                                    type='HAS_METHOD',
                                    source_id=class_node.id,
                                    target_id=method_node.id
                                )
                                relationships.append(rel)
                                
                            # Process properties
                            for prop_data in class_data.get('properties', []):
                                prop_node = self._create_property_node(prop_data, class_data)
                                nodes.append(prop_node)
                                
                                rel = Relationship(
                                    type='HAS_PROPERTY',
                                    source_id=class_node.id,
                                    target_id=prop_node.id
                                )
                                relationships.append(rel)
                                
                    except json.JSONDecodeError as e:
                        errors.append(f"Failed to parse parser output: {e}")
            else:
                # Fallback to basic regex parsing if parser script not available
                nodes.extend(self._basic_parse(file_path))
                
        except Exception as e:
            errors.append(f"Parse error: {str(e)}")
            
        return ParseResult(
            file_path=file_path,
            nodes=nodes,
            relationships=relationships,
            errors=errors,
            warnings=warnings
        )
        
    def stream_parse(self, file_path: str) -> Iterator[ParseResult]:
        """Stream parse results for large files"""
        # For now, just yield single result
        # TODO: Implement actual streaming for large files
        yield self.parse_file(file_path)
        
    def extract_symbols(self, content: str) -> List[Symbol]:
        """Extract symbols from PHP code"""
        symbols = []
        
        # Basic regex-based extraction (fallback)
        import re
        
        # Extract classes
        class_pattern = r'class\\s+(\\w+)'
        for match in re.finditer(class_pattern, content):
            symbol = Symbol(
                name=match.group(1),
                qualified_name=match.group(1),
                kind='class'
            )
            symbols.append(symbol)
            
        # Extract functions
        function_pattern = r'function\\s+(\\w+)\\s*\\('
        for match in re.finditer(function_pattern, content):
            symbol = Symbol(
                name=match.group(1),
                qualified_name=match.group(1),
                kind='function'
            )
            symbols.append(symbol)
            
        return symbols
        
    def extract_dependencies(self, content: str) -> List[str]:
        """Extract dependencies from PHP code"""
        dependencies = []
        
        import re
        
        # Extract use statements
        use_pattern = r'use\\s+([\\w\\\\]+);'
        for match in re.finditer(use_pattern, content):
            dependencies.append(match.group(1))
            
        # Extract require/include statements
        require_pattern = r'(?:require|include)(?:_once)?\\s*[\\(\\s]+[\'"]([^\'"]+)[\'"]'
        for match in re.finditer(require_pattern, content):
            dependencies.append(match.group(1))
            
        return dependencies
        
    def resolve_imports(self, content: str) -> List[Dict[str, str]]:
        """Resolve import statements in PHP code"""
        imports = []
        
        import re
        
        # Extract use statements with aliases
        use_pattern = r'use\\s+([\\w\\\\]+)(?:\\s+as\\s+(\\w+))?;'
        for match in re.finditer(use_pattern, content):
            import_data = {
                'name': match.group(1),
                'alias': match.group(2) if match.group(2) else match.group(1).split('\\\\')[-1]
            }
            imports.append(import_data)
            
        return imports
        
    def resolve_type(self, symbol: str, context: Dict[str, Any]) -> Optional[str]:
        """Resolve type of a symbol in given context"""
        # TODO: Implement proper type resolution
        # This would require maintaining a symbol table and understanding PHP's type system
        return None
        
    def _create_class_node(self, class_data: Dict, file_path: str) -> Symbol:
        """Create a class node from parser data"""
        node = Symbol(
            name=class_data['name'],
            qualified_name=class_data.get('fqcn', class_data['name']),
            kind='class',
            plugin_id='php-language'
        )
        
        node.metadata = {
            'namespace': class_data.get('namespace', ''),
            'is_abstract': class_data.get('is_abstract', False),
            'is_final': class_data.get('is_final', False),
            'is_interface': class_data.get('is_interface', False),
            'file_path': file_path
        }
        
        return node
        
    def _create_method_node(self, method_data: Dict, class_data: Dict) -> Symbol:
        """Create a method node from parser data"""
        node = Symbol(
            name=method_data['name'],
            qualified_name=f"{class_data.get('fqcn', class_data['name'])}::{method_data['name']}",
            kind='method',
            plugin_id='php-language'
        )
        
        visibility_map = {
            'public': Visibility.PUBLIC,
            'protected': Visibility.PROTECTED,
            'private': Visibility.PRIVATE
        }
        
        node.visibility = visibility_map.get(method_data.get('visibility', 'public'))
        
        node.metadata = {
            'class_name': class_data['name'],
            'is_static': method_data.get('is_static', False),
            'is_abstract': method_data.get('is_abstract', False),
            'is_final': method_data.get('is_final', False)
        }
        
        return node
        
    def _create_property_node(self, prop_data: Dict, class_data: Dict) -> Symbol:
        """Create a property node from parser data"""
        node = Symbol(
            name=prop_data['name'],
            qualified_name=f"{class_data.get('fqcn', class_data['name'])}::{prop_data['name']}",
            kind='property',
            plugin_id='php-language'
        )
        
        visibility_map = {
            'public': Visibility.PUBLIC,
            'protected': Visibility.PROTECTED,
            'private': Visibility.PRIVATE
        }
        
        node.visibility = visibility_map.get(prop_data.get('visibility', 'public'))
        
        node.metadata = {
            'class_name': class_data['name'],
            'is_static': prop_data.get('is_static', False)
        }
        
        return node
        
    def _basic_parse(self, file_path: str) -> List[Symbol]:
        """Basic parsing without PHP parser (fallback)"""
        symbols = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                symbols = self.extract_symbols(content)
        except Exception as e:
            logger.error(f"Basic parse failed for {file_path}: {e}")
            
        return symbols


# Entry point for plugin
plugin = PHPLanguagePlugin()