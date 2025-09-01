#!/usr/bin/env python3
from neo4j import GraphDatabase
import json

uri = "bolt://localhost:7688"
auth = ("neo4j", "password123")

driver = GraphDatabase.driver(uri, auth=auth)

def verify_edge_types():
    with driver.session() as session:
        # Get sample edges for each type
        edge_samples = {}
        
        edge_types = [
            'EXTENDS', 'IMPLEMENTS', 'USES_TRAIT', 'CALLS', 'CALLS_STATIC',
            'INSTANTIATES', 'ACCESSES', 'RETURNS', 'PARAMETER_TYPE',
            'INSTANCEOF', 'IMPORTS', 'THROWS', 'USES_CONSTANT'
        ]
        
        for edge_type in edge_types:
            query = f"""
            MATCH (a)-[r:{edge_type}]->(b)
            RETURN a.name as source, b.name as target, type(r) as type
            LIMIT 3
            """
            result = session.run(query)
            samples = []
            for record in result:
                samples.append({
                    'source': record['source'],
                    'target': record['target']
                })
            if samples:
                edge_samples[edge_type] = samples
        
        # Get detailed stats
        stats_query = """
        MATCH ()-[r]->()
        RETURN type(r) as type, count(r) as count
        ORDER BY count DESC
        """
        stats = session.run(stats_query)
        
        print("=" * 70)
        print("EDGE TYPE VERIFICATION REPORT")
        print("=" * 70)
        print()
        
        total = 0
        for record in stats:
            edge_type = record['type']
            count = record['count']
            total += count
            print(f"{edge_type:<20} {count:>6} edges")
            
            if edge_type in edge_samples:
                print(f"  Examples:")
                for sample in edge_samples[edge_type][:2]:
                    print(f"    • {sample['source']} -> {sample['target']}")
            print()
        
        print(f"{'TOTAL':<20} {total:>6} edges")
        print()
        
        # Check for missing types
        found_types = set(edge_samples.keys())
        all_types = set(edge_types)
        missing = all_types - found_types
        
        if missing:
            print("⚠️  Missing Edge Types:")
            for edge_type in sorted(missing):
                print(f"  • {edge_type}")
        else:
            print("✅ All expected edge types found!")

if __name__ == "__main__":
    verify_edge_types()
    driver.close()
