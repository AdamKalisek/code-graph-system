# Universal Code Graph System Architecture

## Vision

A language-agnostic, framework-aware code analysis platform that can create knowledge graphs for any codebase through a plugin ecosystem.

## Core Architecture Principles

### 1. Plugin-Based Design
- **Language Plugins**: PHP, JavaScript, Python, Go, Rust, Java, etc.
- **Framework Plugins**: Laravel, Symfony, React, Vue, Django, Spring, etc.
- **System Plugins**: EspoCRM, WordPress, Drupal, Magento, etc.
- **Analysis Plugins**: Security, Performance, Quality, Documentation

### 2. Layered Architecture

```
┌─────────────────────────────────────────────┐
│           Application Layer (CLI/API)        │
├─────────────────────────────────────────────┤
│           Orchestration Engine               │
├─────────────────────────────────────────────┤
│           Plugin Manager                     │
├─────────────────────────────────────────────┤
│    Language    │  Framework  │   System     │
│    Plugins     │   Plugins   │   Plugins    │
├─────────────────────────────────────────────┤
│           Core Graph Engine                  │
├─────────────────────────────────────────────┤
│    Graph DB    │   Cache     │   Storage    │
│    (Neo4j)     │   (Redis)   │   (S3/FS)    │
└─────────────────────────────────────────────┘
```

## Core Components

### 1. Universal Graph Schema (UGS)

Base node types that all languages must implement:

```yaml
# Core Abstract Nodes
AbstractNode:
  id: UUID
  type: string
  name: string
  qualified_name: string
  source_location: SourceLocation
  metadata: Map<string, any>
  confidence: float
  plugin_id: string

AbstractFile:
  extends: AbstractNode
  path: string
  language: string
  hash: string
  size: integer
  last_modified: datetime

AbstractSymbol:
  extends: AbstractNode
  visibility: enum
  is_exported: boolean
  documentation: string

AbstractCallable:
  extends: AbstractSymbol
  parameters: List<Parameter>
  return_type: string
  is_async: boolean

AbstractType:
  extends: AbstractSymbol
  kind: enum  # class, interface, struct, enum, etc.
  generics: List<Generic>

# Core Relationships
AbstractRelationship:
  type: string
  source: UUID
  target: UUID
  confidence: float
  metadata: Map<string, any>
  plugin_id: string
```

### 2. Plugin Interface System

```python
# core/plugin_interface.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import ast

class PluginCapability(Enum):
    PARSE = "parse"
    ANALYZE = "analyze"
    TRANSFORM = "transform"
    QUERY = "query"
    VISUALIZE = "visualize"

class PluginMetadata:
    id: str
    name: str
    version: str
    author: str
    description: str
    capabilities: List[PluginCapability]
    dependencies: List[str]
    supported_languages: List[str]
    supported_frameworks: List[str]
    schema_extensions: Dict[str, Any]

class IPlugin(ABC):
    @abstractmethod
    def get_metadata(self) -> PluginMetadata:
        pass
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None:
        pass
    
    @abstractmethod
    def can_handle(self, file_path: str) -> bool:
        pass
    
    @abstractmethod
    def get_schema_extensions(self) -> Dict[str, Any]:
        """Return custom node/relationship types"""
        pass

class ILanguagePlugin(IPlugin):
    @abstractmethod
    def parse_file(self, file_path: str) -> 'ParseResult':
        pass
    
    @abstractmethod
    def extract_symbols(self, ast: Any) -> List['Symbol']:
        pass
    
    @abstractmethod
    def extract_dependencies(self, ast: Any) -> List['Dependency']:
        pass
    
    @abstractmethod
    def resolve_type(self, symbol: str, context: 'Context') -> Optional[str]:
        pass

class IFrameworkPlugin(IPlugin):
    @abstractmethod
    def enhance_graph(self, graph: 'Graph', language_plugin: ILanguagePlugin) -> None:
        """Add framework-specific relationships and nodes"""
        pass
    
    @abstractmethod
    def resolve_magic(self, node: 'AbstractNode') -> List['Resolution']:
        """Resolve framework magic (DI, decorators, etc.)"""
        pass
    
    @abstractmethod
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract framework-specific metadata"""
        pass

class ISystemPlugin(IPlugin):
    @abstractmethod
    def get_system_patterns(self) -> 'SystemPatterns':
        """Return system-specific patterns and conventions"""
        pass
    
    @abstractmethod
    def post_process_graph(self, graph: 'Graph') -> None:
        """Apply system-specific processing"""
        pass
```

