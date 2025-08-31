#!/usr/bin/env python3
"""
Enhanced JavaScript Parser using Tree-sitter
Production-ready implementation with all EspoCRM patterns
"""

import tree_sitter
from tree_sitter import Language, Parser, Node
import tree_sitter_javascript as tsjs
from pathlib import Path
import hashlib
import re
from typing import List, Dict, Any, Optional, Set
from code_graph_system.core.schema import Symbol, Relationship, SourceLocation
from code_graph_system.core.plugin_interface import ParseResult


class JavaScriptEnhancedParser:
    """Production JavaScript parser with comprehensive pattern support"""
    
    def __init__(self):
        self.parser = Parser(Language(tsjs.language()))
        
    def parse_file(self, file_path: str) -> ParseResult:
        """Parse JavaScript file and extract all entities"""
        nodes = []
        relationships = []
        errors = []
        
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
        file_id = self._generate_id(file_path)
        file_node = Symbol(
            name=Path(file_path).name,
            qualified_name=file_path,
            kind='file',
            plugin_id='javascript'
        )
        file_node.id = file_id
        file_node.metadata = {'_language': 'javascript'}
        nodes.append(file_node)
        
        # Extract entities by traversing the tree
        self._traverse_tree(tree.root_node, source_code, file_path, file_id, nodes, relationships)
        
        # Extract specific patterns
        self._extract_amd_patterns(tree, source_code, file_path, file_id, nodes, relationships)
        self._extract_backbone_patterns(tree, source_code, file_path, file_id, nodes, relationships)
        self._extract_api_calls(tree, source_code, file_path, file_id, nodes, relationships)
        
        return ParseResult(
            file_path=file_path,
            nodes=nodes,
            relationships=relationships,
            errors=errors
        )
    
    def _traverse_tree(self, node: Node, source: str, file_path: str, file_id: str, 
                      nodes: List, relationships: List, parent_context: Dict = None):
        """Recursively traverse and extract entities"""
        
        context = parent_context or {}
        
        # ES6 Classes
        if node.type == 'class_declaration':
            class_name = None
            parent_class = None
            
            for child in node.children:
                if child.type == 'identifier' and not class_name:
                    class_name = child.text.decode()
                elif child.type == 'class_heritage':
                    for heritage_child in child.children:
                        if heritage_child.type == 'identifier':
                            parent_class = heritage_child.text.decode()
            
            if class_name:
                class_id = self._generate_id(f"{file_path}:{class_name}")
                class_node = Symbol(
                    name=class_name,
                    qualified_name=f"{file_path}:{class_name}",
                    kind='class',
                    plugin_id='javascript'
                )
                class_node.id = class_id
                class_node.metadata = {
                    '_language': 'javascript',
                    'extends': parent_class
                }
                class_node.location = self._get_location(node, file_path)
                nodes.append(class_node)
                
                # Relationships
                relationships.append(Relationship(
                    type='DEFINED_IN',
                    source_id=class_id,
                    target_id=file_id
                ))
                
                if parent_class:
                    parent_id = self._generate_id(f"unresolved:class:{parent_class}")
                    # Create unresolved node
                    parent_node = Symbol(
                        name=parent_class,
                        qualified_name=f"unresolved:class:{parent_class}",
                        kind='unresolved',
                        plugin_id='javascript'
                    )
                    parent_node.id = parent_id
                    nodes.append(parent_node)
                    
                    relationships.append(Relationship(
                        type='EXTENDS',
                        source_id=class_id,
                        target_id=parent_id
                    ))
                
                # Update context for children
                context = {'class_id': class_id, 'class_name': class_name}
        
        # Methods in classes
        elif node.type == 'method_definition' and 'class_id' in context:
            method_name = None
            for child in node.children:
                if child.type == 'property_identifier':
                    method_name = child.text.decode()
                    break
            
            if method_name:
                method_id = self._generate_id(f"{file_path}:{context['class_name']}.{method_name}")
                method_node = Symbol(
                    name=method_name,
                    qualified_name=f"{context['class_name']}.{method_name}",
                    kind='method',
                    plugin_id='javascript'
                )
                method_node.id = method_id
                method_node.metadata = {'_language': 'javascript'}
                method_node.location = self._get_location(node, file_path)
                nodes.append(method_node)
                
                relationships.append(Relationship(
                    type='HAS_METHOD',
                    source_id=context['class_id'],
                    target_id=method_id
                ))
        
        # Functions
        elif node.type == 'function_declaration':
            func_name = None
            for child in node.children:
                if child.type == 'identifier':
                    func_name = child.text.decode()
                    break
            
            if func_name:
                func_id = self._generate_id(f"{file_path}:{func_name}")
                func_node = Symbol(
                    name=func_name,
                    qualified_name=f"{file_path}:{func_name}",
                    kind='function',
                    plugin_id='javascript'
                )
                func_node.id = func_id
                func_node.metadata = {'_language': 'javascript'}
                func_node.location = self._get_location(node, file_path)
                nodes.append(func_node)
                
                relationships.append(Relationship(
                    type='DEFINED_IN',
                    source_id=func_id,
                    target_id=file_id
                ))
        
        # Arrow functions
        elif node.type == 'variable_declarator':
            var_name = None
            is_arrow = False
            
            for child in node.children:
                if child.type == 'identifier' and not var_name:
                    var_name = child.text.decode()
                elif child.type == 'arrow_function':
                    is_arrow = True
            
            if var_name and is_arrow:
                func_id = self._generate_id(f"{file_path}:{var_name}")
                func_node = Symbol(
                    name=var_name,
                    qualified_name=f"{file_path}:{var_name}",
                    kind='function',
                    plugin_id='javascript'
                )
                func_node.id = func_id
                func_node.metadata = {
                    '_language': 'javascript',
                    'arrow': True
                }
                func_node.location = self._get_location(node, file_path)
                nodes.append(func_node)
                
                relationships.append(Relationship(
                    type='DEFINED_IN',
                    source_id=func_id,
                    target_id=file_id
                ))
        
        # ES6 imports
        elif node.type == 'import_statement':
            module_source = None
            for child in node.children:
                if child.type == 'string':
                    module_source = child.text.decode().strip('"\'')
                    break
            
            if module_source:
                import_id = self._generate_id(f"{file_path}:import:{module_source}")
                import_node = Symbol(
                    name=module_source,
                    qualified_name=f"{file_path}:import:{module_source}",
                    kind='import',
                    plugin_id='javascript'
                )
                import_node.id = import_id
                import_node.metadata = {
                    '_language': 'javascript',
                    'module_type': 'es6'
                }
                nodes.append(import_node)
                
                relationships.append(Relationship(
                    type='IMPORTS',
                    source_id=file_id,
                    target_id=import_id
                ))
        
        # CommonJS require
        elif node.type == 'call_expression':
            func_name = None
            module_path = None
            
            for i, child in enumerate(node.children):
                if child.type == 'identifier' and child.text.decode() == 'require':
                    func_name = 'require'
                elif child.type == 'arguments' and func_name == 'require':
                    for arg_child in child.children:
                        if arg_child.type == 'string':
                            module_path = arg_child.text.decode().strip('"\'')
                            break
            
            if func_name == 'require' and module_path:
                import_id = self._generate_id(f"{file_path}:require:{module_path}")
                import_node = Symbol(
                    name=module_path,
                    qualified_name=f"{file_path}:require:{module_path}",
                    kind='import',
                    plugin_id='javascript'
                )
                import_node.id = import_id
                import_node.metadata = {
                    '_language': 'javascript',
                    'module_type': 'commonjs'
                }
                nodes.append(import_node)
                
                relationships.append(Relationship(
                    type='IMPORTS',
                    source_id=file_id,
                    target_id=import_id
                ))
        
        # Object instantiation
        elif node.type == 'new_expression':
            class_name = None
            for child in node.children:
                if child.type == 'identifier':
                    class_name = child.text.decode()
                    break
            
            if class_name:
                # Create INSTANTIATES relationship
                target_id = self._generate_id(f"unresolved:class:{class_name}")
                relationships.append(Relationship(
                    type='INSTANTIATES',
                    source_id=file_id,  # Could be more specific if we track current function
                    target_id=target_id,
                    metadata={'class_name': class_name}
                ))
        
        # Recurse through children
        for child in node.children:
            self._traverse_tree(child, source, file_path, file_id, nodes, relationships, context)
    
    def _extract_amd_patterns(self, tree: tree_sitter.Tree, source: str, file_path: str, 
                             file_id: str, nodes: List, relationships: List):
        """Extract AMD define/require patterns"""
        
        def find_amd_calls(node: Node):
            if node.type == 'call_expression':
                func_name = None
                dependencies = []
                
                for child in node.children:
                    if child.type == 'identifier' and child.text.decode() in ['define', 'require']:
                        func_name = child.text.decode()
                    elif child.type == 'arguments' and func_name:
                        for arg in child.children:
                            if arg.type == 'array':
                                for array_child in arg.children:
                                    if array_child.type == 'string':
                                        dep = array_child.text.decode().strip('"\'')
                                        dependencies.append(dep)
                
                if func_name and dependencies:
                    # Create AMD module node
                    amd_id = self._generate_id(f"{file_path}:amd_module")
                    amd_node = Symbol(
                        name=f"{func_name}_module",
                        qualified_name=f"{file_path}:amd_module",
                        kind='amd_module',
                        plugin_id='javascript'
                    )
                    amd_node.id = amd_id
                    amd_node.metadata = {
                        '_language': 'javascript',
                        'type': func_name,
                        'dependencies': dependencies
                    }
                    nodes.append(amd_node)
                    
                    relationships.append(Relationship(
                        type='DEFINED_IN',
                        source_id=amd_id,
                        target_id=file_id
                    ))
                    
                    # Create import relationships
                    for dep in dependencies:
                        dep_id = self._generate_id(f"{file_path}:amd:{dep}")
                        dep_node = Symbol(
                            name=dep,
                            qualified_name=f"{file_path}:amd:{dep}",
                            kind='import',
                            plugin_id='javascript'
                        )
                        dep_node.id = dep_id
                        dep_node.metadata = {
                            '_language': 'javascript',
                            'module_type': 'amd'
                        }
                        nodes.append(dep_node)
                        
                        relationships.append(Relationship(
                            type='IMPORTS',
                            source_id=amd_id,
                            target_id=dep_id
                        ))
            
            for child in node.children:
                find_amd_calls(child)
        
        find_amd_calls(tree.root_node)
    
    def _extract_backbone_patterns(self, tree: tree_sitter.Tree, source: str, file_path: str,
                                  file_id: str, nodes: List, relationships: List):
        """Extract Backbone.js patterns"""
        
        # Simple regex pattern matching for Backbone
        backbone_patterns = [
            (r'Backbone\.(View|Model|Collection|Router)\.extend', 'backbone'),
            (r'(\w+)\s*=\s*\w+\.(View|Model|Collection)\.extend', 'possible_backbone')
        ]
        
        for pattern, pattern_type in backbone_patterns:
            for match in re.finditer(pattern, source):
                component_type = match.group(1) if match.lastindex >= 1 else 'Component'
                
                comp_id = self._generate_id(f"{file_path}:backbone:{component_type}")
                comp_node = Symbol(
                    name=f"{component_type}Component",
                    qualified_name=f"{file_path}:backbone:{component_type}",
                    kind=f'backbone_{component_type.lower()}',
                    plugin_id='javascript'
                )
                comp_node.id = comp_id
                comp_node.metadata = {
                    '_language': 'javascript',
                    'backbone_type': component_type
                }
                nodes.append(comp_node)
                
                relationships.append(Relationship(
                    type='DEFINED_IN',
                    source_id=comp_id,
                    target_id=file_id
                ))
    
    def _extract_api_calls(self, tree: tree_sitter.Tree, source: str, file_path: str,
                         file_id: str, nodes: List, relationships: List):
        """Extract API calls and create endpoint nodes"""
        
        # Espo.Ajax patterns
        espo_patterns = [
            (r'Espo\.Ajax\.(get|post|put|delete|patch)Request\s*\(\s*[\'"`]([^\'"`]+)[\'"`]', 'espo_ajax'),
            (r'fetch\s*\(\s*[\'"`]([^\'"`]+)[\'"`]', 'fetch'),
            (r'\$\.ajax\s*\(\s*\{[^}]*url:\s*[\'"`]([^\'"`]+)[\'"`]', 'jquery_ajax')
        ]
        
        for pattern, api_type in espo_patterns:
            for match in re.finditer(pattern, source, re.MULTILINE | re.DOTALL):
                if api_type == 'espo_ajax':
                    method = match.group(1).upper()
                    endpoint = match.group(2)
                elif api_type == 'fetch':
                    method = 'GET'
                    endpoint = match.group(1)
                elif api_type == 'jquery_ajax':
                    method = 'GET'  # Default, could parse method from options
                    endpoint = match.group(1)
                else:
                    continue
                
                # Create endpoint node
                endpoint_id = self._generate_id(f"endpoint:{method}:{endpoint}")
                endpoint_node = Symbol(
                    name=f"{method}:{endpoint}",
                    qualified_name=f"endpoint:{method}:{endpoint}",
                    kind='endpoint',
                    plugin_id='javascript'
                )
                endpoint_node.id = endpoint_id
                endpoint_node.metadata = {
                    '_language': 'javascript',
                    'method': method,
                    'url': endpoint,
                    'api_type': api_type
                }
                nodes.append(endpoint_node)
                
                relationships.append(Relationship(
                    type='CALLS_API',
                    source_id=file_id,
                    target_id=endpoint_id
                ))
        
        # Model operations
        model_patterns = [
            (r'(\w+)\.fetch\s*\(', 'fetch'),
            (r'(\w+)\.save\s*\(', 'save'),
            (r'(\w+)\.destroy\s*\(', 'destroy'),
            (r'(\w+)\.sync\s*\(', 'sync')
        ]
        
        for pattern, operation in model_patterns:
            for match in re.finditer(pattern, source):
                model_var = match.group(1)
                
                op_id = self._generate_id(f"{file_path}:model_op:{operation}:{match.start()}")
                op_node = Symbol(
                    name=f"Model.{operation}",
                    qualified_name=f"{file_path}:model:{operation}",
                    kind='model_operation',
                    plugin_id='javascript'
                )
                op_node.id = op_id
                op_node.metadata = {
                    '_language': 'javascript',
                    'operation': operation,
                    'model_var': model_var
                }
                nodes.append(op_node)
                
                relationships.append(Relationship(
                    type='MODEL_OPERATION',
                    source_id=file_id,
                    target_id=op_id
                ))
    
    def _get_location(self, node: Node, file_path: str) -> SourceLocation:
        """Get source location from node"""
        return SourceLocation(
            file_path=file_path,
            start_line=node.start_point[0] + 1,
            start_column=node.start_point[1],
            end_line=node.end_point[0] + 1,
            end_column=node.end_point[1]
        )
    
    def _generate_id(self, content: str) -> str:
        """Generate unique ID"""
        return hashlib.md5(content.encode()).hexdigest()


# Export as main parser
JavaScriptParser = JavaScriptEnhancedParser