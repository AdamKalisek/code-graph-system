"""Database connection and base repository pattern."""

from typing import List, Optional, Dict, Any


class Database:
    """Simple database connection wrapper"""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.connected = False

    def connect(self) -> bool:
        """Establish database connection"""
        print(f"Connecting to {self.connection_string}")
        self.connected = True
        return True

    def disconnect(self) -> None:
        """Close database connection"""
        self.connected = False

    def execute(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict]:
        """Execute a query and return results"""
        if not self.connected:
            raise RuntimeError("Database not connected")
        print(f"Executing: {query}")
        return []


class Repository:
    """Base repository for data access"""

    def __init__(self, db: Database):
        self.db = db

    def find_all(self) -> List[Dict]:
        """Find all records"""
        return self.db.execute("SELECT * FROM table")

    def find_by_id(self, record_id: int) -> Optional[Dict]:
        """Find a record by ID"""
        results = self.db.execute("SELECT * FROM table WHERE id = :id", {"id": record_id})
        return results[0] if results else None
