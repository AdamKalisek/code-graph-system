# Neo4j Visualization Queries for Espo\Core\Record\Service

## Full Service Visualization (All Connections)
```cypher
// Shows the service with ALL its connections
MATCH (service:PHPClass {name: 'Espo\\Core\\Record\\Service'})
OPTIONAL MATCH (service)-[r]-(connected)
RETURN service, r, connected
```

## Service with Methods and Their Calls
```cypher
// Shows service, its methods, and what they call
MATCH (service:PHPClass {name: 'Espo\\Core\\Record\\Service'})
OPTIONAL MATCH (service)-[:DEFINES]->(method:PHPMethod)
OPTIONAL MATCH (method)-[:CALLS]->(called)
RETURN service, method, called
LIMIT 100
```

## Service Dependencies Network
```cypher
// Shows what the service depends on and what depends on it
MATCH path = (dependent)-[:CALLS|EXTENDS|IMPLEMENTS|USES_TRAIT*1..2]-(service:PHPClass {name: 'Espo\\Core\\Record\\Service'})
RETURN path
LIMIT 50
```

## Most Used Methods Visualization
```cypher
// Shows the most called methods of the service
MATCH (service:PHPClass {name: 'Espo\\Core\\Record\\Service'})
MATCH (service)-[:DEFINES]->(method:PHPMethod)
MATCH (caller)-[:CALLS]->(method)
WITH service, method, COUNT(caller) as callCount
ORDER BY callCount DESC
LIMIT 10
MATCH (caller)-[:CALLS]->(method)
RETURN service, method, caller, callCount
```

## Service Inheritance and Traits
```cypher
// Shows inheritance hierarchy and traits
MATCH (service:PHPClass {name: 'Espo\\Core\\Record\\Service'})
OPTIONAL MATCH (service)-[:EXTENDS]->(parent)
OPTIONAL MATCH (service)-[:IMPLEMENTS]->(interface)
OPTIONAL MATCH (service)-[:USES_TRAIT]->(trait)
OPTIONAL MATCH (trait)-[:DEFINES]->(traitMethod)
RETURN service, parent, interface, trait, traitMethod
```

## Compact Overview (Best for Initial View)
```cypher
// Balanced view - service hub with key connections
MATCH (service:PHPClass {name: 'Espo\\Core\\Record\\Service'})
OPTIONAL MATCH (service)-[:DEFINES]->(method:PHPMethod)
WITH service, COLLECT(method)[0..5] as methods
OPTIONAL MATCH (service)-[:USES_TRAIT]->(trait)
WITH service, methods, COLLECT(trait) as traits
OPTIONAL MATCH (caller:PHPClass)-[:CALLS]->(:PHPMethod)<-[:DEFINES]-(service)
WITH service, methods, traits, COLLECT(DISTINCT caller)[0..10] as callers
RETURN service, methods, traits, callers
```