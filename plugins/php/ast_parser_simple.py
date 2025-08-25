#!/usr/bin/env python3
"""
Simplified PHP Parser using regular expressions
Temporary solution until we integrate a proper AST parser
"""

import re
import hashlib
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from code_graph_system.core.schema import Symbol, Relationship, SourceLocation, Visibility
from code_graph_system.core.plugin_interface import ParseResult


class SimplePHPParser:
    """Enhanced PHP parser using better regex patterns"""
    
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
            
            # Create File node
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
            nodes.append(file_node)
            
            # Extract namespace
            namespace = self._extract_namespace(content)
            
            # Extract classes with better patterns
            classes = self._extract_classes(content, file_path, namespace)
            for class_data in classes:
                class_node = class_data['node']
                nodes.append(class_node)
                
                # Link to file
                relationships.append(Relationship(
                    type='DEFINED_IN',
                    source_id=class_node.id,
                    target_id=file_id
                ))
                
                # Extract methods for this class
                methods = self._extract_methods(class_data['content'], class_node, file_path)
                for method in methods:
                    nodes.append(method)
                    relationships.append(Relationship(
                        type='HAS_METHOD',
                        source_id=class_node.id,
                        target_id=method.id
                    ))
                
                # Extract properties for this class
                properties = self._extract_properties(class_data['content'], class_node, file_path)
                for prop in properties:
                    nodes.append(prop)
                    relationships.append(Relationship(
                        type='HAS_PROPERTY',
                        source_id=class_node.id,
                        target_id=prop.id
                    ))
                
                # Extract inheritance
                if class_data.get('extends'):
                    relationships.append(Relationship(
                        type='EXTENDS',
                        source_id=class_node.id,
                        target_id=None,
                        metadata={'target_name': class_data['extends']}
                    ))
                
                # Extract interfaces
                for interface in class_data.get('implements', []):
                    relationships.append(Relationship(
                        type='IMPLEMENTS_INTERFACE',
                        source_id=class_node.id,
                        target_id=None,
                        metadata={'target_name': interface}
                    ))
                    
        except Exception as e:
            errors.append(f"Error parsing file {file_path}: {str(e)}")
            
        return ParseResult(
            file_path=file_path,
            nodes=nodes,
            relationships=relationships,
            errors=errors,
            warnings=[]
        )
    
    def _extract_namespace(self, content: str) -> str:
        """Extract namespace from PHP file"""
        pattern = r'namespace\s+([\w\\]+)\s*;'
        match = re.search(pattern, content)
        return match.group(1) if match else ''
    
    def _extract_classes(self, content: str, file_path: str, namespace: str) -> List[Dict]:
        """Extract classes with their full content"""
        classes = []
        
        # Pattern to match class declaration with extends and implements
        class_pattern = r'''
            (?:abstract\s+|final\s+)?      # Optional abstract or final
            class\s+                        # class keyword
            (\w+)                          # Class name
            (?:\s+extends\s+([\w\\]+))?   # Optional extends
            (?:\s+implements\s+([\w\\,\s]+))? # Optional implements
            \s*\{                          # Opening brace
        '''
        
        for match in re.finditer(class_pattern, content, re.VERBOSE | re.MULTILINE):
            class_name = match.group(1)
            extends = match.group(2)
            implements = match.group(3)
            
            # Find the class content (everything between { and })
            start_pos = match.end() - 1  # Position of {
            brace_count = 1
            end_pos = start_pos + 1
            
            while end_pos < len(content) and brace_count > 0:
                if content[end_pos] == '{':
                    brace_count += 1
                elif content[end_pos] == '}':
                    brace_count -= 1
                end_pos += 1
            
            class_content = content[start_pos:end_pos]
            
            # Get line number
            line_num = content[:match.start()].count('\n') + 1
            
            # Determine if abstract or final
            prefix = content[max(0, match.start()-20):match.start()]
            is_abstract = 'abstract' in prefix
            is_final = 'final' in prefix
            
            # Create qualified name
            qualified_name = f"{namespace}\\{class_name}" if namespace else class_name
            
            # Create class node
            class_node = Symbol(
                name=class_name,
                qualified_name=qualified_name,
                kind='class',
                plugin_id='php'
            )
            class_node.id = self._generate_id(f"{file_path}:class:{qualified_name}")
            class_node.metadata = {
                'namespace': namespace,
                'is_abstract': is_abstract,
                'is_final': is_final,
                'extends': extends,
                'implements': [i.strip() for i in implements.split(',')] if implements else []
            }
            class_node.location = SourceLocation(
                file_path=file_path,
                start_line=line_num,
                start_column=1,
                end_line=line_num,
                end_column=1
            )
            
            classes.append({
                'node': class_node,
                'content': class_content,
                'extends': extends,
                'implements': [i.strip() for i in implements.split(',')] if implements else []
            })
        
        return classes
    
    def _extract_methods(self, class_content: str, class_node: Symbol, file_path: str) -> List[Symbol]:
        """Extract methods from class content"""
        methods = []
        
        # Pattern to match method declarations
        method_pattern = r'''
            (?:(public|protected|private)\s+)?     # Optional visibility
            (?:(static)\s+)?                       # Optional static
            (?:(abstract|final)\s+)?               # Optional abstract/final
            function\s+                             # function keyword
            (\w+)                                   # Method name
            \s*\([^)]*\)                           # Parameters (simplified)
            (?:\s*:\s*([\w\\\?]+))?               # Optional return type
        '''
        
        for match in re.finditer(method_pattern, class_content, re.VERBOSE | re.MULTILINE):
            visibility = match.group(1) or 'public'
            is_static = match.group(2) is not None
            modifier = match.group(3)
            method_name = match.group(4)
            return_type = match.group(5)
            
            # Skip constructor variations that aren't actual methods
            if method_name == '__construct':
                method_name = '__construct'
            
            qualified_name = f"{class_node.qualified_name}::{method_name}"
            
            method_node = Symbol(
                name=method_name,
                qualified_name=qualified_name,
                kind='method',
                plugin_id='php'
            )
            method_node.id = self._generate_id(f"{file_path}:method:{qualified_name}")
            
            # Map visibility
            visibility_map = {
                'public': Visibility.PUBLIC,
                'protected': Visibility.PROTECTED,
                'private': Visibility.PRIVATE
            }
            method_node.visibility = visibility_map.get(visibility, Visibility.PUBLIC)
            
            method_node.metadata = {
                'class_name': class_node.name,
                'is_static': is_static,
                'is_abstract': modifier == 'abstract',
                'is_final': modifier == 'final',
                'return_type': return_type
            }
            
            methods.append(method_node)
        
        return methods
    
    def _extract_properties(self, class_content: str, class_node: Symbol, file_path: str) -> List[Symbol]:
        """Extract properties from class content"""
        properties = []
        
        # Pattern to match property declarations
        property_pattern = r'''
            (?:(public|protected|private)\s+)?     # Optional visibility
            (?:(static)\s+)?                       # Optional static
            (?:(readonly)\s+)?                     # Optional readonly (PHP 8.1+)
            (?:(?:array|string|int|bool|float|object|mixed|[\w\\]+)\s+)?  # Optional type
            \$(\w+)                                # Property name
            (?:\s*=\s*[^;]+)?                     # Optional default value
            \s*;                                   # Semicolon
        '''
        
        for match in re.finditer(property_pattern, class_content, re.VERBOSE | re.MULTILINE):
            # Skip if this is inside a method (basic heuristic)
            before_match = class_content[:match.start()]
            if 'function' in before_match.split('\n')[-1]:
                continue
                
            visibility = match.group(1) or 'public'
            is_static = match.group(2) is not None
            is_readonly = match.group(3) is not None
            prop_name = match.group(4)
            
            # Skip if it looks like a variable inside a method
            # Check if we're inside a function by counting braces
            open_braces_before = before_match.count('{') - before_match.count('}')
            last_function_pos = before_match.rfind('function')
            if last_function_pos > 0:
                braces_after_func = before_match[last_function_pos:].count('{') - before_match[last_function_pos:].count('}')
                if braces_after_func > 0:
                    continue  # We're inside a function
            
            qualified_name = f"{class_node.qualified_name}::${prop_name}"
            
            prop_node = Symbol(
                name=f"${prop_name}",
                qualified_name=qualified_name,
                kind='property',
                plugin_id='php'
            )
            prop_node.id = self._generate_id(f"{file_path}:property:{qualified_name}")
            
            # Map visibility
            visibility_map = {
                'public': Visibility.PUBLIC,
                'protected': Visibility.PROTECTED,
                'private': Visibility.PRIVATE
            }
            prop_node.visibility = visibility_map.get(visibility, Visibility.PUBLIC)
            
            prop_node.metadata = {
                'class_name': class_node.name,
                'is_static': is_static,
                'is_readonly': is_readonly
            }
            
            properties.append(prop_node)
        
        return properties
    
    def _generate_id(self, content: str) -> str:
        """Generate unique ID for a node"""
        return hashlib.md5(content.encode()).hexdigest()