### 3. Plugin Manager

```python
# core/plugin_manager.py
class PluginManager:
    def __init__(self):
        self.plugins: Dict[str, IPlugin] = {}
        self.language_plugins: Dict[str, ILanguagePlugin] = {}
        self.framework_plugins: Dict[str, IFrameworkPlugin] = {}
        self.system_plugins: Dict[str, ISystemPlugin] = {}
        self.plugin_registry = PluginRegistry()
    
    def discover_plugins(self, plugin_dirs: List[str]):
        """Auto-discover and load plugins"""
        for plugin_dir in plugin_dirs:
            for plugin_path in Path(plugin_dir).glob('*/plugin.yaml'):
                self.load_plugin(plugin_path)
    
    def load_plugin(self, plugin_path: str):
        """Dynamic plugin loading"""
        metadata = yaml.load(plugin_path)
        
        # Validate plugin
        if not self.validate_plugin(metadata):
            raise InvalidPluginError(f"Invalid plugin: {plugin_path}")
        
        # Load plugin module
        module = importlib.import_module(metadata['module'])
        plugin_class = getattr(module, metadata['class'])
        
        # Instantiate and register
        plugin = plugin_class()
        self.register_plugin(plugin)
    
    def get_handler_chain(self, file_path: str) -> List[IPlugin]:
        """Get all plugins that can handle this file"""
        handlers = []
        
        # Check language plugins
        for plugin in self.language_plugins.values():
            if plugin.can_handle(file_path):
                handlers.append(plugin)
        
        # Check framework plugins
        for plugin in self.framework_plugins.values():
            if plugin.can_handle(file_path):
                handlers.append(plugin)
        
        return handlers
```

### 4. Graph Engine

```python
# core/graph_engine.py
class UniversalGraphEngine:
    def __init__(self, neo4j_uri: str, plugin_manager: PluginManager):
        self.graph = Graph(neo4j_uri)
        self.plugin_manager = plugin_manager
        self.schema_manager = SchemaManager(self.graph)
        self.query_builder = QueryBuilder()
    
    def process_codebase(self, root_path: str):
        """Main processing pipeline"""
        # Phase 1: Discovery
        files = self.discover_files(root_path)
        
        # Phase 2: Parse with appropriate plugins
        parse_results = {}
        for file in files:
            handlers = self.plugin_manager.get_handler_chain(file)
            if handlers:
                parse_results[file] = self.parse_with_plugins(file, handlers)
        
        # Phase 3: Build initial graph
        graph_data = self.build_graph_data(parse_results)
        
        # Phase 4: Apply framework enhancements
        for framework_plugin in self.plugin_manager.framework_plugins.values():
            framework_plugin.enhance_graph(graph_data)
        
        # Phase 5: Apply system-specific processing
        for system_plugin in self.plugin_manager.system_plugins.values():
            system_plugin.post_process_graph(graph_data)
        
        # Phase 6: Load into Neo4j
        self.load_graph(graph_data)
    
    def merge_plugin_schemas(self):
        """Merge all plugin schemas into unified schema"""
        base_schema = self.load_base_schema()
        
        for plugin in self.plugin_manager.plugins.values():
            extensions = plugin.get_schema_extensions()
            base_schema = self.schema_manager.merge_schemas(base_schema, extensions)
        
        return base_schema
```

