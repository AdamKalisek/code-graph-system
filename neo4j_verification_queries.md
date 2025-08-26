# Neo4j Verification Queries

## How to Access Neo4j Web Interface

1. **Open your browser** and go to: http://localhost:7475
2. **Connect to database**:
   - Connection URL: `bolt://localhost:7688`
   - Username: `neo4j`
   - Password: `password123`

## What You Should See

After running `python demo_indexing.py`, you should have data loaded. Here are the queries to verify everything works:

## 1. Basic Statistics

### Count all nodes and relationships
```cypher
MATCH (n) 
RETURN count(n) as TotalNodes
```

```cypher
MATCH ()-[r]->() 
RETURN count(r) as TotalRelationships
```

## 2. View Node Types

### See all different node labels
```cypher
CALL db.labels() YIELD label
RETURN label
ORDER BY label
```

### Count nodes by type
```cypher
MATCH (n:Symbol)
RETURN n.kind as NodeType, n._language as Language, count(*) as Count
ORDER BY Count DESC
```

## 3. PHP Class Hierarchy

### View PHP classes with their methods
```cypher
MATCH (c:Symbol:PHP:Class)-[:HAS_METHOD]->(m:Symbol:PHP:Method)
RETURN c.name as Class, collect(m.name) as Methods
LIMIT 5
```

### See PHP inheritance (if working)
```cypher
MATCH (child:Symbol:PHP:Class)-[:EXTENDS]->(parent:Symbol:PHP:Class)
RETURN child.name as Child, parent.name as Parent
```

## 4. JavaScript Structure

### View JavaScript files
```cypher
MATCH (f:Symbol:JavaScript:File)
RETURN f.name as FileName, f.metadata_api_calls as APICalls
WHERE f.metadata_api_calls IS NOT NULL
```

### See imports in JavaScript files
```cypher
MATCH (f:Symbol:JavaScript:File)-[:IMPORTS]->(i:Symbol)
RETURN f.name as File, collect(i.name) as Imports
LIMIT 5
```

## 5. API Endpoints

### List all API endpoints
```cypher
MATCH (e:Endpoint)
RETURN e.method as Method, e.path as Path, e.controller as Controller
ORDER BY e.path
LIMIT 20
```

### Count endpoints by HTTP method
```cypher
MATCH (e:Endpoint)
RETURN e.method as Method, count(*) as Count
ORDER BY Count DESC
```

## 6. Cross-Language Relationships (Goal)

### JavaScript calling API endpoints (when CALLS works)
```cypher
MATCH (js:Symbol:JavaScript)-[:CALLS]->(e:Endpoint)
RETURN js.name as JSFile, e.method as Method, e.path as Endpoint
LIMIT 10
```

### Complete chain: JS → Endpoint → PHP (ultimate goal)
```cypher
MATCH (js:Symbol)-[:CALLS]->(e:Endpoint)<-[:HANDLES]-(php:Symbol)
WHERE js._language = 'javascript' AND php._language = 'php'
RETURN js.name as JSFile, e.path as API, php.name as PHPController
LIMIT 5
```

## 7. Visual Graph Exploration

### See a small connected graph
```cypher
MATCH (n:Symbol:PHP:Class)
WHERE n.name = 'User'
MATCH p=(n)-[*1..2]-(connected)
RETURN p
LIMIT 50
```

### View JavaScript file with all its relationships
```cypher
MATCH (f:Symbol:JavaScript:File {name: 'app.js'})
MATCH p=(f)-[*1..2]-(connected)
RETURN p
LIMIT 50
```

## 8. Debug Queries

### Check if metadata is stored
```cypher
MATCH (n:Symbol)
WHERE n.metadata_api_calls IS NOT NULL
RETURN n.name, n.metadata_api_calls
LIMIT 5
```

### See all relationship types
```cypher
CALL db.relationshipTypes() YIELD relationshipType
RETURN relationshipType
ORDER BY relationshipType
```

### Find orphan nodes (not connected)
```cypher
MATCH (n)
WHERE NOT (n)-[]-()
RETURN labels(n) as Labels, n.name as Name, n.kind as Kind
LIMIT 20
```

## Expected Results

After running the demo indexing, you should see:
- **~400-500 total nodes** (PHP classes, methods, JS files, endpoints)
- **~300-400 relationships** (HAS_METHOD, IMPORTS, DEFINED_IN, etc.)
- **287 API Endpoints** from routes.json
- **9 PHP classes** with their methods
- **8 JavaScript files** with imports/exports
- **API calls detected** in app.js file

## What's Currently NOT Working (To Fix)
- **EXTENDS relationships** between PHP classes
- **IMPLEMENTS relationships** for interfaces
- **USES_TRAIT relationships** for PHP traits
- **CALLS relationships** from JavaScript to Endpoints
- **HANDLES relationships** from PHP Controllers to Endpoints

These need additional work in the parsers and linkers.