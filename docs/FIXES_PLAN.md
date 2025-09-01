# Universal Code Graph System - Fixes Implementation Plan

## 🎯 Priority Fixes (Ordered by Impact)

### 1. Replace PHP Parser (CRITICAL)
**Fix:** Install and integrate `nikic/php-parser` for proper AST parsing  
**Impact:** Resolves all parsing errors immediately  
**Time:** 2-3 hours  

### 2. Implement Bulk Data Ingestion (HIGH)
**Fix:** Use Neo4j `UNWIND` for batch operations instead of single inserts  
**Impact:** 100-1000x performance improvement  
**Time:** 1-2 hours  

### 3. Add Multi-Label Support (MEDIUM)
**Fix:** Apply hierarchical labels (`:PHPClass:Symbol:CoreNode`)  
**Impact:** Enables polymorphic queries  
**Time:** 2 hours  

### 4. Convert JSON Properties to Relationships (MEDIUM)
**Fix:** Create proper edges instead of storing as strings  
**Impact:** Enables graph traversal queries  
**Time:** 2 hours  

### 5. Add Directory Nodes (MEDIUM)
**Fix:** Model filesystem structure with Directory nodes  
**Impact:** Architectural analysis capability  
**Time:** 3 hours  

### 6. Parse Configuration Files (LOW)
**Fix:** Add metadata JSON parsing for EspoCRM  
**Impact:** Complete system understanding  
**Time:** 4 hours  

## 📅 Implementation Schedule

### Day 1 (Today)
- [ ] Replace PHP parser with nikic/php-parser
- [ ] Test parsing accuracy
- [ ] Implement bulk ingestion

### Day 2
- [ ] Add multi-label support
- [ ] Convert properties to relationships
- [ ] Update schema

### Day 3
- [ ] Add directory modeling
- [ ] Parse configuration files
- [ ] Full system test

### Day 4
- [ ] Performance testing
- [ ] Documentation update
- [ ] Final validation

## ✅ Success Criteria

- Parse Container.php and find ALL methods/properties
- Process 1000 files in under 30 seconds
- Support queries like `MATCH (s:Symbol) RETURN s`
- Model complete filesystem hierarchy
- Zero parsing errors on EspoCRM codebase

## 🚀 Next Step

Start with replacing the PHP parser - this unblocks everything else.