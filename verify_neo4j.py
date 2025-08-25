#!/usr/bin/env python3
"""
Verify Neo4j data directly
"""

from py2neo import Graph

# Connect to Neo4j
graph = Graph('bolt://localhost:7688', auth=('neo4j', 'password123'))

print("Neo4j Data Verification")
print("=" * 50)

# 1. Count all nodes
result = graph.run("MATCH (n) RETURN count(n) as count").data()
print(f"\nTotal nodes: {result[0]['count']}")

# 2. Count all relationships
result = graph.run("MATCH ()-[r]->() RETURN count(r) as count").data()
print(f"Total relationships: {result[0]['count']}")

# 3. Show all node labels
print("\n--- Node Labels ---")
result = graph.run("""
    MATCH (n)
    RETURN DISTINCT labels(n) as labels, count(n) as count
    ORDER BY count DESC
""").data()

for row in result:
    print(f"  {row['labels']}: {row['count']}")

# 4. Show sample nodes
print("\n--- Sample Nodes ---")
result = graph.run("""
    MATCH (n:Symbol)
    RETURN n.name as name, n.kind as kind, n.type as type, n.qualified_name as qname
    LIMIT 10
""").data()

for row in result:
    print(f"  {row['name']} ({row['kind']}) - {row['qname']}")

# 5. Show relationships
print("\n--- Relationships ---")
result = graph.run("""
    MATCH (s)-[r]->(t)
    RETURN type(r) as type, count(r) as count
    ORDER BY count DESC
""").data()

for row in result:
    print(f"  {row['type']}: {row['count']}")

# 6. Show a specific class
print("\n--- Classes Found ---")
result = graph.run("""
    MATCH (n:Symbol)
    WHERE n.kind = 'class'
    RETURN n.name as name, n.qualified_name as qname
""").data()

if result:
    for row in result:
        print(f"  {row['name']}: {row['qname']}")
else:
    print("  No classes found with kind='class'")
    
# 7. Check what kinds exist
print("\n--- Symbol Kinds ---")
result = graph.run("""
    MATCH (n:Symbol)
    RETURN DISTINCT n.kind as kind, count(n) as count
    ORDER BY count DESC
""").data()

for row in result:
    print(f"  {row['kind']}: {row['count']}")

# 8. Show sample Symbol with all properties
print("\n--- Sample Symbol Properties ---")
result = graph.run("""
    MATCH (n:Symbol)
    RETURN n
    LIMIT 1
""").data()

if result:
    node = result[0]['n']
    print("  Properties:")
    for key, value in dict(node).items():
        print(f"    {key}: {value}")

# 9. Show Files
print("\n--- Files ---")
result = graph.run("""
    MATCH (f:File)
    RETURN f.name as name, f.path as path
""").data()

for row in result:
    print(f"  {row['name']}")

# 10. Show class-like nodes
print("\n--- Looking for class-like nodes ---")
result = graph.run("""
    MATCH (n:Symbol)
    WHERE n.name =~ '.*Container.*' OR n.name =~ '.*Application.*' OR n.name =~ '.*Hook.*'
    RETURN n.name as name, n.kind as kind, n.qualified_name as qname
""").data()

for row in result:
    print(f"  {row['name']} ({row['kind']}): {row['qname']}")

print("\n✓ Verification complete!")