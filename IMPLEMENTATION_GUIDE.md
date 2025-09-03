# Implementation Guide - Adding Missing Features

## 🎯 Priority 1: Add OVERRIDES and IMPLEMENTS_METHOD Relationships

### Problem:
- 297 methods override parent methods but have no OVERRIDES relationship
- 634 methods implement interface methods but have no IMPLEMENTS_METHOD relationship

### Solution:
Add to `parsers/php_reference_resolver.py` after DEFINES creation:

```python
def _create_inheritance_relationships(self):
    """Create OVERRIDES and IMPLEMENTS_METHOD relationships"""
    
    # Find all class inheritance
    extends = self.conn.execute("""
        SELECT s1.id as child_id, s2.id as parent_id
        FROM symbol_references sr
        JOIN symbols s1 ON sr.source_id = s1.id
        JOIN symbols s2 ON sr.target_id = s2.id
        WHERE sr.reference_type = 'EXTENDS'
        AND s1.type = 'class' AND s2.type = 'class'
    """).fetchall()
    
    for child_id, parent_id in extends:
        # Get methods from both classes
        child_methods = self._get_class_methods(child_id)
        parent_methods = self._get_class_methods(parent_id)
        
        # Find matching method names
        for cm in child_methods:
            for pm in parent_methods:
                if cm['name'] == pm['name']:
                    # Create OVERRIDES relationship
                    self.symbol_table.add_reference(
                        source_id=cm['id'],
                        target_id=pm['id'],
                        reference_type='OVERRIDES',
                        line=cm['line'],
                        context='method_override'
                    )
```

## 🎯 Priority 2: Capture Method Parameters

### Problem:
No parameter metadata (names, types, defaults, by-reference)

### Solution:
Modify `parsers/php_enhanced.py` to extract parameters:

```python
def _extract_method_params(self, method_node):
    """Extract method parameters with full metadata"""
    params = []
    param_list = self._find_child_by_type(method_node, 'formal_parameters')
    
    if param_list:
        for param in self._get_children_by_type(param_list, 'simple_parameter'):
            param_info = {
                'name': self._get_node_text(param, 'variable_name'),
                'type': None,
                'default': None,
                'by_reference': False,
                'variadic': False
            }
            
            # Check for type hint
            type_node = self._find_child_by_type(param, 'type')
            if type_node:
                param_info['type'] = self._get_node_text(type_node)
            
            # Check for default value
            default_node = self._find_child_by_type(param, 'default')
            if default_node:
                param_info['default'] = self._get_node_text(default_node)
            
            # Check for by-reference (&)
            if '&' in self._get_node_text(param):
                param_info['by_reference'] = True
            
            # Check for variadic (...)
            if '...' in self._get_node_text(param):
                param_info['variadic'] = True
            
            params.append(param_info)
    
    return json.dumps(params)  # Store as JSON in parameters column
```

### Database Schema Update:
```sql
ALTER TABLE symbols ADD COLUMN parameters TEXT;  -- JSON array
```

## 🎯 Priority 3: Parse and Store DocBlocks

### Problem:
Missing @param, @throws, @return annotations from DocBlocks

### Solution:
Add DocBlock parser to `parsers/php_enhanced.py`:

```python
def _extract_docblock(self, node):
    """Extract and parse PHPDoc comments"""
    # Look for comment node before the current node
    prev_sibling = node.prev_sibling
    if prev_sibling and prev_sibling.type == 'comment':
        docblock_text = self._get_node_text(prev_sibling)
        
        if docblock_text.startswith('/**'):
            docblock_data = {
                'raw': docblock_text,
                'description': '',
                'params': [],
                'returns': None,
                'throws': []
            }
            
            # Parse @param
            param_pattern = r'@param\s+(\S+)\s+(\$\w+)\s*(.*)?'
            for match in re.finditer(param_pattern, docblock_text):
                docblock_data['params'].append({
                    'type': match.group(1),
                    'name': match.group(2),
                    'description': match.group(3) or ''
                })
            
            # Parse @throws
            throws_pattern = r'@throws\s+(\S+)'
            for match in re.finditer(throws_pattern, docblock_text):
                docblock_data['throws'].append(match.group(1))
                
            # Parse @return
            return_match = re.search(r'@return\s+(\S+)', docblock_text)
            if return_match:
                docblock_data['returns'] = return_match.group(1)
            
            return json.dumps(docblock_data)
    
    return None
```

