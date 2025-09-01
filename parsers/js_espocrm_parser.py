#!/usr/bin/env python3
"""
Enhanced JavaScript Parser for EspoCRM
Detects:
- API endpoint calls (Ajax.postRequest, etc.)
- Backbone.js models/views/collections
- Event handlers (listenTo, on, trigger)
- Dynamic requires
- Template dependencies
"""

import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
import tree_sitter_javascript as tjs
from tree_sitter import Language, Parser, Node

logger = logging.getLogger(__name__)

@dataclass
class JSSymbol:
    """Represents a JavaScript symbol"""
    id: str
    name: str
    type: str  # 'class', 'function', 'api_call', 'event_handler', 'template', etc.
    file: str
    line: int
    column: int
    metadata: Dict = field(default_factory=dict)

@dataclass
class JSReference:
    """Represents a reference between JavaScript entities"""
    source_id: str
    target_id: str
    type: str  # 'CALLS_API', 'EXTENDS_BACKBONE', 'LISTENS_TO', 'REQUIRES', 'USES_TEMPLATE'
    file: str
    line: int
    column: int
    context: str = ""

class EspoCRMJavaScriptParser:
    """Parser specifically tailored for EspoCRM JavaScript patterns"""
    
    # API endpoint patterns
    API_PATTERNS = {
        'postRequest': 'POST',
        'getRequest': 'GET',
        'putRequest': 'PUT',
        'patchRequest': 'PATCH',
        'deleteRequest': 'DELETE',
    }
    
    # Backbone patterns
    BACKBONE_TYPES = {
        'Backbone.Model': 'backbone_model',
        'Backbone.Collection': 'backbone_collection',
        'Backbone.View': 'backbone_view',
        'Backbone.Router': 'backbone_router',
    }
    
    # Event handler methods
    EVENT_METHODS = {
        'listenTo', 'stopListening', 'on', 'off', 'trigger',
        'once', 'listenToOnce', 'bind', 'unbind'
    }
    
    def __init__(self):
        self.language = Language(tjs.language())
        self.parser = Parser(self.language)
        self.symbols: Dict[str, JSSymbol] = {}
        self.references: List[JSReference] = []
        self.current_file = ""
        self.content = b""
        
    def parse_file(self, file_path: str) -> Tuple[List[JSSymbol], List[JSReference]]:
        """Parse a JavaScript file and extract all patterns"""
        self.current_file = file_path
        self.symbols = {}
        self.references = []
        
        with open(file_path, 'rb') as f:
            self.content = f.read()
        
        tree = self.parser.parse(self.content)
        self._traverse(tree.root_node)
        
        return list(self.symbols.values()), self.references
    
    def _traverse(self, node: Node, parent_symbol: Optional[JSSymbol] = None):
        """Traverse the AST and extract patterns"""
        
        # Track current context (class/function)
        current_symbol = parent_symbol
        
        # 1. Detect API calls
        if node.type == 'call_expression':
            self._detect_api_call(node, current_symbol)
            self._detect_dynamic_require(node, current_symbol)
            self._detect_event_handler(node, current_symbol)
        
        # 2. Detect class declarations (ES6 and Backbone)
        elif node.type == 'class_declaration':
            current_symbol = self._detect_class(node)
        
        # 3. Detect function/method declarations
        elif node.type in ['function_declaration', 'method_definition', 'function']:
            name_node = node.child_by_field_name('name')
            if name_node:
                func_name = self._get_node_text(name_node)
                func_id = f"function_{node.start_point[0]}_{node.start_point[1]}"
                current_symbol = JSSymbol(
                    id=func_id,
                    name=func_name,
                    type='function',
                    file=self.current_file,
                    line=node.start_point[0] + 1,
                    column=node.start_point[1],
                    metadata={}
                )
                self.symbols[func_id] = current_symbol
        
        # 4. Detect variable declarations that might be Backbone
        elif node.type == 'variable_declarator':
            self._detect_backbone_declaration(node)
        
        # 5. Detect template references
        elif node.type == 'string' or node.type == 'template_string':
            self._detect_template_reference(node, current_symbol)
        
        # 6. Detect import/export statements
        elif node.type == 'import_statement':
            self._detect_import(node)
        elif node.type == 'export_statement':
            self._detect_export(node)
        
        # Recurse to children
        for child in node.children:
            self._traverse(child, current_symbol)
    
    def _detect_api_call(self, node: Node, parent_symbol: Optional[JSSymbol]):
        """Detect API endpoint calls like Ajax.postRequest('/Lead/action/convert')"""
        function_node = node.child_by_field_name('function')
        if not function_node:
            return
        
        function_text = self._get_node_text(function_node)
        
        # Check for Ajax.* or Espo.Ajax.* patterns
        if 'Ajax' in function_text or 'ajax' in function_text.lower():
            for method, http_method in self.API_PATTERNS.items():
                if method in function_text or method.lower() in function_text.lower():
                    # Get the first argument (endpoint)
                    args_node = node.child_by_field_name('arguments')
                    if args_node and args_node.children:
                        for arg in args_node.children:
                            if arg.type in ['string', 'template_string']:
                                endpoint = self._get_node_text(arg).strip('"\'`')
                                
                                # Create API call symbol
                                api_id = f"api_call_{node.start_point[0]}_{node.start_point[1]}"
                                api_symbol = JSSymbol(
                                    id=api_id,
                                    name=f"{http_method} {endpoint}",
                                    type='api_call',
                                    file=self.current_file,
                                    line=node.start_point[0] + 1,
                                    column=node.start_point[1],
                                    metadata={
                                        'method': http_method,
                                        'endpoint': endpoint,
                                        'function': method
                                    }
                                )
                                self.symbols[api_id] = api_symbol
                                
                                # Create CALLS_API reference
                                if parent_symbol:
                                    self.references.append(JSReference(
                                        source_id=parent_symbol.id,
                                        target_id=api_id,
                                        type='CALLS_API',
                                        file=self.current_file,
                                        line=node.start_point[0] + 1,
                                        column=node.start_point[1],
                                        context=f"{method}('{endpoint}')"
                                    ))
                                
                                # Try to map to PHP controller
                                self._create_php_mapping(endpoint, api_symbol)
                                break
    
    def _detect_event_handler(self, node: Node, parent_symbol: Optional[JSSymbol]):
        """Detect event handler calls like this.listenTo(model, 'change', callback)"""
        function_node = node.child_by_field_name('function')
        if not function_node:
            return
        
        function_text = self._get_node_text(function_node)
        
        # Check if it's an event method
        for event_method in self.EVENT_METHODS:
            if event_method in function_text:
                args_node = node.child_by_field_name('arguments')
                if args_node and len(args_node.children) >= 2:
                    # Get event target and event name
                    target = None
                    event_name = None
                    
                    arg_index = 0
                    for arg in args_node.children:
                        if arg.type == ',':
                            continue
                        if arg_index == 0:
                            target = self._get_node_text(arg)
                        elif arg_index == 1:
                            if arg.type in ['string', 'template_string']:
                                event_name = self._get_node_text(arg).strip('"\'`')
                        arg_index += 1
                    
                    if event_name:
                        # Create event handler symbol
                        event_id = f"event_{node.start_point[0]}_{node.start_point[1]}"
                        event_symbol = JSSymbol(
                            id=event_id,
                            name=f"{event_method}:{event_name}",
                            type='event_handler',
                            file=self.current_file,
                            line=node.start_point[0] + 1,
                            column=node.start_point[1],
                            metadata={
                                'method': event_method,
                                'event': event_name,
                                'target': target
                            }
                        )
                        self.symbols[event_id] = event_symbol
                        
                        # Create LISTENS_TO reference
                        if parent_symbol:
                            self.references.append(JSReference(
                                source_id=parent_symbol.id,
                                target_id=event_id,
                                type='LISTENS_TO',
                                file=self.current_file,
                                line=node.start_point[0] + 1,
                                column=node.start_point[1],
                                context=f"{event_method}({target}, '{event_name}')"
                            ))
                break
    
    def _detect_dynamic_require(self, node: Node, parent_symbol: Optional[JSSymbol]):
        """Detect dynamic require calls like require(['views/' + viewName])"""
        function_node = node.child_by_field_name('function')
        if not function_node:
            return
        
        function_text = self._get_node_text(function_node)
        
        if 'require' in function_text:
            args_node = node.child_by_field_name('arguments')
            if args_node and args_node.children:
                for arg in args_node.children:
                    if arg.type == 'array':
                        # Process array of dependencies
                        for child in arg.children:
                            if child.type in ['string', 'template_string', 'binary_expression']:
                                dep_text = self._get_node_text(child)
                                
                                # Create dynamic require symbol
                                req_id = f"dynamic_require_{node.start_point[0]}_{node.start_point[1]}"
                                req_symbol = JSSymbol(
                                    id=req_id,
                                    name=f"require({dep_text})",
                                    type='dynamic_require',
                                    file=self.current_file,
                                    line=node.start_point[0] + 1,
                                    column=node.start_point[1],
                                    metadata={
                                        'dependency': dep_text,
                                        'is_dynamic': '+' in dep_text or '${' in dep_text
                                    }
                                )
                                self.symbols[req_id] = req_symbol
                                
                                # Create REQUIRES reference
                                if parent_symbol:
                                    self.references.append(JSReference(
                                        source_id=parent_symbol.id,
                                        target_id=req_id,
                                        type='REQUIRES_DYNAMIC',
                                        file=self.current_file,
                                        line=node.start_point[0] + 1,
                                        column=node.start_point[1],
                                        context=f"require([{dep_text}])"
                                    ))
    
    def _detect_template_reference(self, node: Node, parent_symbol: Optional[JSSymbol]):
        """Detect template file references like 'record/detail.tpl'"""
        text = self._get_node_text(node).strip('"\'`')
        
        if '.tpl' in text or ('template' in text.lower() and '/' in text):
            # Create template reference symbol
            tpl_id = f"template_{node.start_point[0]}_{node.start_point[1]}"
            tpl_symbol = JSSymbol(
                id=tpl_id,
                name=text,
                type='template',
                file=self.current_file,
                line=node.start_point[0] + 1,
                column=node.start_point[1],
                metadata={
                    'template_path': text
                }
            )
            self.symbols[tpl_id] = tpl_symbol
            
            # Create USES_TEMPLATE reference
            if parent_symbol:
                self.references.append(JSReference(
                    source_id=parent_symbol.id,
                    target_id=tpl_id,
                    type='USES_TEMPLATE',
                    file=self.current_file,
                    line=node.start_point[0] + 1,
                    column=node.start_point[1],
                    context=f"template: '{text}'"
                ))
    
    def _detect_backbone_declaration(self, node: Node):
        """Detect Backbone model/view/collection declarations"""
        init_node = node.child_by_field_name('value')
        if not init_node:
            return
        
        init_text = self._get_node_text(init_node)
        
        for backbone_type, symbol_type in self.BACKBONE_TYPES.items():
            if backbone_type in init_text or f"extend(" in init_text:
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = self._get_node_text(name_node)
                    
                    # Create Backbone symbol
                    bb_id = f"backbone_{node.start_point[0]}_{node.start_point[1]}"
                    bb_symbol = JSSymbol(
                        id=bb_id,
                        name=name,
                        type=symbol_type,
                        file=self.current_file,
                        line=node.start_point[0] + 1,
                        column=node.start_point[1],
                        metadata={
                            'backbone_type': backbone_type
                        }
                    )
                    self.symbols[bb_id] = bb_symbol
                    
                    # Traverse the object for methods and properties
                    self._extract_backbone_members(init_node, bb_symbol)
                    break
    
    def _detect_class(self, node: Node) -> JSSymbol:
        """Detect ES6 class declarations"""
        name_node = node.child_by_field_name('name')
        if not name_node:
            return None
        
        class_name = self._get_node_text(name_node)
        
        # Check if it extends a Backbone class
        heritage_node = node.child_by_field_name('heritage')
        extends_backbone = False
        parent_class = None
        
        if heritage_node:
            for child in heritage_node.children:
                if child.type == 'identifier':
                    parent_class = self._get_node_text(child)
                    if 'View' in parent_class or 'Model' in parent_class:
                        extends_backbone = True
        
        # Create class symbol
        class_id = f"class_{node.start_point[0]}_{node.start_point[1]}"
        class_symbol = JSSymbol(
            id=class_id,
            name=class_name,
            type='backbone_view' if extends_backbone else 'class',
            file=self.current_file,
            line=node.start_point[0] + 1,
            column=node.start_point[1],
            metadata={
                'extends': parent_class,
                'is_backbone': extends_backbone
            }
        )
        self.symbols[class_id] = class_symbol
        
        # Process class body
        body_node = node.child_by_field_name('body')
        if body_node:
            self._extract_class_members(body_node, class_symbol)
        
        return class_symbol
    
    def _extract_class_members(self, body_node: Node, class_symbol: JSSymbol):
        """Extract methods and properties from a class body"""
        for child in body_node.children:
            if child.type == 'method_definition':
                self._traverse(child, class_symbol)
            elif child.type == 'field_definition':
                self._traverse(child, class_symbol)
    
    def _extract_backbone_members(self, obj_node: Node, bb_symbol: JSSymbol):
        """Extract members from a Backbone object literal"""
        if obj_node.type == 'object':
            for child in obj_node.children:
                if child.type == 'pair':
                    key_node = child.child_by_field_name('key')
                    value_node = child.child_by_field_name('value')
                    if key_node:
                        key = self._get_node_text(key_node).strip('"\'')
                        
                        # Check for special Backbone properties
                        if key in ['events', 'triggers', 'routes']:
                            self._process_backbone_events(value_node, bb_symbol, key)
                        elif key == 'template':
                            self._detect_template_reference(value_node, bb_symbol)
    
    def _process_backbone_events(self, value_node: Node, bb_symbol: JSSymbol, event_type: str):
        """Process Backbone events hash"""
        if value_node.type == 'object':
            for child in value_node.children:
                if child.type == 'pair':
                    key_node = child.child_by_field_name('key')
                    if key_node:
                        event_name = self._get_node_text(key_node).strip('"\'')
                        
                        # Create event symbol
                        event_id = f"bb_event_{child.start_point[0]}_{child.start_point[1]}"
                        event_symbol = JSSymbol(
                            id=event_id,
                            name=event_name,
                            type=f'backbone_{event_type}',
                            file=self.current_file,
                            line=child.start_point[0] + 1,
                            column=child.start_point[1],
                            metadata={
                                'event_type': event_type,
                                'event_name': event_name
                            }
                        )
                        self.symbols[event_id] = event_symbol
                        
                        # Create reference
                        self.references.append(JSReference(
                            source_id=bb_symbol.id,
                            target_id=event_id,
                            type='HAS_EVENT',
                            file=self.current_file,
                            line=child.start_point[0] + 1,
                            column=child.start_point[1],
                            context=f"{event_type}: '{event_name}'"
                        ))
    
    def _detect_import(self, node: Node):
        """Detect ES6 import statements"""
        source_node = node.child_by_field_name('source')
        if source_node:
            source = self._get_node_text(source_node).strip('"\'')
            
            # Create import symbol
            import_id = f"import_{node.start_point[0]}_{node.start_point[1]}"
            import_symbol = JSSymbol(
                id=import_id,
                name=source,
                type='import',
                file=self.current_file,
                line=node.start_point[0] + 1,
                column=node.start_point[1],
                metadata={
                    'source': source
                }
            )
            self.symbols[import_id] = import_symbol
    
    def _detect_export(self, node: Node):
        """Detect ES6 export statements"""
        # Create export symbol
        export_id = f"export_{node.start_point[0]}_{node.start_point[1]}"
        export_symbol = JSSymbol(
            id=export_id,
            name='export',
            type='export',
            file=self.current_file,
            line=node.start_point[0] + 1,
            column=node.start_point[1],
            metadata={}
        )
        self.symbols[export_id] = export_symbol
    
    def _create_php_mapping(self, endpoint: str, api_symbol: JSSymbol):
        """Create a mapping to PHP controller based on endpoint"""
        # Parse endpoint like '/Lead/action/convert' -> LeadController::actionConvert
        parts = endpoint.strip('/').split('/')
        if len(parts) >= 2:
            controller = parts[0]
            action = parts[1] if len(parts) > 1 else 'index'
            
            # Handle 'action/' prefix
            if action == 'action' and len(parts) > 2:
                action = parts[2]
            
            # Create PHP target reference
            php_controller = f"{controller}Controller"
            php_method = f"action{action.capitalize()}" if action != 'index' else 'actionIndex'
            
            api_symbol.metadata['php_controller'] = php_controller
            api_symbol.metadata['php_method'] = php_method
            
            # This will be used later to create cross-language references
    
    def _get_node_text(self, node: Node) -> str:
        """Get text content of a node"""
        return self.content[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
    
    def get_stats(self) -> Dict:
        """Get parsing statistics"""
        stats = {
            'total_symbols': len(self.symbols),
            'total_references': len(self.references),
            'api_calls': sum(1 for s in self.symbols.values() if s.type == 'api_call'),
            'backbone_models': sum(1 for s in self.symbols.values() if 'backbone' in s.type),
            'event_handlers': sum(1 for s in self.symbols.values() if s.type == 'event_handler'),
            'dynamic_requires': sum(1 for s in self.symbols.values() if s.type == 'dynamic_require'),
            'templates': sum(1 for s in self.symbols.values() if s.type == 'template'),
        }
        
        # Count reference types
        ref_types = {}
        for ref in self.references:
            ref_types[ref.type] = ref_types.get(ref.type, 0) + 1
        stats['reference_types'] = ref_types
        
        return stats