# Neo4j Query Examples for EspoCRM Code Analysis

## 🎯 Purpose
This document contains tested Neo4j queries for analyzing real code flows in EspoCRM. Each query is designed to answer specific questions about how the system works.

## ⚠️ CRITICAL: Configuration-Aware Queries (UPDATED!)

### Check if a Hook Requires Registration
```cypher
// Find hooks that REQUIRE explicit JSON registration (not auto-discovered)
MATCH (c:PHPClass)-[:IMPLEMENTS]->(i:PHPInterface)
WHERE i.name CONTAINS 'Hook'
OPTIONAL MATCH (c)-[r:REGISTERED_IN]->(f:ConfigFile)
RETURN c.name as hook_class, 
       c.requires_registration as needs_registration,
       f.path as config_file,
       r.config_key as registration_key
```

### Trace Dynamic Loading via Configuration
```cypher
// See how Manager loads hooks through configuration (not filesystem)
MATCH path = (m:PHPClass)-[:LOADS_VIA_CONFIG]->(h:PHPClass)
WHERE m.name CONTAINS 'Manager'
RETURN m.name as manager, h.name as hook, 
       relationships(path)[0].config_key as config_key,
       relationships(path)[0].mechanism as loading_mechanism
```

### Find Orphaned Hooks (Implemented but Not Registered)
```cypher
// CRITICAL: Find hooks that will NEVER execute because not registered
MATCH (c:PHPClass)-[:IMPLEMENTS]->(i:PHPInterface)
WHERE i.name IN ['Espo\\Core\\Authentication\\Hook\\BeforeLogin', 
                 'Espo\\Core\\Authentication\\Hook\\OnLogin']
AND NOT EXISTS((c)-[:REGISTERED_IN]->(:ConfigFile))
RETURN c.name as orphaned_hook, 
       i.name as implements,
       'NOT REGISTERED - WILL NOT EXECUTE!' as warning
```

### View All Configuration Files
```cypher
// See all configuration files in the system
MATCH (f:ConfigFile)
RETURN f.path as config_file, f.type as file_type
ORDER BY f.path
```

### Find Classes Loaded from Configuration
```cypher
// Find all classes that are loaded dynamically from config files
MATCH (c:PHPClass)-[r:REGISTERED_IN]->(f:ConfigFile)
RETURN c.name as class_name,
       r.registration_type as registration_type,
       r.config_key as config_key,
       f.path as config_file
ORDER BY r.registration_type, c.name
```

## 📧 Email System Queries

### 1. How is email sent? (Complete flow)
```cypher
// Trace complete email sending flow
MATCH (m:PHPMethod)
WHERE m.name = 'send' AND m.file_path CONTAINS 'Mail'
WITH m
MATCH (m)-[r:CALLS]->(called:PHPMethod)
RETURN m.name as SendMethod, 
       m.file_path as FromFile,
       type(r) as RelationType,
       called.name as CallsMethod,
       called.file_path as InFile
ORDER BY FromFile, CallsMethod
```

### 2. What classes handle email operations?
```cypher
// Find all email-related classes and their methods
MATCH (c:PHPClass)
WHERE toLower(c.name) CONTAINS 'email' OR toLower(c.name) CONTAINS 'mail'
OPTIONAL MATCH (c)-[:DEFINES]->(m:PHPMethod)
RETURN c.name as ClassName, 
       c.file_path as FilePath,
       collect(DISTINCT m.name) as Methods
ORDER BY c.name
LIMIT 20
```

### 3. Email template processing
```cypher
// How are email templates processed?
MATCH (c:PHPClass)
WHERE c.name CONTAINS 'EmailTemplate' OR c.name CONTAINS 'Template'
OPTIONAL MATCH (c)-[:DEFINES]->(m:PHPMethod)
WHERE m.name CONTAINS 'render' OR m.name CONTAINS 'process' OR m.name CONTAINS 'parse'
RETURN c.name as ClassName, 
       m.name as Method,
       c.file_path as FilePath
```

## 🔐 Authentication Queries

