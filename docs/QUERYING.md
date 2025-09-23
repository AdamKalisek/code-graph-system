# Querying Guide - Thinking in Graph Patterns

## Why Read This?

After importing your code to Neo4j, ALL languages (TypeScript, React, PHP, etc.) live in the same graph. While each plugin adds specific node labels and relationships, **the questions developers ask are universal**: "What calls this?", "What breaks if I change this?", "Where is this used?"

This guide teaches you to translate these questions into Cypher patterns that work across any codebase.

## 1. Mental Model

Think of your code as:
```
(code element) --[relationship]--> (code element)
```

- **Code elements**: Files, functions, classes, components, variables
- **Relationships**: CALLS, IMPORTS, RENDERS, EXTENDS, etc.

### Universal Labels (Work Everywhere)

| Generic Label | Examples from Plugins |
|---------------|----------------------|
| `Symbol` | ReactComponent, TSFunction, PHPClass |
| `File` | All source files |
| `Directory` | All folders |

### Relationship Families

| Family | Common Relationships |
|--------|---------------------|
| **Structural** | CONTAINS, DEFINES, DECLARES |
| **Control Flow** | CALLS, INSTANTIATES, RENDERS |
| **Data Flow** | IMPORTS, EXPORTS, USES, READS, WRITES |
| **Inheritance** | EXTENDS, IMPLEMENTS |

## 2. Universal Query Patterns

These patterns work across ALL languages and frameworks. Replace placeholders with your specific labels/relationships.

### Pattern 1: Impact Analysis (What Breaks?)
**"If I change X, what else might break?"**
```cypher
MATCH (start:Symbol {name: "UserService"})
MATCH path = (start)<-[:CALLS|USES|IMPORTS*1..3]-(impacted)
RETURN DISTINCT impacted.name, impacted.file_path, length(path) as distance
ORDER BY distance
```

### Pattern 2: Dependency Discovery (Who Uses This?)
**"What code depends on this function/component?"**
```cypher
MATCH (target:Symbol {name: "validateEmail"})
MATCH (consumer)-[:CALLS|USES|IMPORTS]->(target)
RETURN consumer.name, consumer.type, consumer.file_path
```

### Pattern 3: Coupling Analysis (Fan-In/Fan-Out)
**"Which components have too many dependencies?"**
```cypher
MATCH (s:Symbol)
WITH s,
     COUNT {(s)<-[:CALLS|USES|IMPORTS]-()} as fan_in,
     COUNT {(s)-[:CALLS|USES|IMPORTS]->()} as fan_out
WHERE fan_in + fan_out > 20
RETURN s.name, s.type, fan_in, fan_out, (fan_in + fan_out) as total_coupling
ORDER BY total_coupling DESC
```

### Pattern 4: Dead Code Detection
**"What code is never used?"**
```cypher
MATCH (s:Symbol)
WHERE NOT EXISTS(()-[:CALLS|USES|IMPORTS]->(s))
  AND NOT s.type IN ['File', 'Directory']
  AND NOT EXISTS((s)-[:EXPORTS]->())
RETURN s.name, s.type, s.file_path
```

### Pattern 5: Hotspot Detection
**"Which files/functions are changed most often?"**
```cypher
MATCH (f:File)-[:CONTAINS]->(s:Symbol)
WITH f, count(s) as symbol_count,
     COUNT {(s)-[:CALLS|USES]->()} as outgoing_deps
WHERE symbol_count > 50 OR outgoing_deps > 100
RETURN f.path, symbol_count, outgoing_deps
ORDER BY symbol_count DESC
```

### Pattern 6: Architecture Violations
**"What code violates our layering rules?"**
```cypher
// Example: UI components shouldn't directly access database
MATCH (ui:ReactComponent)-[:CALLS|IMPORTS*1..3]->(db:Symbol)
WHERE db.name CONTAINS 'Repository' OR db.name CONTAINS 'Entity'
RETURN ui.name as violation, db.name as accessed_layer
```

### Pattern 7: Security Audit Trails
**"Can user input reach sensitive operations?"**
```cypher
// Find paths from API routes to database operations
MATCH path = (api:APIRoute)-[:CALLS*1..5]->(db:Symbol)
WHERE db.name CONTAINS 'query' OR db.name CONTAINS 'execute'
RETURN api.name, db.name, length(path) as depth
```

## 3. Build Your Own Query - Template

Use this fill-in-the-blanks template:

```cypher
MATCH (start:<LABEL> {<property>: $value})
MATCH path = (start)-[:<RELATIONSHIPS>*<min>..<max>]->(target:<LABEL>)
WHERE <condition>
RETURN <what_to_show>
ORDER BY <metric>
LIMIT <count>
```

### Decision Guide:
1. **Direction**: `-[]->` (outgoing), `<-[]-` (incoming), `-[]-` (both)
2. **Relationships**: Use `|` for multiple: `[:CALLS|USES|IMPORTS]`
3. **Depth**: Control with `*1..3` (min 1, max 3 hops)
4. **Filter**: Add WHERE clauses to narrow results
5. **Return**: Choose what to display (nodes, properties, paths)

## 4. Language-Specific Examples

### TypeScript/React Patterns

