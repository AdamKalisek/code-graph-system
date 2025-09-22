# WebSlicer TypeScript Parser Fix Plan

## GOAL
Ensure 100% accurate TypeScript/React parsing with NO PHP labels in the database for webSlicer project.

## Current Problem
- TypeScript files are being labeled with PHP types (PHPSymbol, PHPProperty, etc.)
- Wrong relationship types or missing relationships
- Parser is not correctly identifying TypeScript/React constructs

## Investigation Steps

### Phase 1: Deep Investigation ✅
- [x] Create this plan document
- [ ] Check current database content in detail
- [ ] Trace through the parser pipeline to find where PHP labels are introduced
- [ ] Check plugin registration and selection logic
- [ ] Verify TypeScript parser is actually being used
- [ ] Document all findings with specific code references

### Phase 2: Prepare for Codex
- [ ] Compile list of specific issues with examples
- [ ] Create suggestions for fixes
- [ ] Identify exact files and functions that need changes
- [ ] Prepare clear, actionable request for Codex

### Phase 3: Codex Collaboration
- [ ] Send detailed findings to Codex with suggestions
- [ ] Review Codex's proposed solution
- [ ] Apply Codex's fixes to the codebase

### Phase 4: Clean Rebuild & Verification
- [ ] Clean Neo4j database completely
- [ ] Delete existing SQLite database
- [ ] Re-parse webSlicer with fixed parser
- [ ] Import fresh data to Neo4j
- [ ] Query Neo4j for verification

### Phase 5: Accuracy Verification
- [ ] Query for PHP* labels (should be 0)
- [ ] Check ReactComponent nodes match actual .tsx files
- [ ] Verify TSFunction nodes match actual functions
- [ ] Check RENDERS relationships match JSX in code
- [ ] Verify CALLS relationships match actual function calls
- [ ] Cross-reference 5-10 files manually for 100% accuracy

## Verification Queries

```cypher
// Should return 0
MATCH (n) WHERE n.type STARTS WITH 'PHP' RETURN count(n)

// Should match actual React components
MATCH (n:ReactComponent) RETURN n.name, n.file_path LIMIT 10

// Should show correct relationships
MATCH (c:ReactComponent)-[:RENDERS]->(element) RETURN c.name, element.name LIMIT 20
```

## Success Criteria
1. Zero PHP labels in TypeScript project
2. All React components correctly identified
3. All TypeScript types/interfaces correctly labeled
4. Relationships match actual code structure
5. Manual spot checks pass 100%

## Current Status
**✅ COMPLETED - ALL ISSUES FIXED!**

## Final Results

### Success Metrics Achieved:
- ✅ **ZERO PHP labels** in TypeScript project (0 out of 5,041 nodes)
- ✅ **473 TypeScript types** correctly preserved (TSFunction, TSInterface, TSClass, TSType)
- ✅ **291 React components** correctly identified
- ✅ **31 API routes** properly labeled
- ✅ **All relationships preserved**: RENDERS (1,211), CALLS (517), USES (768), etc.
- ✅ **244 React components** with JSX relationships
- ✅ **65 TypeScript functions** with call relationships

### Fix Applied:
Codex successfully modified `tools/ultra_fast_neo4j_import.py` to preserve original type names from SQLite instead of mapping them to PHP labels. The function now only maps 'file' → 'File' and 'directory' → 'Directory', preserving all other types as-is.

## Investigation Findings

### ROOT CAUSE FOUND! ✅

The issue is NOT in the parser! The TypeScript parser is working correctly. The problem is in the **Neo4j import script**.

**Location:** `tools/ultra_fast_neo4j_import.py`
**Function:** `_get_label_for_type()` (lines 568-583)

**The Problem:**
1. SQLite database has CORRECT types: `ReactComponent`, `TSFunction`, `TSInterface`, etc.
2. The import script has a hardcoded mapping that converts generic types to PHP labels
3. Line 583: `return type_map.get(symbol_type, 'PHPSymbol')` - defaults to PHPSymbol for unmapped types!

**Current Broken Mapping:**
```python
type_map = {
    'class': 'PHPClass',           # Maps TSClass → PHPClass
    'function': 'PHPFunction',      # Maps TSFunction → PHPFunction
    'property': 'PHPProperty',      # Maps property → PHPProperty
    'interface': 'PHPInterface',    # Maps TSInterface → PHPInterface
    ...
}
return type_map.get(symbol_type, 'PHPSymbol')  # Everything else → PHPSymbol
```

**Evidence:**
- SQLite has correct types: TSFunction (174), ReactComponent (291), TSInterface (147)
- Neo4j shows same counts but under generic labels
- The import script is stripping the TS/React prefixes and mapping to PHP labels

## Suggestions for Codex

### Request for Codex:

**File to fix:** `tools/ultra_fast_neo4j_import.py`

**Function to fix:** `_get_label_for_type()` (lines 568-583)

**Required changes:**
1. Remove the hardcoded PHP mapping
2. Use the actual type from SQLite as the Neo4j label
3. Keep special handling only for file/directory
4. Simple solution: just return the symbol_type directly (with capital first letter)

**Suggested implementation:**
```python
def _get_label_for_type(self, symbol_type: str) -> str:
    """Map symbol type to Neo4j label"""
    # Special cases that need different labels
    special_cases = {
        'file': 'File',
        'directory': 'Directory',
    }

    # For special cases, use the mapping
    if symbol_type in special_cases:
        return special_cases[symbol_type]

    # For everything else, use the type as-is
    # This preserves ReactComponent, TSFunction, TSInterface, etc.
    return symbol_type if symbol_type else 'Symbol'
```

**Additional context for Codex:**
- The parser already creates correct types like ReactComponent, TSFunction, TSInterface
- We need to preserve these exact types in Neo4j
- No PHP labels should exist for TypeScript/React projects
- The import script should be language-agnostic