### Create THROWS Relationships:
```python
# After parsing DocBlock
if docblock_data['throws']:
    for exception_class in docblock_data['throws']:
        # Find exception class symbol
        exception_id = self._resolve_class_name(exception_class)
        if exception_id:
            self.symbol_table.add_reference(
                source_id=method_id,
                target_id=exception_id,
                reference_type='THROWS',
                line=line_number
            )
```

## 🎯 Priority 4: Implement Namespace Resolver

### Problem:
Can't resolve `use...as` aliases, grouped imports, or relative names

### Solution:
Create `parsers/namespace_resolver.py`:

```python
class NamespaceResolver:
    def __init__(self):
        self.current_namespace = None
        self.use_statements = {}  # alias -> FQN
        self.class_context = None
        
    def enter_namespace(self, namespace: str):
        """Set current namespace context"""
        self.current_namespace = namespace
        self.use_statements.clear()
        
    def add_use_statement(self, fqn: str, alias: str = None):
        """Register a use statement"""
        if alias:
            self.use_statements[alias] = fqn
        else:
            # Extract class name from FQN
            parts = fqn.split('\\')
            self.use_statements[parts[-1]] = fqn
            
    def add_grouped_use(self, base: str, items: List[Tuple[str, str]]):
        """Handle grouped use statements: use A\{B, C as D}"""
        for name, alias in items:
            full_name = f"{base}\\{name}"
            self.add_use_statement(full_name, alias or name)
            
    def resolve(self, name: str, context: str = 'class') -> str:
        """Resolve a name to fully qualified name"""
        # Handle special keywords
        if name == 'self':
            return self.class_context
        elif name == 'parent':
            return self._get_parent_class()
        elif name == 'static':
            return self.class_context  # Late static binding
            
        # Check if it's already fully qualified
        if name.startswith('\\'):
            return name[1:]
            
        # Check use statements
        if name in self.use_statements:
            return self.use_statements[name]
            
        # Check if it's a built-in type
        if name in ['string', 'int', 'bool', 'array', 'float', 'object', 'mixed', 'void']:
            return name
            
        # Resolve relative to current namespace
        if self.current_namespace:
            return f"{self.current_namespace}\\{name}"
            
        return name
```

## 🎯 Priority 5: Add PHP 8+ Features Support

### Problem:
Missing union types, attributes, readonly, enums

### Solution for Union Types:
```python
def _parse_union_type(self, type_node):
    """Parse PHP 8 union types like int|string"""
    if type_node.type == 'union_type':
        types = []
        for child in type_node.children:
            if child.type == 'named_type':
                types.append(self._get_node_text(child))
        return '|'.join(types)
    return self._get_node_text(type_node)
```

### Solution for Attributes:
```python
def _extract_attributes(self, node):
    """Extract PHP 8 attributes #[...]"""
    attributes = []
    
    # Look for attribute_group nodes
    for child in node.children:
        if child.type == 'attribute_group':
            for attr in self._get_children_by_type(child, 'attribute'):
                attr_data = {
                    'name': self._get_attribute_name(attr),
                    'arguments': self._get_attribute_args(attr)
                }
                attributes.append(attr_data)
                
                # Create HAS_ATTRIBUTE relationship
                self.symbol_table.add_reference(
                    source_id=symbol_id,
                    target_id=f"attribute_{attr_data['name']}",
                    reference_type='HAS_ATTRIBUTE',
                    line=attr.start_point[0]
                )
    
    return json.dumps(attributes) if attributes else None
```

### Database Schema Updates:
```sql
ALTER TABLE symbols ADD COLUMN union_types TEXT;
ALTER TABLE symbols ADD COLUMN attributes TEXT;  -- JSON
ALTER TABLE symbols ADD COLUMN is_readonly BOOLEAN DEFAULT FALSE;
ALTER TABLE symbols ADD COLUMN is_enum BOOLEAN DEFAULT FALSE;
ALTER TABLE symbols ADD COLUMN enum_cases TEXT;  -- JSON for enum cases
```

## 🎯 Priority 6: Replace JavaScript Parser

### Problem:
Regex-based parsing is inadequate for modern JavaScript

### Solution:
Install and use tree-sitter-javascript:

```bash
pip install tree-sitter tree-sitter-javascript
```

