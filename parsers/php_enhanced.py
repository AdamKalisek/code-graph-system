"""Enhanced PHP parser with Symbol Table support - Pass 1: Symbol Collection"""

import os
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from tree_sitter import Language, Parser, Node
import tree_sitter_php
import logging

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.core.symbol_table import SymbolTable, Symbol, SymbolType

logger = logging.getLogger(__name__)


class PHPSymbolCollector:
    """Pass 1: Collects all symbol definitions from PHP files"""
    
    def __init__(self, symbol_table: SymbolTable):
        self.symbol_table = symbol_table
        PHP_LANGUAGE = Language(tree_sitter_php.language_php())
        self.parser = Parser(PHP_LANGUAGE)
        
        # Track current context during traversal
        self.current_file = None
        self.current_namespace = None
        self.current_class = None
        self.current_function = None
        self.imports = {}
        self.use_statements = {}
    
    def parse_file(self, file_path: str) -> None:
        """Parse a PHP file and collect all symbols"""
        # Check if file needs parsing
        with open(file_path, 'rb') as f:
            content = f.read()
            file_hash = hashlib.md5(content).hexdigest()
        
        if not self.symbol_table.needs_parsing(file_path, file_hash):
            logger.debug(f"Skipping {file_path} - already parsed")
            return
        
        logger.info(f"Collecting symbols from {file_path}")
        
        # Clear old symbols from this file
        self.symbol_table.clear_file_symbols(file_path)
        
        # Reset context
        self.current_file = file_path
        self.current_namespace = None
        self.current_class = None
        self.current_function = None
        self.imports = {}
        self.use_statements = {}
        
        # Parse the file
        tree = self.parser.parse(content)
        
        # Use a single transaction for the whole file
        try:
            self.symbol_table.begin_transaction()
        except:
            # Transaction might already be active from test
            pass
        
        try:
            # Traverse and collect symbols
            self._traverse(tree.root_node)
            
            # Update file hash
            self.symbol_table.update_file_hash(file_path, file_hash)
            
            # Commit transaction
            self.symbol_table.commit()
            
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            self.symbol_table.rollback()
            raise
    
    def _traverse(self, node: Node, parent_symbol_id: Optional[str] = None) -> None:
        """Traverse the AST and collect symbols"""
        
        if node.type == 'namespace_definition':
            self._handle_namespace(node)
        
        elif node.type == 'namespace_use_declaration':
            self._handle_use_statement(node)
        
        elif node.type == 'class_declaration':
            symbol_id = self._handle_class(node, parent_symbol_id)
            # Traverse class body with class as parent
            for child in node.children:
                if child.type == 'declaration_list':
                    old_class = self.current_class
                    self.current_class = self._get_node_text(node.child_by_field_name('name'))
                    self._traverse(child, symbol_id)
                    self.current_class = old_class
            return  # Don't traverse children again
        
        elif node.type == 'interface_declaration':
            symbol_id = self._handle_interface(node, parent_symbol_id)
            # Traverse interface body
            for child in node.children:
                if child.type == 'declaration_list':
                    self._traverse(child, symbol_id)
            return
        
        elif node.type == 'trait_declaration':
            symbol_id = self._handle_trait(node, parent_symbol_id)
            # Traverse trait body
            for child in node.children:
                if child.type == 'declaration_list':
                    self._traverse(child, symbol_id)
            return
        
        elif node.type == 'function_definition':
            symbol_id = self._handle_function(node, parent_symbol_id)
            # Don't traverse function body in Pass 1
            return
        
        elif node.type == 'method_declaration':
            symbol_id = self._handle_method(node, parent_symbol_id)
            # Don't traverse method body in Pass 1
            return
        
        elif node.type == 'property_declaration':
            self._handle_property(node, parent_symbol_id)
            return
        
        elif node.type == 'const_declaration':
            self._handle_constant(node, parent_symbol_id)
            return
        
        elif node.type == 'enum_declaration':
            symbol_id = self._handle_enum(node, parent_symbol_id)
            for child in node.children:
                if child.type == 'enum_declaration_list':
                    self._traverse(child, symbol_id)
            return
        
        # Traverse children
        for child in node.children:
            self._traverse(child, parent_symbol_id)
    
    def _handle_namespace(self, node: Node) -> None:
        """Handle namespace declaration"""
        name_node = node.child_by_field_name('name')
        if name_node:
            self.current_namespace = self._get_node_text(name_node)
            
            # Add namespace as a symbol
            symbol = Symbol(
                id=self._generate_id(node, SymbolType.NAMESPACE),
                name=self.current_namespace,
                type=SymbolType.NAMESPACE,
                file_path=self.current_file,
                line_number=node.start_point[0] + 1,
                column_number=node.start_point[1],
                namespace=None,  # Namespaces don't have a parent namespace
            )
            self.symbol_table.add_symbol(symbol)
    
    def _handle_use_statement(self, node: Node) -> None:
        """Handle use/import statement"""
        for child in node.children:
            if child.type == 'namespace_use_clause':
                name_node = child.child_by_field_name('name')
                alias_node = child.child_by_field_name('alias')
                
                if name_node:
                    full_name = self._get_node_text(name_node)
                    alias = self._get_node_text(alias_node) if alias_node else full_name.split('\\')[-1]
                    
                    self.imports[alias] = full_name
                    self.use_statements[alias] = full_name
                    
                    # Add import as a symbol
                    symbol = Symbol(
                        id=self._generate_id(child, SymbolType.IMPORT),
                        name=alias,
                        type=SymbolType.IMPORT,
                        file_path=self.current_file,
                        line_number=child.start_point[0] + 1,
                        column_number=child.start_point[1],
                        namespace=self.current_namespace,
                        metadata={'imported_name': full_name}
                    )
                    self.symbol_table.add_symbol(symbol)
    
    def _handle_class(self, node: Node, parent_id: Optional[str]) -> str:
        """Handle class declaration"""
        name_node = node.child_by_field_name('name')
        if not name_node:
            return None
        
        class_name = self._get_node_text(name_node)
        full_name = self._get_full_name(class_name)
        
        # Get modifiers
        is_abstract = False
        is_final = False
        for child in node.children:
            if child.type == 'abstract_modifier':
                is_abstract = True
            elif child.type == 'final_modifier':
                is_final = True
        
        # Get extends (try both field names for compatibility)
        extends = None
        extends_node = node.child_by_field_name('superclass')  # Older versions
        if not extends_node:
            # Newer versions use base_clause
            for child in node.children:
                if child.type == 'base_clause':
                    # Extract the actual class name from "extends ClassName"
                    for base_child in child.children:
                        if base_child.type in ['name', 'qualified_name']:
                            extends_node = base_child
                            break
        if extends_node:
            extends = self._get_node_text(extends_node)
        
        # Get implements
        implements = []
        for child in node.children:
            if child.type == 'class_interface_clause':
                for interface in child.children:
                    if interface.type == 'name' or interface.type == 'qualified_name':
                        implements.append(self._get_node_text(interface))
        
        # Create symbol
        symbol = Symbol(
            id=self._generate_id(node, SymbolType.CLASS),
            name=full_name,
            type=SymbolType.CLASS,
            file_path=self.current_file,
            line_number=node.start_point[0] + 1,
            column_number=node.start_point[1],
            namespace=self.current_namespace,
            parent_id=parent_id,
            is_abstract=is_abstract,
            is_final=is_final,
            extends=extends,
            implements=implements or None
        )
        
        self.symbol_table.add_symbol(symbol)
        return symbol.id
    
    def _handle_interface(self, node: Node, parent_id: Optional[str]) -> str:
        """Handle interface declaration"""
        name_node = node.child_by_field_name('name')
        if not name_node:
            return None
        
        interface_name = self._get_node_text(name_node)
        full_name = self._get_full_name(interface_name)
        
        # Get extends (interfaces can extend other interfaces)
        extends = []
        for child in node.children:
            if child.type == 'base_clause':
                for base in child.children:
                    if base.type == 'name' or base.type == 'qualified_name':
                        extends.append(self._get_node_text(base))
        
        symbol = Symbol(
            id=self._generate_id(node, SymbolType.INTERFACE),
            name=full_name,
            type=SymbolType.INTERFACE,
            file_path=self.current_file,
            line_number=node.start_point[0] + 1,
            column_number=node.start_point[1],
            namespace=self.current_namespace,
            parent_id=parent_id,
            implements=extends or None  # Store extends in implements field
        )
        
        self.symbol_table.add_symbol(symbol)
        return symbol.id
    
    def _handle_trait(self, node: Node, parent_id: Optional[str]) -> str:
        """Handle trait declaration"""
        name_node = node.child_by_field_name('name')
        if not name_node:
            return None
        
        trait_name = self._get_node_text(name_node)
        full_name = self._get_full_name(trait_name)
        
        symbol = Symbol(
            id=self._generate_id(node, SymbolType.TRAIT),
            name=full_name,
            type=SymbolType.TRAIT,
            file_path=self.current_file,
            line_number=node.start_point[0] + 1,
            column_number=node.start_point[1],
            namespace=self.current_namespace,
            parent_id=parent_id
        )
        
        self.symbol_table.add_symbol(symbol)
        return symbol.id
    
    def _handle_function(self, node: Node, parent_id: Optional[str]) -> str:
        """Handle function declaration"""
        name_node = node.child_by_field_name('name')
        if not name_node:
            return None
        
        function_name = self._get_node_text(name_node)
        full_name = self._get_full_name(function_name)
        
        # Get parameters
        parameters = self._extract_parameters(node.child_by_field_name('parameters'))
        if not parameters:
            parameters = None
        
        # Get return type
        return_type = None
        return_node = node.child_by_field_name('return_type')
        if return_node:
            return_type = self._get_node_text(return_node)
        
        symbol = Symbol(
            id=self._generate_id(node, SymbolType.FUNCTION),
            name=full_name,
            type=SymbolType.FUNCTION,
            file_path=self.current_file,
            line_number=node.start_point[0] + 1,
            column_number=node.start_point[1],
            namespace=self.current_namespace,
            parent_id=parent_id,
            return_type=return_type,
            parameters=parameters
        )
        
        self.symbol_table.add_symbol(symbol)
        return symbol.id
    
    def _handle_method(self, node: Node, parent_id: Optional[str]) -> str:
        """Handle method declaration"""
        name_node = node.child_by_field_name('name')
        if not name_node:
            return None
        
        method_name = self._get_node_text(name_node)
        
        # Get visibility and modifiers
        visibility = 'public'  # default
        is_static = False
        is_abstract = False
        is_final = False
        
        for child in node.children:
            if child.type == 'visibility_modifier':
                visibility = self._get_node_text(child)
            elif child.type == 'static_modifier':
                is_static = True
            elif child.type == 'abstract_modifier':
                is_abstract = True
            elif child.type == 'final_modifier':
                is_final = True
        
        # Get parameters
        parameters = self._extract_parameters(node.child_by_field_name('parameters'))
        if not parameters:
            parameters = None
        
        # Get return type
        return_type = None
        return_node = node.child_by_field_name('return_type')
        if return_node:
            return_type = self._get_node_text(return_node)
        
        symbol = Symbol(
            id=self._generate_id(node, SymbolType.METHOD),
            name=method_name,
            type=SymbolType.METHOD,
            file_path=self.current_file,
            line_number=node.start_point[0] + 1,
            column_number=node.start_point[1],
            namespace=self.current_namespace,
            parent_id=parent_id,
            visibility=visibility,
            is_static=is_static,
            is_abstract=is_abstract,
            is_final=is_final,
            return_type=return_type,
            parameters=parameters
        )
        
        self.symbol_table.add_symbol(symbol)
        return symbol.id
    
    def _handle_property(self, node: Node, parent_id: Optional[str]) -> None:
        """Handle property declaration"""
        # Get visibility and modifiers
        visibility = 'public'  # default
        is_static = False
        
        for child in node.children:
            if child.type == 'visibility_modifier':
                visibility = self._get_node_text(child)
            elif child.type == 'static_modifier':
                is_static = True
        
        # Get type hint
        type_hint = None
        type_node = node.child_by_field_name('type')
        if type_node:
            type_hint = self._get_node_text(type_node)
        
        # Handle each property in the declaration
        for child in node.children:
            if child.type == 'property_element':
                name_node = child.child_by_field_name('name')
                if name_node:
                    property_name = self._get_node_text(name_node).lstrip('$')
                    
                    symbol = Symbol(
                        id=self._generate_id(child, SymbolType.PROPERTY),
                        name=property_name,
                        type=SymbolType.PROPERTY,
                        file_path=self.current_file,
                        line_number=child.start_point[0] + 1,
                        column_number=child.start_point[1],
                        namespace=self.current_namespace,
                        parent_id=parent_id,
                        visibility=visibility,
                        is_static=is_static,
                        return_type=type_hint  # Store type in return_type field
                    )
                    
                    self.symbol_table.add_symbol(symbol)
    
    def _handle_constant(self, node: Node, parent_id: Optional[str]) -> None:
        """Handle constant declaration"""
        visibility = 'public'  # default for class constants
        
        # Check for visibility modifier
        for child in node.children:
            if child.type == 'visibility_modifier':
                visibility = self._get_node_text(child)
        
        # Handle each constant in the declaration
        for child in node.children:
            if child.type == 'const_element':
                # The name is the first child of type 'name'
                name_node = None
                for elem_child in child.children:
                    if elem_child.type == 'name':
                        name_node = elem_child
                        break
                if name_node:
                    const_name = self._get_node_text(name_node)
                    
                    symbol = Symbol(
                        id=self._generate_id(child, SymbolType.CONSTANT),
                        name=const_name,
                        type=SymbolType.CONSTANT,
                        file_path=self.current_file,
                        line_number=child.start_point[0] + 1,
                        column_number=child.start_point[1],
                        namespace=self.current_namespace,
                        parent_id=parent_id,
                        visibility=visibility if parent_id else None  # Only class constants have visibility
                    )
                    
                    self.symbol_table.add_symbol(symbol)
    
    def _handle_enum(self, node: Node, parent_id: Optional[str]) -> str:
        """Handle enum declaration (PHP 8.1+)"""
        name_node = node.child_by_field_name('name')
        if not name_node:
            return None
        
        enum_name = self._get_node_text(name_node)
        full_name = self._get_full_name(enum_name)
        
        # Get backing type if present
        backing_type = None
        for child in node.children:
            if child.type == ':':
                next_child = child.next_sibling
                if next_child:
                    backing_type = self._get_node_text(next_child)
                    break
        
        symbol = Symbol(
            id=self._generate_id(node, SymbolType.ENUM),
            name=full_name,
            type=SymbolType.ENUM,
            file_path=self.current_file,
            line_number=node.start_point[0] + 1,
            column_number=node.start_point[1],
            namespace=self.current_namespace,
            parent_id=parent_id,
            metadata={'is_enum': True, 'backing_type': backing_type}
        )
        
        self.symbol_table.add_symbol(symbol)
        return symbol.id
    
    def _extract_parameters(self, params_node: Node) -> List[Dict[str, Any]]:
        """Extract parameter information from a formal_parameters node"""
        if not params_node:
            return []
        
        parameters = []
        for child in params_node.children:
            if child.type in ['simple_parameter', 'variadic_parameter', 
                              'property_promotion_parameter']:
                param = {}
                
                # Get type
                type_node = child.child_by_field_name('type')
                if type_node:
                    param['type'] = self._get_node_text(type_node)
                
                # Get name
                name_node = child.child_by_field_name('name')
                if name_node:
                    param['name'] = self._get_node_text(name_node).lstrip('$')
                
                # Check if optional (has default value)
                default_node = child.child_by_field_name('default')
                param['optional'] = default_node is not None
                
                # Check if variadic
                param['variadic'] = child.type == 'variadic_parameter'
                
                # Check if reference
                param['by_reference'] = False
                for grandchild in child.children:
                    if grandchild.type == '&':
                        param['by_reference'] = True
                        break
                
                parameters.append(param)
        
        return parameters
    
    def _get_full_name(self, name: str) -> str:
        """Get the fully qualified name including namespace"""
        if self.current_namespace and not name.startswith('\\'):
            return f"{self.current_namespace}\\{name}"
        return name.lstrip('\\')
    
    def _get_node_text(self, node: Node) -> str:
        """Get the text content of a node"""
        if not node:
            return ""
        
        with open(self.current_file, 'rb') as f:
            content = f.read()
            return content[node.start_byte:node.end_byte].decode('utf-8')
    
    def _generate_id(self, node: Node, symbol_type: SymbolType = None) -> str:
        """Generate a unique ID for a symbol with proper prefix"""
        # Determine prefix based on node type
        prefix = ""
        if symbol_type:
            if symbol_type == SymbolType.CLASS:
                prefix = "php_class_"
            elif symbol_type == SymbolType.INTERFACE:
                prefix = "php_interface_"
            elif symbol_type == SymbolType.TRAIT:
                prefix = "php_trait_"
            elif symbol_type == SymbolType.FUNCTION:
                prefix = "php_function_"
            elif symbol_type == SymbolType.METHOD:
                prefix = "php_method_"
            elif symbol_type == SymbolType.PROPERTY:
                prefix = "php_property_"
            elif symbol_type == SymbolType.CONSTANT:
                prefix = "php_constant_"
            elif symbol_type == SymbolType.NAMESPACE:
                prefix = "php_namespace_"
            elif symbol_type == SymbolType.IMPORT:
                prefix = "php_import_"
            elif symbol_type == SymbolType.ENUM:
                prefix = "php_enum_"
        else:
            # Fallback based on node.type
            if node.type == 'class_declaration':
                prefix = "php_class_"
            elif node.type == 'interface_declaration':
                prefix = "php_interface_"
            elif node.type == 'trait_declaration':
                prefix = "php_trait_"
            elif node.type == 'function_definition':
                prefix = "php_function_"
            elif node.type == 'method_declaration':
                prefix = "php_method_"
            elif node.type == 'property_declaration':
                prefix = "php_property_"
            elif node.type == 'const_declaration':
                prefix = "php_constant_"
            elif node.type == 'namespace_definition':
                prefix = "php_namespace_"
            elif node.type == 'namespace_use_clause':
                prefix = "php_import_"
            elif node.type == 'enum_declaration':
                prefix = "php_enum_"
                
        id_string = f"{self.current_file}:{node.start_point[0]}:{node.start_point[1]}:{node.type}"
        return prefix + hashlib.md5(id_string.encode()).hexdigest()
    
    def parse_directory(self, directory: str, extensions: List[str] = None) -> None:
        """Parse all PHP files in a directory"""
        if extensions is None:
            extensions = ['.php']
        
        path = Path(directory)
        files = []
        
        for ext in extensions:
            files.extend(path.rglob(f'*{ext}'))
        
        total = len(files)
        for i, file_path in enumerate(files, 1):
            logger.info(f"Processing {i}/{total}: {file_path}")
            try:
                self.parse_file(str(file_path))
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                continue
        
        # Print statistics
        stats = self.symbol_table.get_stats()
        logger.info(f"Symbol collection complete: {stats}")