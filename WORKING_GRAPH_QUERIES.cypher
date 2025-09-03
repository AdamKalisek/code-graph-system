// ============================================================
// WORKING NEO4J QUERIES - TESTED AND VERIFIED
// Copy these to Neo4j Browser at http://localhost:7474
// ============================================================

// 1. 🌟 SEE EVERYTHING - The Complete Graph Overview
MATCH (n)-[r]-(m)
RETURN n, r, m
LIMIT 1000;

// 2. 🎯 Show ALL Relationship Types with Real Examples
MATCH ()-[r]->()
RETURN TYPE(r) as relationship_type, COUNT(r) as count
ORDER BY count DESC;

// 3. 🏗️ Complete Inheritance Hierarchy (EXTENDS + IMPLEMENTS + USES_TRAIT)
MATCH (child)-[r:EXTENDS|IMPLEMENTS|USES_TRAIT]->(parent)
RETURN child, r, parent
LIMIT 500;

// 4. 📧 Email System - Complete Subgraph
MATCH (n)
WHERE toLower(n.name) CONTAINS 'email' OR toLower(n.name) CONTAINS 'send'
OPTIONAL MATCH (n)-[r]-(connected)
RETURN n, r, connected
LIMIT 500;

// 5. 🔥 The Big Picture - Most Connected Nodes
MATCH (n)
WITH n, COUNT((n)-[]->()) + COUNT((n)<-[]-()) as degree
ORDER BY degree DESC
LIMIT 50
MATCH (n)-[r]-(m)
RETURN n, r, m
LIMIT 1000;

// 6. 📊 Show Different Node Types
MATCH (n)
RETURN DISTINCT labels(n) as node_types, COUNT(n) as count
ORDER BY count DESC;

// 7. 🌐 Class Extends Class - Inheritance Chain
MATCH path = (c1:PHPClass)-[:EXTENDS*1..3]->(c2:PHPClass)
RETURN path
LIMIT 100;

// 8. 🎪 Maximum Diversity - Sample of Everything
MATCH (n)-[r]->(m)
WHERE rand() < 0.05
RETURN n, r, m
LIMIT 1000;

// 9. 📦 File and Directory Structure
MATCH (d:Directory)-[:CONTAINS]->(f:File)
RETURN d, f
LIMIT 200;

// 10. 🔍 Find Specific Class and Its Relationships
MATCH (n {name: 'Espo\\Core\\Mail\\EmailSender'})-[r]-(connected)
RETURN n, r, connected;

// 11. 💎 THE BEST QUERY - Rich Connected Graph
MATCH (n1)-[r]->(n2)
WITH n1, r, n2, labels(n1) as l1, labels(n2) as l2
WHERE SIZE(l1) > 0 AND SIZE(l2) > 0
RETURN n1, r, n2
LIMIT 2000;

// 12. 🚀 User-Related Everything
MATCH (n)
WHERE n.name CONTAINS 'User'
OPTIONAL MATCH (n)-[r]-(m)
RETURN n, r, m
LIMIT 500;

// ============================================================
// STATISTICS QUERIES
// ============================================================

// Total Nodes
MATCH (n) RETURN COUNT(n) as total_nodes;

// Total Relationships
MATCH ()-[r]->() RETURN COUNT(r) as total_relationships;

// Inheritance Statistics
MATCH ()-[r:EXTENDS]->() RETURN 'EXTENDS' as type, COUNT(r) as count
UNION
MATCH ()-[r:IMPLEMENTS]->() RETURN 'IMPLEMENTS' as type, COUNT(r) as count
UNION
MATCH ()-[r:USES_TRAIT]->() RETURN 'USES_TRAIT' as type, COUNT(r) as count;