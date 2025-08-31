# Code Graph Edge Design Requirements
## For Building a System "Better Than Grep"

## Current State Analysis

### What We Have (Existing Edges)
- **DEFINED_IN** - Symbol defined in file
- **HAS_METHOD** - Class has method
- **HAS_PROPERTY** - Class has property  
- **CALLS** - Method/function calls another
- **EXTENDS** - Class inheritance
- **IMPORTS** - Module imports (partially working)
- **CALLS_API** - Frontend calls backend API
- **READS/WRITES** - Property access
- **INSTANTIATES** - Creates new instance
- **MODEL_OPERATION** - Database operations
- **THROWS** - Exception throwing
- **IN_DIRECTORY/CONTAINS** - File system structure

### Critical Missing Edges (Why We Can't Beat Grep)

## 1. UNIVERSAL EDGES (Language Agnostic - Architectural Necessity)

### A. Import/Dependency Edges ⚠️ **CRITICAL MISSING**
```
USES_NAMESPACE     - PHP: use Espo\Core\Mail
IMPORTS_CLASS      - PHP: use EmailSender
IMPORTS_FUNCTION   - PHP: use function array_map
REQUIRES_MODULE    - JS: require('./module')
IMPORTS_ES6        - JS: import { Component } from 'react'
INCLUDES_FILE      - PHP: include/require
```
**Why Critical:** Without these, we can't trace what libraries/classes are actually used

### B. Type System Edges ⚠️ **CRITICAL MISSING**
```
IMPLEMENTS         - Interface implementation
RETURNS_TYPE       - Method return type
ACCEPTS_TYPE       - Parameter type hints
CASTS_TO          - Type casting
INSTANCEOF        - Type checking
```
**Why Critical:** Modern code heavily relies on interfaces and type contracts

### C. Dependency Injection Edges ⚠️ **CRITICAL MISSING**
```
INJECTS           - Constructor/setter injection
PROVIDES          - DI container provisions
BINDS_TO          - Interface to implementation binding
RESOLVES_TO       - Runtime resolution
```
**Why Critical:** Most frameworks use DI - can't trace execution without this

### D. Event System Edges
```
LISTENS_TO        - Event listener registration
EMITS             - Event emission
HANDLES           - Event handler
SUBSCRIBES_TO     - Observable/pub-sub
```
**Why Critical:** Async/event-driven code is invisible without these

### E. Configuration Edges
```
CONFIGURED_BY     - Config file relationship
ROUTES_TO         - URL routing to controller
MAPS_TO          - Config key to handler
ALIASES          - Aliased classes/functions
```
**Why Critical:** Runtime behavior depends on configuration

### F. Data Flow Edges
```
TRANSFORMS       - Data transformation
VALIDATES        - Input validation
SERIALIZES       - Object serialization
QUERIES          - Database queries (with query text)
FETCHES          - HTTP/API calls
```

### G. Control Flow Edges
```
CATCHES          - Exception handling
YIELDS           - Generator functions
AWAITS           - Async/await
DELEGATES_TO     - Delegation pattern
DECORATES        - Decorator pattern
```

### H. Documentation Edges
```
DOCUMENTS        - PHPDoc/JSDoc relationships
DEPRECATED_BY    - Deprecation chains
REPLACES         - API evolution
ANNOTATED_WITH   - Annotations/decorators
```

## 2. FRAMEWORK-SPECIFIC EDGES

### PHP/Laravel/Symfony Patterns
```
MIDDLEWARE        - Middleware chain
SERVICE_PROVIDER  - Service registration
FACADE           - Facade pattern
TRAIT_USE        - PHP traits
MAGIC_METHOD     - __call, __get handlers
```

### JavaScript/React/Vue Patterns
```
RENDERS          - Component rendering
PROPS_TO         - Props passing
STATE_OF         - State management
HOOKS            - React hooks usage
COMPUTED_FROM    - Vue computed properties
```

### EspoCRM Specific
```
ENTITY_RELATION  - Entity relationships
ACL_CONTROLLED   - Access control
WORKFLOW_TRIGGER - Workflow connections
FORMULA          - Formula script usage
```

## 3. ENHANCED EXISTING EDGES

### CALLS Edge Enhancement
Current: Simple method call
Enhanced needs:
- **call_type**: direct, dynamic, reflection, callback
- **parameters**: Parameter mapping
- **async**: true/false
- **conditional**: Inside if/switch/ternary

### IMPORTS Edge Enhancement
Current: Basic import
Enhanced needs:
- **import_type**: namespace, class, function, constant
- **alias**: Aliased name
- **partial**: Specific exports imported
- **dynamic**: Runtime imports

## Implementation Priority

### Phase 1: Critical Universal Edges (Must Have)
1. **USES_NAMESPACE/IMPORTS_CLASS** - Fix import tracking
2. **IMPLEMENTS** - Interface contracts
3. **INJECTS/PROVIDES** - Dependency injection
4. **CONFIGURED_BY/ROUTES_TO** - Configuration

### Phase 2: Better Than Grep (Should Have)
1. **LISTENS_TO/EMITS** - Event systems
2. **RETURNS_TYPE/ACCEPTS_TYPE** - Type system
3. **QUERIES** - Database operations with SQL
4. **TRANSFORMS** - Data flow

### Phase 3: Advanced Analysis (Nice to Have)
1. **DOCUMENTS** - Documentation links
2. **DEPRECATED_BY** - API evolution
3. Framework-specific patterns

## Neo4j Scalability Context

**Production Limits (2025):**
- **Nodes**: 34.4 billion (expanding to 1 trillion)
- **Relationships**: 1+ trillion demonstrated
- **Real-world**: NASA uses billions of nodes
- **Performance**: 6.2M nodes/second loading

**For Code Graphs:**
- Linux kernel: ~15M LOC = ~500K nodes realistic
- Large enterprise: ~10M LOC = ~300K nodes
- With all edges: ~5-10M relationships
- **Conclusion**: Neo4j can handle any codebase

## Success Metrics

To be "Better Than Grep" we need:

1. **Query Speed**: Find mail sending in <100ms (grep takes seconds)
2. **Completeness**: >90% of execution paths traceable
3. **Accuracy**: No false positives from text matching
4. **Context**: Full call stack in one query
5. **Impact**: "What breaks if I change this?" in one query

## Example Queries That Should Work

```cypher
// Find complete mail sending flow (currently fails)
MATCH path = (entry:Method)-[:CALLS|INJECTS|CONFIGURED_BY*1..10]->(mail:Method)
WHERE mail.name =~ '.*send.*' 
  AND (mail)-[:USES_NAMESPACE]->(:Namespace {name: 'Laminas\\Mail'})
RETURN path

// Find all implementations of an interface (currently missing)
MATCH (interface:Interface {name: 'MailerInterface'})
      <-[:IMPLEMENTS]-(implementation:Class)
      -[:HAS_METHOD]->(method:Method)
RETURN implementation, collect(method)

// Trace event flow (currently impossible)
MATCH path = (emitter)-[:EMITS]->(event:Event)<-[:LISTENS_TO]-(handler)
WHERE event.name = 'user.registered'
RETURN path
```

## Conclusion

**Current State**: We have 30% of needed edges
**To Beat Grep**: Need 80% of Universal edges
**To Excel**: Need Universal + Framework edges

The vision IS right - graph databases ARE designed for this. We just need complete edge extraction.