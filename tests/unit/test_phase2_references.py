#!/usr/bin/env python3
"""Phase 2 Test: Reference Resolution Validation"""

import sqlite3
from collections import defaultdict
from parsers.php_enhanced import PHPSymbolCollector
from parsers.php_reference_resolver import PHPReferenceResolver
from symbol_table import SymbolTable

def test_reference_resolution(file_path: str):
    """Test reference resolution for a file"""
    print(f"\n{'='*60}")
    print(f"Testing References: {file_path}")
    print('='*60)
    
    # Create clean symbol table
    db_path = ".cache/test_references.db"
    st = SymbolTable(db_path)
    
    # Phase 1: Collect symbols
    collector = PHPSymbolCollector(st)
    collector.parse_file(file_path)
    
    # Phase 2: Resolve references
    resolver = PHPReferenceResolver(st)
    resolver.resolve_file(file_path)
    
    # Analyze references
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Count references by type
    cur.execute("""
        SELECT reference_type, COUNT(*) as count
        FROM symbol_references
        GROUP BY reference_type
        ORDER BY count DESC
    """)
    
    reference_counts = {}
    print("\nReference Type Counts:")
    for row in cur.fetchall():
        ref_type, count = row
        reference_counts[ref_type] = count
        print(f"  {ref_type:<20} {count:>3}")
    
    # List all references with details
    print("\nDetailed References:")
    cur.execute("""
        SELECT 
            s1.name as source,
            r.reference_type as type,
            s2.name as target,
            r.line_number as line
        FROM symbol_references r
        JOIN symbols s1 ON r.source_id = s1.id
        JOIN symbols s2 ON r.target_id = s2.id
        ORDER BY r.reference_type, r.line_number
    """)
    
    references_by_type = defaultdict(list)
    for row in cur.fetchall():
        source, ref_type, target, line = row
        references_by_type[ref_type].append(f"L{line}: {source} -> {target}")
    
    for ref_type in sorted(references_by_type.keys()):
        print(f"\n  {ref_type}:")
        for ref in references_by_type[ref_type][:3]:  # Show first 3 of each type
            print(f"    {ref}")
        if len(references_by_type[ref_type]) > 3:
            print(f"    ... and {len(references_by_type[ref_type])-3} more")
    
    conn.close()
    
    return reference_counts

# Test both files
print("\n" + "="*60)
print("PHASE 2: REFERENCE RESOLUTION TESTING")
print("="*60)

# Test simple file
counts1 = test_reference_resolution('test_simple_edges.php')

# Test complex file
counts2 = test_reference_resolution('test_all_edges.php')

# Validate expected edge types
print("\n" + "="*60)
print("PHASE 2 VALIDATION")
print("="*60)

expected_types = [
    'EXTENDS', 'IMPLEMENTS', 'USES_TRAIT', 'IMPORTS',
    'THROWS', 'USES_CONSTANT', 'CALLS', 'CALLS_STATIC',
    'INSTANTIATES', 'ACCESSES', 'PARAMETER_TYPE', 
    'RETURNS', 'INSTANCEOF'
]

print("\nEdge Type Coverage (Complex File):")
for edge_type in expected_types:
    count = counts2.get(edge_type, 0)
    status = "✅" if count > 0 else "❌"
    print(f"  {edge_type:<20} {count:>3} {status}")

# Summary
missing = [t for t in expected_types if counts2.get(t, 0) == 0]
coverage = (len(expected_types) - len(missing)) / len(expected_types) * 100

print(f"\nCoverage: {coverage:.1f}% ({len(expected_types)-len(missing)}/{len(expected_types)} edge types)")
if missing:
    print(f"Missing: {', '.join(missing)}")

print(f"\nPhase 2 Result: {'✅ PASSED' if coverage >= 90 else '❌ FAILED'}")