### 4. How does authentication work?
```cypher
// Trace authentication flow
MATCH (c:PHPClass)
WHERE toLower(c.name) CONTAINS 'auth' OR c.name CONTAINS 'Login'
OPTIONAL MATCH (c)-[:DEFINES]->(m:PHPMethod)
WHERE m.name IN ['authenticate', 'login', 'verify', 'check', 'validate']
RETURN c.name as ClassName,
       m.name as Method,
       c.file_path as FilePath
ORDER BY c.name
```

### 5. Password handling
```cypher
// Find password-related operations
MATCH (m:PHPMethod)
WHERE toLower(m.name) CONTAINS 'password'
RETURN m.name as Method,
       m.file_path as FilePath
ORDER BY FilePath
LIMIT 30
```

## 🪝 Webhook System Queries

### 6. How are webhooks triggered?
```cypher
// Find webhook execution chain
MATCH (c:PHPClass)
WHERE c.name CONTAINS 'Webhook'
OPTIONAL MATCH (c)-[:DEFINES]->(m:PHPMethod)
WHERE m.name IN ['trigger', 'send', 'execute', 'process', 'fire']
OPTIONAL MATCH (m)-[:CALLS]->(called:PHPMethod)
RETURN c.name as ClassName,
       m.name as Method,
       collect(DISTINCT called.name) as CallsMethods
```

### 7. Event listeners and hooks
```cypher
// Find all hook/event listener patterns
MATCH (c:PHPClass)
WHERE c.name CONTAINS 'Hook' OR c.name CONTAINS 'Listener' OR c.name CONTAINS 'Event'
OPTIONAL MATCH (c)-[:DEFINES]->(m:PHPMethod)
WHERE m.name IN ['handle', 'process', 'on', 'fire', 'trigger', 'dispatch']
RETURN c.name as ClassName,
       m.name as Method,
       c.file_path as FilePath
LIMIT 30
```

## 📊 Data Operations Queries

### 8. How are records saved?
```cypher
// Find save/create operations
MATCH (m:PHPMethod)
WHERE m.name IN ['save', 'create', 'store', 'persist']
RETURN m.name as Method,
       m.file_path as FilePath
ORDER BY FilePath
LIMIT 30
```

### 9. Database query building
```cypher
// How are database queries built?
MATCH (c:PHPClass)
WHERE c.name CONTAINS 'Query' OR c.name CONTAINS 'Builder' OR c.name CONTAINS 'Select'
OPTIONAL MATCH (c)-[:DEFINES]->(m:PHPMethod)
WHERE m.name IN ['where', 'select', 'from', 'join', 'build', 'execute']
RETURN c.name as ClassName,
       collect(DISTINCT m.name) as QueryMethods,
       c.file_path as FilePath
```

## 🔄 Import/Export Queries

### 10. How does data import work?
```cypher
// Trace import process
MATCH (c:PHPClass)
WHERE c.name CONTAINS 'Import'
OPTIONAL MATCH (c)-[:DEFINES]->(m:PHPMethod)
WHERE m.name IN ['import', 'process', 'run', 'execute', 'parse']
OPTIONAL MATCH (m)-[:CALLS]->(called:PHPMethod)
RETURN c.name as ClassName,
       m.name as Method,
       collect(DISTINCT called.name) as CallsChain
```

### 11. Export functionality
```cypher
// Find export operations
MATCH (c:PHPClass)
WHERE c.name CONTAINS 'Export'
OPTIONAL MATCH (c)-[:DEFINES]->(m:PHPMethod)
RETURN c.name as ClassName,
       collect(DISTINCT m.name) as Methods,
       c.file_path as FilePath
```

## 🔑 API Queries

### 12. API endpoint handling
```cypher
// Find API controllers and their actions
MATCH (c:PHPClass)
WHERE c.file_path CONTAINS 'Controllers' 
OPTIONAL MATCH (c)-[:DEFINES]->(m:PHPMethod)
WHERE m.name STARTS WITH 'action' OR m.name STARTS WITH 'post' OR m.name STARTS WITH 'get'
RETURN c.name as Controller,
       collect(DISTINCT m.name) as Actions
ORDER BY c.name
LIMIT 20
```

### 13. REST API routes
```cypher
// Find REST operations
MATCH (m:PHPMethod)
WHERE m.name IN ['get', 'post', 'put', 'patch', 'delete'] 
  AND m.file_path CONTAINS 'Controller'
RETURN m.name as HTTPMethod,
       m.file_path as Controller
LIMIT 30
```

