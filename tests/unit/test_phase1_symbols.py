#!/usr/bin/env python3
"""Phase 1 Test: Symbol Collection Validation"""

import sqlite3
from pathlib import Path
from parsers.php_enhanced import PHPSymbolCollector
from symbol_table import SymbolTable

def test_symbol_collection(file_path: str, expected: dict):
    """Test symbol collection for a single file"""
    print(f"\n{'='*60}")
    print(f"Testing: {file_path}")
    print('='*60)
    
    # Create clean symbol table
    db_path = f".cache/test_{Path(file_path).stem}.db"
    st = SymbolTable(db_path)
    
    # Collect symbols
    collector = PHPSymbolCollector(st)
    collector.parse_file(file_path)
    
    # Get statistics
    stats = st.get_stats()
    print(f"\nCollected Statistics:")
    for key, value in stats.items():
        if key.startswith('type_'):
            symbol_type = key.replace('type_', '')
            expected_val = expected.get(symbol_type, 0)
            status = "✅" if value == expected_val else "❌"
            print(f"  {symbol_type:<15} {value:>3} (expected: {expected_val}) {status}")
    
    # List all symbols
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    print(f"\nDetailed Symbol List:")
    cur.execute("""
        SELECT name, type, visibility, parent_id, extends, implements
        FROM symbols 
        ORDER BY type, name
    """)
    
    for row in cur.fetchall():
        name, stype, vis, parent, extends, implements = row
        details = []
        if vis: details.append(f"vis:{vis}")
        if parent: details.append("has_parent")
        if extends: details.append(f"extends:{extends}")
        if implements: details.append(f"impl:{implements}")
        detail_str = f" [{', '.join(details)}]" if details else ""
        print(f"  {stype:<10} {name:<40}{detail_str}")
    
    conn.close()
    
    # Validate
    passed = all(
        stats.get(f'type_{k}', 0) == v 
        for k, v in expected.items()
    )
    
    return passed, stats

# Test Case 1.1: Simple file
print("\n" + "="*60)
print("PHASE 1: SYMBOL COLLECTION TESTING")
print("="*60)

tc1_1_expected = {
    'namespace': 1,
    'class': 2,
    'method': 3,
    'constant': 1
}

passed1, stats1 = test_symbol_collection('test_simple_edges.php', tc1_1_expected)

# Test Case 1.2: Complex file
tc1_2_expected = {
    'namespace': 1,
    'class': 5,      # BaseController, PaymentInterface, PaymentController, Transaction, PaymentCalculator, PaymentConfig
    'interface': 1,  # PaymentInterface (defined twice, should be 1)
    'trait': 2,      # LoggerTrait, TimestampTrait
    'method': 12,    # Various methods
    'property': 5,   # user, emailService, repository, id, amount
    'constant': 6,   # Various constants
    'function': 1    # processOrder function
}

passed2, stats2 = test_symbol_collection('test_all_edges.php', tc1_2_expected)

# Summary
print("\n" + "="*60)
print("PHASE 1 TEST RESULTS")
print("="*60)
print(f"TC1.1 Simple Symbol Collection: {'✅ PASSED' if passed1 else '❌ FAILED'}")
print(f"TC1.2 Complex Symbol Collection: {'✅ PASSED' if passed2 else '❌ FAILED'}")
print(f"Overall Phase 1: {'✅ PASSED' if passed1 and passed2 else '❌ FAILED'}")