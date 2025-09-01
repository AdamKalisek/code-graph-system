# Next Fix Plan - Complete EspoCRM Graph Implementation

## Current Achievement ✅
Successfully indexed entire EspoCRM:
- **3,051 PHP files** parsed
- **1,083 JavaScript files** (file nodes only)
- **413 metadata JSON** files
- **2,205 directories** with filesystem structure
- **25,581 nodes** and **24,497 relationships** in Neo4j
- Performance: **1357 nodes/second**

## O3's Priority Recommendations 🎯

### Priority 1: AST-Based PHP Parser (CRITICAL)
**Why First:** Every downstream feature depends on accurate PHP parsing
**Solution:** Integrate `nikic/PHP-Parser` or `tree-sitter-php`
**Benefits:**
- Stable FQN (Fully Qualified Names) as primary keys
- Accurate EXTENDS/IMPLEMENTS resolution
- Proper inheritance chains
- Foundation for cross-language links

### Priority 2: Multi-Label Support
**Implementation:** During parser refactor
```cypher
MERGE (c:Symbol:PHP:Class {fqn: row.fqn})
```
**Benefits:** 2-4× faster queries, removes property filters

### Priority 3: JavaScript Parser
**Tools:** tree-sitter or Babel parser
**Focus Areas:**
- import/require/export statements
- function/class definitions
- fetch()/$.ajax/axios calls with literal strings
- Route definitions

### Priority 4: Cross-Language References
**Design:** Introduce `:Endpoint` abstraction
```
(:Endpoint {method:"GET", path:"/api/v1/accounts"})
PHP: (:Controller)-[:HANDLES]->(:Endpoint)
JS: (:Module)-[:CALLS]->(:Endpoint)
```

### Priority 5: Performance Optimization
- Batch sizes: 5k-10k rows per UNWIND
- Create indexes before ingest
- Use `apoc.periodic.iterate` for updates

## Implementation Plan 📋

### Phase 1: PHP Parser Replacement (Week 1)
```bash
# Install nikic/PHP-Parser
composer require nikic/php-parser

# Or use tree-sitter
npm install tree-sitter tree-sitter-php
```

**Tasks:**
1. [ ] Create AST-based PHP parser
2. [ ] Generate stable FQNs: `Namespace\Class::method`
3. [ ] Populate EXTENDS/IMPLEMENTS with resolved targets
4. [ ] Mark unresolved with `:Unresolved` label
5. [ ] Add multi-labeling: `:Symbol:PHP:Class`

### Phase 2: Graph Structure Optimization (Week 1)
**Directory Model:**
```
(:Directory {path, depth})-[:CONTAINS {order}]->(:File)
(:File)-[:DECLARES]->(:Symbol)
```

**Indexes:**
```cypher
CREATE INDEX sym_fqn IF NOT EXISTS FOR (s:Symbol) ON (s.fqn);
CREATE INDEX file_path IF NOT EXISTS FOR (f:File) ON (f.path);
CREATE INDEX endpoint_path IF NOT EXISTS FOR (e:Endpoint) ON (e.path);
```

### Phase 3: JavaScript Parser (Week 2)
**Tree-sitter Integration:**
```python
import tree_sitter
from tree_sitter_javascript import Language

parser = tree_sitter.Parser()
parser.set_language(Language(tree_sitter_javascript.language()))

# Parse JS file
tree = parser.parse(bytes(js_content, "utf8"))
root = tree.root_node

# Extract:
# - ES6 imports/exports
# - Class/function definitions  
# - API calls with literal URLs
```

### Phase 4: Endpoint Abstraction (Week 2)
**Model:**
```python
# PHP Controller
endpoint = Endpoint(
    method="GET",
    path="/api/v1/Lead",
    controller="Lead",
    action="list"
)

# JS Ajax Call
call = AjaxCall(
    file="client/src/views/lead/list.js",
    line=42,
    endpoint_path="/api/v1/Lead"
)

# Create relationships
(:Controller)-[:HANDLES]->(:Endpoint)
(:JSModule)-[:CALLS]->(:Endpoint)
```

### Phase 5: Complete Cross-References (Week 3)
1. **Route Mapping:**
   - Parse routes.json → Create Endpoint nodes
   - Link Controllers to Endpoints

2. **API Call Tracking:**
   - Parse JS fetch/ajax calls
   - Link to Endpoint nodes

3. **Event System:**
   - Create `:Event` nodes for hooks
   - Link publishers and subscribers

## Expected Outcomes 🎯

### After Phase 1-2:
- Accurate PHP inheritance chains
- 2-4× faster queries with multi-labels
- Resolved EXTENDS/IMPLEMENTS relationships

### After Phase 3-4:
- Complete JavaScript module graph
- Frontend-backend connections visible
- API dependency tracking

### After Phase 5:
- Full cross-language impact analysis
- "Change PHP endpoint → find affected JS views"
- Complete EspoCRM system graph

## Query Examples After Implementation

```cypher
// Find all JS modules calling a PHP endpoint
MATCH (js:Symbol:JavaScript:Module)-[:CALLS]->(e:Endpoint)
      <-[:HANDLES]-(php:Symbol:PHP:Controller)
WHERE php.name = 'LeadController'
RETURN js.path, e.path, php.fqn

// Impact analysis for API change
MATCH (e:Endpoint {path: '/api/v1/Lead'})<-[:CALLS]-(consumer)
RETURN consumer.path, consumer.type
ORDER BY consumer.type

// Find unused endpoints
MATCH (e:Endpoint)
WHERE NOT (e)<-[:CALLS]-()
RETURN e.path, e.method

// Cross-language dependency tree
MATCH path = (js:JavaScript:Module)-[:CALLS*1..3]->(php:PHP:Class)
RETURN path
```

## Success Metrics 📊

### Phase 1 Success:
- [ ] 100% of PHP inheritance resolved
- [ ] Multi-labels on all nodes
- [ ] Query performance improved 2×

### Phase 2 Success:
- [ ] Directory structure navigable
- [ ] File→Symbol relationships clear
- [ ] Indexes reduce query time <100ms

### Phase 3 Success:
- [ ] 1000+ JS modules parsed
- [ ] ES6 imports mapped
- [ ] API calls extracted

### Phase 4 Success:
- [ ] All routes mapped to endpoints
- [ ] PHP controllers linked
- [ ] JS calls linked

### Phase 5 Success:
- [ ] Cross-language queries working
- [ ] Impact analysis accurate
- [ ] Complete system graph

## Technical Debt to Address

1. **Regex PHP Parser:** Replace immediately (Priority 1)
2. **Missing JS Parser:** Implement Week 2
3. **Unresolved References:** Fix with AST parser
4. **Single Labels:** Add multi-label support
5. **No Endpoints:** Create abstraction layer

## Next Immediate Steps

1. **Today:** Start nikic/PHP-Parser integration
2. **Tomorrow:** Implement multi-labeling
3. **This Week:** Complete PHP parser replacement
4. **Next Week:** JavaScript parser with tree-sitter

---

## Conclusion

With O3's architectural guidance, we have a clear path to complete the EspoCRM graph implementation. The system already works well (25k+ nodes indexed), but needs these improvements for production-quality cross-language analysis.

Priority is clear: **Fix PHP parser first** → everything else depends on accurate symbol resolution.