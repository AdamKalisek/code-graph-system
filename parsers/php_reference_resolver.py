"""PHP Reference Resolver - Pass 2: Resolve all references using Symbol Table"""

import os
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
from tree_sitter import Language, Parser, Node
import tree_sitter_php
import logging

from symbol_table import SymbolTable, Symbol, SymbolType
from symbol_table.resolution import SymbolResolver, ResolutionContext

logger = logging.getLogger(__name__)


class PHPReferenceResolver:
    """Pass 2: Resolves all references using the populated symbol table"""
    
    def __init__(self, symbol_table: SymbolTable):
        self.symbol_table = symbol_table
        self.resolver = SymbolResolver(symbol_table)
        PHP_LANGUAGE = Language(tree_sitter_php.language_php())
        self.parser = Parser(PHP_LANGUAGE)
        
        # Track context during traversal
        self.context = None
        self.current_symbol_stack = []  # Stack of symbol IDs we're inside
        
    def resolve_file(self, file_path: str) -> None:
        """Resolve all references in a PHP file"""
        logger.info(f"Resolving references in {file_path}")
        
        # Get all symbols in this file to establish context
        file_symbols = self.symbol_table.get_symbols_in_file(file_path)
        
        # Initialize context
        self.context = ResolutionContext(
            current_file=file_path,
            current_namespace=None,
            current_class=None,
            current_function=None,
            imports={},
            use_statements={}
        )
        
        # Build imports map from file symbols
        for symbol in file_symbols:
            if symbol.type == SymbolType.NAMESPACE:
                self.context.current_namespace = symbol.name
            elif symbol.type == SymbolType.IMPORT and symbol.metadata:
                imported_name = symbol.metadata.get('imported_name')
                if imported_name:
                    self.context.imports[symbol.name] = imported_name
                    self.context.use_statements[symbol.name] = imported_name
        
        # Parse the file
        with open(file_path, 'rb') as f:
            content = f.read()
        
        tree = self.parser.parse(content)
        
        # Start transaction for batch insert
        self.symbol_table.begin_transaction()
        
        try:
            # Traverse and resolve references
            self._traverse(tree.root_node, content)
            
            # Commit transaction
            self.symbol_table.commit()
            
        except Exception as e:
            logger.error(f"Error resolving references in {file_path}: {e}")
            self.symbol_table.rollback()
            raise
    
    def _traverse(self, node: Node, content: bytes, parent_symbol: Optional[Symbol] = None) -> None:
        """Traverse the AST and resolve references"""
        
        # Update context based on node type
        if node.type == 'namespace_definition':
            name_node = node.child_by_field_name('name')
            if name_node:
                self.context.current_namespace = self._get_node_text(name_node, content)
        
        elif node.type == 'namespace_use_declaration':
            logger.debug(f"Found namespace_use_declaration at line {node.start_point[0] + 1}")
            # Create IMPORTS edges for use statements
            for child in node.children:
                logger.debug(f"  Checking child type: {child.type}")
                if child.type == 'namespace_use_clause':
                    # Get the imported namespace/class
                    # The structure is: name (or qualified_name) [as alias]
                    name_node = None
                    alias_node = None
                    
                    for clause_child in child.children:
                        if clause_child.type in ['name', 'qualified_name']:
                            name_node = clause_child
                        elif clause_child.type == 'namespace_aliasing_clause':
                            # Handle alias
                            for alias_child in clause_child.children:
                                if alias_child.type == 'name':
                                    alias_node = alias_child
                    
                    logger.debug(f"  name_node: {name_node}, alias_node: {alias_node}")
                    
                    if name_node:
                        imported_name = self._get_node_text(name_node, content)
                        alias = self._get_node_text(alias_node, content) if alias_node else imported_name.split('\\')[-1]
                        logger.debug(f"  Importing: {imported_name}")
                        
                        # Find the source file symbol to attach the import to
                        # We'll use the namespace or first class in the file
                        source_symbol = self._get_file_main_symbol()
                        logger.debug(f"  Source symbol: {source_symbol.name if source_symbol else None}")
                        if source_symbol:
                            # Try to resolve the imported symbol
                            target = self.symbol_table.resolve(imported_name, "", {})
                            
                            # If not found, create a placeholder for external dependency
                            if not target:
                                target = self._create_external_symbol(imported_name)
                            
                            if target:
                                self.symbol_table.add_reference(
                                    source_id=source_symbol.id,
                                    target_id=target.id,
                                    reference_type='IMPORTS',
                                    line=child.start_point[0] + 1,
                                    column=child.start_point[1],
                                    context=f"Imports {imported_name}"
                                )
        
        elif node.type == 'class_declaration':
            name_node = node.child_by_field_name('name')
            if name_node:
                class_name = self._get_node_text(name_node, content)
                self.context.current_class = self._get_full_name(class_name)
                
                # Find the symbol for this class
                class_symbol = self._find_symbol_at_location(
                    node.start_point[0] + 1,
                    node.start_point[1],
                    SymbolType.CLASS
                )
                
                if class_symbol:
                    # Resolve extends (try both field names for compatibility)
                    extends_node = node.child_by_field_name('superclass')  # Older versions
                    if not extends_node:
                        # Newer versions use base_clause
                        for child in node.children:
                            if child.type == 'base_clause':
                                for base_child in child.children:
                                    if base_child.type in ['name', 'qualified_name']:
                                        extends_node = base_child
                                        break
                    if extends_node:
                        self._resolve_type_reference(extends_node, content, class_symbol.id, 'EXTENDS')
                    
                    # Resolve implements
                    for child in node.children:
                        if child.type == 'class_interface_clause':
                            for interface in child.children:
                                if interface.type in ['name', 'qualified_name']:
                                    self._resolve_type_reference(interface, content, class_symbol.id, 'IMPLEMENTS')
                    
                    # Traverse class body with updated context
                    for child in node.children:
                        if child.type == 'declaration_list':
                            self._traverse(child, content, class_symbol)
                    
                    self.context.current_class = None
                    return
        
        elif node.type in ['trait_use_clause', 'use_declaration']:
            # Resolve trait uses (inside a class context)
            # Check if we're inside a class and this is a trait use
            if parent_symbol and parent_symbol.type == SymbolType.CLASS:
                for child in node.children:
                    if child.type in ['name', 'qualified_name']:
                        self._resolve_type_reference(child, content, parent_symbol.id, 'USES_TRAIT')
        
        elif node.type in ['function_definition', 'method_declaration']:
            name_node = node.child_by_field_name('name')
            if name_node:
                function_name = self._get_node_text(name_node, content)
                old_function = self.context.current_function
                self.context.current_function = function_name
                
                # Find the symbol for this function/method
                func_symbol = self._find_symbol_at_location(
                    node.start_point[0] + 1,
                    node.start_point[1],
                    SymbolType.FUNCTION if node.type == 'function_definition' else SymbolType.METHOD
                )
                
                if func_symbol:
                    # Resolve parameter types
                    params_node = node.child_by_field_name('parameters')
                    if params_node:
                        self._resolve_parameter_types(params_node, content, func_symbol.id)
                    
                    # Resolve return type (handles simple, nullable, union, etc.)
                    return_node = node.child_by_field_name('return_type')
                    if return_node:
                        self._traverse_and_resolve_type_nodes(return_node, content, func_symbol.id, 'RETURNS')
                    
                    # Traverse function body
                    body_node = node.child_by_field_name('body')
                    if body_node:
                        self._traverse(body_node, content, func_symbol)
                
                self.context.current_function = old_function
                return
        
        # Resolve references in expressions
        elif node.type == 'function_call_expression':
            self._resolve_function_call(node, content, parent_symbol)
        
        elif node.type == 'member_call_expression':
            self._resolve_method_call(node, content, parent_symbol)
        
        elif node.type == 'member_access_expression':
            self._resolve_property_access(node, content, parent_symbol)
        
        elif node.type == 'scoped_call_expression':
            self._resolve_static_call(node, content, parent_symbol)
        
        elif node.type == 'class_constant_access_expression':
            logger.debug(f"Found class_constant_access_expression at line {node.start_point[0] + 1}")
            self._resolve_class_constant(node, content, parent_symbol)
        
        elif node.type == 'object_creation_expression':
            self._resolve_new_expression(node, content, parent_symbol)
        
        elif node.type == 'instanceof_expression':
            # The RHS of an 'instanceof' is a type reference
            # e.g., $obj instanceof MyClass, $obj instanceof A|B
            rhs_node = node.child_by_field_name('type')
            if not rhs_node:
                # Fallback: look for name/qualified_name after 'instanceof' keyword
                instanceof_found = False
                for child in node.children:
                    if instanceof_found and child.type in ['name', 'qualified_name']:
                        self._traverse_and_resolve_type_nodes(child, content, 
                                                             parent_symbol.id if parent_symbol else None, 
                                                             'INSTANCEOF')
                        break
                    if child.type == 'instanceof':
                        instanceof_found = True
            elif parent_symbol:
                self._traverse_and_resolve_type_nodes(rhs_node, content, parent_symbol.id, 'INSTANCEOF')
        
        elif node.type in ['name', 'qualified_name']:
            # Could be a type reference in various contexts
            # Note: instanceof is handled directly now
            parent_type = node.parent.type if node.parent else None
            if parent_type == 'binary_expression':
                # This could be for other comparisons, skip for now
                pass
        
        elif node.type == 'throw_expression':
            self._resolve_throw_expression(node, content, parent_symbol)
        
        # Traverse children
        for child in node.children:
            self._traverse(child, content, parent_symbol)
    
    def _resolve_function_call(self, node: Node, content: bytes, parent_symbol: Optional[Symbol]) -> None:
        """Resolve a function call"""
        function_node = node.child_by_field_name('function')
        if not function_node:
            return
        
        function_name = self._get_node_text(function_node, content)
        
        # Try to resolve the function
        resolved = self.resolver.resolve_function_call(function_name, self.context)
        
        if resolved and parent_symbol:
            self.symbol_table.add_reference(
                source_id=parent_symbol.id,
                target_id=resolved.id,
                reference_type='CALLS',
                line=node.start_point[0] + 1,
                column=node.start_point[1],
                context=f"Calls {function_name}"
            )
        elif not resolved:
            self.resolver.track_unresolved(
                'function_call',
                function_name,
                self.context,
                node.start_point[0] + 1,
                node.start_point[1]
            )
    
    def _resolve_method_call(self, node: Node, content: bytes, parent_symbol: Optional[Symbol]) -> None:
        """Resolve a method call like $obj->method()"""
        object_node = node.child_by_field_name('object')
        name_node = node.child_by_field_name('name')
        
        if not name_node:
            return
        
        method_name = self._get_node_text(name_node, content)
        
        # Try to determine object type (simplified - would need type inference)
        if object_node and object_node.type == 'variable_name':
            var_name = self._get_node_text(object_node, content).lstrip('$')
            
            # Special case for $this
            if var_name == 'this' and self.context.current_class:
                class_symbol = self.symbol_table.resolve(
                    self.context.current_class,
                    self.context.current_namespace,
                    self.context.imports
                )
                
                if class_symbol:
                    # Look for method in class
                    methods = self.symbol_table.get_children(class_symbol.id)
                    for method in methods:
                        if method.type == SymbolType.METHOD and method.name == method_name:
                            if parent_symbol:
                                self.symbol_table.add_reference(
                                    source_id=parent_symbol.id,
                                    target_id=method.id,
                                    reference_type='CALLS',
                                    line=node.start_point[0] + 1,
                                    column=node.start_point[1],
                                    context=f"Calls method {method_name}"
                                )
                            return
    
    def _resolve_property_access(self, node: Node, content: bytes, parent_symbol: Optional[Symbol]) -> None:
        """Resolve a property access like $obj->property"""
        object_node = node.child_by_field_name('object')
        name_node = node.child_by_field_name('name')
        
        if not name_node:
            return
        
        property_name = self._get_node_text(name_node, content).lstrip('$')
        
        # Try to determine object type
        if object_node and object_node.type == 'variable_name':
            var_name = self._get_node_text(object_node, content).lstrip('$')
            
            resolved = self.resolver.resolve_property_access(var_name, property_name, self.context)
            
            if resolved and parent_symbol:
                self.symbol_table.add_reference(
                    source_id=parent_symbol.id,
                    target_id=resolved.id,
                    reference_type='ACCESSES',
                    line=node.start_point[0] + 1,
                    column=node.start_point[1],
                    context=f"Accesses property {property_name}"
                )
    
    def _resolve_static_call(self, node: Node, content: bytes, parent_symbol: Optional[Symbol]) -> None:
        """Resolve a static call like ClassName::method()"""
        scope_node = node.child_by_field_name('scope')
        name_node = node.child_by_field_name('name')
        
        if not scope_node or not name_node:
            return
        
        class_name = self._get_node_text(scope_node, content)
        method_name = self._get_node_text(name_node, content)
        
        # Resolve the class
        class_symbol = self._resolve_class_name(class_name)
        
        if class_symbol:
            # Look for static method
            methods = self.symbol_table.get_children(class_symbol.id)
            for method in methods:
                if method.type == SymbolType.METHOD and method.name == method_name and method.is_static:
                    if parent_symbol:
                        self.symbol_table.add_reference(
                            source_id=parent_symbol.id,
                            target_id=method.id,
                            reference_type='CALLS_STATIC',
                            line=node.start_point[0] + 1,
                            column=node.start_point[1],
                            context=f"Calls static method {class_name}::{method_name}"
                        )
                    return
    
    def _resolve_class_constant(self, node: Node, content: bytes, parent_symbol: Optional[Symbol]) -> None:
        """Resolve a class constant access like ClassName::CONSTANT"""
        # The structure is: name (class), ::, name (constant)
        children = list(node.children)
        if len(children) < 3:
            return
        
        class_node = children[0] if children[0].type == 'name' else None
        const_node = children[2] if len(children) > 2 and children[2].type == 'name' else None
        
        if not class_node or not const_node:
            return
        
        class_name = self._get_node_text(class_node, content)
        const_name = self._get_node_text(const_node, content)
        
        logger.debug(f"Resolving class constant: {class_name}::{const_name}")
        resolved = self.resolver.resolve_class_constant(class_name, const_name, self.context)
        
        if resolved and parent_symbol:
            self.symbol_table.add_reference(
                source_id=parent_symbol.id,
                target_id=resolved.id,
                reference_type='USES_CONSTANT',
                line=node.start_point[0] + 1,
                column=node.start_point[1],
                context=f"Uses constant {class_name}::{const_name}"
            )
    
    def _resolve_new_expression(self, node: Node, content: bytes, parent_symbol: Optional[Symbol]) -> None:
        """Resolve a new expression like new ClassName()"""
        for child in node.children:
            if child.type in ['name', 'qualified_name']:
                class_name = self._get_node_text(child, content)
                
                resolved = self._resolve_class_name(class_name)
                
                if resolved and parent_symbol:
                    self.symbol_table.add_reference(
                        source_id=parent_symbol.id,
                        target_id=resolved.id,
                        reference_type='INSTANTIATES',
                        line=node.start_point[0] + 1,
                        column=node.start_point[1],
                        context=f"Creates instance of {class_name}"
                    )
                    
                    # Also look for constructor
                    constructors = self.symbol_table.get_children(resolved.id)
                    for constructor in constructors:
                        if constructor.type == SymbolType.METHOD and constructor.name == '__construct':
                            self.symbol_table.add_reference(
                                source_id=parent_symbol.id,
                                target_id=constructor.id,
                                reference_type='CALLS',
                                line=node.start_point[0] + 1,
                                column=node.start_point[1],
                                context="Calls constructor"
                            )
                return
    
    def _resolve_throw_expression(self, node: Node, content: bytes, parent_symbol: Optional[Symbol]) -> None:
        """Resolve a throw expression like 'throw new ExceptionClass()'"""
        for child in node.children:
            if child.type == 'object_creation_expression':
                # Find the class being instantiated
                for grandchild in child.children:
                    if grandchild.type in ['name', 'qualified_name']:
                        exception_class = self._get_node_text(grandchild, content)
                        
                        resolved = self._resolve_class_name(exception_class)
                        
                        # If not found, create external symbol for built-in exceptions
                        if not resolved and ('Exception' in exception_class or 'Error' in exception_class):
                            resolved = self._create_external_symbol(exception_class)
                        
                        if resolved and parent_symbol:
                            self.symbol_table.add_reference(
                                source_id=parent_symbol.id,
                                target_id=resolved.id,
                                reference_type='THROWS',
                                line=node.start_point[0] + 1,
                                column=node.start_point[1],
                                context=f"Throws {exception_class}"
                            )
                        return
    
    def _resolve_type_reference(self, node: Node, content: bytes, 
                               source_id: str, reference_type: str) -> None:
        """Resolve a type reference"""
        type_name = self._get_node_text(node, content)
        
        resolved = self.resolver.resolve_type(type_name, self.context)
        
        if resolved and source_id:
            self.symbol_table.add_reference(
                source_id=source_id,
                target_id=resolved.id,
                reference_type=reference_type,
                line=node.start_point[0] + 1,
                column=node.start_point[1],
                context=f"{reference_type} {type_name}"
            )
    
    def _resolve_parameter_types(self, params_node: Node, content: bytes, function_id: str) -> None:
        """Resolve type hints in function parameters"""
        for child in params_node.children:
            if child.type in ['simple_parameter', 'variadic_parameter', 'property_promotion_parameter']:
                type_node = child.child_by_field_name('type')
                if type_node:
                    # A parameter type can also be complex (union, etc.)
                    self._traverse_and_resolve_type_nodes(type_node, content, function_id, 'PARAMETER_TYPE')
    
    def _traverse_and_resolve_type_nodes(self, type_node: Node, content: bytes, 
                                         source_id: str, reference_type: str) -> None:
        """
        Traverses a type hint node which may be simple, nullable, a union, or an intersection,
        and creates a reference for each constituent type name found.
        
        This uses an iterative approach to avoid deep recursion on complex types.
        Handles: string, ?string, A|B, A&B, and nested combinations.
        """
        if not source_id:
            return
            
        nodes_to_visit = [type_node]
        
        while nodes_to_visit:
            current_node = nodes_to_visit.pop()
            
            # If we find a name, resolve it. This is our base case.
            if current_node.type in ['name', 'qualified_name']:
                type_name = self._get_node_text(current_node, content)
                
                # Ignore primitive types that won't be in the symbol table
                if type_name not in ['string', 'int', 'float', 'bool', 'array', 
                                     'object', 'void', 'mixed', 'never', 'null',
                                     'false', 'true', 'callable', 'iterable', 'resource']:
                    self._resolve_type_reference(current_node, content, source_id, reference_type)
            # Otherwise, add its children to the stack to visit them next.
            else:
                # Add children in reverse to maintain original order
                nodes_to_visit.extend(reversed(current_node.children))
    
    def _resolve_class_name(self, class_name: str) -> Optional[Symbol]:
        """Resolve a class name considering context"""
        # Handle self, parent, static
        if class_name in ['self', 'static'] and self.context.current_class:
            class_name = self.context.current_class
        elif class_name == 'parent' and self.context.current_class:
            class_symbol = self.symbol_table.resolve(
                self.context.current_class,
                self.context.current_namespace,
                self.context.imports
            )
            if class_symbol and class_symbol.extends:
                class_name = class_symbol.extends
        
        return self.symbol_table.resolve(
            class_name,
            self.context.current_namespace,
            self.context.imports
        )
    
    def _find_symbol_at_location(self, line: int, column: int, 
                                symbol_type: SymbolType) -> Optional[Symbol]:
        """Find a symbol at a specific location in the current file"""
        symbols = self.symbol_table.get_symbols_in_file(self.context.current_file)
        
        for symbol in symbols:
            if (symbol.line_number == line and 
                symbol.column_number == column and
                symbol.type == symbol_type):
                return symbol
        
        return None
    
    def _get_full_name(self, name: str) -> str:
        """Get the fully qualified name including namespace"""
        if self.context.current_namespace and not name.startswith('\\'):
            return f"{self.context.current_namespace}\\{name}"
        return name.lstrip('\\')
    
    def _get_file_main_symbol(self) -> Optional[Symbol]:
        """Get the main symbol for the current file (namespace or first class)"""
        symbols = self.symbol_table.get_symbols_in_file(self.context.current_file)
        
        # Prefer namespace
        for symbol in symbols:
            if symbol.type == SymbolType.NAMESPACE:
                return symbol
        
        # Fall back to first class
        for symbol in symbols:
            if symbol.type == SymbolType.CLASS:
                return symbol
        
        # Fall back to any symbol
        return symbols[0] if symbols else None
    
    def _create_external_symbol(self, name: str) -> Optional[Symbol]:
        """Create a placeholder symbol for external dependencies"""
        # Determine the type based on naming conventions
        symbol_type = SymbolType.CLASS  # Default to class
        
        # Check if it's likely an interface or trait
        if 'Interface' in name:
            symbol_type = SymbolType.INTERFACE
        elif 'Trait' in name:
            symbol_type = SymbolType.TRAIT
        elif 'Exception' in name or 'Error' in name:
            symbol_type = SymbolType.CLASS
        
        # Create a unique ID for the external symbol
        import hashlib
        symbol_id = hashlib.md5(f"external:{name}".encode()).hexdigest()
        
        # Check if we already created this external symbol
        # Try to resolve by ID
        existing = self.symbol_table.resolve(symbol_id, "", {})
        if existing:
            return existing
        
        # Create the external symbol
        symbol = Symbol(
            id=symbol_id,
            name=name,
            type=symbol_type,
            file_path="<external>",  # Mark as external
            line_number=0,
            column_number=0,
            namespace=None,
            metadata={"is_external": True}
        )
        
        self.symbol_table.add_symbol(symbol)
        return symbol
    
    def _get_node_text(self, node: Node, content: bytes) -> str:
        """Get the text content of a node"""
        if not node:
            return ""
        return content[node.start_byte:node.end_byte].decode('utf-8')
    
    def resolve_directory(self, directory: str, extensions: List[str] = None) -> None:
        """Resolve references in all PHP files in a directory"""
        if extensions is None:
            extensions = ['.php']
        
        path = Path(directory)
        files = []
        
        for ext in extensions:
            files.extend(path.rglob(f'*{ext}'))
        
        total = len(files)
        for i, file_path in enumerate(files, 1):
            logger.info(f"Resolving {i}/{total}: {file_path}")
            try:
                self.resolve_file(str(file_path))
            except Exception as e:
                logger.error(f"Error resolving {file_path}: {e}")
                continue
        
        # Report unresolved references
        unresolved = self.resolver.get_unresolved_report()
        if unresolved:
            logger.warning(f"Unresolved references: {unresolved}")
        
        # Print statistics
        stats = self.symbol_table.get_stats()
        logger.info(f"Reference resolution complete: {stats}")