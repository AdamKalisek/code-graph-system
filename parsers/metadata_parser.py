#!/usr/bin/env python3
"""
Metadata Configuration Parser for EspoCRM
Parses JSON configuration files to capture runtime registration requirements
that are invisible to static code analysis.
"""

import json
import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import logging

class MetadataParser:
    """Parse EspoCRM metadata JSON files to capture configuration-based runtime behavior."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self.php_class_pattern = re.compile(r'^[A-Z][A-Za-z0-9_\\\\]+$')
        self.config_references = []
        
    def parse_metadata(self, root_path: str):
        """Parse all metadata JSON files in the project."""
        root = Path(root_path)
        json_files = list(root.rglob("**/Resources/metadata/**/*.json"))
        json_files.extend(root.rglob("**/resources/metadata/**/*.json"))
        json_files.extend(root.rglob("**/Custom/Resources/**/*.json"))
        
        self.logger.info(f"Found {len(json_files)} metadata JSON files")
        
        for json_file in json_files:
            try:
                self._parse_json_file(json_file, root_path)
            except Exception as e:
                self.logger.error(f"Error parsing {json_file}: {e}")
                
    def _parse_json_file(self, file_path: Path, root_path: str):
        """Parse a single JSON file for class references."""
        relative_path = str(file_path.relative_to(root_path))
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Special handling for authentication hooks
            if 'authentication.json' in str(file_path):
                self._parse_authentication_hooks(data, relative_path)
            
            # General class reference scanning
            self._scan_for_class_references(data, relative_path, trail=())
            
        except json.JSONDecodeError as e:
            self.logger.warning(f"Invalid JSON in {file_path}: {e}")
            
    def _parse_authentication_hooks(self, data: Dict, file_path: str):
        """Special parser for authentication hook registration."""
        hook_types = [
            'beforeLoginHookClassNameList',
            'onLoginHookClassNameList', 
            'onFailHookClassNameList',
            'onSuccessHookClassNameList',
            'onSuccessByTokenHookClassNameList',
            'onSecondStepRequiredHookClassNameList'
        ]
        
        for hook_type in hook_types:
            if hook_type in data:
                for class_name in data[hook_type]:
                    if class_name != '__APPEND__' and self._is_php_class(class_name):
                        self.config_references.append({
                            'config_file': file_path,
                            'config_key': hook_type,
                            'class_name': class_name,
                            'reference_type': 'AUTHENTICATION_HOOK'
                        })
                        
    def _scan_for_class_references(self, node: Any, file_path: str, trail: Tuple):
        """Recursively scan JSON structure for PHP class references."""
        if isinstance(node, str):
            # Check if it looks like a PHP class name
            if self._is_php_class(node):
                self.config_references.append({
                    'config_file': file_path,
                    'config_key': '::'.join(str(k) for k in trail),
                    'class_name': node,
                    'reference_type': 'CLASS_REFERENCE'
                })
        elif isinstance(node, dict):
            for key, value in node.items():
                self._scan_for_class_references(value, file_path, trail + (key,))
        elif isinstance(node, list):
            for idx, value in enumerate(node):
                self._scan_for_class_references(value, file_path, trail + (str(idx),))
                
    def _is_php_class(self, value: str) -> bool:
        """Check if a string looks like a PHP class name."""
        if not isinstance(value, str):
            return False
        # Check for PHP namespace pattern
        return bool(self.php_class_pattern.match(value) and '\\' in value)
    
    def save_to_database(self):
        """Save configuration references to the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create table for configuration references
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS config_references (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_file TEXT NOT NULL,
                config_key TEXT,
                class_name TEXT NOT NULL,
                reference_type TEXT NOT NULL,
                UNIQUE(config_file, config_key, class_name)
            )
        ''')
        
        # Insert references
        for ref in self.config_references:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO config_references 
                    (config_file, config_key, class_name, reference_type)
                    VALUES (?, ?, ?, ?)
                ''', (
                    ref['config_file'],
                    ref['config_key'],
                    ref['class_name'],
                    ref['reference_type']
                ))
            except sqlite3.Error as e:
                self.logger.error(f"Error inserting config reference: {e}")
                
        conn.commit()
        
        # Log statistics
        cursor.execute("SELECT COUNT(*) FROM config_references")
        count = cursor.fetchone()[0]
        self.logger.info(f"Saved {count} configuration references to database")
        
        # Show sample authentication hooks
        cursor.execute("""
            SELECT config_key, class_name 
            FROM config_references 
            WHERE reference_type = 'AUTHENTICATION_HOOK'
            LIMIT 10
        """)
        hooks = cursor.fetchall()
        if hooks:
            self.logger.info("Sample authentication hooks found:")
            for key, class_name in hooks:
                self.logger.info(f"  {key}: {class_name}")
                
        conn.close()
        
    def get_orphaned_hooks(self) -> List[Dict]:
        """Find hook classes that implement interfaces but aren't registered."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Find all classes implementing login hook interfaces
        cursor.execute("""
            SELECT DISTINCT s.name, t.name as target_name
            FROM symbols s
            JOIN symbol_references sr ON s.id = sr.source_id
            JOIN symbols t ON sr.target_id = t.id
            WHERE sr.reference_type = 'IMPLEMENTS'
            AND t.name IN (
                'Espo\\Core\\Authentication\\Hook\\BeforeLogin',
                'Espo\\Core\\Authentication\\Hook\\OnLogin',
                'Espo\\Core\\Authentication\\Hook\\OnFail',
                'Espo\\Core\\Authentication\\Hook\\OnSuccess'
            )
        """)
        implementing_classes = cursor.fetchall()
        
        # Find which ones are registered
        registered_classes = set()
        cursor.execute("""
            SELECT DISTINCT class_name 
            FROM config_references 
            WHERE reference_type = 'AUTHENTICATION_HOOK'
        """)
        for row in cursor.fetchall():
            registered_classes.add(row[0])
            
        # Find orphaned hooks
        orphaned = []
        for class_name, interface in implementing_classes:
            if class_name not in registered_classes:
                orphaned.append({
                    'class': class_name,
                    'implements': interface,
                    'status': 'NOT_REGISTERED'
                })
                
        conn.close()
        return orphaned


def main():
    """Main entry point for metadata parsing."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Parse EspoCRM metadata configuration files')
    parser.add_argument('project_root', help='Path to EspoCRM project root')
    parser.add_argument('--db', required=True, help='Path to SQLite database')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    metadata_parser = MetadataParser(args.db)
    metadata_parser.parse_metadata(args.project_root)
    metadata_parser.save_to_database()
    
    # Check for orphaned hooks
    orphaned = metadata_parser.get_orphaned_hooks()
    if orphaned:
        print("\n⚠️  WARNING: Found orphaned hook implementations:")
        for hook in orphaned:
            print(f"  - {hook['class']} implements {hook['implements']} but is NOT REGISTERED")
        print("\nThese hooks will NEVER execute unless registered in metadata/app/authentication.json")
    else:
        print("\n✅ All hook implementations are properly registered")


if __name__ == '__main__':
    main()