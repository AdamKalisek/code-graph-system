"""
Core schema definitions for the Universal Code Graph System.

This module defines the base node and relationship types that all plugins must extend.
"""

from dataclasses import dataclass, field, fields
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime
from enum import Enum


class NodeType(Enum):
    """Base node types in the graph"""
    FILE = "File"
    SYMBOL = "Symbol"
    REFERENCE = "Reference"
    MODULE = "Module"
    PACKAGE = "Package"
    

class RelationType(Enum):
    """Base relationship types"""
    CONTAINS = "CONTAINS"
    DEPENDS_ON = "DEPENDS_ON"
    CALLS = "CALLS"
    IMPORTS = "IMPORTS"
    EXTENDS = "EXTENDS"
    IMPLEMENTS = "IMPLEMENTS"
    REFERENCES = "REFERENCES"
    

class Visibility(Enum):
    """Symbol visibility levels"""
    PUBLIC = "public"
    PROTECTED = "protected"
    PRIVATE = "private"
    INTERNAL = "internal"
    

@dataclass
class SourceLocation:
    """Location in source code"""
    file_path: str
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    

@dataclass
class CoreNode:
    """Base node that all plugins must extend"""
    id: UUID = field(default_factory=uuid4)
    type: str = ""
    name: str = ""
    plugin_id: str = ""
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert node to dictionary for storage"""
        # Get all fields from dataclass
        result = {}
        for field_info in fields(self):
            value = getattr(self, field_info.name)
            
            # Handle special types
            if field_info.name in ['id', 'source_id', 'target_id'] and value is not None:
                value = str(value)
            elif field_info.name in ['created_at', 'updated_at'] and value is not None:
                value = value.isoformat()
            elif field_info.name == 'source_location' and value is not None:
                value = {
                    'file_path': value.file_path,
                    'start_line': value.start_line,
                    'start_column': value.start_column,
                    'end_line': value.end_line,
                    'end_column': value.end_column
                }
            elif field_info.name == 'visibility' and value is not None:
                value = value.value
            elif isinstance(value, Enum):
                value = value.value
                
            # Only include non-None values
            if value is not None:
                result[field_info.name] = value
                
        return result
    

@dataclass
class File(CoreNode):
    """Represents a source code file"""
    path: str = ""
    language: str = ""
    hash: str = ""
    size: int = 0
    encoding: str = "utf-8"
    
    def __post_init__(self):
        self.type = NodeType.FILE.value
        

@dataclass
class Symbol(CoreNode):
    """Represents a code symbol (class, function, variable, etc.)"""
    qualified_name: str = ""
    kind: str = ""  # class, function, variable, constant, etc.
    visibility: Optional[Visibility] = None
    source_location: Optional[SourceLocation] = None
    documentation: Optional[str] = None
    is_exported: bool = False
    
    def __post_init__(self):
        self.type = NodeType.SYMBOL.value
        
    def get_labels(self) -> List[str]:
        """Return list of Neo4j labels for this symbol"""
        labels = ['Symbol']
        
        # Add language label if available
        if hasattr(self, '_language') and self._language:
            labels.append(self._language.upper())
        elif self.metadata and '_language' in self.metadata:
            labels.append(self.metadata['_language'].upper())
            
        # Add kind-specific label
        if self.kind:
            kind_label_map = {
                'class': 'Class',
                'method': 'Method',
                'function': 'Function',
                'property': 'Property',
                'file': 'File',
                'directory': 'Directory',
                'interface': 'Interface',
                'trait': 'Trait',
                'namespace': 'Namespace',
                'module': 'Module',
                'variable': 'Variable',
                'constant': 'Constant',
                'metadata': 'Metadata'
            }
            if self.kind.lower() in kind_label_map:
                labels.append(kind_label_map[self.kind.lower()])
                
        return labels
        

@dataclass
class Module(CoreNode):
    """Represents a module or namespace"""
    qualified_name: str = ""
    language: str = ""
    version: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        self.type = NodeType.MODULE.value
        

@dataclass
class Reference(CoreNode):
    """Represents a reference between symbols"""
    from_symbol_id: UUID = field(default_factory=uuid4)
    to_symbol_id: UUID = field(default_factory=uuid4)
    reference_type: str = ""
    source_location: Optional[SourceLocation] = None
    
    def __post_init__(self):
        self.type = NodeType.REFERENCE.value
        

@dataclass
class Relationship:
    """Base relationship between nodes"""
    id: UUID = field(default_factory=uuid4)
    type: str = ""
    source_id: UUID = field(default_factory=uuid4)
    target_id: UUID = field(default_factory=uuid4)
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    plugin_id: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert relationship to dictionary for storage"""
        return {
            'id': str(self.id),
            'type': self.type,
            'source_id': str(self.source_id),
            'target_id': str(self.target_id),
            'confidence': self.confidence,
            'metadata': self.metadata,
            'plugin_id': self.plugin_id,
            'created_at': self.created_at.isoformat()
        }


@dataclass
class Endpoint(CoreNode):
    """API Endpoint abstraction for cross-language connections"""
    method: str = ""  # GET, POST, PUT, DELETE, PATCH
    path: str = ""     # /api/v1/Lead
    controller: Optional[str] = None
    action: Optional[str] = None
    entity: Optional[str] = None  # Entity name if applicable
    
    def __post_init__(self):
        self.type = 'Endpoint'
        # Generate ID from method and path
        import hashlib
        self.id = hashlib.md5(f"{self.method}:{self.path}".encode()).hexdigest()
        
    def get_labels(self) -> List[str]:
        """Return list of Neo4j labels for this endpoint"""
        return ['Endpoint', 'API', self.method]


# Plugin extension examples
@dataclass
class PHPClass(Symbol):
    """PHP-specific class node"""
    namespace: str = ""
    is_abstract: bool = False
    is_final: bool = False
    is_interface: bool = False
    traits: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        super().__post_init__()
        self.kind = "class"
        self.metadata['language'] = 'php'
        

@dataclass
class JavaScriptModule(Module):
    """JavaScript-specific module node"""
    module_type: str = "es6"  # es6, commonjs, amd
    exports: List[str] = field(default_factory=list)
    imports: List[Dict[str, str]] = field(default_factory=list)
    
    def __post_init__(self):
        super().__post_init__()
        self.language = "javascript"
        self.metadata['module_type'] = self.module_type