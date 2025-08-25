"""
Plugin interface definitions for the Universal Code Graph System.

All plugins must implement these interfaces to integrate with the system.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Iterator, Optional, Set
from enum import Enum
from dataclasses import dataclass
from pathlib import Path

from .schema import CoreNode, Relationship, Symbol


class PluginCapability(Enum):
    """Plugin capabilities"""
    PARSE = "parse"
    ANALYZE = "analyze"
    TRANSFORM = "transform"
    QUERY = "query"
    VISUALIZE = "visualize"
    

class PluginType(Enum):
    """Types of plugins"""
    LANGUAGE = "language"
    FRAMEWORK = "framework"
    SYSTEM = "system"
    ANALYSIS = "analysis"
    

@dataclass
class PluginMetadata:
    """Plugin metadata"""
    id: str
    name: str
    version: str
    author: str = ""
    description: str = ""
    type: PluginType = PluginType.LANGUAGE
    capabilities: List[PluginCapability] = None
    dependencies: List[str] = None
    supported_languages: List[str] = None
    supported_frameworks: List[str] = None
    supported_extensions: List[str] = None
    namespace: str = ""
    
    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []
        if self.dependencies is None:
            self.dependencies = []
        if self.supported_languages is None:
            self.supported_languages = []
        if self.supported_frameworks is None:
            self.supported_frameworks = []
        if self.supported_extensions is None:
            self.supported_extensions = []
            

@dataclass
class ParseResult:
    """Result of parsing a file"""
    file_path: str
    nodes: List[CoreNode]
    relationships: List[Relationship]
    errors: List[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
            

class IPlugin(ABC):
    """Base plugin interface"""
    
    @abstractmethod
    def get_metadata(self) -> PluginMetadata:
        """Return plugin metadata"""
        pass
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize plugin with configuration"""
        pass
    
    @abstractmethod
    def can_handle(self, file_path: str) -> bool:
        """Check if plugin can handle this file"""
        pass
    
    @abstractmethod
    def get_namespace(self) -> str:
        """Return plugin namespace for schema extensions"""
        pass
    
    @abstractmethod
    def get_schema_extensions(self) -> Dict[str, Any]:
        """Return custom node and relationship types"""
        pass
    
    def validate(self) -> bool:
        """Validate plugin configuration and dependencies"""
        return True
    
    def cleanup(self) -> None:
        """Cleanup resources"""
        pass
        

class ILanguagePlugin(IPlugin):
    """Language-specific parsing plugin interface"""
    
    @abstractmethod
    def parse_file(self, file_path: str) -> ParseResult:
        """Parse a single file and return results"""
        pass
    
    @abstractmethod
    def stream_parse(self, file_path: str) -> Iterator[ParseResult]:
        """Stream parse results for large files"""
        pass
    
    @abstractmethod
    def extract_symbols(self, content: str) -> List[Symbol]:
        """Extract symbols from code content"""
        pass
    
    @abstractmethod
    def extract_dependencies(self, content: str) -> List[str]:
        """Extract dependencies from code"""
        pass
    
    @abstractmethod
    def resolve_imports(self, content: str) -> List[Dict[str, str]]:
        """Resolve import statements"""
        pass
    
    @abstractmethod
    def resolve_type(self, symbol: str, context: Dict[str, Any]) -> Optional[str]:
        """Resolve type of a symbol in given context"""
        pass
    
    def get_language_features(self) -> Dict[str, bool]:
        """Return supported language features"""
        return {
            'classes': False,
            'interfaces': False,
            'traits': False,
            'generics': False,
            'async': False,
            'modules': False,
            'namespaces': False
        }
        

class IFrameworkPlugin(IPlugin):
    """Framework-specific enhancement plugin interface"""
    
    @abstractmethod
    def enhance_graph(self, nodes: List[CoreNode], relationships: List[Relationship]) -> tuple:
        """Add framework-specific enhancements to the graph"""
        pass
    
    @abstractmethod
    def resolve_magic(self, node: CoreNode, context: Dict[str, Any]) -> List[CoreNode]:
        """Resolve framework magic (DI, decorators, annotations, etc.)"""
        pass
    
    @abstractmethod
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract framework-specific metadata from configuration files"""
        pass
    
    @abstractmethod
    def detect_framework(self, project_root: str) -> bool:
        """Detect if this framework is used in the project"""
        pass
    
    def get_framework_patterns(self) -> Dict[str, str]:
        """Return framework-specific file patterns"""
        return {}
        

class ISystemPlugin(IPlugin):
    """System-specific plugin interface (e.g., EspoCRM, WordPress)"""
    
    @abstractmethod
    def get_system_patterns(self) -> Dict[str, List[str]]:
        """Return system-specific patterns and conventions"""
        pass
    
    @abstractmethod
    def post_process_graph(self, nodes: List[CoreNode], relationships: List[Relationship]) -> tuple:
        """Apply system-specific post-processing to the graph"""
        pass
    
    @abstractmethod
    def extract_system_metadata(self, project_root: str) -> Dict[str, Any]:
        """Extract system-specific metadata"""
        pass
    
    @abstractmethod
    def validate_system_structure(self, project_root: str) -> List[str]:
        """Validate system structure and return issues"""
        pass
    
    def get_system_components(self) -> Dict[str, str]:
        """Return system component paths"""
        return {}
        

class IAnalysisPlugin(IPlugin):
    """Analysis plugin interface for specialized analysis"""
    
    @abstractmethod
    def analyze(self, nodes: List[CoreNode], relationships: List[Relationship]) -> Dict[str, Any]:
        """Perform analysis on the graph"""
        pass
    
    @abstractmethod
    def get_metrics(self, nodes: List[CoreNode], relationships: List[Relationship]) -> Dict[str, float]:
        """Calculate metrics from the graph"""
        pass
    
    @abstractmethod
    def detect_patterns(self, nodes: List[CoreNode], relationships: List[Relationship]) -> List[Dict[str, Any]]:
        """Detect patterns in the code"""
        pass
    
    @abstractmethod
    def find_issues(self, nodes: List[CoreNode], relationships: List[Relationship]) -> List[Dict[str, Any]]:
        """Find potential issues in the code"""
        pass
    
    def get_analysis_types(self) -> List[str]:
        """Return supported analysis types"""
        return []