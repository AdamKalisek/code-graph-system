#!/usr/bin/env python3
"""
Enhanced Tree-sitter JavaScript Parser
Comprehensive AST-based parsing with relationship extraction
"""

import tree_sitter
from tree_sitter import Language, Parser, Node, Query
import tree_sitter_javascript as tsjs
from pathlib import Path
import hashlib
import json
import re
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from code_graph_system.core.schema import Symbol, Relationship, SourceLocation
from code_graph_system.core.plugin_interface import ParseResult

@dataclass
class ExtractedEntity:
    """Represents an extracted code entity"""
    type: str  # class, function, method, property, etc.
    name: str
    qualified_name: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    location: SourceLocation = None
    id: str = None
    
    def __post_init__(self):
        if not self.id:
            self.id = hashlib.md5(self.qualified_name.encode()).hexdigest()

@dataclass
class ExtractedRelationship:
    """Represents a relationship between entities"""
    type: str  # CALLS, IMPORTS, EXTENDS, etc.
    source_id: str
    target_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class EnhancedJavaScriptParser:
    """Enhanced Tree-sitter based JavaScript parser with full relationship extraction"""
    
    def __init__(self):
        # Initialize parser with JavaScript language
        self.parser = Parser(Language(tsjs.language()))
        
        # Load queries
        self._load_queries()
        
        # Track current parsing context
        self.current_file = None
        self.current_module = None
        self.extracted_entities = {}  # id -> entity
        self.extracted_relationships = []
        
    def _load_queries(self):
        """Load tree-sitter queries for pattern matching"""
        self.queries = {}
        
        # ES6 Classes and inheritance
        self.queries['es6_class'] = """
        (class_declaration
          name: (identifier) @class_name
          superclass: (identifier)? @parent_class
          body: (class_body) @class_body
        ) @class
        """
        
        # Class methods and properties
        self.queries['class_members'] = """
        (class_body
          [(method_definition
            key: (property_identifier) @method_name
            parameters: (formal_parameters) @params
          ) @method]
        )
        
        (class_body
          [(public_field_definition
            name: (property_identifier) @field_name
            value: (_)? @field_value
          ) @field]
        )
        """
        
        # Functions (all types)
        self.queries['functions'] = """
        [
          (function_declaration
            name: (identifier) @func_name
            parameters: (formal_parameters) @params
            body: (statement_block) @body
          ) @function
          
          (variable_declarator
            name: (identifier) @func_name
            value: (arrow_function
              parameters: (_) @params
              body: (_) @body
            )
          ) @arrow_function
          
          (assignment_expression
            left: (identifier) @func_name
            right: (function_expression
              parameters: (formal_parameters) @params
              body: (statement_block) @body
            )
          ) @function_expr
        ]
        """
        
        # AMD define/require patterns
        self.queries['amd_module'] = """
        (call_expression
          function: (identifier) @amd_func (#match? @amd_func "^(define|require)$")
          arguments: (arguments
            [(array (string) @dependency)*]?
            (function_expression
              parameters: (formal_parameters (identifier) @param)*
              body: (statement_block) @module_body
            )? @factory
          )
        ) @amd_call
        """
        
        # CommonJS patterns
        self.queries['commonjs'] = """
        (call_expression
          function: (identifier) @require (#eq? @require "require")
          arguments: (arguments (string) @module_path)
        ) @require_call
        
        (assignment_expression
          left: (member_expression
            object: (identifier) @module (#eq? @module "module")
            property: (property_identifier) @exports (#eq? @exports "exports")
          )
          right: (_) @exported_value
        ) @module_export
        
        (assignment_expression
          left: (member_expression
            object: (identifier) @exports (#eq? @exports "exports")
            property: (property_identifier) @export_name
          )
          right: (_) @exported_value
        ) @named_export
        """
        
        # ES6 imports/exports
        self.queries['es6_modules'] = """
        (import_statement
          (import_clause
            [(named_imports (import_specifier name: (identifier) @import_name))*]?
            [(namespace_import (identifier) @namespace_name)]?
            [(identifier) @default_import]?
          )?
          source: (string) @module_source
        ) @import
        
        (export_statement
          (export_clause
            (export_specifier name: (identifier) @export_name)*
          )
        ) @named_export
        
        (export_statement
          declaration: [
            (class_declaration name: (identifier) @export_name)
            (function_declaration name: (identifier) @export_name)
            (variable_declaration (variable_declarator name: (identifier) @export_name))
          ]
        ) @export_declaration
        """
        
        # Backbone.js patterns
        self.queries['backbone'] = """
        (call_expression
          function: (member_expression
            object: (member_expression
              object: (identifier) @backbone (#eq? @backbone "Backbone")
              property: (property_identifier) @component_type
            )
            property: (property_identifier) @extend (#eq? @extend "extend")
          )
          arguments: (arguments (object) @component_config)
        ) @backbone_component
        
        (call_expression
          function: (member_expression
            object: (identifier) @view_or_model
            property: (property_identifier) @extend (#eq? @extend "extend")
          )
          arguments: (arguments (object) @component_config)
        ) @possible_backbone
        """
        
        # API calls
        self.queries['api_calls'] = """
        (call_expression
          function: (member_expression
            object: (member_expression
              object: (identifier) @espo (#eq? @espo "Espo")
              property: (property_identifier) @ajax (#eq? @ajax "Ajax")
            )
            property: (property_identifier) @http_method
          )
          arguments: (arguments 
            (string) @endpoint
            (_)? @data
          )
        ) @espo_ajax
        
        (call_expression
          function: (identifier) @fetch (#eq? @fetch "fetch")
          arguments: (arguments 
            (string) @url
            (object)? @options
          )
        ) @fetch_call
        
        (call_expression
          function: (member_expression
            object: (identifier) @jquery (#match? @jquery "^(\\$|jQuery)$")
            property: (property_identifier) @ajax (#eq? @ajax "ajax")
          )
          arguments: (arguments 
            (object) @ajax_config
          )
        ) @jquery_ajax
        """
        
        # Function/method calls
        self.queries['calls'] = """
        (call_expression
          function: [
            (identifier) @called_func
            (member_expression
              object: (_) @object
              property: (property_identifier) @called_method
            )
          ]
          arguments: (arguments) @args
        ) @call
        """
        
        # Object instantiation
        self.queries['instantiations'] = """
        (new_expression
          constructor: [
            (identifier) @class_name
            (member_expression
              object: (_) @namespace
              property: (property_identifier) @class_name
            )
          ]
          arguments: (arguments)? @args
        ) @instantiation
        """
        
        # Model/Collection operations (Backbone specific)
        self.queries['model_operations'] = """
        (call_expression
          function: (member_expression
            object: (identifier) @model_var
            property: (property_identifier) @operation (#match? @operation "^(fetch|save|destroy|sync|set|get)$")
          )
          arguments: (arguments)? @args
        ) @model_operation
        
        (call_expression
          function: (member_expression
            object: (identifier) @collection_var
            property: (property_identifier) @operation (#match? @operation "^(fetch|create|sync|add|remove|reset)$")
          )
          arguments: (arguments)? @args
        ) @collection_operation
        """
        
    def parse_file(self, file_path: str) -> ParseResult:
        """Parse a JavaScript file and extract all entities and relationships"""
        self.current_file = file_path
        self.extracted_entities = {}
        self.extracted_relationships = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
        except Exception as e:
            return ParseResult(
                file_path=file_path,
                nodes=[],
                relationships=[],
                errors=[f"Failed to read file: {e}"]
            )
        
        # Parse with tree-sitter
        tree = self.parser.parse(bytes(source_code, 'utf8'))
        
        # Create file node
        file_entity = self._create_file_entity(file_path)
        self.extracted_entities[file_entity.id] = file_entity
        
        # Extract all patterns
        self._extract_classes(tree, source_code)
        self._extract_functions(tree, source_code)
        self._extract_imports(tree, source_code)
        self._extract_amd_modules(tree, source_code)
        self._extract_backbone_components(tree, source_code)
        self._extract_api_calls(tree, source_code)
        self._extract_calls(tree, source_code)
        self._extract_instantiations(tree, source_code)
        
        # Convert to Symbol and Relationship objects
        nodes = self._entities_to_symbols()
        relationships = self._relationships_to_schema()
        
        return ParseResult(
            file_path=file_path,
            nodes=nodes,
            relationships=relationships,
            errors=[]
        )
    
    def _create_file_entity(self, file_path: str) -> ExtractedEntity:
        """Create entity for the file itself"""
        return ExtractedEntity(
            type='file',
            name=Path(file_path).name,
            qualified_name=file_path,
            metadata={
                '_language': 'javascript',
                'extension': Path(file_path).suffix
            }
        )
    
    def _extract_classes(self, tree: tree_sitter.Tree, source: str):
        """Extract ES6 classes"""
        query = self.parser.language.query(self.queries['es6_class'])
        matches = query.matches(tree.root_node)
        
        for match_id, captures_dict in matches:
            class_node = None
            class_name = None
            parent_class = None
            class_body = None
            
            for capture_name, nodes in captures_dict.items():
                for node in nodes:
                    if capture_name == 'class':
                        class_node = node
                    elif capture_name == 'class_name':
                        class_name = node.text.decode()
                    elif capture_name == 'parent_class':
                        parent_class = node.text.decode()
                    elif capture_name == 'class_body':
                        class_body = node
            
            if class_name:
                class_entity = ExtractedEntity(
                    type='class',
                    name=class_name,
                    qualified_name=f"{self.current_file}:{class_name}",
                    location=self._get_location(class_node) if class_node else None
                )
                
                if parent_class:
                    class_entity.metadata['extends'] = parent_class
                    parent_id = self._get_or_create_unresolved(parent_class, 'class')
                    self._add_relationship('EXTENDS', class_entity.id, parent_id)
                
                self.extracted_entities[class_entity.id] = class_entity
                self._add_relationship('DEFINED_IN', class_entity.id,
                                     self.extracted_entities[list(self.extracted_entities.keys())[0]].id)
                
                if class_body:
                    self._extract_class_members(class_body, source, class_entity)
    
    def _extract_class_members(self, class_body_node: Node, source: str, class_entity: ExtractedEntity):
        """Extract methods and properties from a class body"""
        query = self.parser.language.query(self.queries['class_members'])
        matches = query.matches(class_body_node)
        
        for match_id, captures_dict in matches:
            for capture_name, nodes in captures_dict.items():
                for node in nodes:
                    if capture_name == 'method_name':
                        method_name = node.text.decode()
                        method_entity = ExtractedEntity(
                            type='method',
                            name=method_name,
                            qualified_name=f"{class_entity.qualified_name}.{method_name}",
                            metadata={'class': class_entity.name},
                            location=self._get_location(node)
                        )
                        self.extracted_entities[method_entity.id] = method_entity
                        self._add_relationship('HAS_METHOD', class_entity.id, method_entity.id)
                        
                    elif capture_name == 'field_name':
                        field_name = node.text.decode()
                        field_entity = ExtractedEntity(
                            type='property',
                            name=field_name,
                            qualified_name=f"{class_entity.qualified_name}.{field_name}",
                            metadata={'class': class_entity.name},
                            location=self._get_location(node)
                        )
                        self.extracted_entities[field_entity.id] = field_entity
                        self._add_relationship('HAS_PROPERTY', class_entity.id, field_entity.id)
    
    def _extract_functions(self, tree: tree_sitter.Tree, source: str):
        """Extract all function types"""
        query = self.parser.language.query(self.queries['functions'])
        captures = query.captures(tree.root_node)
        
        for node, capture_name in captures:
            if capture_name == 'func_name':
                func_name = node.text.decode()
                func_entity = ExtractedEntity(
                    type='function',
                    name=func_name,
                    qualified_name=f"{self.current_file}:{func_name}",
                    location=self._get_location(node)
                )
                
                # Check if it's an arrow function or async
                parent = node.parent
                if parent and 'arrow' in parent.type:
                    func_entity.metadata['arrow'] = True
                if parent and 'async' in source[parent.start_byte:parent.end_byte]:
                    func_entity.metadata['async'] = True
                    
                self.extracted_entities[func_entity.id] = func_entity
                self._add_relationship('DEFINED_IN', func_entity.id,
                                     self.extracted_entities[list(self.extracted_entities.keys())[0]].id)
    
    def _extract_imports(self, tree: tree_sitter.Tree, source: str):
        """Extract ES6 and CommonJS imports"""
        # ES6 imports
        es6_query = self.parser.language.query(self.queries['es6_modules'])
        captures = es6_query.captures(tree.root_node)
        
        for node, capture_name in captures:
            if capture_name == 'module_source':
                module_path = node.text.decode().strip('"\'')
                import_entity = ExtractedEntity(
                    type='import',
                    name=module_path,
                    qualified_name=f"{self.current_file}:import:{module_path}",
                    metadata={'module_type': 'es6'},
                    location=self._get_location(node)
                )
                self.extracted_entities[import_entity.id] = import_entity
                self._add_relationship('IMPORTS',
                                     self.extracted_entities[list(self.extracted_entities.keys())[0]].id,
                                     import_entity.id)
        
        # CommonJS requires
        cjs_query = self.parser.language.query(self.queries['commonjs'])
        captures = cjs_query.captures(tree.root_node)
        
        for node, capture_name in captures:
            if capture_name == 'module_path':
                module_path = node.text.decode().strip('"\'')
                import_entity = ExtractedEntity(
                    type='import',
                    name=module_path,
                    qualified_name=f"{self.current_file}:require:{module_path}",
                    metadata={'module_type': 'commonjs'},
                    location=self._get_location(node)
                )
                self.extracted_entities[import_entity.id] = import_entity
                self._add_relationship('IMPORTS',
                                     self.extracted_entities[list(self.extracted_entities.keys())[0]].id,
                                     import_entity.id)
    
    def _extract_amd_modules(self, tree: tree_sitter.Tree, source: str):
        """Extract AMD define/require patterns"""
        query = self.parser.language.query(self.queries['amd_module'])
        captures = query.captures(tree.root_node)
        
        current_module = None
        dependencies = []
        
        for node, capture_name in captures:
            if capture_name == 'amd_func':
                # Start new AMD module
                if current_module:
                    current_module.metadata['dependencies'] = dependencies
                    self.extracted_entities[current_module.id] = current_module
                    # Create import relationships for dependencies
                    for dep in dependencies:
                        dep_entity = ExtractedEntity(
                            type='import',
                            name=dep,
                            qualified_name=f"{self.current_file}:amd:{dep}",
                            metadata={'module_type': 'amd'}
                        )
                        self.extracted_entities[dep_entity.id] = dep_entity
                        self._add_relationship('IMPORTS', current_module.id, dep_entity.id)
                
                func_type = node.text.decode()
                current_module = ExtractedEntity(
                    type='amd_module',
                    name=f"{func_type}_module",
                    qualified_name=f"{self.current_file}:amd_module",
                    metadata={'type': func_type},
                    location=self._get_location(node)
                )
                dependencies = []
                
            elif capture_name == 'dependency' and current_module:
                dep_path = node.text.decode().strip('"\'')
                dependencies.append(dep_path)
        
        # Don't forget the last module
        if current_module:
            current_module.metadata['dependencies'] = dependencies
            self.extracted_entities[current_module.id] = current_module
            for dep in dependencies:
                dep_entity = ExtractedEntity(
                    type='import',
                    name=dep,
                    qualified_name=f"{self.current_file}:amd:{dep}",
                    metadata={'module_type': 'amd'}
                )
                self.extracted_entities[dep_entity.id] = dep_entity
                self._add_relationship('IMPORTS', current_module.id, dep_entity.id)
    
    def _extract_backbone_components(self, tree: tree_sitter.Tree, source: str):
        """Extract Backbone.js components"""
        query = self.parser.language.query(self.queries['backbone'])
        captures = query.captures(tree.root_node)
        
        for node, capture_name in captures:
            if capture_name == 'component_type':
                comp_type = node.text.decode()
                comp_entity = ExtractedEntity(
                    type=f'backbone_{comp_type.lower()}',
                    name=f"{comp_type}Component",
                    qualified_name=f"{self.current_file}:backbone:{comp_type}",
                    metadata={'backbone_type': comp_type},
                    location=self._get_location(node)
                )
                self.extracted_entities[comp_entity.id] = comp_entity
                self._add_relationship('DEFINED_IN', comp_entity.id,
                                     self.extracted_entities[list(self.extracted_entities.keys())[0]].id)
    
    def _extract_api_calls(self, tree: tree_sitter.Tree, source: str):
        """Extract API calls and create endpoint nodes"""
        query = self.parser.language.query(self.queries['api_calls'])
        captures = query.captures(tree.root_node)
        
        for node, capture_name in captures:
            if capture_name == 'endpoint':
                # Espo.Ajax call
                endpoint = node.text.decode().strip('"\'')
                # Get HTTP method from previous capture
                method_node = node.parent.parent.children[-1]
                if method_node.type == 'property_identifier':
                    http_method = method_node.text.decode().upper().replace('REQUEST', '')
                else:
                    http_method = 'GET'
                    
                endpoint_entity = ExtractedEntity(
                    type='endpoint',
                    name=f"{http_method}:{endpoint}",
                    qualified_name=f"endpoint:{http_method}:{endpoint}",
                    metadata={'method': http_method, 'url': endpoint},
                    location=self._get_location(node)
                )
                self.extracted_entities[endpoint_entity.id] = endpoint_entity
                self._add_relationship('CALLS_API',
                                     self.extracted_entities[list(self.extracted_entities.keys())[0]].id,
                                     endpoint_entity.id)
                
            elif capture_name == 'url':
                # fetch call
                url = node.text.decode().strip('"\'')
                endpoint_entity = ExtractedEntity(
                    type='endpoint',
                    name=f"GET:{url}",
                    qualified_name=f"endpoint:GET:{url}",
                    metadata={'method': 'GET', 'url': url},
                    location=self._get_location(node)
                )
                self.extracted_entities[endpoint_entity.id] = endpoint_entity
                self._add_relationship('CALLS_API',
                                     self.extracted_entities[list(self.extracted_entities.keys())[0]].id,
                                     endpoint_entity.id)
    
    def _extract_calls(self, tree: tree_sitter.Tree, source: str):
        """Extract function/method calls"""
        query = self.parser.language.query(self.queries['calls'])
        captures = query.captures(tree.root_node)
        
        for node, capture_name in captures:
            if capture_name in ['called_func', 'called_method']:
                called_name = node.text.decode()
                # Create unresolved reference if not found
                target_id = self._get_or_create_unresolved(called_name, 'function')
                # Find the containing function/method
                source_id = self._find_containing_function(node)
                if source_id:
                    self._add_relationship('CALLS', source_id, target_id)
    
    def _extract_instantiations(self, tree: tree_sitter.Tree, source: str):
        """Extract object instantiations"""
        query = self.parser.language.query(self.queries['instantiations'])
        captures = query.captures(tree.root_node)
        
        for node, capture_name in captures:
            if capture_name == 'class_name':
                class_name = node.text.decode()
                target_id = self._get_or_create_unresolved(class_name, 'class')
                source_id = self._find_containing_function(node)
                if source_id:
                    self._add_relationship('INSTANTIATES', source_id, target_id)
    
    def _find_containing_function(self, node: Node) -> Optional[str]:
        """Find the function/method containing this node"""
        current = node.parent
        while current:
            if current.type in ['function_declaration', 'method_definition', 'arrow_function']:
                # Try to find the function's name
                for child in current.children:
                    if child.type == 'identifier':
                        func_name = child.text.decode()
                        # Look for this function in our entities
                        for entity_id, entity in self.extracted_entities.items():
                            if entity.type in ['function', 'method'] and entity.name == func_name:
                                return entity_id
                break
            current = current.parent
        # Default to file if no containing function
        return list(self.extracted_entities.keys())[0] if self.extracted_entities else None
    
    def _get_or_create_unresolved(self, name: str, entity_type: str) -> str:
        """Get existing entity or create unresolved reference"""
        # Check if entity exists
        for entity_id, entity in self.extracted_entities.items():
            if entity.name == name and entity.type == entity_type:
                return entity_id
        
        # Create unresolved reference
        unresolved = ExtractedEntity(
            type='unresolved',
            name=name,
            qualified_name=f"unresolved:{entity_type}:{name}",
            metadata={'expected_type': entity_type}
        )
        self.extracted_entities[unresolved.id] = unresolved
        return unresolved.id
    
    def _add_relationship(self, rel_type: str, source_id: str, target_id: str, metadata: Dict = None):
        """Add a relationship"""
        rel = ExtractedRelationship(
            type=rel_type,
            source_id=source_id,
            target_id=target_id,
            metadata=metadata or {}
        )
        self.extracted_relationships.append(rel)
    
    def _get_location(self, node: Node) -> SourceLocation:
        """Get source location from node"""
        return SourceLocation(
            file_path=self.current_file,
            start_line=node.start_point[0] + 1,
            start_column=node.start_point[1],
            end_line=node.end_point[0] + 1,
            end_column=node.end_point[1]
        )
    
    def _entities_to_symbols(self) -> List[Symbol]:
        """Convert extracted entities to Symbol objects"""
        symbols = []
        for entity in self.extracted_entities.values():
            symbol = Symbol(
                name=entity.name,
                qualified_name=entity.qualified_name,
                kind=entity.type,
                plugin_id='javascript'
            )
            symbol.id = entity.id
            symbol.metadata = entity.metadata
            symbol.metadata['_language'] = 'javascript'
            symbol.location = entity.location
            symbols.append(symbol)
        return symbols
    
    def _relationships_to_schema(self) -> List[Relationship]:
        """Convert extracted relationships to Relationship objects"""
        relationships = []
        for rel in self.extracted_relationships:
            relationship = Relationship(
                type=rel.type,
                source_id=rel.source_id,
                target_id=rel.target_id,
                metadata=rel.metadata
            )
            relationships.append(relationship)
        return relationships


# Export as main parser
JavaScriptParser = EnhancedJavaScriptParser