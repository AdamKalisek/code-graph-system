# Neo4j Queries to Visualize COMPLETE Graph with ALL Edges

## 1. 🌟 MEGA QUERY - Show Everything Connected (All Types, All Relationships)
```cypher
// THE ULTIMATE GRAPH VISUALIZATION - Shows ALL node types and ALL relationship types
MATCH (n)
WHERE (n)-[]-() // Only nodes that have relationships
WITH n, 
     SIZE((n)-[]-()) as degree,
     labels(n) as node_labels
ORDER BY degree DESC
LIMIT 100
WITH COLLECT(n) as important_nodes
UNWIND important_nodes as source
MATCH path = (source)-[r]-(target)
WHERE target IN important_nodes 
   OR (target.name CONTAINS 'User' OR target.name CONTAINS 'Email' 
       OR target.name CONTAINS 'Entity' OR target.name CONTAINS 'Repository'
       OR target.name CONTAINS 'Controller' OR target.name CONTAINS 'Service')
RETURN path
LIMIT 2000
```

## 2. 🎯 Show ALL Relationship Types with Examples
```cypher
// See EVERY type of relationship in the database with examples
MATCH (n1)-[r]->(n2)
WITH TYPE(r) as rel_type, 
     n1.name as source_name, 
     n2.name as target_name,
     labels(n1)[0] as source_type,
     labels(n2)[0] as target_type,
     r
RETURN rel_type, 
       source_type + ': ' + source_name as source,
       target_type + ': ' + target_name as target
ORDER BY rel_type
LIMIT 500
```

## 3. 🏗️ Complete Class Hierarchy Graph
```cypher
// Show ALL inheritance relationships - EXTENDS, IMPLEMENTS, USES_TRAIT
MATCH path = (child)-[r:EXTENDS|IMPLEMENTS|USES_TRAIT*1..3]->(parent)
WHERE child.type = 'class' OR child.type = 'interface' OR child.type = 'trait'
RETURN path
LIMIT 1000
```

## 4. 📊 Densest Part of Graph (Most Connected Nodes)
```cypher
// Find the most interconnected part of the codebase
MATCH (n)
WITH n, SIZE((n)-[]-()) as degree
WHERE degree > 5
MATCH path = (n)-[r]-(m)
WHERE SIZE((m)-[]-()) > 5
RETURN path
LIMIT 1500
```

## 5. 🔍 ALL Node Types with ALL Their Relationships
```cypher
// Shows diversity - every node type and every relationship type
MATCH (n)
WITH DISTINCT labels(n) as node_labels
UNWIND node_labels as label
MATCH (n2)
WHERE label IN labels(n2)
WITH n2, label
LIMIT 20
MATCH path = (n2)-[r]->()
RETURN path, label, TYPE(r) as relationship
LIMIT 2000
```

## 6. 🌐 Email System Complete Graph
```cypher
// Everything related to email - classes, methods, files, directories
MATCH (n)
WHERE toLower(n.name) CONTAINS 'email' OR toLower(n.name) CONTAINS 'mail'
WITH n
MATCH path = (n)-[r*0..2]->(related)
WHERE TYPE(r) IN ['EXTENDS', 'IMPLEMENTS', 'CONTAINS', 'USES_TRAIT', 'CALLS', 'INSTANTIATES']
   OR related.name CONTAINS 'Send' 
   OR related.name CONTAINS 'SMTP'
RETURN path
LIMIT 1000
```

## 7. 🎪 The FULL CIRCUS - Every Type of Node and Edge
```cypher
// THE COMPLETE PICTURE - All node types, all edge types, maximum diversity
MATCH (n1)-[r]->(n2)
WITH 
  labels(n1) as from_labels,
  labels(n2) as to_labels,
  TYPE(r) as rel_type,
  n1, r, n2
WHERE SIZE(from_labels) > 0 AND SIZE(to_labels) > 0
WITH 
  from_labels[0] + '-[' + rel_type + ']->' + to_labels[0] as pattern,
  n1, r, n2
WITH DISTINCT pattern, COLLECT({source: n1, rel: r, target: n2})[0..5] as examples
UNWIND examples as ex
MATCH path = (ex.source)-[ex.rel]->(ex.target)
RETURN path
LIMIT 3000
```

## 8. 📦 Directory and File Structure with Code
```cypher
// Complete file system structure WITH the code it contains
MATCH path = (d:Directory)-[:CONTAINS*1..3]->(f:File)
WHERE d.name IN ['Controllers', 'Services', 'Repositories', 'Entities']
WITH path, f
MATCH (f)-[:DEFINES]->(code)
WHERE code.type IN ['class', 'interface', 'trait']
WITH path, COLLECT(code) as defined_code
RETURN path
LIMIT 1000
```

## 9. 🔥 The MONSTER Query - EVERYTHING Connected
```cypher
// WARNING: This shows A LOT - the complete interconnected graph
MATCH (n)
WHERE n.name IS NOT NULL
WITH n ORDER BY SIZE((n)-[]-()) DESC LIMIT 200
WITH COLLECT(n) as top_nodes
UNWIND top_nodes as node
MATCH path = (node)-[r]-(m)
WHERE m IN top_nodes OR m.type IN ['class', 'interface', 'method', 'file', 'directory']
RETURN DISTINCT path
LIMIT 5000
```

## 10. 🌟 ULTIMATE VISUALIZATION - All Types & Relationships
```cypher
// Best for Neo4j Browser - Shows maximum diversity
MATCH (n1)-[r]->(n2)
WHERE rand() < 0.1  // Random 10% sample for performance
WITH n1, r, n2,
     labels(n1) as n1_labels,
     labels(n2) as n2_labels,
     TYPE(r) as rel_type
WHERE SIZE(n1_labels) > 0 AND SIZE(n2_labels) > 0
RETURN n1, r, n2
LIMIT 2000
```

## 🎯 HOW TO USE THESE QUERIES:

1. **In Neo4j Browser** (http://localhost:7474):
   - Copy any query above
   - Paste in the query editor
   - Click Run
   - Use the visualization controls to explore

2. **For Best Visualization**:
   - Query #10 gives the best overview
   - Query #3 shows inheritance clearly  
   - Query #6 shows a complete subsystem (email)
   - Query #7 shows maximum diversity

3. **Visualization Tips**:
   - Different colors = different node types
   - Click nodes to see properties
   - Drag nodes to rearrange
   - Double-click to expand connections

## 📊 WHAT YOU'LL SEE:

- **Node Types**: PHPClass, PHPInterface, PHPTrait, PHPMethod, File, Directory, JSModule
- **Edge Types**: EXTENDS, IMPLEMENTS, USES_TRAIT, CONTAINS, CALLS, INSTANTIATES, and more
- **Patterns**: Inheritance hierarchies, file structures, method calls, dependencies

Copy these queries to Neo4j Browser for an AMAZING visualization of your complete code graph!