## Plugin Examples

### 1. PHP Language Plugin

```python
# plugins/language/php/plugin.py
class PHPLanguagePlugin(ILanguagePlugin):
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            id="php-language",
            name="PHP Language Support",
            version="1.0.0",
            capabilities=[PluginCapability.PARSE, PluginCapability.ANALYZE],
            supported_languages=["php"],
            schema_extensions={
                "nodes": {
                    "PHPClass": {
                        "extends": "AbstractType",
                        "properties": {
                            "namespace": "string",
                            "traits": "List<string>",
                            "is_abstract": "boolean",
                            "is_final": "boolean"
                        }
                    },
                    "PHPTrait": {
                        "extends": "AbstractType",
                        "properties": {
                            "namespace": "string"
                        }
                    }
                },
                "relationships": {
                    "USES_TRAIT": {
                        "from": "PHPClass",
                        "to": "PHPTrait"
                    }
                }
            }
        )
    
    def parse_file(self, file_path: str) -> ParseResult:
        # Use nikic/php-parser via subprocess
        result = subprocess.run(
            ['php', 'parser.php', file_path],
            capture_output=True,
            text=True
        )
        return self.process_ast(json.loads(result.stdout))
```

### 2. Laravel Framework Plugin

```python
# plugins/framework/laravel/plugin.py
class LaravelFrameworkPlugin(IFrameworkPlugin):
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            id="laravel-framework",
            name="Laravel Framework Support",
            version="1.0.0",
            supported_frameworks=["laravel"],
            dependencies=["php-language"],
            schema_extensions={
                "nodes": {
                    "LaravelController": {
                        "extends": "PHPClass",
                        "properties": {
                            "routes": "List<Route>",
                            "middleware": "List<string>"
                        }
                    },
                    "LaravelModel": {
                        "extends": "PHPClass",
                        "properties": {
                            "table": "string",
                            "fillable": "List<string>",
                            "relationships": "Map<string, Relationship>"
                        }
                    },
                    "LaravelService": {
                        "extends": "AbstractNode",
                        "properties": {
                            "binding": "string",
                            "singleton": "boolean"
                        }
                    }
                },
                "relationships": {
                    "REGISTERED_IN_CONTAINER": {
                        "from": "LaravelService",
                        "to": "PHPClass"
                    },
                    "HAS_ROUTE": {
                        "from": "LaravelController",
                        "to": "Route"
                    }
                }
            }
        )
    
    def enhance_graph(self, graph: Graph, language_plugin: ILanguagePlugin):
        # Add Laravel-specific enhancements
        self.resolve_service_container(graph)
        self.map_routes_to_controllers(graph)
        self.resolve_eloquent_relationships(graph)
        self.process_middleware(graph)
```

### 3. EspoCRM System Plugin

```python
# plugins/system/espocrm/plugin.py
class EspoCRMSystemPlugin(ISystemPlugin):
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            id="espocrm-system",
            name="EspoCRM System Support",
            version="1.0.0",
            dependencies=["php-language", "javascript-language"],
            schema_extensions={
                "nodes": {
                    "EspoEntity": {
                        "extends": "AbstractNode",
                        "properties": {
                            "fields": "Map<string, Field>",
                            "relationships": "Map<string, Relationship>",
                            "indexes": "List<Index>"
                        }
                    },
                    "EspoHook": {
                        "extends": "AbstractNode",
                        "properties": {
                            "entity": "string",
                            "type": "string",
                            "order": "integer"
                        }
                    },
                    "EspoMetadata": {
                        "extends": "AbstractNode",
                        "properties": {
                            "type": "string",
                            "scope": "string",
                            "data": "Map<string, any>"
                        }
                    }
                }
            }
        )
    
    def get_system_patterns(self) -> SystemPatterns:
        return SystemPatterns(
            hook_patterns=[
                "application/Espo/Hooks/{Entity}/{Name}.php",
                "custom/Espo/Custom/Hooks/{Entity}/{Name}.php"
            ],
            service_patterns=[
                "application/Espo/Services/{Name}.php",
                "application/Espo/Core/Services/{Name}.php"
            ],
            metadata_patterns=[
                "application/Espo/Resources/metadata/**/*.json",
                "custom/Espo/Custom/Resources/metadata/**/*.json"
            ]
        )
```