## 🏗️ Inheritance & Traits Queries

### 14. Class inheritance chains
```cypher
// Find inheritance hierarchies
MATCH path = (child:PHPClass)-[:EXTENDS*1..5]->(parent:PHPClass)
WHERE parent.name CONTAINS 'Base' OR parent.name CONTAINS 'Abstract'
RETURN child.name as ChildClass,
       parent.name as ParentClass,
       length(path) as InheritanceDepth
ORDER BY InheritanceDepth DESC
LIMIT 20
```

### 15. Trait usage patterns
```cypher
// Which classes use which traits?
MATCH (c:PHPClass)-[:USES_TRAIT]->(t:PHPTrait)
RETURN c.name as ClassName,
       t.name as TraitName,
       c.file_path as FilePath
ORDER BY t.name
```

## 📊 Statistics Queries

### 16. Most called methods
```cypher
// Find the most frequently called methods
MATCH (m:PHPMethod)<-[r:CALLS]-()
RETURN m.name as Method,
       m.file_path as FilePath,
       count(r) as CallCount
ORDER BY CallCount DESC
LIMIT 20
```

### 17. Most complex classes (by relationships)
```cypher
// Find classes with most relationships
MATCH (c:PHPClass)-[r]-()
RETURN c.name as ClassName,
       count(DISTINCT r) as RelationshipCount,
       collect(DISTINCT type(r)) as RelationshipTypes
ORDER BY RelationshipCount DESC
LIMIT 20
```

## 🔍 Advanced Pattern Queries

### 18. Find circular dependencies
```cypher
// Detect circular dependencies
MATCH path = (c1:PHPClass)-[:EXTENDS|IMPLEMENTS|USES_TRAIT|DEPENDS_ON*2..5]->(c1)
RETURN c1.name as Class,
       length(path) as CycleLength,
       [node IN nodes(path) | node.name] as Cycle
LIMIT 10
```

### 19. Find factory patterns
```cypher
// Find factory methods and classes
MATCH (c:PHPClass)
WHERE c.name CONTAINS 'Factory'
OPTIONAL MATCH (c)-[:DEFINES]->(m:PHPMethod)
WHERE m.name IN ['create', 'make', 'build', 'getInstance']
RETURN c.name as FactoryClass,
       collect(DISTINCT m.name) as FactoryMethods,
       c.file_path as FilePath
```

### 20. Service layer identification
```cypher
// Find service classes and their operations
MATCH (c:PHPClass)
WHERE c.name CONTAINS 'Service' AND c.file_path CONTAINS 'Services'
OPTIONAL MATCH (c)-[:DEFINES]->(m:PHPMethod)
WHERE NOT m.name STARTS WITH '__'
RETURN c.name as ServiceClass,
       count(m) as MethodCount,
       collect(m.name)[0..5] as SampleMethods
ORDER BY MethodCount DESC
```

## 💡 Query Tips

1. **Use `toLower()` for case-insensitive searches**:
   ```cypher
   WHERE toLower(c.name) CONTAINS 'email'
   ```

2. **Use `OPTIONAL MATCH` to include nodes without relationships**:
   ```cypher
   OPTIONAL MATCH (c)-[:DEFINES]->(m:PHPMethod)
   ```

3. **Use `collect()` to aggregate results**:
   ```cypher
   collect(DISTINCT m.name) as Methods
   ```

4. **Use path queries to trace flows**:
   ```cypher
   MATCH path = (start)-[:CALLS*1..3]->(end)
   ```

5. **Limit results during exploration**:
   ```cypher
   LIMIT 20
   ```

## 🎯 Query Analysis Checklist

Before using a query, verify:
- [ ] Node labels are correct (PHPClass, PHPMethod, etc.)
- [ ] Property names match database schema (name, file_path)
- [ ] Relationship types are valid (CALLS, EXTENDS, etc.)
- [ ] WHERE clauses use correct operators
- [ ] LIMIT is set for exploration queries
- [ ] Results make sense for the codebase

## 📝 Notes
- All queries tested against EspoCRM codebase
- Database contains 35,786 nodes and 80,619 relationships
- Relationship types: CALLS (18,939), IMPORTS (14,151), ACCESSES (10,339), etc.
- Use these as templates and modify for specific needs