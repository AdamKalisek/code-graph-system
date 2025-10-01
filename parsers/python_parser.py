"""Python parser using tree-sitter for extracting symbols and references."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from tree_sitter import Language, Parser, Node
import tree_sitter_python as tspython

logger = logging.getLogger(__name__)


@dataclass
class PySymbol:
    """Python symbol (class, function, method, etc.)"""
    id: str
    name: str
    type: str  # 'class', 'function', 'method', 'variable', etc.
    file: str
    line: int
    column: int
    metadata: Dict[str, object] = field(default_factory=dict)


@dataclass
class PyReference:
    """Reference from one symbol to another"""
    source_id: str
    target_id: str
    type: str  # 'imports', 'calls', 'inherits', 'uses'
    file: str
    line: int
    column: int
    context: str = ""


class PythonParser:
    """Parse Python files and extract symbols and references"""

    def __init__(self) -> None:
        self.language = Language(tspython.language())
        self.parser = Parser(self.language)
        self.symbols: Dict[str, PySymbol] = {}
        self.references: List[PyReference] = []
        self.current_file = ""
        self.content = b""
        self.current_class = None
        self.imports: Dict[str, str] = {}  # alias -> full_name

    def parse_file(self, file_path: str) -> Tuple[List[PySymbol], List[PyReference]]:
        """Parse a Python file and return symbols and references"""
        self.current_file = file_path
        self.symbols.clear()
        self.references.clear()
        self.imports.clear()
        self.current_class = None

        with open(file_path, 'rb') as handle:
            self.content = handle.read()

        tree = self.parser.parse(self.content)
        self._traverse(tree.root_node)

        return list(self.symbols.values()), list(self.references)

    # ------------------------------------------------------------------
    # Traversal
    # ------------------------------------------------------------------

    def _traverse(self, node: Node, parent_class: Optional[str] = None) -> None:
        """Traverse the AST and extract symbols"""
        current_class = parent_class

        # Handle different node types
        if node.type == 'class_definition':
            class_sym = self._register_class(node)
            if class_sym:
                current_class = class_sym.name
                # Process class body
                for child in node.children:
                    self._traverse(child, current_class)
                return

        elif node.type == 'function_definition':
            self._register_function(node, parent_class)

        elif node.type == 'import_statement':
            self._handle_import(node)

        elif node.type == 'import_from_statement':
            self._handle_import_from(node)

        elif node.type == 'call':
            self._handle_call(node)

        elif node.type == 'assignment':
            self._handle_assignment(node, parent_class)

        # Recurse to children
        for child in node.children:
            self._traverse(child, current_class)

    # ------------------------------------------------------------------
    # Symbol registration
    # ------------------------------------------------------------------

    def _register_class(self, node: Node) -> Optional[PySymbol]:
        """Register a class definition"""
        name_node = node.child_by_field_name('name')
        if not name_node:
            return None

        class_name = self._text(name_node)
        symbol_id = self._symbol_id('class', node)

        # Extract base classes
        bases = []
        superclasses_node = node.child_by_field_name('superclasses')
        if superclasses_node:
            for child in superclasses_node.children:
                if child.type == 'identifier':
                    bases.append(self._text(child))

        symbol = PySymbol(
            id=symbol_id,
            name=class_name,
            type='class',
            file=self.current_file,
            line=node.start_point[0] + 1,
            column=node.start_point[1],
            metadata={'bases': bases}
        )
        self.symbols[symbol_id] = symbol

        # Create inheritance relationships
        for base in bases:
            base_id = f"python_{base}_{self.current_file}"
            self.references.append(PyReference(
                source_id=symbol_id,
                target_id=base_id,
                type='EXTENDS',
                file=self.current_file,
                line=node.start_point[0] + 1,
                column=node.start_point[1],
                context=f'Class {class_name} extends {base}'
            ))

        return symbol

    def _register_function(self, node: Node, parent_class: Optional[str] = None) -> Optional[PySymbol]:
        """Register a function or method definition"""
        name_node = node.child_by_field_name('name')
        if not name_node:
            return None

        func_name = self._text(name_node)

        # Determine if it's a method or function
        symbol_type = 'method' if parent_class else 'function'
        symbol_id = self._symbol_id(symbol_type, node)

        # Extract decorators
        decorators = []
        for child in node.children:
            if child.type == 'decorator':
                dec_name = self._text(child)
                decorators.append(dec_name.lstrip('@'))

        # Extract parameters
        params = []
        parameters_node = node.child_by_field_name('parameters')
        if parameters_node:
            for param in parameters_node.children:
                if param.type == 'identifier':
                    params.append(self._text(param))

        is_async = any(child.type == 'async' for child in node.children)

        symbol = PySymbol(
            id=symbol_id,
            name=func_name,
            type=symbol_type,
            file=self.current_file,
            line=node.start_point[0] + 1,
            column=node.start_point[1],
            metadata={
                'parent_class': parent_class,
                'decorators': decorators,
                'parameters': params,
                'is_async': is_async
            }
        )
        self.symbols[symbol_id] = symbol
        return symbol

    def _handle_assignment(self, node: Node, parent_class: Optional[str] = None) -> None:
        """Handle variable assignments"""
        left_node = node.child_by_field_name('left')
        if not left_node or left_node.type != 'identifier':
            return

        var_name = self._text(left_node)

        # Skip private variables
        if var_name.startswith('_') and not parent_class:
            return

        symbol_type = 'property' if parent_class else 'variable'
        symbol_id = self._symbol_id(symbol_type, node)

        symbol = PySymbol(
            id=symbol_id,
            name=var_name,
            type=symbol_type,
            file=self.current_file,
            line=node.start_point[0] + 1,
            column=node.start_point[1],
            metadata={'parent_class': parent_class}
        )
        self.symbols[symbol_id] = symbol

    # ------------------------------------------------------------------
    # Import handling
    # ------------------------------------------------------------------

    def _handle_import(self, node: Node) -> None:
        """Handle import statements: import module"""
        for child in node.children:
            if child.type == 'dotted_name':
                module_name = self._text(child)
                self.imports[module_name] = module_name

                symbol_id = self._symbol_id('import', node)
                symbol = PySymbol(
                    id=symbol_id,
                    name=module_name,
                    type='import',
                    file=self.current_file,
                    line=node.start_point[0] + 1,
                    column=node.start_point[1],
                    metadata={'module': module_name}
                )
                self.symbols[symbol_id] = symbol

    def _handle_import_from(self, node: Node) -> None:
        """Handle from...import statements"""
        module_node = node.child_by_field_name('module_name')
        if not module_node:
            return

        module_name = self._text(module_node)

        # Get imported names
        for child in node.children:
            if child.type == 'dotted_name' and child != module_node:
                imported_name = self._text(child)
                self.imports[imported_name] = f"{module_name}.{imported_name}"

            elif child.type == 'identifier':
                imported_name = self._text(child)
                self.imports[imported_name] = f"{module_name}.{imported_name}"

        symbol_id = self._symbol_id('import', node)
        symbol = PySymbol(
            id=symbol_id,
            name=module_name,
            type='import',
            file=self.current_file,
            line=node.start_point[0] + 1,
            column=node.start_point[1],
            metadata={'module': module_name, 'from_import': True}
        )
        self.symbols[symbol_id] = symbol

    def _handle_call(self, node: Node) -> None:
        """Handle function calls to create CALLS relationships"""
        function_node = node.child_by_field_name('function')
        if not function_node:
            return

        func_name = self._text(function_node)

        # Skip built-in functions
        if func_name in {'print', 'len', 'str', 'int', 'list', 'dict', 'set', 'tuple', 'range'}:
            return

        # Create a call reference (we'll resolve the target later)
        call_id = f"call_{hashlib.md5(f'{self.current_file}_{node.start_point}'.encode()).hexdigest()[:16]}"

        # Try to find the current function/method we're in
        # This is a simplified version - a full implementation would track scope
        source_id = call_id

        target_id = f"python_{func_name}_{self.current_file}"

        self.references.append(PyReference(
            source_id=source_id,
            target_id=target_id,
            type='CALLS',
            file=self.current_file,
            line=node.start_point[0] + 1,
            column=node.start_point[1],
            context=f'Calls {func_name}'
        ))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _text(self, node: Node) -> str:
        """Extract text from a node"""
        return self.content[node.start_byte:node.end_byte].decode('utf-8')

    def _symbol_id(self, prefix: str, node: Node) -> str:
        """Generate a unique symbol ID"""
        position = f"{self.current_file}:{node.start_point[0]}:{node.start_point[1]}"
        hash_part = hashlib.md5(position.encode()).hexdigest()[:16]
        return f"python_{prefix}_{hash_part}"