## Configuration System

```yaml
# config/code-graph.yaml
system:
  neo4j:
    uri: bolt://localhost:7688
    auth:
      username: neo4j
      password: ${NEO4J_PASSWORD}
  
  cache:
    type: redis
    uri: redis://localhost:6379
    ttl: 3600
  
  storage:
    type: filesystem
    path: ./storage

plugins:
  enabled:
    - php-language
    - javascript-language
    - python-language
    - laravel-framework
    - symfony-framework
    - espocrm-system
  
  directories:
    - ./plugins/builtin
    - ./plugins/community
    - ~/.code-graph/plugins

analysis:
  parallel_workers: 8
  batch_size: 1000
  incremental: true
  cache_ast: true

project:
  type: espocrm  # This determines which system plugin to prioritize
  root: ./espocrm
  exclude:
    - vendor/
    - node_modules/
    - .git/
    - cache/
```

## Query System

```python
# core/query_system.py
class UniversalQuerySystem:
    def __init__(self, graph_engine: UniversalGraphEngine):
        self.graph_engine = graph_engine
        self.query_plugins = {}
    
    def register_query_plugin(self, plugin: 'IQueryPlugin'):
        """Register plugin-specific queries"""
        self.query_plugins[plugin.get_id()] = plugin
    
    def execute_universal_query(self, query_type: str, params: Dict):
        """Execute cross-language queries"""
        
        if query_type == "impact_analysis":
            return self.impact_analysis(params['target'])
        
        elif query_type == "find_implementations":
            return self.find_implementations(params['interface'])
        
        elif query_type == "trace_data_flow":
            return self.trace_data_flow(params['source'], params['sink'])
        
        elif query_type == "detect_patterns":
            return self.detect_patterns(params['pattern'])
    
    def impact_analysis(self, target: str):
        """Universal impact analysis across all languages"""
        query = """
        MATCH (target:AbstractSymbol {qualified_name: $target})
        CALL apoc.path.subgraphNodes(target, {
            relationshipFilter: 'CALLS>|DEPENDS_ON>|EXTENDS>|IMPLEMENTS>|IMPORTS>',
            minLevel: 0,
            maxLevel: $depth
        }) YIELD node
        RETURN node, labels(node) as types
        """
        return self.graph_engine.run_query(query, target=target, depth=5)
```

## Implementation Roadmap

### Phase 1: Core Framework (Week 1-2)
1. Implement plugin interface system
2. Create plugin manager with dynamic loading
3. Build universal graph schema
4. Set up configuration system

### Phase 2: Base Plugins (Week 3-4)
1. PHP language plugin
2. JavaScript language plugin
3. Python language plugin
4. Base framework detection

### Phase 3: Framework Plugins (Week 5-6)
1. Laravel framework plugin
2. Symfony framework plugin
3. React framework plugin
4. Django framework plugin

### Phase 4: System Plugins (Week 7-8)
1. EspoCRM system plugin
2. WordPress system plugin
3. Drupal system plugin

### Phase 5: Advanced Features (Week 9-10)
1. Incremental updates
2. Plugin marketplace
3. Query builder UI
4. Visualization system

## Benefits of This Architecture

1. **Extensibility**: New languages/frameworks via plugins
2. **Reusability**: Core logic shared across all plugins
3. **Maintainability**: Clean separation of concerns
4. **Scalability**: Parallel processing, distributed analysis
5. **Community**: Open plugin ecosystem
6. **Future-proof**: Easy to add new technologies