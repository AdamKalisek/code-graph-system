#!/usr/bin/env python3
"""
JavaScript parser using tree-sitter
Extracts ES6 modules, functions, classes, and API calls
"""

import tree_sitter
from tree_sitter import Language, Parser, Node
import tree_sitter_javascript as tsjs
from pathlib import Path
import hashlib
import json
import re
from typing import List, Dict, Any, Optional
from code_graph_system.core.schema import Symbol, Relationship, SourceLocation
from code_graph_system.core.plugin_interface import ParseResult


class JavaScriptParser:
    """Tree-sitter based JavaScript parser"""
    
    def __init__(self):
        # Create parser with JavaScript language
        self.parser = Parser(Language(tsjs.language()))
        
    def parse_file(self, file_path: str) -> ParseResult:
        """Parse JavaScript file using tree-sitter"""
        nodes = []
        relationships = []
        errors = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Parse with tree-sitter
            tree = self.parser.parse(bytes(content, 'utf8'))
            
            # Create file node
            file_id = self._generate_id(file_path)
            file_node = Symbol(
                name=Path(file_path).name,
                qualified_name=file_path,
                kind='file',
                plugin_id='javascript'
            )
            file_node.id = file_id
            file_node.metadata = {
                '_language': 'javascript',
                'extension': Path(file_path).suffix
            }
            nodes.append(file_node)
            
            # Detect module type
            module_type = self._detect_module_type(tree.root_node, content)
            
            # Extract imports
            imports = self._extract_imports(tree.root_node, content)
            for imp in imports:
                imp_node = self._create_import_node(imp, file_path)
                nodes.append(imp_node)
                relationships.append(Relationship(
                    type='IMPORTS',
                    source_id=file_id,
                    target_id=imp_node.id,
                    metadata={'from': imp['from']}
                ))
            
            # Extract exports
            exports = self._extract_exports(tree.root_node, content)
            for exp in exports:
                exp_node = self._create_export_node(exp, file_path)
                nodes.append(exp_node)
                relationships.append(Relationship(
                    type='EXPORTS',
                    source_id=file_id,
                    target_id=exp_node.id
                ))
            
            # Extract classes
            classes = self._extract_classes(tree.root_node, content, file_path)
            for cls in classes:
                cls_node = self._create_class_node(cls, file_path)
                nodes.append(cls_node)
                relationships.append(Relationship(
                    type='DEFINED_IN',
                    source_id=cls_node.id,
                    target_id=file_id
                ))
                
                # Check for extends
                if cls.get('extends'):
                    relationships.append(Relationship(
                        type='EXTENDS',
                        source_id=cls_node.id,
                        target_id=self._generate_id(cls['extends']),
                        metadata={'target_name': cls['extends']}
                    ))
            
            # Extract functions
            functions = self._extract_functions(tree.root_node, content, file_path)
            for func in functions:
                func_node = self._create_function_node(func, file_path)
                nodes.append(func_node)
                relationships.append(Relationship(
                    type='DEFINED_IN',
                    source_id=func_node.id,
                    target_id=file_id
                ))
            
            # Extract API calls
            api_calls = self._extract_api_calls(tree.root_node, content)
            for call in api_calls:
                # Store as metadata on file node for now
                if 'api_calls' not in file_node.metadata:
                    file_node.metadata['api_calls'] = []
                file_node.metadata['api_calls'].append(call)
                
            # Extract Backbone views/models
            backbone_components = self._extract_backbone_components(tree.root_node, content, file_path)
            for comp in backbone_components:
                comp_node = self._create_backbone_node(comp, file_path)
                nodes.append(comp_node)
                relationships.append(Relationship(
                    type='DEFINED_IN',
                    source_id=comp_node.id,
                    target_id=file_id
                ))
                
        except Exception as e:
            errors.append(f"Parse error: {str(e)}")
            
        return ParseResult(
            file_path=file_path,
            nodes=nodes,
            relationships=relationships,
            errors=errors
        )
    
    def _detect_module_type(self, node: Node, source: str) -> str:
        """Detect if ES6, CommonJS, or AMD module"""
        content = source[:1000]  # Check beginning of file
        
        if 'import ' in content or 'export ' in content:
            return 'es6'
        elif 'require(' in content or 'module.exports' in content:
            return 'commonjs'
        elif 'define(' in content:
            return 'amd'
        else:
            return 'script'
    
    def _extract_imports(self, node: Node, source: str) -> List[Dict]:
        """Extract import statements"""
        imports = []
        
        # ES6 imports
        if node.type == 'import_statement':
            # Use field name 'source' instead of looking for 'string' type
            from_clause = node.child_by_field_name('source')
            if from_clause:
                from_path = self._get_node_text(from_clause, source).strip('"\'')
                
                # Get imported items
                items = []
                import_clause = self._find_child_by_type(node, 'import_clause')
                if import_clause:
                    # Named imports
                    named_imports = self._find_child_by_type(import_clause, 'named_imports')
                    if named_imports:
                        for child in named_imports.children:
                            if child.type == 'import_specifier':
                                name = self._get_node_text(child, source)
                                items.append(name)
                    
                    # Default import
                    default_import = import_clause.child_by_field_name('default')
                    if default_import:
                        items.append(self._get_node_text(default_import, source))
                
                imports.append({
                    'type': 'es6',
                    'from': from_path,
                    'items': items,
                    'line': node.start_point[0] + 1
                })
        
        # CommonJS require
        elif node.type == 'call_expression':
            func = node.child_by_field_name('function')
            if func and self._get_node_text(func, source) == 'require':
                args = node.child_by_field_name('arguments')
                if args and args.child_count > 1:
                    first_arg = args.children[1]
                    if first_arg.type == 'string':
                        path = self._get_node_text(first_arg, source).strip('"\'')
                        imports.append({
                            'type': 'commonjs',
                            'from': path,
                            'items': [],
                            'line': node.start_point[0] + 1
                        })
        
        # Recurse through children
        for child in node.children:
            imports.extend(self._extract_imports(child, source))
            
        return imports
    
    def _extract_exports(self, node: Node, source: str) -> List[Dict]:
        """Extract export statements"""
        exports = []
        
        # ES6 exports
        if node.type == 'export_statement':
            declaration = node.child_by_field_name('declaration')
            if declaration:
                if declaration.type == 'function_declaration':
                    name = declaration.child_by_field_name('name')
                    if name:
                        exports.append({
                            'type': 'function',
                            'name': self._get_node_text(name, source),
                            'line': node.start_point[0] + 1
                        })
                elif declaration.type == 'class_declaration':
                    name = declaration.child_by_field_name('name')
                    if name:
                        exports.append({
                            'type': 'class',
                            'name': self._get_node_text(name, source),
                            'line': node.start_point[0] + 1
                        })
        
        # Recurse
        for child in node.children:
            exports.extend(self._extract_exports(child, source))
            
        return exports
    
    def _extract_classes(self, node: Node, source: str, file_path: str) -> List[Dict]:
        """Extract class definitions"""
        classes = []
        
        if node.type == 'class_declaration':
            name_node = node.child_by_field_name('name')
            if name_node:
                name = self._get_node_text(name_node, source)
                
                # Check for extends
                heritage = node.child_by_field_name('heritage')
                extends = None
                if heritage:
                    extends_node = heritage.child_by_field_name('parent')
                    if extends_node:
                        extends = self._get_node_text(extends_node, source)
                
                # Extract methods
                methods = []
                body = node.child_by_field_name('body')
                if body:
                    for child in body.children:
                        if child.type == 'method_definition':
                            method_name = child.child_by_field_name('name')
                            if method_name:
                                methods.append(self._get_node_text(method_name, source))
                
                classes.append({
                    'name': name,
                    'extends': extends,
                    'methods': methods,
                    'line': node.start_point[0] + 1
                })
        
        # Recurse
        for child in node.children:
            classes.extend(self._extract_classes(child, source, file_path))
            
        return classes
    
    def _extract_functions(self, node: Node, source: str, file_path: str) -> List[Dict]:
        """Extract function definitions"""
        functions = []
        
        if node.type in ['function_declaration', 'arrow_function', 'function_expression']:
            name_node = node.child_by_field_name('name')
            name = self._get_node_text(name_node, source) if name_node else '<anonymous>'
            
            # Get parameters
            params = []
            params_node = node.child_by_field_name('parameters')
            if params_node:
                for child in params_node.children:
                    if child.type == 'identifier':
                        params.append(self._get_node_text(child, source))
            
            functions.append({
                'name': name,
                'params': params,
                'async': 'async' in self._get_node_text(node, source)[:10],
                'line': node.start_point[0] + 1
            })
        
        # Recurse
        for child in node.children:
            functions.extend(self._extract_functions(child, source, file_path))
            
        return functions
    
    def _extract_api_calls(self, node: Node, source: str) -> List[Dict]:
        """Extract API calls (fetch, ajax, axios)"""
        api_calls = []
        
        if node.type == 'call_expression':
            func_node = node.child_by_field_name('function')
            if func_node:
                func_name = self._get_node_text(func_node, source)
                
                # Check for API call functions (case-insensitive)
                func_name_lower = func_name.lower()
                # Check for fetch, axios, or ajax calls (including jQuery $.ajax)
                is_api_call = (
                    'fetch' in func_name_lower or
                    'axios' in func_name_lower or
                    'ajax' in func_name_lower or
                    func_name in ['$.ajax', 'jQuery.ajax']
                )
                
                if is_api_call:
                    args_node = node.child_by_field_name('arguments')
                    if args_node and args_node.child_count > 1:
                        first_arg = args_node.children[1]
                        
                        # Extract URL - could be string or object with url property
                        url = None
                        method = 'GET'
                        
                        if first_arg.type in ['string', 'template_string']:
                            # Direct URL string (fetch, axios.get, etc.)
                            url = self._get_node_text(first_arg, source).strip('"\'`')
                        elif first_arg.type == 'binary_expression':
                            # Handle string concatenation (e.g., '/api/v1/User/' + userId)
                            # Extract the left side if it's a string literal
                            left_node = first_arg.child_by_field_name('left')
                            if left_node and left_node.type in ['string', 'template_string']:
                                url = self._get_node_text(left_node, source).strip('"\'`')
                                # Add placeholder for dynamic parts
                                if not url.endswith('{id}'):
                                    url = url.rstrip('/') + '/{id}'
                        
                        # Try to detect HTTP method from second arg (for string URLs)
                        if url and first_arg.type != 'object':
                            if args_node.child_count > 2:
                                second_arg = args_node.children[2]
                                if second_arg.type == 'object':
                                    obj_text = self._get_node_text(second_arg, source)
                                    if 'method:' in obj_text:
                                        method_match = re.search(r"method:\s*['\"](\w+)['\"]", obj_text)
                                        if method_match:
                                            method = method_match.group(1).upper()
                                            
                        elif first_arg.type == 'object':
                            # Object with url property ($.ajax style)
                            obj_text = self._get_node_text(first_arg, source)
                            
                            # Extract URL from object
                            url_match = re.search(r"url:\s*['\"]([^'\"]+)['\"]", obj_text)
                            if url_match:
                                url = url_match.group(1)
                            
                            # Extract method from object
                            method_match = re.search(r"method:\s*['\"](\w+)['\"]", obj_text)
                            if not method_match:
                                method_match = re.search(r"type:\s*['\"](\w+)['\"]", obj_text)
                            if method_match:
                                method = method_match.group(1).upper()
                        
                        # Also check for method in function name (axios.post, etc.)
                        if 'post' in func_name_lower:
                            method = 'POST'
                        elif 'put' in func_name_lower:
                            method = 'PUT'
                        elif 'delete' in func_name_lower:
                            method = 'DELETE'
                        elif 'patch' in func_name_lower:
                            method = 'PATCH'
                            
                        if url:
                            api_calls.append({
                                'function': func_name,
                                'url': url,
                                'method': method,
                                'line': node.start_point[0] + 1
                            })
        
        # Recurse
        for child in node.children:
            api_calls.extend(self._extract_api_calls(child, source))
            
        return api_calls
    
    def _extract_backbone_components(self, node: Node, source: str, file_path: str) -> List[Dict]:
        """Extract Backbone.js Views, Models, Collections"""
        components = []
        
        if node.type == 'call_expression':
            func_node = node.child_by_field_name('function')
            if func_node:
                func_text = self._get_node_text(func_node, source)
                
                # Check for Backbone component patterns
                backbone_types = {
                    'Backbone.View.extend': 'view',
                    'View.extend': 'view',
                    'Backbone.Model.extend': 'model',
                    'Model.extend': 'model',
                    'Backbone.Collection.extend': 'collection',
                    'Collection.extend': 'collection'
                }
                
                for pattern, comp_type in backbone_types.items():
                    if pattern in func_text:
                        # Try to find the assignment
                        parent = node.parent
                        if parent and parent.type == 'assignment_expression':
                            left = parent.child_by_field_name('left')
                            if left:
                                name = self._get_node_text(left, source)
                                
                                # Extract properties from extend argument
                                args_node = node.child_by_field_name('arguments')
                                properties = {}
                                if args_node and args_node.child_count > 1:
                                    obj_node = args_node.children[1]
                                    if obj_node.type == 'object':
                                        properties = self._extract_object_properties(obj_node, source)
                                
                                components.append({
                                    'name': name,
                                    'type': comp_type,
                                    'properties': list(properties.keys()),
                                    'line': node.start_point[0] + 1
                                })
                        break
        
        # Recurse
        for child in node.children:
            components.extend(self._extract_backbone_components(child, source, file_path))
            
        return components
    
    def _extract_object_properties(self, node: Node, source: str) -> Dict:
        """Extract properties from an object literal"""
        properties = {}
        
        for child in node.children:
            if child.type == 'pair':
                key_node = child.child_by_field_name('key')
                if key_node:
                    key = self._get_node_text(key_node, source).strip('"\'')
                    properties[key] = True
                    
        return properties
    
    def _create_import_node(self, imp: Dict, file_path: str) -> Symbol:
        """Create Symbol node for import"""
        symbol = Symbol(
            name=imp['from'],
            qualified_name=f"{file_path}:import:{imp['from']}",
            kind='import',
            plugin_id='javascript'
        )
        symbol.id = self._generate_id(symbol.qualified_name)
        symbol.metadata = {
            '_language': 'javascript',
            'module_type': imp['type'],
            'items': imp.get('items', [])
        }
        symbol.location = SourceLocation(
            file_path=file_path,
            start_line=imp['line'],
            start_column=0,
            end_line=imp['line'],
            end_column=0
        )
        return symbol
    
    def _create_export_node(self, exp: Dict, file_path: str) -> Symbol:
        """Create Symbol node for export"""
        symbol = Symbol(
            name=exp['name'],
            qualified_name=f"{file_path}:export:{exp['name']}",
            kind='export',
            plugin_id='javascript'
        )
        symbol.id = self._generate_id(symbol.qualified_name)
        symbol.metadata = {
            '_language': 'javascript',
            'export_type': exp['type']
        }
        symbol.location = SourceLocation(
            file_path=file_path,
            start_line=exp['line'],
            start_column=0,
            end_line=exp['line'],
            end_column=0
        )
        return symbol
    
    def _create_class_node(self, cls: Dict, file_path: str) -> Symbol:
        """Create Symbol node for class"""
        symbol = Symbol(
            name=cls['name'],
            qualified_name=f"{file_path}:{cls['name']}",
            kind='class',
            plugin_id='javascript'
        )
        symbol.id = self._generate_id(symbol.qualified_name)
        symbol.metadata = {
            '_language': 'javascript',
            'methods': cls.get('methods', []),
            'extends': cls.get('extends')
        }
        symbol.location = SourceLocation(
            file_path=file_path,
            start_line=cls['line'],
            start_column=0,
            end_line=cls['line'],
            end_column=0
        )
        return symbol
    
    def _create_function_node(self, func: Dict, file_path: str) -> Symbol:
        """Create Symbol node for function"""
        symbol = Symbol(
            name=func['name'],
            qualified_name=f"{file_path}:{func['name']}",
            kind='function',
            plugin_id='javascript'
        )
        symbol.id = self._generate_id(symbol.qualified_name)
        symbol.metadata = {
            '_language': 'javascript',
            'params': func.get('params', []),
            'async': func.get('async', False)
        }
        symbol.location = SourceLocation(
            file_path=file_path,
            start_line=func['line'],
            start_column=0,
            end_line=func['line'],
            end_column=0
        )
        return symbol
    
    def _create_backbone_node(self, comp: Dict, file_path: str) -> Symbol:
        """Create Symbol node for Backbone component"""
        symbol = Symbol(
            name=comp['name'],
            qualified_name=f"{file_path}:{comp['name']}",
            kind=f"backbone_{comp['type']}",
            plugin_id='javascript'
        )
        symbol.id = self._generate_id(symbol.qualified_name)
        symbol.metadata = {
            '_language': 'javascript',
            'component_type': comp['type'],
            'properties': comp.get('properties', [])
        }
        symbol.location = SourceLocation(
            file_path=file_path,
            start_line=comp['line'],
            start_column=0,
            end_line=comp['line'],
            end_column=0
        )
        return symbol
    
    def _find_child_by_type(self, node: Node, node_type: str) -> Optional[Node]:
        """Find first child node of given type"""
        for child in node.children:
            if child.type == node_type:
                return child
        return None
    
    def _get_node_text(self, node: Node, source: str) -> str:
        """Get text content of a node"""
        if node:
            return source[node.start_byte:node.end_byte]
        return ""
    
    def _generate_id(self, content: str) -> str:
        """Generate unique ID"""
        return hashlib.md5(content.encode()).hexdigest()