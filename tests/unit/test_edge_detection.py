#!/usr/bin/env python3
"""Test script to verify all edge types are detected correctly"""

import os
import sys
import json
from pathlib import Path
from neo4j import GraphDatabase
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EdgeDetectionTester:
    def __init__(self):
        self.neo4j_uri = "bolt://localhost:7688"
        self.neo4j_auth = ("neo4j", "password123")
        self.driver = GraphDatabase.driver(self.neo4j_uri, auth=self.neo4j_auth)
        
        # Expected edge types and minimum counts
        self.expected_edges = {
            'EXTENDS': {'min_count': 1, 'description': 'Class inheritance'},
            'IMPLEMENTS': {'min_count': 1, 'description': 'Interface implementation'},
            'USES_TRAIT': {'min_count': 2, 'description': 'Trait usage'},
            'IMPORTS': {'min_count': 3, 'description': 'Namespace imports'},
            'THROWS': {'min_count': 3, 'description': 'Exception throwing'},
            'USES_CONSTANT': {'min_count': 4, 'description': 'Constant usage'},
            'CALLS': {'min_count': 5, 'description': 'Method calls'},
            'CALLS_STATIC': {'min_count': 1, 'description': 'Static method calls'},
            'INSTANTIATES': {'min_count': 2, 'description': 'Object creation'},
            'ACCESSES': {'min_count': 3, 'description': 'Property access'},
            'PARAMETER_TYPE': {'min_count': 3, 'description': 'Parameter types'},
            'RETURNS': {'min_count': 1, 'description': 'Return types'},
            'INSTANCEOF': {'min_count': 1, 'description': 'Type checking'}
        }
    
    def clean_database(self):
        """Clean the database before testing"""
        logger.info("Cleaning database...")
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        logger.info("Database cleaned")
    
    def import_test_file(self):
        """Import the test file"""
        logger.info("Importing test file...")
        
        # Run the enhanced pipeline on our test file
        test_file = "/home/david/Work/Programming/memory/test_all_edges.php"
        cmd = f"""python enhanced_pipeline.py {test_file} \
            --neo4j-uri {self.neo4j_uri} \
            --neo4j-password password123 \
            --verbose 2>&1"""
        
        result = os.system(cmd)
        if result != 0:
            logger.error("Import failed!")
            return False
        
        logger.info("Import completed")
        return True
    
    def verify_edges(self):
        """Verify all edge types are created"""
        logger.info("\n" + "="*70)
        logger.info("EDGE TYPE VERIFICATION")
        logger.info("="*70)
        
        results = {
            'passed': [],
            'failed': [],
            'missing': []
        }
        
        with self.driver.session() as session:
            # Get all edge types and counts
            query = """
            MATCH ()-[r]->()
            RETURN type(r) as edge_type, count(r) as count
            ORDER BY count DESC
            """
            
            edge_counts = {}
            result = session.run(query)
            for record in result:
                edge_counts[record['edge_type']] = record['count']
            
            # Verify each expected edge type
            for edge_type, expected in self.expected_edges.items():
                count = edge_counts.get(edge_type, 0)
                min_count = expected['min_count']
                description = expected['description']
                
                if count == 0:
                    results['missing'].append(edge_type)
                    logger.error(f"❌ {edge_type:<20} MISSING - Expected {min_count}+ {description}")
                elif count < min_count:
                    results['failed'].append(edge_type)
                    logger.warning(f"⚠️  {edge_type:<20} LOW ({count}/{min_count}) - {description}")
                else:
                    results['passed'].append(edge_type)
                    logger.info(f"✅ {edge_type:<20} PASSED ({count}/{min_count}) - {description}")
                
                # Show examples for detected edges
                if count > 0:
                    examples_query = f"""
                    MATCH (a)-[r:{edge_type}]->(b)
                    RETURN a.name as source, b.name as target
                    LIMIT 2
                    """
                    examples = session.run(examples_query)
                    for ex in examples:
                        logger.info(f"     Example: {ex['source']} -> {ex['target']}")
        
        # Summary
        logger.info("\n" + "="*70)
        logger.info("SUMMARY")
        logger.info("="*70)
        
        total = len(self.expected_edges)
        passed = len(results['passed'])
        failed = len(results['failed'])
        missing = len(results['missing'])
        
        logger.info(f"Total edge types tested: {total}")
        logger.info(f"✅ Passed: {passed}/{total}")
        logger.info(f"⚠️  Low count: {failed}/{total}")
        logger.info(f"❌ Missing: {missing}/{total}")
        
        if missing:
            logger.error(f"\nMissing edge types: {', '.join(results['missing'])}")
        
        if failed:
            logger.warning(f"Low count edge types: {', '.join(results['failed'])}")
        
        success_rate = (passed / total) * 100
        logger.info(f"\nSuccess rate: {success_rate:.1f}%")
        
        return missing == [] and failed == []
    
    def get_detailed_stats(self):
        """Get detailed statistics about the imported graph"""
        with self.driver.session() as session:
            # Node statistics
            node_query = """
            MATCH (n)
            RETURN labels(n)[0] as type, count(n) as count
            ORDER BY count DESC
            """
            
            logger.info("\n" + "="*70)
            logger.info("NODE STATISTICS")
            logger.info("="*70)
            
            result = session.run(node_query)
            for record in result:
                logger.info(f"{record['type']:<20} {record['count']:>6} nodes")
            
            # Total relationships
            rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()['count']
            node_count = session.run("MATCH (n) RETURN count(n) as count").single()['count']
            
            logger.info(f"\nTotal nodes: {node_count}")
            logger.info(f"Total relationships: {rel_count}")
            logger.info(f"Avg relationships per node: {rel_count/node_count:.2f}")
    
    def run_test(self):
        """Run the complete test"""
        try:
            # Step 1: Clean database
            self.clean_database()
            
            # Step 2: Import test file
            if not self.import_test_file():
                logger.error("Import failed, aborting test")
                return False
            
            # Step 3: Verify edges
            success = self.verify_edges()
            
            # Step 4: Show detailed stats
            self.get_detailed_stats()
            
            return success
            
        except Exception as e:
            logger.error(f"Test failed: {e}")
            return False
        finally:
            self.driver.close()

if __name__ == "__main__":
    tester = EdgeDetectionTester()
    success = tester.run_test()
    
    if success:
        logger.info("\n🎉 All edge detection tests PASSED!")
        sys.exit(0)
    else:
        logger.error("\n❌ Some edge detection tests FAILED")
        sys.exit(1)