# JavaScript Parser Implementation Plan

## Goal
Create a comprehensive JavaScript parser using tree-sitter that extracts ALL code elements and relationships for the code graph system, with special support for EspoCRM's mixed JavaScript patterns (ES6, AMD, Backbone.js).

## Strategy Decision
**CHOSEN: Enhance existing tree-sitter parser** 
- Already integrated with Python
- Powerful query language perfect for pattern matching
- Can handle mixed JS patterns (ES6, AMD, Backbone)
- No external process overhead

## Architecture

### 1. Core Parser Enhancement (`plugins/javascript/tree_sitter_enhanced.py`)
- Base tree-sitter integration
- Query execution engine
- Result processing and normalization

### 2. Query Definitions (`plugins/javascript/queries/`)
- `classes.scm` - ES6 classes, methods, properties
- `functions.scm` - Named, arrow, async functions
- `imports.scm` - ES6, CommonJS, AMD patterns
- `api_calls.scm` - fetch, Ajax, WebSocket
- `backbone.scm` - Backbone.View.extend patterns
- `relationships.scm` - CALLS, INSTANTIATES, etc.

### 3. EspoCRM Patterns (`plugins/espocrm/javascript_patterns.py`)
- AMD module resolution
- Backbone component extraction
- Espo.Ajax specific patterns
- View/Model relationships

### 4. API Endpoint Nodes
- Create unique Endpoint nodes for each API call
- Link JavaScript calls to PHP controllers
- Track HTTP methods and parameters

## Implementation Steps

### Phase 1: Base Parser Enhancement ✅ TODO
1. [ ] Update tree-sitter-javascript to latest version
2. [ ] Create query loader and executor
3. [ ] Implement basic node extraction (classes, functions)
4. [ ] Add comprehensive logging and debugging

### Phase 2: Query Development
1. [ ] **Classes & Methods Query**
   ```scheme
   (class_declaration
     name: (identifier) @class_name
     (class_heritage (extends_clause (identifier) @parent_class))?
     body: (class_body
       (method_definition
         name: (property_identifier) @method_name
         parameters: (formal_parameters) @params
       )*
     )
   )
   ```

2. [ ] **AMD Define Query**
   ```scheme
   (call_expression
     function: (identifier) @amd_func (#eq? @amd_func "define")
     arguments: (arguments
       (array (string) @dependency)*
       (function_expression
         parameters: (formal_parameters (identifier) @param)*
         body: (statement_block) @module_body
       )
     )
   )
   ```

3. [ ] **Backbone Component Query**
   ```scheme
   (call_expression
     function: (member_expression
       object: (member_expression
         object: (identifier) @backbone (#eq? @backbone "Backbone")
         property: (property_identifier) @component_type
       )
       property: (property_identifier) @extend (#eq? @extend "extend")
     )
     arguments: (arguments (object) @component_def)
   )
   ```

4. [ ] **API Call Query**
   ```scheme
   ; Espo.Ajax patterns
   (call_expression
     function: (member_expression
       object: (member_expression
         object: (identifier) @espo (#eq? @espo "Espo")
         property: (property_identifier) @ajax (#eq? @ajax "Ajax")
       )
       property: (property_identifier) @method
     )
     arguments: (arguments (string) @endpoint)
   )
   
   ; fetch patterns
   (call_expression
     function: (identifier) @fetch (#eq? @fetch "fetch")
     arguments: (arguments (string) @url)
   )
   ```

### Phase 3: Relationship Extraction
1. [ ] **CALLS relationships**
   - Function calls within scope
   - Method calls on objects
   - Callback patterns

2. [ ] **IMPORTS relationships**
   - ES6 imports
   - CommonJS require
   - AMD dependencies

3. [ ] **EXTENDS relationships**
   - ES6 class inheritance
   - Backbone.extend patterns

4. [ ] **INSTANTIATES relationships**
   - new Class() patterns
   - Factory patterns

### Phase 4: EspoCRM Integration
1. [ ] Parse view definitions
2. [ ] Extract model bindings
3. [ ] Map API calls to endpoints
4. [ ] Handle dynamic module loading

### Phase 5: Cross-Language Linking
1. [ ] Create Endpoint nodes for API calls
2. [ ] Match endpoints to PHP controllers
3. [ ] Link frontend models to backend entities
4. [ ] Track data flow across languages

## Test Cases

### Basic JavaScript
```javascript
// Test: ES6 class with methods
class UserView extends BaseView {
  constructor() { super(); }
  render() { return this; }
}

// Test: Arrow functions
const fetchUser = async (id) => {
  return await fetch(`/api/v1/User/${id}`);
};

// Test: CommonJS
const utils = require('./utils');
module.exports = UserView;
```

### AMD Modules
```javascript
define(['views/base', 'models/user'], function(BaseView, UserModel) {
  return BaseView.extend({
    model: UserModel,
    setup: function() {}
  });
});
```

### Backbone Components
```javascript
const ListView = Backbone.View.extend({
  events: {
    'click .item': 'selectItem'
  },
  selectItem: function(e) {
    this.model.fetch();
  }
});
```

### API Calls
```javascript
// Espo.Ajax
Espo.Ajax.postRequest('User/action/create', data);

// jQuery
$.ajax({
  url: '/api/v1/User',
  method: 'POST',
  data: userData
});

// fetch
fetch('/api/v1/User/' + id, {
  method: 'DELETE'
});
```

## Expected Outputs

### Nodes
- `(:JavaScriptFile {path: '...'})`
- `(:Class {name: 'UserView', extends: 'BaseView'})`
- `(:Function {name: 'fetchUser', async: true})`
- `(:AMDModule {dependencies: ['views/base']})`
- `(:BackboneView {name: 'ListView'})`
- `(:Endpoint {method: 'POST', url: '/api/v1/User'})`

### Relationships
- `(:Class)-[:EXTENDS]->(:Class)`
- `(:Function)-[:CALLS]->(:Function)`
- `(:File)-[:IMPORTS]->(:Module)`
- `(:View)-[:USES_MODEL]->(:Model)`
- `(:Function)-[:CALLS_API]->(:Endpoint)`
- `(:Endpoint)-[:MAPS_TO]->(:PHPController)`

## Success Metrics
1. [ ] Extract 1000+ JavaScript files from EspoCRM
2. [ ] Identify all Backbone views/models
3. [ ] Map 90%+ of API calls to endpoints
4. [ ] Create cross-language relationships
5. [ ] Query traversal from JS to PHP works

## Timeline
- Phase 1-2: 2 hours (Base parser + queries)
- Phase 3: 1 hour (Relationships)
- Phase 4: 1 hour (EspoCRM patterns)
- Phase 5: 1 hour (Cross-language)
- Testing: 1 hour

Total: ~6 hours of implementation