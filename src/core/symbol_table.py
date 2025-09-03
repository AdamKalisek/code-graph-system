"""Symbol Table implementation with SQLite backend"""

import sqlite3
import json
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Set
from pathlib import Path
from functools import lru_cache
import hashlib
import logging

logger = logging.getLogger(__name__)


class SymbolType(Enum):
    """Types of symbols in the codebase"""
    CLASS = "class"
    INTERFACE = "interface"
    TRAIT = "trait"
    FUNCTION = "function"
    METHOD = "method"
    PROPERTY = "property"
    CONSTANT = "constant"
    NAMESPACE = "namespace"
    FILE = "file"
    VARIABLE = "variable"
    PARAMETER = "parameter"
    IMPORT = "import"
    TYPE_ALIAS = "type_alias"


@dataclass
class Symbol:
    """Represents a symbol in the codebase"""
    id: str
    name: str
    type: SymbolType
    file_path: str
    line_number: int
    column_number: int
    namespace: Optional[str] = None
    parent_id: Optional[str] = None
    visibility: Optional[str] = None  # public, private, protected
    is_static: bool = False
    is_abstract: bool = False
    is_final: bool = False
    return_type: Optional[str] = None
    parameters: Optional[List[Dict[str, Any]]] = None
    extends: Optional[str] = None
    implements: Optional[List[str]] = None
    uses: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    hash: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        result = {}
        for key, value in asdict(self).items():
            if key == 'type':
                result[key] = value.value
            elif key in ['parameters', 'implements', 'uses', 'metadata'] and value:
                result[key] = json.dumps(value)
            else:
                result[key] = value
        return result
    
    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'Symbol':
        """Create from database row"""
        data = dict(row)
        data['type'] = SymbolType(data['type'])
        
        # Parse JSON fields
        for field in ['parameters', 'implements', 'uses', 'metadata']:
            if field in data and data[field]:
                data[field] = json.loads(data[field])
        
        # Remove database-only fields
        data.pop('created_at', None)
        data.pop('updated_at', None)
        
        return cls(**data)


