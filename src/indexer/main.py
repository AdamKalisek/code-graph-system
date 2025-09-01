#!/usr/bin/env python3
"""
COMPLETE EspoCRM Indexer - Backend + Frontend + Cross-Language Links
Creates a comprehensive code graph with all relationships
"""

import argparse
import logging
import sys
import time
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Backend parsers
from src.core.symbol_table import SymbolTable
from parsers.php_enhanced import PHPSymbolCollector
from parsers.php_reference_resolver import PHPReferenceResolver

# Frontend parser
from parsers.js_espocrm_parser import EspoCRMJavaScriptParser

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CompleteEspoCRMIndexer:
    """Complete indexer for entire EspoCRM codebase"""
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.symbol_table = SymbolTable('.cache/complete_espocrm.db')
        self.js_parser = EspoCRMJavaScriptParser()
        
        # Statistics
        self.stats = {
            'php_files': 0,
            'js_files': 0,
            'php_symbols': 0,
            'js_symbols': 0,
            'php_references': 0,
            'js_references': 0,
            'cross_language_links': 0,
            'api_endpoints': {},
            'total_time': 0
        }
        
        # Track API endpoints for cross-language linking
        self.php_endpoints = {}  # controller::method -> symbol_id
        self.js_api_calls = []   # List of JS API call symbols
        
    def run(self):
        """Run complete indexing"""
        start_time = time.time()
        
        logger.info("="*70)
        logger.info("COMPLETE ESPOCRM INDEXING - BACKEND + FRONTEND")
        logger.info("="*70)
        
        # Step 1: Index PHP Backend
        logger.info("\n[1/5] INDEXING PHP BACKEND...")
        self._index_php_backend()
        
        # Step 2: Index JavaScript Frontend
        logger.info("\n[2/5] INDEXING JAVASCRIPT FRONTEND...")
        self._index_javascript_frontend()
        
        # Step 3: Create Cross-Language Links
        logger.info("\n[3/5] CREATING CROSS-LANGUAGE LINKS...")
        self._create_cross_language_links()
        
        # Step 4: Export to Neo4j
        logger.info("\n[4/5] EXPORTING TO NEO4J...")
        self._export_to_neo4j()
        
        # Step 5: Generate Statistics
        logger.info("\n[5/5] GENERATING STATISTICS...")
        self.stats['total_time'] = time.time() - start_time
        self._print_statistics()
        
        return self.stats
    
    def _index_php_backend(self):
        """Index all PHP files"""
        php_files = list(self.project_path.rglob("*.php"))
        self.stats['php_files'] = len(php_files)
        
        logger.info(f"Found {len(php_files)} PHP files")
        
        # Pass 1: Symbol Collection
        logger.info("Pass 1: Collecting PHP symbols...")
        collector = PHPSymbolCollector(self.symbol_table)
        
        for i, file_path in enumerate(php_files, 1):
            if i % 100 == 0:
                logger.info(f"  Processing {i}/{len(php_files)}: {file_path.name}")
            try:
                collector.parse_file(str(file_path))
            except Exception as e:
                logger.debug(f"Error parsing {file_path}: {e}")
        
        # Pass 2: Reference Resolution
        logger.info("Pass 2: Resolving PHP references...")
        resolver = PHPReferenceResolver(self.symbol_table)
        
        for i, file_path in enumerate(php_files, 1):
            if i % 100 == 0:
                logger.info(f"  Resolving {i}/{len(php_files)}: {file_path.name}")
            try:
                resolver.resolve_file(str(file_path))
            except Exception as e:
                logger.debug(f"Error resolving {file_path}: {e}")
        
        # Collect PHP endpoints
        self._collect_php_endpoints()
        
        # Get statistics
        stats = self.symbol_table.get_stats()
        self.stats['php_symbols'] = stats.get('total_symbols', 0)
        self.stats['php_references'] = stats.get('total_references', 0)
        
        logger.info(f"PHP Backend: {self.stats['php_symbols']} symbols, {self.stats['php_references']} references")
    
    def _index_javascript_frontend(self):
        """Index all JavaScript files"""
        js_patterns = ["*.js", "*.jsx", "*.mjs"]
        js_files = []
        
        # Find JavaScript files in client/src
        client_src_path = self.project_path / "client" / "src"
        if client_src_path.exists():
            for pattern in js_patterns:
                js_files.extend(client_src_path.rglob(pattern))
        
        # Also check client/modules
        client_modules_path = self.project_path / "client" / "modules"
        if client_modules_path.exists():
            for pattern in js_patterns:
                js_files.extend(client_modules_path.rglob(pattern))
        
        # Filter out node_modules and lib
        js_files = [f for f in js_files if 'node_modules' not in str(f) and '/lib/' not in str(f)]
        self.stats['js_files'] = len(js_files)
        
        logger.info(f"Found {len(js_files)} JavaScript files")
        
        total_js_symbols = 0
        total_js_references = 0
        
        for i, file_path in enumerate(js_files, 1):
            if i % 50 == 0:
                logger.info(f"  Processing JS {i}/{len(js_files)}: {file_path.name}")
            
            try:
                # Parse JavaScript file
                symbols, references = self.js_parser.parse_file(str(file_path))
                
                # Store JS symbols in our database
                for symbol in symbols:
                    # Add JS symbols with js_ prefix to distinguish from PHP
                    symbol_id = f"js_{symbol.id}"
                    
                    self.symbol_table.add_symbol(
                        id=symbol_id,
                        name=symbol.name,
                        type=f"js_{symbol.type}",
                        file=str(file_path),
                        namespace=None,
                        line=symbol.line,
                        column=symbol.column,
                        parent_id=None,
                        metadata=json.dumps(symbol.metadata) if symbol.metadata else None
                    )
                    
                    # Track API calls for cross-language linking
                    if symbol.type == 'api_call':
                        self.js_api_calls.append({
                            'symbol_id': symbol_id,
                            'endpoint': symbol.metadata.get('endpoint'),
                            'method': symbol.metadata.get('method'),
                            'php_controller': symbol.metadata.get('php_controller'),
                            'php_method': symbol.metadata.get('php_method'),
                            'file': str(file_path),
                            'line': symbol.line
                        })
                
                # Store JS references
                for ref in references:
                    self.symbol_table.add_reference(
                        source_id=f"js_{ref.source_id}" if not ref.source_id.startswith('js_') else ref.source_id,
                        target_id=f"js_{ref.target_id}" if not ref.target_id.startswith('js_') else ref.target_id,
                        reference_type=ref.type,
                        line=ref.line,
                        column=ref.column,
                        context=ref.context
                    )
                
                total_js_symbols += len(symbols)
                total_js_references += len(references)
                
            except Exception as e:
                logger.debug(f"Error parsing JS file {file_path}: {e}")
        
        self.stats['js_symbols'] = total_js_symbols
        self.stats['js_references'] = total_js_references
        
        logger.info(f"JavaScript Frontend: {total_js_symbols} symbols, {total_js_references} references")
    
    def _collect_php_endpoints(self):
        """Collect PHP controller endpoints for cross-language linking"""
        conn = sqlite3.connect('.cache/complete_espocrm.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Find all controller classes and their methods
        controllers = cursor.execute("""
            SELECT id, name
            FROM symbols 
            WHERE type = 'class' AND name LIKE '%Controller'
        """).fetchall()
        
        for controller in controllers:
            controller_name = controller['name']
            
            # Get methods of this controller
            methods = cursor.execute("""
                SELECT id, name 
                FROM symbols 
                WHERE type = 'method' 
                AND parent_id = ?
                AND name LIKE 'action%'
            """, (controller['id'],)).fetchall()
            
            for method in methods:
                # Create endpoint mapping
                # e.g., LeadController::actionConvert -> Lead/action/convert
                controller_base = controller_name.replace('Controller', '')
                action_name = method['name'].replace('action', '').lower()
                
                if action_name == 'index':
                    endpoint_key = f"{controller_base}"
                else:
                    endpoint_key = f"{controller_base}/action/{action_name}"
                
                self.php_endpoints[endpoint_key.lower()] = {
                    'controller_id': controller['id'],
                    'method_id': method['id'],
                    'controller': controller_name,
                    'method': method['name']
                }
        
        conn.close()
        logger.info(f"Collected {len(self.php_endpoints)} PHP endpoints")
    
    def _create_cross_language_links(self):
        """Create links between JavaScript API calls and PHP endpoints"""
        links_created = 0
        
        for api_call in self.js_api_calls:
            endpoint = api_call['endpoint']
            if not endpoint:
                continue
            
            # Normalize endpoint
            endpoint_key = endpoint.strip('/').lower()
            
            # Try to find matching PHP endpoint
            php_endpoint = self.php_endpoints.get(endpoint_key)
            
            if not php_endpoint:
                # Try without 'action/' prefix
                if '/action/' in endpoint_key:
                    alt_key = endpoint_key.replace('/action/', '/')
                    php_endpoint = self.php_endpoints.get(alt_key)
            
            if php_endpoint:
                # Create cross-language reference
                self.symbol_table.add_reference(
                    source_id=api_call['symbol_id'],
                    target_id=php_endpoint['method_id'],
                    reference_type='JS_CALLS_PHP',
                    line=api_call['line'],
                    column=0,
                    context=f"JS API call to {php_endpoint['controller']}::{php_endpoint['method']}"
                )
                links_created += 1
                
                # Track in statistics
                endpoint_stat = f"{api_call['method']} {endpoint}"
                self.stats['api_endpoints'][endpoint_stat] = self.stats['api_endpoints'].get(endpoint_stat, 0) + 1
        
        self.stats['cross_language_links'] = links_created
        logger.info(f"Created {links_created} cross-language links")
    
    def _export_to_neo4j(self):
        """Export complete graph to Neo4j"""
        logger.info("Preparing Neo4j export...")
        
        # Connect to database
        conn = sqlite3.connect('.cache/complete_espocrm.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all symbols
        symbols = cursor.execute("SELECT * FROM symbols").fetchall()
        references = cursor.execute("SELECT * FROM symbol_references").fetchall()
        
        logger.info(f"Exporting {len(symbols)} symbols and {len(references)} references to Neo4j")
        
        # Create Cypher export file
        with open('espocrm_complete.cypher', 'w') as f:
            # Clear database
            f.write("MATCH (n) DETACH DELETE n;\n\n")
            
            # Create indexes
            f.write("CREATE INDEX symbol_id IF NOT EXISTS FOR (s:Symbol) ON (s.id);\n")
            f.write("CREATE INDEX php_class IF NOT EXISTS FOR (c:PHPClass) ON (c.name);\n")
            f.write("CREATE INDEX js_module IF NOT EXISTS FOR (m:JSModule) ON (m.name);\n\n")
            
            # Create nodes
            for symbol in symbols:
                # Determine node label based on type
                symbol_type = symbol['type']
                if symbol_type.startswith('js_'):
                    label = 'JSSymbol'
                    if 'class' in symbol_type or 'backbone' in symbol_type:
                        label = 'JSModule'
                    elif 'api_call' in symbol_type:
                        label = 'APICall'
                else:
                    label = 'PHPSymbol'
                    if symbol_type == 'class':
                        label = 'PHPClass'
                    elif symbol_type == 'method':
                        label = 'PHPMethod'
                
                props = {
                    'id': symbol['id'],
                    'name': symbol['name'],
                    'type': symbol_type
                }
                
                # Add optional properties
                if symbol['file']:
                    props['file'] = symbol['file']
                if symbol['line']:
                    props['line'] = symbol['line']
                if symbol['namespace']:
                    props['namespace'] = symbol['namespace']
                
                f.write(f"CREATE (n:{label} {json.dumps(props)});\n")
            
            f.write("\n// Creating relationships\n")
            
            # Create relationships
            for ref in references:
                rel_type = ref['type'].replace('-', '_').upper()
                f.write(f"MATCH (s:Symbol {{id: '{ref['source_id']}'}}), ")
                f.write(f"(t:Symbol {{id: '{ref['target_id']}'}}) ")
                f.write(f"CREATE (s)-[:{rel_type}]->(t);\n")
        
        conn.close()
        
        logger.info("Created espocrm_complete.cypher - Import this into Neo4j for visualization")
        
        # Try to import using MCP if available
        try:
            self._import_to_neo4j_mcp(symbols, references)
        except Exception as e:
            logger.info(f"Could not import via MCP: {e}")
            logger.info("Please run: cat espocrm_complete.cypher | cypher-shell")
    
    def _import_to_neo4j_mcp(self, symbols, references):
        """Try to import using Neo4j MCP"""
        logger.info("Attempting Neo4j import via MCP...")
        
        # This would use the MCP tool if available
        # For now, we've created the Cypher file for manual import
        pass
    
    def _print_statistics(self):
        """Print comprehensive statistics"""
        print("\n" + "="*70)
        print("COMPLETE ESPOCRM CODE GRAPH STATISTICS")
        print("="*70)
        
        print(f"\n📊 OVERVIEW:")
        print(f"  Total processing time: {self.stats['total_time']:.2f} seconds")
        print(f"  Total files parsed: {self.stats['php_files'] + self.stats['js_files']}")
        print(f"  Total symbols: {self.stats['php_symbols'] + self.stats['js_symbols']}")
        print(f"  Total references: {self.stats['php_references'] + self.stats['js_references']}")
        
        print(f"\n🔷 PHP BACKEND:")
        print(f"  Files: {self.stats['php_files']}")
        print(f"  Symbols: {self.stats['php_symbols']}")
        print(f"  References: {self.stats['php_references']}")
        
        print(f"\n🔶 JAVASCRIPT FRONTEND:")
        print(f"  Files: {self.stats['js_files']}")
        print(f"  Symbols: {self.stats['js_symbols']}")
        print(f"  References: {self.stats['js_references']}")
        
        print(f"\n🔗 CROSS-LANGUAGE:")
        print(f"  JS→PHP Links: {self.stats['cross_language_links']}")
        
        if self.stats['api_endpoints']:
            print(f"\n📡 TOP API ENDPOINTS:")
            sorted_endpoints = sorted(self.stats['api_endpoints'].items(), 
                                     key=lambda x: x[1], reverse=True)[:10]
            for endpoint, count in sorted_endpoints:
                print(f"  {endpoint}: {count} calls")
        
        # Calculate edge type statistics
        conn = sqlite3.connect('.cache/complete_espocrm.db')
        cursor = conn.cursor()
        
        edge_types = cursor.execute("""
            SELECT type, COUNT(*) as count 
            FROM symbol_references 
            GROUP BY type 
            ORDER BY count DESC
        """).fetchall()
        
        print(f"\n📈 EDGE TYPES:")
        for edge_type in edge_types[:15]:  # Show top 15
            print(f"  {edge_type[0]}: {edge_type[1]}")
        
        conn.close()
        
        print("\n✅ INDEXING COMPLETE!")
        print(f"📄 Export file: espocrm_complete.cypher")
        print(f"📊 Database: .cache/complete_espocrm.db")
        print("\nTo visualize in Neo4j:")
        print("  1. Start Neo4j: neo4j start")
        print("  2. Import: cat espocrm_complete.cypher | cypher-shell -u neo4j -p your_password")
        print("  3. Open browser: http://localhost:7474")
        print("  4. Query: MATCH (n) RETURN n LIMIT 100")

def main():
    parser = argparse.ArgumentParser(description='Complete EspoCRM Indexer')
    parser.add_argument('--project', default='espocrm', help='EspoCRM project path')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    indexer = CompleteEspoCRMIndexer(args.project)
    stats = indexer.run()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())