#!/usr/bin/env python3
"""
Natural Language Query Processor for Neo4j Code Graph
Translates natural language questions into Cypher queries
"""

import re
from typing import Dict, List, Tuple, Optional
from neo4j import GraphDatabase
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NaturalLanguageProcessor:
    """Process natural language queries against code graph"""
    
    def __init__(self, neo4j_uri="bolt://localhost:7688", 
                 neo4j_user="neo4j", neo4j_password="password123"):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        
        # Define query patterns and their Cypher templates
        self.query_patterns = {
            # Email-related queries
            r"how.*(email|mail).*(sent|send)": {
                "cypher": """
                    // Find email sending functionality
                    MATCH (n)
                    WHERE toLower(n.name) CONTAINS 'email' OR toLower(n.name) CONTAINS 'mail'
                        OR toLower(n.name) CONTAINS 'smtp' OR toLower(n.name) CONTAINS 'send'
                    WITH n
                    WHERE n.type IN ['class', 'method', 'function']
                    RETURN DISTINCT n.type as type, n.name as name, n.file_path as path
                    ORDER BY 
                        CASE WHEN toLower(n.name) CONTAINS 'send' THEN 0 ELSE 1 END,
                        CASE WHEN toLower(n.name) CONTAINS 'email' THEN 0 ELSE 1 END
                    LIMIT 20
                """,
                "description": "Finding email sending functionality"
            },
            
            # Authentication queries
            r"(where|how).*(auth|login|authentication)": {
                "cypher": """
                    // Find authentication logic
                    MATCH (n)
                    WHERE toLower(n.name) CONTAINS 'auth' OR toLower(n.name) CONTAINS 'login'
                        OR toLower(n.name) CONTAINS 'authenticate' OR toLower(n.name) CONTAINS 'session'
                    WITH n
                    WHERE n.type IN ['class', 'method', 'function']
                    RETURN DISTINCT n.type as type, n.name as name, n.file_path as path
                    ORDER BY 
                        CASE WHEN n.type = 'class' THEN 0 ELSE 1 END,
                        CASE WHEN toLower(n.name) CONTAINS 'auth' THEN 0 ELSE 1 END
                    LIMIT 20
                """,
                "description": "Finding authentication logic"
            },
            
            # User validation
            r"(what|where|how).*(validat|sanitiz).*(user|input|data)": {
                "cypher": """
                    // Find validation logic
                    MATCH (n)
                    WHERE toLower(n.name) CONTAINS 'validat' OR toLower(n.name) CONTAINS 'sanitiz'
                        OR toLower(n.name) CONTAINS 'filter' OR toLower(n.name) CONTAINS 'check'
                    WITH n
                    WHERE n.type IN ['class', 'method', 'function']
                    RETURN DISTINCT n.type as type, n.name as name, n.file_path as path
                    ORDER BY 
                        CASE WHEN toLower(n.name) CONTAINS 'validat' THEN 0 ELSE 1 END,
                        n.name
                    LIMIT 20
                """,
                "description": "Finding validation logic"
            },
            
            # Database queries
            r"(how|where).*(database|query|sql|repository)": {
                "cypher": """
                    // Find database interaction
                    MATCH (n)
                    WHERE toLower(n.name) CONTAINS 'query' OR toLower(n.name) CONTAINS 'repository'
                        OR toLower(n.name) CONTAINS 'database' OR toLower(n.name) CONTAINS 'entity'
                        OR toLower(n.name) CONTAINS 'orm'
                    WITH n
                    WHERE n.type IN ['class', 'method']
                    RETURN DISTINCT n.type as type, n.name as name, n.file_path as path
                    ORDER BY 
                        CASE WHEN n.type = 'class' THEN 0 ELSE 1 END,
                        CASE WHEN toLower(n.name) CONTAINS 'repository' THEN 0 ELSE 1 END
                    LIMIT 20
                """,
                "description": "Finding database interaction"
            },
            
            # API endpoints
            r"(what|where|list).*(api|endpoint|route|controller)": {
                "cypher": """
                    // Find API endpoints and controllers
                    MATCH (n)
                    WHERE toLower(n.name) CONTAINS 'controller' OR toLower(n.name) CONTAINS 'action'
                        OR toLower(n.name) CONTAINS 'api' OR toLower(n.name) CONTAINS 'endpoint'
                    WITH n
                    WHERE n.type IN ['class', 'method']
                    RETURN DISTINCT n.type as type, n.name as name, n.file_path as path
                    ORDER BY 
                        CASE WHEN n.type = 'class' AND toLower(n.name) CONTAINS 'controller' THEN 0 ELSE 1 END,
                        n.name
                    LIMIT 20
                """,
                "description": "Finding API endpoints and controllers"
            },
            
            # Error handling
            r"(how|where).*(error|exception).*(handled|caught|thrown)": {
                "cypher": """
                    // Find error handling
                    MATCH (n)
                    WHERE toLower(n.name) CONTAINS 'error' OR toLower(n.name) CONTAINS 'exception'
                        OR toLower(n.name) CONTAINS 'catch' OR toLower(n.name) CONTAINS 'throw'
                    WITH n
                    RETURN DISTINCT n.type as type, n.name as name, n.file_path as path
                    ORDER BY 
                        CASE WHEN toLower(n.name) CONTAINS 'exception' THEN 0 ELSE 1 END,
                        n.name
                    LIMIT 20
                """,
                "description": "Finding error handling"
            },
            
            # Class hierarchy
            r"(what|which).*(class|classes).*(extend|inherit|implement).*(\w+)": {
                "cypher_template": """
                    // Find class inheritance for: {target}
                    MATCH (c:PHPClass)-[:EXTENDS|IMPLEMENTS]->(p)
                    WHERE toLower(p.name) CONTAINS toLower('{target}')
                    RETURN c.name as child_class, type(r) as relationship, p.name as parent
                    LIMIT 20
                """,
                "description": "Finding class inheritance",
                "extract_param": r"(extend|inherit|implement)\s+(\w+)"
            },
            
            # Method calls
            r"(what|which|who).*(call|invoke|use).*(\w+)": {
                "cypher_template": """
                    // Find who calls method: {target}
                    MATCH (m1)-[:CALLS]->(m2)
                    WHERE toLower(m2.name) CONTAINS toLower('{target}')
                    RETURN m1.type as caller_type, m1.name as caller, 
                           m2.name as called_method, m1.file_path as path
                    LIMIT 20
                """,
                "description": "Finding method calls",
                "extract_param": r"(call|invoke|use)\s+(\w+)"
            },
            
            # File location
            r"(where|which file).*(class|function|method).*(\w+)": {
                "cypher_template": """
                    // Find location of: {target}
                    MATCH (n)
                    WHERE toLower(n.name) CONTAINS toLower('{target}')
                    RETURN n.type as type, n.name as name, 
                           n.file_path as path, n.line_number as line
                    ORDER BY 
                        CASE WHEN toLower(n.name) = toLower('{target}') THEN 0 ELSE 1 END
                    LIMIT 10
                """,
                "description": "Finding code location",
                "extract_param": r"(class|function|method)\s+(\w+)"
            }
        }
        
        # Keyword mappings for better search
        self.keyword_mappings = {
            'email': ['email', 'mail', 'smtp', 'mailer', 'message'],
            'auth': ['auth', 'login', 'authenticate', 'session', 'token', 'credential'],
            'database': ['database', 'db', 'query', 'sql', 'repository', 'entity', 'orm'],
            'user': ['user', 'account', 'profile', 'member'],
            'api': ['api', 'endpoint', 'route', 'controller', 'action', 'rest'],
            'error': ['error', 'exception', 'throw', 'catch', 'handle', 'fail'],
            'validate': ['validate', 'validation', 'sanitize', 'filter', 'check', 'verify']
        }
    
    def process_query(self, natural_query: str) -> Dict:
        """Process a natural language query and return results"""
        natural_query = natural_query.lower().strip()
        
        logger.info(f"Processing query: {natural_query}")
        
        # Try to match query patterns
        for pattern, config in self.query_patterns.items():
            if re.search(pattern, natural_query):
                if 'cypher_template' in config:
                    # Extract parameter and fill template
                    param_match = re.search(config['extract_param'], natural_query)
                    if param_match:
                        target = param_match.group(2)
                        cypher = config['cypher_template'].replace('{target}', target)
                        description = f"{config['description']}: {target}"
                    else:
                        continue
                else:
                    cypher = config['cypher']
                    description = config['description']
                
                return self._execute_query(cypher, description)
        
        # Fallback to keyword search
        keywords = self._extract_keywords(natural_query)
        if keywords:
            return self._keyword_search(keywords)
        
        return {
            'success': False,
            'message': "Could not understand the query. Try asking about email, authentication, validation, database, API, or error handling.",
            'results': []
        }
    
    def _extract_keywords(self, query: str) -> List[str]:
        """Extract relevant keywords from query"""
        keywords = []
        
        # Check for mapped keywords
        for key, synonyms in self.keyword_mappings.items():
            for synonym in synonyms:
                if synonym in query:
                    keywords.extend(synonyms)
                    break
        
        # Extract potential code identifiers (camelCase, snake_case, etc.)
        identifiers = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', query)
        keywords.extend([id for id in identifiers if len(id) > 2])
        
        return list(set(keywords))
    
    def _keyword_search(self, keywords: List[str]) -> Dict:
        """Perform keyword-based search"""
        where_clauses = []
        for keyword in keywords[:5]:  # Limit to 5 keywords
            where_clauses.append(f"toLower(n.name) CONTAINS '{keyword.lower()}'")
        
        cypher = f"""
            MATCH (n)
            WHERE {' OR '.join(where_clauses)}
            RETURN n.type as type, n.name as name, n.file_path as path
            ORDER BY n.type, n.name
            LIMIT 30
        """
        
        return self._execute_query(cypher, f"Keyword search: {', '.join(keywords)}")
    
    def _execute_query(self, cypher: str, description: str) -> Dict:
        """Execute Cypher query and format results"""
        try:
            with self.driver.session() as session:
                logger.debug(f"Executing: {description}")
                result = session.run(cypher)
                
                records = []
                for record in result:
                    records.append(dict(record))
                
                return {
                    'success': True,
                    'description': description,
                    'count': len(records),
                    'results': records,
                    'cypher': cypher if logger.level == logging.DEBUG else None
                }
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'description': description,
                'results': []
            }
    
    def suggest_queries(self) -> List[str]:
        """Return example queries that can be processed"""
        return [
            "How is email sent?",
            "Where is user authentication handled?",
            "What validates user input?",
            "How are database queries executed?",
            "What are the API endpoints?",
            "How are errors handled?",
            "Which classes extend BaseEntity?",
            "What calls the save method?",
            "Where is the User class defined?",
            "Show me the authentication controllers"
        ]
    
    def close(self):
        """Close database connection"""
        self.driver.close()


def main():
    """Interactive query interface"""
    processor = NaturalLanguageProcessor()
    
    print("=" * 60)
    print("Natural Language Query Processor for Code Graph")
    print("=" * 60)
    print("\nExample queries:")
    for query in processor.suggest_queries():
        print(f"  - {query}")
    print("\nType 'quit' to exit\n")
    
    while True:
        query = input("Ask a question: ").strip()
        
        if query.lower() in ['quit', 'exit', 'q']:
            break
        
        if not query:
            continue
        
        result = processor.process_query(query)
        
        if result['success']:
            print(f"\n✓ {result['description']}")
            print(f"Found {result['count']} results:\n")
            
            for i, record in enumerate(result['results'][:10], 1):
                print(f"{i}. ", end="")
                for key, value in record.items():
                    if value:
                        print(f"{key}: {value} | ", end="")
                print()
            
            if result['count'] > 10:
                print(f"\n... and {result['count'] - 10} more results")
        else:
            print(f"\n✗ {result.get('message', result.get('error', 'Query failed'))}")
        
        print()
    
    processor.close()
    print("\nGoodbye!")


if __name__ == '__main__':
    main()