class SymbolTable:
    """Symbol Table with SQLite backend for fast lookups"""
    
    def __init__(self, db_path: str = ".cache/symbols.db"):
        """Initialize the symbol table"""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA cache_size=10000")
        self.conn.execute("PRAGMA temp_store=MEMORY")
        
        self._create_tables()
        self._create_indexes()
        
        # Create a cached version of resolve method
        self._resolve_cache = {}
    
    def _create_tables(self):
        """Create database tables"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS symbols (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                file_path TEXT NOT NULL,
                line_number INTEGER NOT NULL,
                column_number INTEGER NOT NULL,
                namespace TEXT,
                parent_id TEXT,
                visibility TEXT,
                is_static BOOLEAN DEFAULT 0,
                is_abstract BOOLEAN DEFAULT 0,
                is_final BOOLEAN DEFAULT 0,
                return_type TEXT,
                parameters TEXT,
                extends TEXT,
                implements TEXT,
                uses TEXT,
                metadata TEXT,
                hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_id) REFERENCES symbols(id) ON DELETE CASCADE
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS symbol_references (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                reference_type TEXT NOT NULL,
                line_number INTEGER NOT NULL,
                column_number INTEGER NOT NULL,
                context TEXT,
                FOREIGN KEY (source_id) REFERENCES symbols(id) ON DELETE CASCADE,
                FOREIGN KEY (target_id) REFERENCES symbols(id) ON DELETE CASCADE,
                UNIQUE(source_id, target_id, line_number, column_number)
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS file_hashes (
                file_path TEXT PRIMARY KEY,
                hash TEXT NOT NULL,
                last_parsed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.conn.commit()
    
    def _create_indexes(self):
        """Create database indexes for performance"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name)",
            "CREATE INDEX IF NOT EXISTS idx_symbols_namespace ON symbols(namespace)",
            "CREATE INDEX IF NOT EXISTS idx_symbols_type ON symbols(type)",
            "CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_path)",
            "CREATE INDEX IF NOT EXISTS idx_symbols_parent ON symbols(parent_id)",
            "CREATE INDEX IF NOT EXISTS idx_symbols_extends ON symbols(extends)",
            "CREATE INDEX IF NOT EXISTS idx_symbols_hash ON symbols(hash)",
            "CREATE INDEX IF NOT EXISTS idx_references_source ON symbol_references(source_id)",
            "CREATE INDEX IF NOT EXISTS idx_references_target ON symbol_references(target_id)",
            "CREATE INDEX IF NOT EXISTS idx_references_type ON symbol_references(reference_type)",
        ]
        
        for index in indexes:
            self.conn.execute(index)
        
        self.conn.commit()
    
    def add_symbol(self, symbol: Symbol) -> None:
        """Add a symbol to the table"""
        data = symbol.to_dict()
        
        # Generate ID if not provided
        if not symbol.id:
            id_string = f"{symbol.file_path}:{symbol.name}:{symbol.line_number}:{symbol.column_number}"
            symbol.id = hashlib.md5(id_string.encode()).hexdigest()
            data['id'] = symbol.id
        
        # Generate hash for content
        if not data.get('hash'):
            type_str = data['type'] if isinstance(data['type'], str) else data['type'].value
            hash_string = f"{data['name']}:{type_str}:{data.get('namespace') or ''}"
            data['hash'] = hashlib.md5(hash_string.encode()).hexdigest()
        
        columns = list(data.keys())
        placeholders = ['?' for _ in columns]
        
        query = f"""
            INSERT OR REPLACE INTO symbols ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
        """
        
        self.conn.execute(query, [data[col] for col in columns])
        
    def add_reference(self, source_id: str, target_id: str, 
                     reference_type: str, line: int, column: int,
                     context: Optional[str] = None) -> None:
        """Add a reference between symbols"""
        self.conn.execute("""
            INSERT OR IGNORE INTO symbol_references 
            (source_id, target_id, reference_type, line_number, column_number, context)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (source_id, target_id, reference_type, line, column, context))
    
    def resolve(self, name: str, current_namespace: str = "",
                imports: Optional[Dict[str, str]] = None) -> Optional[Symbol]:
        """FIXED VERSION - Resolve a symbol name to a Symbol object
        
        Resolution order:
        1. Check if it's a fully qualified name
        2. Check imports (aliases) FIRST before namespace resolution
        3. Check current namespace
        4. Check global namespace
        5. NEW: Try partial namespace matching for EspoCRM classes
        
        IMPORTANT: Only resolve to PHP symbols (classes, interfaces, traits, functions),
        never to directories or files.
        """
        imports = imports or {}
        
        # Create cache key from immutable parts
        cache_key = (name, current_namespace, tuple(sorted(imports.items())) if imports else ())
        if cache_key in self._resolve_cache:
            return self._resolve_cache[cache_key]
        
        # Define PHP code symbol types (exclude directories and files)
        php_symbol_types = ('class', 'interface', 'trait', 'function', 'namespace', 'enum')
        
        # FIX: Don't reject namespace names with backslashes!
        # Only reject if it's clearly a file path (has .extension)
        if '/' in name and ('.' in name.split('/')[-1]):
            self._resolve_cache[cache_key] = None
            return None
        
        # 1. Check if fully qualified (starts with \)
        if name.startswith('\\'):
            clean_name = name[1:]  # Remove leading \
            cursor = self.conn.execute(
                "SELECT * FROM symbols WHERE name = ? AND type IN (?, ?, ?, ?, ?, ?) LIMIT 1",
                (clean_name, *php_symbol_types)
            )
            row = cursor.fetchone()
            if row:
                result = Symbol.from_row(row)
                self._resolve_cache[cache_key] = result
                return result
        
        # 2. Check imports FIRST (before namespace resolution)
        if name in imports:
            resolved_name = imports[name]
            # Try with leading backslash removed
            clean_name = resolved_name.lstrip('\\')
            cursor = self.conn.execute(
                "SELECT * FROM symbols WHERE name = ? AND type IN (?, ?, ?, ?, ?, ?) LIMIT 1",
                (clean_name, *php_symbol_types)
            )
            row = cursor.fetchone()
            if row:
                result = Symbol.from_row(row)
                self._resolve_cache[cache_key] = result
                return result
        
        # 3. Check current namespace + name
        if current_namespace:
            namespaced_name = f"{current_namespace}\\{name}"
            cursor = self.conn.execute(
                "SELECT * FROM symbols WHERE name = ? AND type IN (?, ?, ?, ?, ?, ?) LIMIT 1",
                (namespaced_name, *php_symbol_types)
            )
            row = cursor.fetchone()
            if row:
                result = Symbol.from_row(row)
                self._resolve_cache[cache_key] = result
                return result
        
        # 4. Check global namespace (exact match)
        cursor = self.conn.execute(
            "SELECT * FROM symbols WHERE name = ? AND type IN (?, ?, ?, ?, ?, ?) LIMIT 1",
            (name, *php_symbol_types)
        )
        row = cursor.fetchone()
        if row:
            result = Symbol.from_row(row)
            self._resolve_cache[cache_key] = result
            return result
        
        # 5. NEW: Try partial namespace matching for EspoCRM classes
        if '\\' not in name:  # Only for simple class names
            cursor = self.conn.execute(
                "SELECT * FROM symbols WHERE name LIKE ? AND type IN (?, ?, ?, ?, ?, ?) LIMIT 1",
                (f"%\\{name}", *php_symbol_types)
            )
            row = cursor.fetchone()
            if row:
                result = Symbol.from_row(row)
                self._resolve_cache[cache_key] = result
                return result
        
        self._resolve_cache[cache_key] = None
        return None
    
    def get_by_id(self, symbol_id: str) -> Optional[Symbol]:
        """Get a symbol by its ID"""
        cursor = self.conn.execute(
            "SELECT * FROM symbols WHERE id = ? LIMIT 1",
            (symbol_id,)
        )
        row = cursor.fetchone()
        return Symbol.from_row(row) if row else None
    
    def get_symbols_in_file(self, file_path: str) -> List[Symbol]:
        """Get all symbols in a file"""
        cursor = self.conn.execute(
            "SELECT * FROM symbols WHERE file_path = ? ORDER BY line_number",
            (file_path,)
        )
        return [Symbol.from_row(row) for row in cursor]
    
    def get_children(self, parent_id: str) -> List[Symbol]:
        """Get child symbols of a parent"""
        cursor = self.conn.execute(
            "SELECT * FROM symbols WHERE parent_id = ?",
            (parent_id,)
        )
        return [Symbol.from_row(row) for row in cursor]
    
    def get_references_from(self, source_id: str) -> List[Dict[str, Any]]:
        """Get all references from a symbol"""
        cursor = self.conn.execute("""
            SELECT r.*, s.name as target_name, s.type as target_type
            FROM symbol_references r
            JOIN symbols s ON r.target_id = s.id
            WHERE r.source_id = ?
        """, (source_id,))
        
        return [dict(row) for row in cursor]
    
    def get_references_to(self, target_id: str) -> List[Dict[str, Any]]:
        """Get all references to a symbol"""
        cursor = self.conn.execute("""
            SELECT r.*, s.name as source_name, s.type as source_type
            FROM symbol_references r
            JOIN symbols s ON r.source_id = s.id
            WHERE r.target_id = ?
        """, (target_id,))
        
        return [dict(row) for row in cursor]
    
    def get_implementations(self, interface_name: str) -> List[Symbol]:
        """Get all implementations of an interface"""
        cursor = self.conn.execute("""
            SELECT * FROM symbols 
            WHERE implements LIKE ? 
            AND type IN ('class', 'trait')
        """, (f'%"{interface_name}"%',))
        
        return [Symbol.from_row(row) for row in cursor]
    
    def get_subclasses(self, class_name: str) -> List[Symbol]:
        """Get all subclasses of a class"""
        cursor = self.conn.execute("""
            SELECT * FROM symbols 
            WHERE extends = ? 
            AND type = 'class'
        """, (class_name,))
        
        return [Symbol.from_row(row) for row in cursor]
    
    def update_file_hash(self, file_path: str, file_hash: str) -> None:
        """Update the hash of a parsed file"""
        self.conn.execute("""
            INSERT OR REPLACE INTO file_hashes (file_path, hash, last_parsed)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (file_path, file_hash))
    
    def get_file_hash(self, file_path: str) -> Optional[str]:
        """Get the stored hash of a file"""
        cursor = self.conn.execute(
            "SELECT hash FROM file_hashes WHERE file_path = ?",
            (file_path,)
        )
        row = cursor.fetchone()
        return row['hash'] if row else None
    
    def needs_parsing(self, file_path: str, current_hash: str) -> bool:
        """Check if a file needs parsing based on hash"""
        stored_hash = self.get_file_hash(file_path)
        return stored_hash != current_hash
    
    def clear_file_symbols(self, file_path: str) -> None:
        """Clear all symbols from a file (before re-parsing)"""
        self.conn.execute(
            "DELETE FROM symbols WHERE file_path = ?",
            (file_path,)
        )
    
    def commit(self) -> None:
        """Commit current transaction"""
        self.conn.commit()
    
    def begin_transaction(self) -> None:
        """Begin a new transaction"""
        self.conn.execute("BEGIN")
    
    def rollback(self) -> None:
        """Rollback current transaction"""
        self.conn.rollback()
    
    def close(self) -> None:
        """Close the database connection"""
        self.conn.close()
    
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about the symbol table"""
        stats = {}
        
        # Total symbols
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM symbols")
        stats['total_symbols'] = cursor.fetchone()['count']
        
        # Symbols by type
        cursor = self.conn.execute("""
            SELECT type, COUNT(*) as count 
            FROM symbols 
            GROUP BY type
        """)
        for row in cursor:
            stats[f"type_{row['type']}"] = row['count']
        
        # Total references
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM symbol_references")
        stats['total_references'] = cursor.fetchone()['count']
        
        # Files parsed
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM file_hashes")
        stats['files_parsed'] = cursor.fetchone()['count']
        
        return stats
    
    def export_to_neo4j_format(self) -> tuple[List[Dict], List[Dict]]:
        """Export symbols and references in Neo4j format"""
        # Export nodes
        cursor = self.conn.execute("SELECT * FROM symbols")
        nodes = []
        for row in cursor:
            symbol = Symbol.from_row(row)
            node = {
                'id': symbol.id,
                'name': symbol.name,
                'type': symbol.type.value,
                'file_path': symbol.file_path,
                'line_number': symbol.line_number,
                'namespace': symbol.namespace,
                'visibility': symbol.visibility,
                'is_static': symbol.is_static,
                'is_abstract': symbol.is_abstract,
                'is_final': symbol.is_final,
                'return_type': symbol.return_type,
            }
            nodes.append(node)
        
        # Export edges
        cursor = self.conn.execute("SELECT * FROM symbol_references")
        edges = []
        for row in cursor:
            edge = {
                'source_id': row['source_id'],
                'target_id': row['target_id'],
                'type': row['reference_type'],
                'line_number': row['line_number'],
                'column_number': row['column_number'],
                'context': row['context']
            }
            edges.append(edge)
        
        return nodes, edges