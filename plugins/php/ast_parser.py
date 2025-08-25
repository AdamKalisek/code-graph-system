#!/usr/bin/env python3
"""
PHP AST Parser using phply
Properly parses PHP files into Abstract Syntax Trees
"""

import phply
from phply import phplex
from phply.phpparse import make_parser
from typing import List, Dict, Any, Optional, Set
from pathlib import Path
import uuid
import hashlib
from datetime import datetime

from code_graph_system.core.schema import (
    CoreNode, Symbol, Relationship, SourceLocation, Visibility
)
from code_graph_system.core.plugin_interface import ParseResult


class PHPASTParser:
    """Proper PHP parser using AST instead of token scanning"""
    
    def __init__(self):
        self.lexer = phplex.PhpLexer()
        self.parser = make_parser()
        
    def parse_file(self, file_path: str) -> ParseResult:
        """Parse a PHP file into nodes and relationships"""
        nodes = []
        relationships = []
        errors = []
        
        try:
            # Read file content
            path = Path(file_path)
            content = path.read_text(encoding='utf-8', errors='ignore')
            
            # Generate file ID
            file_id = self._generate_id(str(path))
            
            # Create File node as Symbol
            file_node = Symbol(
                name=path.name,
                qualified_name=str(path),
                kind='file',
                plugin_id='php'
            )
            file_node.id = file_id
            file_node.metadata = {
                'extension': path.suffix,
                'size': len(content),
                'lines': len(content.split('\n'))
            }
            file_node.location = SourceLocation(
                file=str(path),
                start_line=1,
                start_column=1,
                end_line=len(content.split('\n')),
                end_column=1
            )
            nodes.append(file_node)
            
            # Parse PHP content
            try:
                # Tokenize
                tokens = self.lexer.input(content, lineno=1)
                
                # Parse into AST
                ast = self.parser.parse(content, lexer=self.lexer)
                
                if ast:
                    # Process AST nodes
                    self._process_ast(ast, nodes, relationships, file_node, str(path))
                    
            except Exception as parse_error:
                errors.append(f"Parse error in {path}: {str(parse_error)}")
                # Continue with partial parsing if possible
                
        except Exception as e:
            errors.append(f"Error reading file {file_path}: {str(e)}")
            
        return ParseResult(
            nodes=nodes,
            relationships=relationships,
            errors=errors,
            success=len(errors) == 0
        )
    
    def _process_ast(self, ast, nodes: List[Node], relationships: List[Relationship], 
                     file_node: Node, file_path: str):
        """Process AST nodes recursively"""
        
        if isinstance(ast, list):
            for node in ast:
                self._process_ast_node(node, nodes, relationships, file_node, file_path)
        else:
            self._process_ast_node(ast, nodes, relationships, file_node, file_path)
    
    def _process_ast_node(self, node, nodes: List[Node], relationships: List[Relationship],
                          file_node: Node, file_path: str, parent_node: Optional[Node] = None):
        """Process a single AST node"""
        
        if node is None:
            return None
            
        node_type = type(node).__name__
        
        # Handle namespaces
        if node_type == 'Namespace':
            namespace_id = self._generate_id(f"{file_path}:namespace:{node.name}")
            namespace_node = Node(
                id=namespace_id,
                name=node.name or 'global',
                kind='namespace',
                qualified_name=node.name or 'global',
                location=self._get_location(node, file_path),
                metadata=Metadata(
                    language='php',
                    created_at=datetime.utcnow(),
                    properties={}
                )
            )
            nodes.append(namespace_node)
            
            # Link to file
            relationships.append(Relationship(
                source_id=file_node.id,
                target_id=namespace_id,
                kind='DEFINES_NAMESPACE'
            ))
            
            # Process namespace contents
            if hasattr(node, 'nodes') and node.nodes:
                for child in node.nodes:
                    self._process_ast_node(child, nodes, relationships, file_node, 
                                         file_path, namespace_node)
                                         
        # Handle classes
        elif node_type == 'Class':
            class_name = node.name
            namespace = parent_node.name if parent_node and parent_node.kind == 'namespace' else ''
            qualified_name = f"{namespace}\\{class_name}" if namespace else class_name
            
            class_id = self._generate_id(f"{file_path}:class:{qualified_name}")
            
            # Extract class properties
            is_abstract = getattr(node, 'abstract', False)
            is_final = getattr(node, 'final', False)
            extends = getattr(node, 'extends', None)
            implements = getattr(node, 'implements', [])
            
            class_node = Node(
                id=class_id,
                name=class_name,
                kind='class',
                qualified_name=qualified_name,
                location=self._get_location(node, file_path),
                metadata=Metadata(
                    language='php',
                    created_at=datetime.utcnow(),
                    properties={
                        'is_abstract': is_abstract,
                        'is_final': is_final,
                        'extends': extends,
                        'implements': implements if implements else []
                    }
                )
            )
            nodes.append(class_node)
            
            # Link to file or namespace
            parent_id = parent_node.id if parent_node else file_node.id
            relationships.append(Relationship(
                source_id=parent_id,
                target_id=class_id,
                kind='DEFINES_CLASS'
            ))
            
            # Handle inheritance
            if extends:
                relationships.append(Relationship(
                    source_id=class_id,
                    target_id=self._generate_id(f"class:{extends}"),
                    kind='EXTENDS'
                ))
            
            # Handle interfaces
            for interface in (implements or []):
                relationships.append(Relationship(
                    source_id=class_id,
                    target_id=self._generate_id(f"interface:{interface}"),
                    kind='IMPLEMENTS_INTERFACE'
                ))
            
            # Process class members
            if hasattr(node, 'nodes') and node.nodes:
                for member in node.nodes:
                    self._process_class_member(member, nodes, relationships, 
                                              class_node, file_path)
                                              
        # Handle interfaces
        elif node_type == 'Interface':
            interface_name = node.name
            namespace = parent_node.name if parent_node and parent_node.kind == 'namespace' else ''
            qualified_name = f"{namespace}\\{interface_name}" if namespace else interface_name
            
            interface_id = self._generate_id(f"{file_path}:interface:{qualified_name}")
            
            interface_node = Node(
                id=interface_id,
                name=interface_name,
                kind='interface',
                qualified_name=qualified_name,
                location=self._get_location(node, file_path),
                metadata=Metadata(
                    language='php',
                    created_at=datetime.utcnow(),
                    properties={}
                )
            )
            nodes.append(interface_node)
            
            # Link to file or namespace
            parent_id = parent_node.id if parent_node else file_node.id
            relationships.append(Relationship(
                source_id=parent_id,
                target_id=interface_id,
                kind='DEFINES_INTERFACE'
            ))
            
        # Handle traits
        elif node_type == 'Trait':
            trait_name = node.name
            namespace = parent_node.name if parent_node and parent_node.kind == 'namespace' else ''
            qualified_name = f"{namespace}\\{trait_name}" if namespace else trait_name
            
            trait_id = self._generate_id(f"{file_path}:trait:{qualified_name}")
            
            trait_node = Node(
                id=trait_id,
                name=trait_name,
                kind='trait',
                qualified_name=qualified_name,
                location=self._get_location(node, file_path),
                metadata=Metadata(
                    language='php',
                    created_at=datetime.utcnow(),
                    properties={}
                )
            )
            nodes.append(trait_node)
            
            # Link to file or namespace
            parent_id = parent_node.id if parent_node else file_node.id
            relationships.append(Relationship(
                source_id=parent_id,
                target_id=trait_id,
                kind='DEFINES_TRAIT'
            ))
            
        # Handle functions (not in classes)
        elif node_type == 'Function':
            func_name = node.name
            namespace = parent_node.name if parent_node and parent_node.kind == 'namespace' else ''
            qualified_name = f"{namespace}\\{func_name}" if namespace else func_name
            
            func_id = self._generate_id(f"{file_path}:function:{qualified_name}")
            
            # Extract parameters
            params = []
            if hasattr(node, 'params'):
                for param in node.params:
                    param_info = {
                        'name': getattr(param, 'name', ''),
                        'type': getattr(param, 'type', None),
                        'default': getattr(param, 'default', None)
                    }
                    params.append(param_info)
            
            func_node = Node(
                id=func_id,
                name=func_name,
                kind='function',
                qualified_name=qualified_name,
                location=self._get_location(node, file_path),
                metadata=Metadata(
                    language='php',
                    created_at=datetime.utcnow(),
                    properties={
                        'parameters': params,
                        'return_type': getattr(node, 'return_type', None)
                    }
                )
            )
            nodes.append(func_node)
            
            # Link to file or namespace
            parent_id = parent_node.id if parent_node else file_node.id
            relationships.append(Relationship(
                source_id=parent_id,
                target_id=func_id,
                kind='DEFINES_FUNCTION'
            ))
            
        # Process other node types recursively
        elif hasattr(node, 'nodes') and node.nodes:
            for child in node.nodes:
                self._process_ast_node(child, nodes, relationships, file_node, 
                                     file_path, parent_node)
    
    def _process_class_member(self, member, nodes: List[Node], relationships: List[Relationship],
                             class_node: Node, file_path: str):
        """Process class members (methods, properties, constants)"""
        
        if member is None:
            return
            
        member_type = type(member).__name__
        
        # Handle methods
        if member_type == 'Method':
            method_name = member.name
            qualified_name = f"{class_node.qualified_name}::{method_name}"
            
            method_id = self._generate_id(f"{file_path}:method:{qualified_name}")
            
            # Extract method properties
            visibility = getattr(member, 'visibility', 'public')
            is_static = getattr(member, 'static', False)
            is_abstract = getattr(member, 'abstract', False)
            is_final = getattr(member, 'final', False)
            
            # Extract parameters
            params = []
            if hasattr(member, 'params'):
                for param in member.params:
                    param_info = {
                        'name': getattr(param, 'name', ''),
                        'type': getattr(param, 'type', None),
                        'default': getattr(param, 'default', None)
                    }
                    params.append(param_info)
            
            method_node = Node(
                id=method_id,
                name=method_name,
                kind='method',
                qualified_name=qualified_name,
                location=self._get_location(member, file_path),
                metadata=Metadata(
                    language='php',
                    created_at=datetime.utcnow(),
                    properties={
                        'visibility': visibility,
                        'is_static': is_static,
                        'is_abstract': is_abstract,
                        'is_final': is_final,
                        'parameters': params,
                        'return_type': getattr(member, 'return_type', None)
                    }
                )
            )
            nodes.append(method_node)
            
            relationships.append(Relationship(
                source_id=class_node.id,
                target_id=method_id,
                kind='HAS_METHOD'
            ))
            
        # Handle properties
        elif member_type == 'ClassVariable':
            for prop in member.nodes:
                if hasattr(prop, 'name'):
                    prop_name = prop.name
                    qualified_name = f"{class_node.qualified_name}::${prop_name}"
                    
                    prop_id = self._generate_id(f"{file_path}:property:{qualified_name}")
                    
                    visibility = getattr(member, 'visibility', 'public')
                    is_static = getattr(member, 'static', False)
                    prop_type = getattr(member, 'type', None)
                    
                    property_node = Node(
                        id=prop_id,
                        name=f"${prop_name}",
                        kind='property',
                        qualified_name=qualified_name,
                        location=self._get_location(member, file_path),
                        metadata=Metadata(
                            language='php',
                            created_at=datetime.utcnow(),
                            properties={
                                'visibility': visibility,
                                'is_static': is_static,
                                'type': prop_type
                            }
                        )
                    )
                    nodes.append(property_node)
                    
                    relationships.append(Relationship(
                        source_id=class_node.id,
                        target_id=prop_id,
                        kind='HAS_PROPERTY'
                    ))
                    
        # Handle class constants
        elif member_type == 'ClassConstant':
            for const in member.nodes:
                if hasattr(const, 'name'):
                    const_name = const.name
                    qualified_name = f"{class_node.qualified_name}::{const_name}"
                    
                    const_id = self._generate_id(f"{file_path}:constant:{qualified_name}")
                    
                    visibility = getattr(member, 'visibility', 'public')
                    
                    const_node = Node(
                        id=const_id,
                        name=const_name,
                        kind='constant',
                        qualified_name=qualified_name,
                        location=self._get_location(member, file_path),
                        metadata=Metadata(
                            language='php',
                            created_at=datetime.utcnow(),
                            properties={
                                'visibility': visibility
                            }
                        )
                    )
                    nodes.append(const_node)
                    
                    relationships.append(Relationship(
                        source_id=class_node.id,
                        target_id=const_id,
                        kind='HAS_CONSTANT'
                    ))
                    
        # Handle trait usage
        elif member_type == 'TraitUse':
            for trait in member.traits:
                relationships.append(Relationship(
                    source_id=class_node.id,
                    target_id=self._generate_id(f"trait:{trait}"),
                    kind='USES_TRAIT'
                ))
    
    def _get_location(self, node, file_path: str) -> Location:
        """Extract location information from AST node"""
        start_line = getattr(node, 'lineno', 1)
        
        return Location(
            file_path=file_path,
            start_position=Position(line=start_line, column=1),
            end_position=Position(line=start_line, column=1)
        )
    
    def _generate_id(self, content: str) -> str:
        """Generate unique ID for a node"""
        return hashlib.md5(content.encode()).hexdigest()