#!/usr/bin/env python3
"""
Fix missing DEFINES relationships in Neo4j database
Creates proper DEFINES relationships between:
- Files -> Classes/Interfaces/Traits
- Classes -> Methods/Properties
"""

import logging
from neo4j import GraphDatabase
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DefinesRelationshipFixer:
    """Fix missing DEFINES relationships in Neo4j"""
    
    def __init__(self, neo4j_uri="bolt://localhost:7688", 
                 neo4j_user="neo4j", neo4j_password="password123"):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.stats = {
            'file_to_class': 0,
            'class_to_method': 0,
            'class_to_property': 0,
            'total_time': 0
        }
    
    def fix_file_to_class_defines(self):
        """Create DEFINES relationships from Files to Classes/Interfaces/Traits"""
        logger.info("Creating FILE->CLASS DEFINES relationships...")
        
        with self.driver.session() as session:
            # First, let's see what we have
            result = session.run("""
                MATCH (f:File)-[:CONTAINS]->(c:PHPClass)
                RETURN count(*) as existing_contains
            """)
            existing = result.single()['existing_contains']
            logger.info(f"  Found {existing} existing File->Class CONTAINS relationships")
            
            # Convert CONTAINS to DEFINES for classes
            result = session.run("""
                MATCH (f:File)-[r:CONTAINS]->(c:PHPClass)
                CREATE (f)-[:DEFINES]->(c)
                DELETE r
                RETURN count(*) as created
            """)
            count = result.single()['created']
            self.stats['file_to_class'] += count
            logger.info(f"  Converted {count} File->PHPClass relationships to DEFINES")
            
            # Do the same for interfaces
            result = session.run("""
                MATCH (f:File)-[r:CONTAINS]->(i:PHPInterface)
                CREATE (f)-[:DEFINES]->(i)
                DELETE r
                RETURN count(*) as created
            """)
            count = result.single()['created']
            self.stats['file_to_class'] += count
            logger.info(f"  Converted {count} File->PHPInterface relationships to DEFINES")
            
            # And for traits
            result = session.run("""
                MATCH (f:File)-[r:CONTAINS]->(t:PHPTrait)
                CREATE (f)-[:DEFINES]->(t)
                DELETE r
                RETURN count(*) as created
            """)
            count = result.single()['created']
            self.stats['file_to_class'] += count
            logger.info(f"  Converted {count} File->PHPTrait relationships to DEFINES")
    
    def fix_class_to_method_defines(self):
        """Create DEFINES relationships from Classes to their Methods"""
        logger.info("Creating CLASS->METHOD DEFINES relationships...")
        
        with self.driver.session() as session:
            # Methods should belong to the class in the same file and namespace
            # We can infer this from the file path and namespace matching
            result = session.run("""
                MATCH (c:PHPClass)
                MATCH (m:PHPMethod)
                WHERE c.file_path = m.file_path
                AND (
                    (c.namespace IS NULL AND m.namespace IS NULL) OR
                    (c.namespace = m.namespace)
                )
                CREATE (c)-[:DEFINES]->(m)
                RETURN count(*) as created
            """)
            count = result.single()['created']
            self.stats['class_to_method'] = count
            logger.info(f"  Created {count} Class->Method DEFINES relationships")
            
            # Also handle properties
            result = session.run("""
                MATCH (c:PHPClass)
                MATCH (p:PHPProperty)
                WHERE c.file_path = p.file_path
                AND (
                    (c.namespace IS NULL AND p.namespace IS NULL) OR
                    (c.namespace = p.namespace)
                )
                CREATE (c)-[:DEFINES]->(p)
                RETURN count(*) as created
            """)
            count = result.single()['created']
            self.stats['class_to_property'] = count
            logger.info(f"  Created {count} Class->Property DEFINES relationships")
    
    def fix_interface_trait_defines(self):
        """Create DEFINES relationships for interfaces and traits"""
        logger.info("Creating INTERFACE/TRAIT->METHOD DEFINES relationships...")
        
        with self.driver.session() as session:
            # Interface methods
            result = session.run("""
                MATCH (i:PHPInterface)
                MATCH (m:PHPMethod)
                WHERE i.file_path = m.file_path
                AND (
                    (i.namespace IS NULL AND m.namespace IS NULL) OR
                    (i.namespace = m.namespace)
                )
                CREATE (i)-[:DEFINES]->(m)
                RETURN count(*) as created
            """)
            interface_count = result.single()['created']
            logger.info(f"  Created {interface_count} Interface->Method DEFINES relationships")
            
            # Trait methods and properties
            result = session.run("""
                MATCH (t:PHPTrait)
                MATCH (m:PHPMethod)
                WHERE t.file_path = m.file_path
                AND (
                    (t.namespace IS NULL AND m.namespace IS NULL) OR
                    (t.namespace = m.namespace)
                )
                CREATE (t)-[:DEFINES]->(m)
                RETURN count(*) as created
            """)
            trait_method_count = result.single()['created']
            
            result = session.run("""
                MATCH (t:PHPTrait)
                MATCH (p:PHPProperty)
                WHERE t.file_path = p.file_path
                AND (
                    (t.namespace IS NULL AND p.namespace IS NULL) OR
                    (t.namespace = p.namespace)
                )
                CREATE (t)-[:DEFINES]->(p)
                RETURN count(*) as created
            """)
            trait_prop_count = result.single()['created']
            
            logger.info(f"  Created {trait_method_count} Trait->Method DEFINES relationships")
            logger.info(f"  Created {trait_prop_count} Trait->Property DEFINES relationships")
    
    def verify_fixes(self):
        """Verify the fixes worked"""
        logger.info("\nVerifying DEFINES relationships...")
        
        with self.driver.session() as session:
            # Check File->Class
            result = session.run("""
                MATCH (f:File)-[:DEFINES]->(c:PHPClass)
                RETURN count(*) as count
            """)
            file_class = result.single()['count']
            
            # Check Class->Method
            result = session.run("""
                MATCH (c:PHPClass)-[:DEFINES]->(m:PHPMethod)
                RETURN count(*) as count
            """)
            class_method = result.single()['count']
            
            # Check Class->Property
            result = session.run("""
                MATCH (c:PHPClass)-[:DEFINES]->(p:PHPProperty)
                RETURN count(*) as count
            """)
            class_property = result.single()['count']
            
            print("\n✅ DEFINES Relationships Created:")
            print(f"  File -> Class: {file_class}")
            print(f"  Class -> Method: {class_method}")
            print(f"  Class -> Property: {class_property}")
            
            # Test a query
            print("\n🔍 Testing Service Query:")
            result = session.run("""
                MATCH (c:PHPClass)-[:DEFINES]->(m:PHPMethod)<-[r:CALLS]-()
                WHERE c.name CONTAINS 'Service'
                RETURN c.name as ServiceClass, m.name as Method, count(r) as CallCount
                ORDER BY CallCount DESC
                LIMIT 5
            """)
            
            for record in result:
                print(f"  {record['ServiceClass']}.{record['Method']}() - {record['CallCount']} calls")
    
    def run(self):
        """Run all fixes"""
        start_time = time.time()
        
        try:
            logger.info("Starting DEFINES relationship fixes...")
            
            # Fix relationships
            self.fix_file_to_class_defines()
            self.fix_class_to_method_defines()
            self.fix_interface_trait_defines()
            
            # Verify
            self.verify_fixes()
            
            self.stats['total_time'] = time.time() - start_time
            
            print(f"\n" + "="*60)
            print("✅ FIXES COMPLETE!")
            print("="*60)
            print(f"⏱️  Time taken: {self.stats['total_time']:.2f} seconds")
            print(f"📊 Relationships created:")
            print(f"  File->Class: {self.stats['file_to_class']}")
            print(f"  Class->Method: {self.stats['class_to_method']}")
            print(f"  Class->Property: {self.stats['class_to_property']}")
            
        except Exception as e:
            logger.error(f"Fix failed: {e}")
            raise
        finally:
            self.driver.close()


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fix missing DEFINES relationships in Neo4j')
    parser.add_argument('--uri', default='bolt://localhost:7688', help='Neo4j URI')
    parser.add_argument('--user', default='neo4j', help='Neo4j username')
    parser.add_argument('--password', default='password123', help='Neo4j password')
    
    args = parser.parse_args()
    
    fixer = DefinesRelationshipFixer(args.uri, args.user, args.password)
    fixer.run()


if __name__ == '__main__':
    main()