#### Find all components rendering a specific element
```cypher
MATCH (c:ReactComponent)-[:RENDERS*1..3]->(element:JSXElement {name: "Button"})
RETURN c.name, c.file_path
```

#### Trace prop drilling
```cypher
MATCH path = (root:ReactComponent)-[:RENDERS*]->(leaf:ReactComponent)
WHERE length(path) > 3
RETURN path
```

#### Find circular dependencies in imports
```cypher
MATCH path = (m1:File)-[:IMPORTS*2..5]->(m1)
RETURN path
```

### PHP Patterns

#### Find all classes extending a base class
```cypher
MATCH (child:PHPClass)-[:EXTENDS*]->(base:PHPClass {name: "BaseController"})
RETURN child.name, child.namespace
```

#### Detect god classes
```cypher
MATCH (c:PHPClass)-[:DEFINES]->(m:PHPMethod)
WITH c, count(m) as method_count
WHERE method_count > 20
RETURN c.name, method_count
```

### Next.js Specific

#### Find API routes and their consumers
```cypher
MATCH (api:APIRoute)<-[:CALLS*1..3]-(consumer)
RETURN api.path, collect(DISTINCT consumer.name) as consumers
```

#### Server vs Client component analysis
```cypher
MATCH (c:ReactComponent)
RETURN c.is_server_component, count(c) as count
```

## 5. Performance Tips

### Use Indexes
```cypher
// Check what indexes exist
SHOW INDEXES
```

### Limit Depth
```cypher
// Bad: unlimited depth
MATCH path = (a)-[:CALLS*]->(b)

// Good: bounded depth
MATCH path = (a)-[:CALLS*1..5]->(b)
```

### Filter Early
```cypher
// Bad: filter after expansion
MATCH (a)-[:CALLS*1..5]->(b)
WHERE a.name = "foo"

// Good: filter before expansion
MATCH (a {name: "foo"})-[:CALLS*1..5]->(b)
```

### Use COUNT {} Instead of size()
```cypher
// Modern syntax (Neo4j 5+)
COUNT {(n)-[:CALLS]->()} as call_count
```

## 6. Common Questions Mapped to Patterns

| Developer Question | Query Pattern | Example |
|-------------------|---------------|---------|
| "What calls this function?" | Pattern 2 | `(caller)-[:CALLS]->(target)` |
| "What will break if I delete this?" | Pattern 1 | `(start)<-[:USES\|IMPORTS*]-(impacted)` |
| "Is this code used anywhere?" | Pattern 4 | `NOT EXISTS(()-[:USES]->(s))` |
| "What are the most complex files?" | Pattern 5 | Count symbols per file |
| "Are there circular dependencies?" | Pattern 3 | `(m1)-[:IMPORTS*]->(m1)` |
| "Which components are tightly coupled?" | Pattern 3 | High fan-in + fan-out |
| "Does UI access database directly?" | Pattern 6 | Cross-layer relationships |

## 7. AI Agent Queries

For AI assistants understanding code:

### Context Gathering
```cypher
// Get full context around a symbol
MATCH (s:Symbol {name: $name})
OPTIONAL MATCH (s)-[r1]->(uses)
OPTIONAL MATCH (s)<-[r2]-(used_by)
RETURN s, collect(DISTINCT uses) as dependencies,
       collect(DISTINCT used_by) as dependents
```

### Impact Radius
```cypher
// Understand change impact for AI code modification
MATCH (s:Symbol {name: $target})
MATCH (s)<-[:CALLS|USES|IMPORTS*1..2]-(impacted)
WITH count(DISTINCT impacted) as impact_count
RETURN impact_count,
       CASE
         WHEN impact_count < 5 THEN 'Low Risk'
         WHEN impact_count < 20 THEN 'Medium Risk'
         ELSE 'High Risk'
       END as risk_level
```

## 8. Debugging Queries

### See what's in the database
```cypher
// Count by type
MATCH (n)
RETURN labels(n)[0] as label, count(n) as count
ORDER BY count DESC

// Sample nodes
MATCH (n)
RETURN n LIMIT 25
```

### Profile query performance
```cypher
PROFILE
MATCH (c:ReactComponent)-[:RENDERS*1..3]->(e)
RETURN count(e)
```

### Explore relationships
```cypher
// What relationships exist?
MATCH ()-[r]->()
RETURN type(r) as rel_type, count(r) as count
ORDER BY count DESC
```

## 9. Export Results

### To JSON
```cypher
MATCH (c:ReactComponent)
RETURN collect({name: c.name, path: c.file_path}) as components
```

### To CSV
```cypher
// Use Neo4j Browser's export feature or:
MATCH (c:ReactComponent)-[:RENDERS]->(e)
RETURN c.name, e.name
```

## 10. Further Reading

- [Neo4j Cypher Manual](https://neo4j.com/docs/cypher-manual/)
- [Graph Data Science Library](https://neo4j.com/docs/graph-data-science/)
- [APOC Procedures](https://neo4j.com/docs/apoc/) - Extended functionality
- [Query Tuning](https://neo4j.com/docs/cypher-manual/current/query-tuning/)

---

Remember: **Think in patterns, not specific queries.** Once you understand the pattern, you can adapt it to any codebase or framework.