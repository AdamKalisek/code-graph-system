#!/usr/bin/env python3
"""Debug the parser to see why constants aren't collected"""

from parsers.php_enhanced import PHPSymbolCollector
from symbol_table import SymbolTable
import logging

logging.basicConfig(level=logging.DEBUG)

# Create symbol table
st = SymbolTable('.cache/test_debug.db')

# Create collector
collector = PHPSymbolCollector(st)

# Parse the test file
print("Parsing test file...")
collector.parse_file('test_simple_edges.php')

# Check what was collected
stats = st.get_stats()
print(f"\nCollected symbols: {stats}")

# List all symbols
import sqlite3
conn = sqlite3.connect('.cache/test_debug.db')
cur = conn.cursor()
cur.execute("SELECT name, type, parent_id FROM symbols ORDER BY line_number")
print("\nAll symbols:")
for row in cur.fetchall():
    print(f"  {row[0]:<30} {row[1]:<10} parent={row[2]}")
conn.close()