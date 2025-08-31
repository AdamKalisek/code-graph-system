"""Symbol resolution utilities"""

from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
import logging

from .symbol_table import SymbolTable, Symbol, SymbolType

logger = logging.getLogger(__name__)


@dataclass
class ResolutionContext:
    """Context for symbol resolution"""
    current_file: str
    current_namespace: Optional[str] = None
    current_class: Optional[str] = None
    current_function: Optional[str] = None
    imports: Dict[str, str] = None
    use_statements: Dict[str, str] = None
    
    def __post_init__(self):
        if self.imports is None:
            self.imports = {}
        if self.use_statements is None:
            self.use_statements = {}


class SymbolResolver:
    """Resolves symbol references using the symbol table"""
    
    def __init__(self, symbol_table: SymbolTable):
        self.symbol_table = symbol_table
        self.unresolved_references: List[Dict] = []
    
    def resolve_type(self, type_name: str, context: ResolutionContext) -> Optional[Symbol]:
        """Resolve a type reference"""
        # Handle built-in types
        if type_name in ['int', 'string', 'bool', 'float', 'array', 'object', 
                         'void', 'mixed', 'null', 'resource', 'callable']:
            return None
        
        # Handle nullable types
        if type_name.startswith('?'):
            type_name = type_name[1:]
        
        # Handle array types
        if type_name.endswith('[]'):
            type_name = type_name[:-2]
        
        # Try to resolve using symbol table
        return self.symbol_table.resolve(
            type_name,
            context.current_namespace,
            context.imports
        )
    
    def resolve_function_call(self, function_name: str, 
                             context: ResolutionContext) -> Optional[Symbol]:
        """Resolve a function call"""
        # Check if it's a method call on current class
        if context.current_class and not '\\' in function_name:
            class_symbol = self.symbol_table.resolve(
                context.current_class,
                context.current_namespace,
                context.imports
            )
            if class_symbol:
                # Look for method in class
                methods = self.symbol_table.get_children(class_symbol.id)
                for method in methods:
                    if method.type == SymbolType.METHOD and method.name == function_name:
                        return method
        
        # Try to resolve as a function
        return self.symbol_table.resolve(
            function_name,
            context.current_namespace,
            context.imports
        )
    
    def resolve_property_access(self, object_name: str, property_name: str,
                               context: ResolutionContext) -> Optional[Symbol]:
        """Resolve a property access like $obj->property"""
        # First resolve the object type
        # This would need variable type tracking in real implementation
        # For now, we'll try to resolve based on naming conventions
        
        # If object is $this, use current class
        if object_name == 'this' and context.current_class:
            class_symbol = self.symbol_table.resolve(
                context.current_class,
                context.current_namespace,
                context.imports
            )
            if class_symbol:
                properties = self.symbol_table.get_children(class_symbol.id)
                for prop in properties:
                    if prop.type == SymbolType.PROPERTY and prop.name == property_name:
                        return prop
        
        return None
    
    def resolve_class_constant(self, class_name: str, constant_name: str,
                              context: ResolutionContext) -> Optional[Symbol]:
        """Resolve a class constant like ClassName::CONSTANT"""
        # Handle self, parent, static
        if class_name in ['self', 'static'] and context.current_class:
            class_name = context.current_class
        elif class_name == 'parent' and context.current_class:
            # Would need to look up parent class
            class_symbol = self.symbol_table.resolve(
                context.current_class,
                context.current_namespace,
                context.imports
            )
            if class_symbol and class_symbol.extends:
                class_name = class_symbol.extends
        
        # Resolve the class
        class_symbol = self.symbol_table.resolve(
            class_name,
            context.current_namespace,
            context.imports
        )
        
        if class_symbol:
            # Look for constant in class
            constants = self.symbol_table.get_children(class_symbol.id)
            for const in constants:
                if const.type == SymbolType.CONSTANT and const.name == constant_name:
                    return const
        
        return None
    
    def resolve_namespace_parts(self, parts: List[str], 
                               context: ResolutionContext) -> Optional[Symbol]:
        r"""Resolve namespace parts like Namespace\Class\Method"""
        full_name = '\\'.join(parts)
        
        # Try as full name first
        symbol = self.symbol_table.resolve(
            full_name,
            context.current_namespace,
            context.imports
        )
        
        if symbol:
            return symbol
        
        # Try resolving step by step
        current = None
        for i, part in enumerate(parts):
            if i == 0:
                current = self.symbol_table.resolve(
                    part,
                    context.current_namespace,
                    context.imports
                )
            elif current:
                # Look for child with this name
                children = self.symbol_table.get_children(current.id)
                for child in children:
                    if child.name == part:
                        current = child
                        break
                else:
                    return None
        
        return current
    
    def track_unresolved(self, reference_type: str, name: str,
                        context: ResolutionContext, line: int, column: int):
        """Track an unresolved reference for reporting"""
        self.unresolved_references.append({
            'type': reference_type,
            'name': name,
            'file': context.current_file,
            'namespace': context.current_namespace,
            'line': line,
            'column': column
        })
    
    def get_unresolved_report(self) -> Dict[str, List[Dict]]:
        """Get a report of unresolved references grouped by type"""
        report = {}
        for ref in self.unresolved_references:
            ref_type = ref['type']
            if ref_type not in report:
                report[ref_type] = []
            report[ref_type].append(ref)
        return report
    
    def clear_unresolved(self):
        """Clear the unresolved references list"""
        self.unresolved_references = []