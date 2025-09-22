"""Generic JavaScript parser using tree-sitter."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import tree_sitter_javascript as tjs
from tree_sitter import Language, Parser, Node

logger = logging.getLogger(__name__)


@dataclass
class JSSymbol:
    id: str
    name: str
    type: str  # 'class', 'function', 'variable', etc.
    file: str
    line: int
    column: int
    metadata: Dict[str, object] = field(default_factory=dict)


@dataclass
class JSReference:
    source_id: str
    target_id: str
    type: str
    file: str
    line: int
    column: int
    context: str = ""


class JavaScriptParser:
    """Generic JavaScript parser collecting classes/functions."""

    def __init__(self) -> None:
        self.language = Language(tjs.language())
        self.parser = Parser(self.language)
        self.symbols: Dict[str, JSSymbol] = {}
        self.references: List[JSReference] = []
        self.current_file = ""
        self.content = b""

    def parse_file(self, file_path: str) -> Tuple[List[JSSymbol], List[JSReference]]:
        self.current_file = file_path
        self.symbols.clear()
        self.references.clear()

        with open(file_path, 'rb') as handle:
            self.content = handle.read()

        tree = self.parser.parse(self.content)
        self._traverse(tree.root_node)

        return list(self.symbols.values()), list(self.references)

    # ------------------------------------------------------------------
    # Traversal helpers
    # ------------------------------------------------------------------

    def _traverse(self, node: Node, parent_symbol: Optional[JSSymbol] = None) -> None:
        current_symbol = parent_symbol

        if node.type == 'class_declaration':
            current_symbol = self._register_class(node)
        elif node.type in {'function_declaration', 'method_definition', 'function'}:
            current_symbol = self._register_function(node)
        elif node.type == 'variable_declarator':
            self._register_variable(node, parent_symbol)

        for child in node.children:
            self._traverse(child, current_symbol)

    def _register_class(self, node: Node) -> Optional[JSSymbol]:
        name_node = node.child_by_field_name('name')
        if not name_node:
            return None
        class_name = self._text(name_node)
        symbol_id = self._symbol_id('class', node)
        symbol = JSSymbol(
            id=symbol_id,
            name=class_name,
            type='class',
            file=self.current_file,
            line=node.start_point[0] + 1,
            column=node.start_point[1],
        )
        self.symbols[symbol_id] = symbol
        return symbol

    def _register_function(self, node: Node) -> Optional[JSSymbol]:
        name_node = node.child_by_field_name('name')
        if not name_node:
            return None
        func_name = self._text(name_node)
        symbol_id = self._symbol_id('function', node)
        symbol = JSSymbol(
            id=symbol_id,
            name=func_name,
            type='function',
            file=self.current_file,
            line=node.start_point[0] + 1,
            column=node.start_point[1],
        )
        self.symbols[symbol_id] = symbol
        return symbol

    def _register_variable(self, node: Node, parent_symbol: Optional[JSSymbol]) -> None:
        name_node = node.child_by_field_name('name')
        if not name_node:
            return
        var_name = self._text(name_node)
        symbol_id = self._symbol_id('variable', node)
        symbol = JSSymbol(
            id=symbol_id,
            name=var_name,
            type='variable',
            file=self.current_file,
            line=node.start_point[0] + 1,
            column=node.start_point[1],
        )
        self.symbols[symbol_id] = symbol

    def _text(self, node: Node) -> str:
        return self.content[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')

    def _symbol_id(self, prefix: str, node: Node) -> str:
        return f"js_{prefix}_{node.start_point[0]}_{node.start_point[1]}"
