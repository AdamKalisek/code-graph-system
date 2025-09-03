#!/usr/bin/env python3
"""Import inheritance relationships to Neo4j"""

from neo4j import GraphDatabase
import re

# Neo4j connection details
URI = "bolt://localhost:7687"
AUTH = ("neo4j", "12345678")

def import_relationships(driver, file_path):
    """Import relationships from Cypher file"""
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    count = 0
    with driver.session() as session:
        for line in lines:
            line = line.strip()
            if line and line.startswith('MATCH'):
                try:
                    session.run(line)
                    count += 1
                    if count % 50 == 0:
                        print(f"Imported {count} relationships...")
                except Exception as e:
                    print(f"Error on line: {line}")
                    print(f"Error: {e}")
    
    print(f"Successfully imported {count} relationships")

if __name__ == "__main__":
    driver = GraphDatabase.driver(URI, auth=AUTH)
    try:
        import_relationships(driver, "inheritance.cypher")
    finally:
        driver.close()