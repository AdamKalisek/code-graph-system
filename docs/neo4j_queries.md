# Neo4j Queries for EspoCRM Code Graph Visualization

## Complete Graph Statistics
- **Total Nodes**: 32,163
- **Total Relationships**: 74,556
- **PHP Files**: 3,049
- **JavaScript Files**: 1,083
- **Classes**: 3,253
- **JavaScript Modules**: 8,327
- **API Calls**: 91
- **Inheritance Relations**: 952
- **Import Relations**: 9,296

## 1. View Full Graph Structure (Limited for Performance)
```cypher
// Get a representative sample of the complete graph
MATCH (n)
WITH n LIMIT 500
OPTIONAL MATCH (n)-[r]-(m)
RETURN n, r, m
```

## 2. PHP Backend Structure
```cypher
// View PHP class hierarchy with methods
MATCH (f:File)-[:CONTAINS]->(c:Class)
WHERE f.name CONTAINS '.php'
OPTIONAL MATCH (c)-[:HAS_METHOD]->(m:Method)
OPTIONAL MATCH (c)-[:EXTENDS]->(parent:Class)
RETURN f, c, m, parent
LIMIT 100
```

## 3. JavaScript Frontend Structure
```cypher
// View JavaScript modules and their dependencies
MATCH (js:JAVASCRIPT)
OPTIONAL MATCH (js)-[:IMPORTS]->(dep)
OPTIONAL MATCH (js)-[:CALLS_API]->(api)
OPTIONAL MATCH (js)-[:EXTENDS]->(parent)
RETURN js, dep, api, parent
LIMIT 100
```

## 4. Cross-Language API Connections
```cypher
// Show JavaScript to PHP API calls
MATCH path = (js:JAVASCRIPT)-[:CALLS_API]->(api)
RETURN path
```

## 5. Complete Directory Structure
```cypher
// View directory tree with files
MATCH (d:Directory)-[:CONTAINS]->(child)
OPTIONAL MATCH (child)-[:IN_DIRECTORY]->(d)
RETURN d, child
LIMIT 200
```

## 6. Class Inheritance Tree
```cypher
// Show all class inheritance relationships
MATCH path = (child:Class)-[:EXTENDS*]->(parent:Class)
RETURN path
```

## 7. Method Call Graph
```cypher
// Show method calls between classes
MATCH (caller)-[:CALLS]->(callee)
WHERE (caller:Method OR caller:Function OR caller:JAVASCRIPT)
RETURN caller, callee
LIMIT 200
```

## 8. Model Operations
```cypher
// Show all model operations (CRUD)
MATCH (n)-[:MODEL_OPERATION]->(op)
RETURN n, op
```

## 9. Most Connected Nodes (Hubs)
```cypher
// Find the most connected nodes in the graph
MATCH (n)
WITH n, size((n)--()) as degree
ORDER BY degree DESC
LIMIT 20
RETURN n.name as node, labels(n) as type, degree
```

## 10. Full Graph Export Query
```cypher
// Export entire graph structure
CALL apoc.export.json.all("espocrm_graph.json", {})
YIELD file, nodes, relationships
RETURN file, nodes, relationships
```

## 11. Interactive Exploration Query
```cypher
// Start from a specific node and explore connections
MATCH (start {name: "User"})  // Change "User" to any class/file name
CALL apoc.path.subgraphAll(start, {
    maxLevel: 3,
    relationshipFilter: "EXTENDS|CALLS|IMPORTS|CALLS_API|HAS_METHOD"
})
YIELD nodes, relationships
RETURN nodes, relationships
```

## 12. Statistics by Node Type
```cypher
MATCH (n)
UNWIND labels(n) as label
RETURN label, count(n) as count
ORDER BY count DESC
```

## 13. Statistics by Relationship Type
```cypher
MATCH ()-[r]->()
RETURN type(r) as relationship, count(r) as count
ORDER BY count DESC
```

## Usage in Neo4j Browser

1. Open Neo4j Browser at http://localhost:7474
2. Copy any query above
3. For better visualization:
   - Use the "Graph" view mode
   - Adjust node colors by label
   - Size nodes by relationship count
   - Enable captions to show node names

## Recommended Visualization Settings

In Neo4j Browser settings:
- Initial Node Display: 300
- Max Neighbors: 100
- Connect result nodes: ON
- Node caption: `name` property
- Relationship caption: TYPE
- Color scheme: By node label