#!/usr/bin/env python3
"""Execute systematic tests against Neo4j database"""

import time
from neo4j import GraphDatabase
from tabulate import tabulate

class GraphTester:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            "bolt://localhost:7688", 
            auth=("neo4j", "password123")
        )
        self.results = []
        self.issues = []
    
    def test_node_counts(self):
        """Test Phase 1.1: Node counts"""
        print("\n" + "="*60)
        print("PHASE 1: NODE COUNT VERIFICATION")
        print("="*60)
        
        with self.driver.session() as session:
            tests = [
                ("PHP Classes", "MATCH (c:PHPClass) RETURN COUNT(c) as count"),
                ("PHP Interfaces", "MATCH (i:PHPInterface) RETURN COUNT(i) as count"),
                ("PHP Traits", "MATCH (t:PHPTrait) RETURN COUNT(t) as count"),
                ("PHP Methods", "MATCH (m:PHPMethod) RETURN COUNT(m) as count"),
                ("PHP Properties", "MATCH (p:PHPProperty) RETURN COUNT(p) as count"),
                ("JS Modules", "MATCH (m:JSModule) RETURN COUNT(m) as count"),
                ("JS Functions", "MATCH (f:JSFunction) RETURN COUNT(f) as count"),
                ("Directories", "MATCH (d:Directory) RETURN COUNT(d) as count"),
                ("Files", "MATCH (f:File) RETURN COUNT(f) as count"),
                ("Total Nodes", "MATCH (n) RETURN COUNT(n) as count"),
            ]
            
            results = []
            for name, query in tests:
                result = session.run(query)
                count = result.single()['count']
                status = "✓" if count > 0 else "✗"
                results.append([name, count, status])
                
                if count == 0 and name not in ["PHP Interfaces", "PHP Traits"]:
                    self.issues.append(f"Missing {name}")
            
            print(tabulate(results, headers=["Node Type", "Count", "Status"], tablefmt="grid"))
    
    def test_relationships(self):
        """Test Phase 2: Relationships"""
        print("\n" + "="*60)
        print("PHASE 2: RELATIONSHIP VALIDATION")
        print("="*60)
        
        with self.driver.session() as session:
            # Expected counts from SQLite
            expected = {
                "EXTENDS": 266,
                "IMPLEMENTS": 189,
                "USES_TRAIT": 25
            }
            
            # Check all relationship types
            result = session.run("""
                MATCH ()-[r]->()
                RETURN TYPE(r) as type, COUNT(r) as count
                ORDER BY count DESC
            """)
            
            relationships = {}
            for record in result:
                relationships[record['type']] = record['count']
            
            # Check inheritance relationships
            inheritance_results = []
            for rel_type, expected_count in expected.items():
                actual = relationships.get(rel_type, 0)
                status = "✓" if actual >= expected_count * 0.9 else "✗"  # Allow 10% variance
                percentage = (actual / expected_count * 100) if expected_count > 0 else 0
                inheritance_results.append([rel_type, expected_count, actual, f"{percentage:.1f}%", status])
                
                if actual < expected_count * 0.5:  # Less than 50% is critical
                    self.issues.append(f"CRITICAL: {rel_type} only has {actual}/{expected_count} relationships")
            
            print("\nInheritance Relationships:")
            print(tabulate(inheritance_results, 
                         headers=["Type", "Expected", "Actual", "Coverage", "Status"], 
                         tablefmt="grid"))
            
            # Check for wrong relationships
            result = session.run("""
                MATCH (c:PHPClass)-[r]->(d:Directory)
                RETURN COUNT(r) as count
            """)
            wrong_count = result.single()['count']
            
            if wrong_count == 0:
                print("\n✅ No classes extending directories (CORRECT)")
            else:
                print(f"\n❌ CRITICAL: {wrong_count} classes extend directories!")
                self.issues.append(f"CRITICAL: {wrong_count} classes incorrectly extend directories")
            
            # Show all relationship types
            if relationships:
                print("\nAll Relationship Types:")
                rel_table = [[rel_type, count] for rel_type, count in relationships.items()]
                print(tabulate(rel_table, headers=["Type", "Count"], tablefmt="grid"))
            else:
                print("\n❌ NO RELATIONSHIPS FOUND IN DATABASE!")
                self.issues.append("CRITICAL: No relationships in database")
    
    def test_search_capability(self, keyword):
        """Test Phase 3: Search by keyword"""
        with self.driver.session() as session:
            query = """
                MATCH (n)
                WHERE toLower(n.name) CONTAINS $keyword
                RETURN labels(n)[0] as type, n.name as name
                LIMIT 10
            """
            results = session.run(query, keyword=keyword)
            matches = []
            for record in results:
                matches.append(f"{record['type']}: {record['name']}")
            return matches
    
    def test_sample_queries(self):
        """Test natural language query capabilities"""
        print("\n" + "="*60)
        print("PHASE 3: SEARCH CAPABILITY TESTING")
        print("="*60)
        
        keywords = ['email', 'auth', 'user', 'database', 'controller', 'service']
        
        for keyword in keywords:
            matches = self.test_search_capability(keyword)
            print(f"\n🔍 Search '{keyword}': Found {len(matches)} matches")
            if matches:
                for match in matches[:3]:
                    print(f"   - {match}")
            else:
                self.issues.append(f"No results for keyword '{keyword}'")
    
    def test_file_structure(self):
        """Test file and directory structure"""
        print("\n" + "="*60)
        print("PHASE 4: FILE STRUCTURE VERIFICATION")
        print("="*60)
        
        with self.driver.session() as session:
            # Check CONTAINS relationships
            result = session.run("""
                MATCH (d:Directory)-[:CONTAINS]->(n)
                RETURN COUNT(DISTINCT d) as dirs_with_content, 
                       COUNT(n) as total_contained
            """)
            record = result.single()
            
            if record['dirs_with_content'] > 0:
                print(f"✓ Directories with content: {record['dirs_with_content']}")
                print(f"✓ Total contained items: {record['total_contained']}")
            else:
                print("✗ No CONTAINS relationships found")
                self.issues.append("Missing CONTAINS relationships")
            
            # Check specific directory
            result = session.run("""
                MATCH (d:Directory)
                WHERE d.name = 'Controllers' OR d.path CONTAINS 'Controllers'
                RETURN d.id, d.name, d.path
                LIMIT 1
            """)
            
            controller_dir = result.single()
            if controller_dir:
                print(f"\n✓ Found Controllers directory: {controller_dir.get('path', controller_dir['name'])}")
                
                # Check its contents
                result = session.run("""
                    MATCH (d:Directory)-[:CONTAINS]->(f:File)
                    WHERE d.id = $dir_id
                    RETURN COUNT(f) as file_count
                """, dir_id=controller_dir['id'])
                
                count = result.single()['file_count']
                if count > 0:
                    print(f"  Contains {count} files")
                else:
                    print("  WARNING: No files in Controllers directory")
    
    def generate_report(self):
        """Generate final test report"""
        print("\n" + "="*60)
        print("TEST EXECUTION SUMMARY")
        print("="*60)
        
        if not self.issues:
            print("\n✅ ALL TESTS PASSED!")
            print("The graph database is ready for use.")
        else:
            print(f"\n❌ FOUND {len(self.issues)} ISSUES:")
            for i, issue in enumerate(self.issues, 1):
                print(f"{i}. {issue}")
            
            # Determine severity
            critical = sum(1 for i in self.issues if "CRITICAL" in i)
            if critical > 0:
                print(f"\n🔴 {critical} CRITICAL issues - database is UNUSABLE")
                print("The inheritance graph is broken. Fix import process immediately.")
            else:
                print("\n🟡 Non-critical issues - database is DEGRADED")
                print("Basic functionality works but some features are limited.")
    
    def run_all_tests(self):
        """Execute all tests"""
        print("=" * 60)
        print("SYSTEMATIC TEST EXECUTION FOR NEO4J GRAPH DATABASE")
        print("=" * 60)
        print(f"Target: bolt://localhost:7688")
        print(f"Testing EspoCRM code graph import")
        
        try:
            # Run test phases
            self.test_node_counts()
            self.test_relationships()
            self.test_file_structure()
            self.test_sample_queries()
            
            # Generate report
            self.generate_report()
            
        except Exception as e:
            print(f"\n❌ TEST EXECUTION FAILED: {e}")
            self.issues.append(f"Test execution error: {e}")
        finally:
            self.driver.close()

if __name__ == "__main__":
    print("Starting Neo4j Graph Database Tests...")
    print("Make sure Neo4j is running on port 7688")
    print("-" * 60)
    
    tester = GraphTester()
    tester.run_all_tests()