Create `parsers/js_tree_sitter_parser.py`:

```python
import tree_sitter_javascript as tsjs
from tree_sitter import Language, Parser

class JavaScriptTreeSitterParser:
    def __init__(self):
        JS_LANGUAGE = Language(tsjs.language(), 'javascript')
        self.parser = Parser()
        self.parser.set_language(JS_LANGUAGE)
        
    def parse_file(self, file_path: str):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        tree = self.parser.parse(bytes(content, 'utf8'))
        
        symbols = []
        references = []
        
        # Walk the AST
        self._walk_tree(tree.root_node, symbols, references, file_path)
        
        return symbols, references
        
    def _walk_tree(self, node, symbols, references, file_path):
        """Recursively walk the AST"""
        
        # Handle different node types
        if node.type == 'class_declaration':
            self._extract_class(node, symbols, file_path)
        elif node.type == 'function_declaration':
            self._extract_function(node, symbols, file_path)
        elif node.type == 'method_definition':
            self._extract_method(node, symbols, file_path)
        elif node.type == 'variable_declaration':
            self._extract_variable(node, symbols, file_path)
        elif node.type == 'import_statement':
            self._extract_import(node, references, file_path)
        elif node.type == 'call_expression':
            self._extract_call(node, references, file_path)
            
        # Recurse to children
        for child in node.children:
            self._walk_tree(child, symbols, references, file_path)
```

## 🎯 Priority 7: Add READS vs WRITES Tracking

### Problem:
Can't differentiate between reading and writing properties

### Solution:
Modify property access detection:

```python
def _determine_access_type(self, access_node):
    """Determine if property access is READ or WRITE"""
    parent = access_node.parent
    
    # Check if it's on the left side of assignment
    if parent and parent.type == 'assignment_expression':
        left_side = parent.children[0]
        if access_node == left_side or access_node in self._get_all_descendants(left_side):
            return 'WRITE'
    
    # Check if it's being modified (++, --, +=, etc.)
    if parent and parent.type in ['update_expression', 'augmented_assignment_expression']:
        return 'WRITE'
        
    # Check if it's in a unset() call
    if self._is_in_unset_call(access_node):
        return 'WRITE'
        
    return 'READ'
```

Then create separate relationships:
```python
access_type = self._determine_access_type(property_access_node)
reference_type = 'READS' if access_type == 'READ' else 'WRITES'

self.symbol_table.add_reference(
    source_id=method_id,
    target_id=property_id,
    reference_type=reference_type,
    line=line_number,
    context=f"property_{access_type.lower()}"
)
```

## 🚀 Testing Each Implementation

### Test OVERRIDES:
```cypher
MATCH (c:PHPMethod)-[:OVERRIDES]->(p:PHPMethod)
RETURN c.name, p.name LIMIT 10
```

### Test Parameters:
```cypher
MATCH (m:PHPMethod) 
WHERE m.parameters IS NOT NULL
RETURN m.name, m.parameters LIMIT 10
```

### Test DocBlocks:
```cypher
MATCH (m:PHPMethod)-[:THROWS]->(e)
RETURN m.name, e.name LIMIT 10
```

### Test PHP 8 Features:
```cypher
MATCH (n) 
WHERE n.union_types IS NOT NULL 
   OR n.attributes IS NOT NULL
   OR n.is_readonly = true
RETURN n.name, n.union_types, n.attributes
```

## 📋 Implementation Checklist

- [ ] Add OVERRIDES relationships (297 missing)
- [ ] Add IMPLEMENTS_METHOD relationships (634 missing)  
- [ ] Capture method parameters metadata
- [ ] Parse and store DocBlocks
- [ ] Create THROWS relationships from @throws
- [ ] Implement NamespaceResolver class
- [ ] Add union type support
- [ ] Add PHP attributes support
- [ ] Add readonly property support
- [ ] Replace JS regex parser with tree-sitter
- [ ] Add READS vs WRITES distinction
- [ ] Add SQLite WAL mode
- [ ] Add incremental analysis with run_id

## 💡 Tips

1. **Test incrementally** - Implement one feature at a time
2. **Backup databases** - Before major changes
3. **Profile performance** - Use `time` and `memory_profiler`
4. **Validate relationships** - Check counts match expectations
5. **Document changes** - Update this guide as you implement

---

**Remember**: The goal is to capture **100% of codebase semantics** for comprehensive analysis!