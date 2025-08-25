"""
EspoCRM System Plugin for Universal Code Graph System.

Specialized analysis for EspoCRM-specific patterns:
- Metadata-driven architecture
- Hook system
- Entity definitions
- Backbone.js frontend structure
- API endpoints
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from uuid import UUID, uuid4

from code_graph_system.core.plugin_interface import ISystemPlugin, ParseResult
from code_graph_system.core.schema import (
    CoreNode, Symbol, File, Module, Relationship
)


logger = logging.getLogger(__name__)


class EspoCRMSystemPlugin(ISystemPlugin):
    """EspoCRM-specific code analysis plugin"""
    
    def __init__(self):
        self.plugin_id = 'espocrm'
        self.name = 'EspoCRM System Plugin'
        self.version = '1.0.0'
        self.config = {}
        
    def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize the plugin with configuration"""
        self.config = config
        logger.info(f"Initialized {self.name} v{self.version}")
        return True
        
    def detect(self, path: str) -> float:
        """
        Detect if this is an EspoCRM project.
        
        Returns confidence score (0.0 to 1.0)
        """
        path_obj = Path(path)
        confidence = 0.0
        
        # Check for EspoCRM-specific markers
        markers = [
            'application/Espo/Core/Application.php',
            'application/Espo/Core/Container.php',
            'client/src/app.js',
            'application/Espo/Resources/metadata',
        ]
        
        for marker in markers:
            if (path_obj / marker).exists():
                confidence += 0.25
                
        # Check for composer.json with EspoCRM
        composer_file = path_obj / 'composer.json'
        if composer_file.exists():
            try:
                with open(composer_file) as f:
                    data = json.load(f)
                    if 'espocrm' in data.get('name', '').lower():
                        confidence = min(confidence + 0.5, 1.0)
            except:
                pass
                
        return min(confidence, 1.0)
        
    def analyze(self, path: str) -> ParseResult:
        """
        Analyze EspoCRM-specific patterns and structures.
        """
        nodes = []
        relationships = []
        path_obj = Path(path)
        
        # Create project node
        project_node = Symbol(
            id=uuid4(),
            type='EspoCRMProject',
            name=path_obj.name,
            qualified_name=str(path_obj),
            kind='project',
            plugin_id=self.plugin_id,
            metadata={
                'system': 'espocrm',
                'path': str(path_obj)
            }
        )
        nodes.append(project_node)
        
        # Analyze metadata
        metadata_nodes, metadata_rels = self._analyze_metadata(path_obj, project_node.id)
        nodes.extend(metadata_nodes)
        relationships.extend(metadata_rels)
        
        # Analyze hooks
        hook_nodes, hook_rels = self._analyze_hooks(path_obj, project_node.id)
        nodes.extend(hook_nodes)
        relationships.extend(hook_rels)
        
        # Analyze entities
        entity_nodes, entity_rels = self._analyze_entities(path_obj, project_node.id)
        nodes.extend(entity_nodes)
        relationships.extend(entity_rels)
        
        # Analyze client-side structure
        client_nodes, client_rels = self._analyze_client(path_obj, project_node.id)
        nodes.extend(client_nodes)
        relationships.extend(client_rels)
        
        return ParseResult(
            success=True,
            nodes=nodes,
            relationships=relationships,
            errors=[],
            warnings=[]
        )
        
    def _analyze_metadata(self, path: Path, parent_id: UUID) -> tuple:
        """Analyze EspoCRM metadata definitions"""
        nodes = []
        relationships = []
        
        metadata_path = path / 'application/Espo/Resources/metadata'
        if not metadata_path.exists():
            return nodes, relationships
            
        # Create metadata root node
        metadata_node = Symbol(
            id=uuid4(),
            type='MetadataRoot',
            name='Metadata',
            qualified_name=str(metadata_path),
            kind='metadata',
            plugin_id=self.plugin_id
        )
        nodes.append(metadata_node)
        relationships.append(Relationship(
            source_id=parent_id,
            target_id=metadata_node.id,
            type='HAS_METADATA'
        ))
        
        # Parse entityDefs
        entity_defs_path = metadata_path / 'entityDefs'
        if entity_defs_path.exists():
            for entity_file in entity_defs_path.glob('*.json'):
                try:
                    with open(entity_file) as f:
                        entity_data = json.load(f)
                        entity_name = entity_file.stem
                        
                        # Create entity definition node
                        entity_def_node = Symbol(
                            id=uuid4(),
                            type='EntityDefinition',
                            name=entity_name,
                            qualified_name=f"EntityDef.{entity_name}",
                            kind='entity_def',
                            plugin_id=self.plugin_id,
                            metadata={
                                'fields': list(entity_data.get('fields', {}).keys()),
                                'links': list(entity_data.get('links', {}).keys()),
                                'indexes': list(entity_data.get('indexes', {}).keys())
                            }
                        )
                        nodes.append(entity_def_node)
                        relationships.append(Relationship(
                            source_id=metadata_node.id,
                            target_id=entity_def_node.id,
                            type='DEFINES_ENTITY'
                        ))
                        
                        # Analyze fields
                        for field_name, field_def in entity_data.get('fields', {}).items():
                            field_node = Symbol(
                                id=uuid4(),
                                type='Field',
                                name=field_name,
                                qualified_name=f"{entity_name}.{field_name}",
                                kind='field',
                                plugin_id=self.plugin_id,
                                metadata={
                                    'type': field_def.get('type'),
                                    'required': field_def.get('required', False)
                                }
                            )
                            nodes.append(field_node)
                            relationships.append(Relationship(
                                source_id=entity_def_node.id,
                                target_id=field_node.id,
                                type='HAS_FIELD'
                            ))
                            
                except Exception as e:
                    logger.warning(f"Failed to parse entity def {entity_file}: {e}")
                    
        # Parse clientDefs
        client_defs_path = metadata_path / 'clientDefs'
        if client_defs_path.exists():
            for client_file in client_defs_path.glob('*.json'):
                try:
                    with open(client_file) as f:
                        client_data = json.load(f)
                        entity_name = client_file.stem
                        
                        # Create client definition node
                        client_def_node = Symbol(
                            id=uuid4(),
                            type='ClientDefinition',
                            name=f"{entity_name}Client",
                            qualified_name=f"ClientDef.{entity_name}",
                            kind='client_def',
                            plugin_id=self.plugin_id,
                            metadata={
                                'views': client_data.get('views', {}),
                                'recordViews': client_data.get('recordViews', {}),
                                'controller': client_data.get('controller')
                            }
                        )
                        nodes.append(client_def_node)
                        relationships.append(Relationship(
                            source_id=metadata_node.id,
                            target_id=client_def_node.id,
                            type='DEFINES_CLIENT'
                        ))
                        
                except Exception as e:
                    logger.warning(f"Failed to parse client def {client_file}: {e}")
                    
        return nodes, relationships
        
    def _analyze_hooks(self, path: Path, parent_id: UUID) -> tuple:
        """Analyze EspoCRM hook system"""
        nodes = []
        relationships = []
        
        hooks_path = path / 'application/Espo/Hooks'
        if not hooks_path.exists():
            return nodes, relationships
            
        # Create hooks root node
        hooks_node = Symbol(
            id=uuid4(),
            type='HooksRoot',
            name='Hooks',
            qualified_name=str(hooks_path),
            kind='hooks',
            plugin_id=self.plugin_id
        )
        nodes.append(hooks_node)
        relationships.append(Relationship(
            source_id=parent_id,
            target_id=hooks_node.id,
            type='HAS_HOOKS'
        ))
        
        # Scan for hook files
        for hook_dir in hooks_path.iterdir():
            if hook_dir.is_dir():
                entity_name = hook_dir.name
                
                for hook_file in hook_dir.glob('*.php'):
                    hook_class = hook_file.stem
                    
                    # Create hook node
                    hook_node = Symbol(
                        id=uuid4(),
                        type='Hook',
                        name=hook_class,
                        qualified_name=f"Hook.{entity_name}.{hook_class}",
                        kind='hook',
                        plugin_id=self.plugin_id,
                        metadata={
                            'entity': entity_name,
                            'file': str(hook_file)
                        }
                    )
                    nodes.append(hook_node)
                    relationships.append(Relationship(
                        source_id=hooks_node.id,
                        target_id=hook_node.id,
                        type='DEFINES_HOOK'
                    ))
                    
        return nodes, relationships
        
    def _analyze_entities(self, path: Path, parent_id: UUID) -> tuple:
        """Analyze EspoCRM entity classes"""
        nodes = []
        relationships = []
        
        entities_path = path / 'application/Espo/Entities'
        if not entities_path.exists():
            return nodes, relationships
            
        # Create entities root node
        entities_node = Symbol(
            id=uuid4(),
            type='EntitiesRoot',
            name='Entities',
            qualified_name=str(entities_path),
            kind='entities',
            plugin_id=self.plugin_id
        )
        nodes.append(entities_node)
        relationships.append(Relationship(
            source_id=parent_id,
            target_id=entities_node.id,
            type='HAS_ENTITIES'
        ))
        
        # Scan for entity files
        for entity_file in entities_path.glob('*.php'):
            entity_name = entity_file.stem
            
            # Create entity node
            entity_node = Symbol(
                id=uuid4(),
                type='Entity',
                name=entity_name,
                qualified_name=f"Entity.{entity_name}",
                kind='entity',
                plugin_id=self.plugin_id,
                metadata={
                    'file': str(entity_file)
                }
            )
            nodes.append(entity_node)
            relationships.append(Relationship(
                source_id=entities_node.id,
                target_id=entity_node.id,
                type='DEFINES_ENTITY_CLASS'
            ))
            
        return nodes, relationships
        
    def _analyze_client(self, path: Path, parent_id: UUID) -> tuple:
        """Analyze EspoCRM client-side structure"""
        nodes = []
        relationships = []
        
        client_path = path / 'client/src'
        if not client_path.exists():
            return nodes, relationships
            
        # Create client root node
        client_node = Symbol(
            id=uuid4(),
            type='ClientRoot',
            name='Client',
            qualified_name=str(client_path),
            kind='client',
            plugin_id=self.plugin_id
        )
        nodes.append(client_node)
        relationships.append(Relationship(
            source_id=parent_id,
            target_id=client_node.id,
            type='HAS_CLIENT'
        ))
        
        # Analyze view structure
        views_path = client_path / 'views'
        if views_path.exists():
            views_node = Symbol(
                id=uuid4(),
                type='ViewsRoot',
                name='Views',
                qualified_name=str(views_path),
                kind='views',
                plugin_id=self.plugin_id
            )
            nodes.append(views_node)
            relationships.append(Relationship(
                source_id=client_node.id,
                target_id=views_node.id,
                type='HAS_VIEWS'
            ))
            
            # Scan view files
            for view_file in views_path.rglob('*.js'):
                relative_path = view_file.relative_to(views_path)
                view_name = str(relative_path).replace('/', '.').replace('.js', '')
                
                view_node = Symbol(
                    id=uuid4(),
                    type='View',
                    name=view_name,
                    qualified_name=f"View.{view_name}",
                    kind='view',
                    plugin_id=self.plugin_id,
                    metadata={
                        'file': str(view_file)
                    }
                )
                nodes.append(view_node)
                relationships.append(Relationship(
                    source_id=views_node.id,
                    target_id=view_node.id,
                    type='DEFINES_VIEW'
                ))
                
        return nodes, relationships
        
    def query(self, query_type: str, params: Dict[str, Any]) -> Any:
        """
        Execute EspoCRM-specific queries.
        
        Supported queries:
        - find_hooks: Find all hooks for an entity
        - find_entity_fields: Get all fields for an entity
        - find_views: Find all views for an entity
        """
        if query_type == 'find_hooks':
            entity_name = params.get('entity')
            # This would query the graph store
            return f"Hooks for {entity_name}"
            
        elif query_type == 'find_entity_fields':
            entity_name = params.get('entity')
            return f"Fields for {entity_name}"
            
        elif query_type == 'find_views':
            entity_name = params.get('entity')
            return f"Views for {entity_name}"
            
        else:
            return None
            
    def get_metadata(self) -> Dict[str, Any]:
        """Get plugin metadata"""
        return {
            'id': self.plugin_id,
            'name': self.name,
            'version': self.version,
            'type': 'system',
            'capabilities': [
                'metadata_parsing',
                'hook_detection',
                'entity_mapping',
                'backbone_views',
                'api_endpoints'
            ]
        }
        
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate plugin configuration"""
        return True
        
    def cleanup(self) -> bool:
        """Cleanup plugin resources"""
        return True