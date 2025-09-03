// ============================================================
// COMPLETE HIERARCHY VISUALIZATION 
// Shows: Directory → File → Class → Methods with ALL relationships
// ============================================================

// First, increase display limits:
:config initialNodeDisplay: 5000
:config maxNeighbours: 1000

// ============================================================
// 1. 🎯 THE COMPLETE HIERARCHY QUERY - SEE EVERYTHING!
// ============================================================
MATCH path = (d:Directory)-[:CONTAINS]->(f:File)
WHERE d.name IN ['Controllers', 'Repositories', 'Entities', 'Services', 'Core', 'Modules']
WITH d, f
OPTIONAL MATCH (f)-[:DEFINES]->(c)
WHERE c.type IN ['class', 'interface', 'trait', 'method']
WITH d, f, c
OPTIONAL MATCH (c)-[rel:EXTENDS|IMPLEMENTS|USES_TRAIT]->(parent)
RETURN d, f, c, rel, parent
LIMIT 2000;

// ============================================================
// 2. 📂 FULL DIRECTORY → FILE → CODE STRUCTURE
// ============================================================
MATCH (d:Directory)
WHERE d.name IN ['Espo', 'Controllers', 'Services', 'Entities']
MATCH path = (d)-[:CONTAINS*1..2]->(item)
OPTIONAL MATCH (item)-[:DEFINES]->(code)
OPTIONAL MATCH (code)-[r:EXTENDS|IMPLEMENTS|USES_TRAIT|CALLS|INSTANTIATES]->(target)
RETURN path, code, r, target
LIMIT 3000;

// ============================================================
// 3. 🌳 THE COMPLETE TREE - ALL NODE TYPES, ALL EDGE TYPES
// ============================================================
MATCH (d:Directory {name: 'Espo'})
MATCH path1 = (d)-[:CONTAINS*1..3]->(child)
WITH path1, child
OPTIONAL MATCH path2 = (child)-[:DEFINES|EXTENDS|IMPLEMENTS|USES_TRAIT]->(related)
WITH path1, path2, child, related
OPTIONAL MATCH path3 = (related)-[:CALLS|INSTANTIATES|IMPORTS|ACCESSES]->(deeper)
RETURN path1, path2, path3
LIMIT 2000;

// ============================================================
// 4. 🔍 VERIFY ALL EDGE TYPES EXIST - Visual Proof
// ============================================================
// This shows one example of EACH relationship type
MATCH (a)-[r:CONTAINS]->(b) WITH a, r, b LIMIT 5
RETURN a, r, b
UNION
MATCH (a)-[r:EXTENDS]->(b) WITH a, r, b LIMIT 5  
RETURN a, r, b
UNION
MATCH (a)-[r:IMPLEMENTS]->(b) WITH a, r, b LIMIT 5
RETURN a, r, b
UNION
MATCH (a)-[r:USES_TRAIT]->(b) WITH a, r, b LIMIT 5
RETURN a, r, b
UNION
MATCH (a)-[r:DEFINES]->(b) WITH a, r, b LIMIT 5
RETURN a, r, b
UNION
MATCH (a)-[r:CALLS]->(b) WITH a, r, b LIMIT 5
RETURN a, r, b
UNION
MATCH (a)-[r:INSTANTIATES]->(b) WITH a, r, b LIMIT 5
RETURN a, r, b;

// ============================================================
// 5. 🎪 THE MEGA VISUALIZATION - EVERYTHING AT ONCE
// ============================================================
MATCH (d:Directory)
WHERE d.path CONTAINS '/Espo/' OR d.path CONTAINS '/Modules/'
WITH d LIMIT 20
MATCH path = (d)-[:CONTAINS*1..2]->(:File)-[:DEFINES*0..1]->(code)
WHERE code IS NULL OR code.type IN ['class', 'interface', 'trait']
WITH path, code
OPTIONAL MATCH inheritance = (code)-[:EXTENDS|IMPLEMENTS|USES_TRAIT*1..2]->(parent)
OPTIONAL MATCH usage = (code)-[:CALLS|INSTANTIATES|IMPORTS*1..1]->(used)
RETURN path, inheritance, usage
LIMIT 5000;

// ============================================================
// 6. 📊 PROOF OF COMPLETE STRUCTURE
// ============================================================
// This query PROVES we have the complete hierarchy
MATCH (d:Directory)-[:CONTAINS]->(f:File)
WITH COUNT(DISTINCT d) as directories_with_files
MATCH (f:File)-[:DEFINES]->(c:PHPClass)
WITH directories_with_files, COUNT(DISTINCT f) as files_with_classes
MATCH (c:PHPClass)-[:EXTENDS]->(p:PHPClass)
WITH directories_with_files, files_with_classes, COUNT(DISTINCT c) as classes_with_inheritance
MATCH (c:PHPClass)-[:IMPLEMENTS]->(i:PHPInterface)
WITH directories_with_files, files_with_classes, classes_with_inheritance, COUNT(DISTINCT c) as classes_with_interfaces
MATCH (c:PHPClass)-[:USES_TRAIT]->(t:PHPTrait)
RETURN 
  directories_with_files as "Directories→Files",
  files_with_classes as "Files→Classes",
  classes_with_inheritance as "Classes→Extends",
  classes_with_interfaces as "Classes→Implements",
  COUNT(DISTINCT c) as "Classes→Traits";

// ============================================================
// 7. 🚀 THE ULTIMATE VISUAL PROOF - SEE ALL LAYERS
// ============================================================
// This shows the COMPLETE cascade: Directory → File → Class → Methods → Calls
MATCH path1 = (d:Directory)-[:CONTAINS]->(f:File)
WHERE d.name = 'Controllers' OR d.name = 'Services' OR d.name = 'Repositories'
WITH d, f, path1
MATCH path2 = (f)-[:DEFINES]->(class:PHPClass)
WITH d, f, class, path1, path2
OPTIONAL MATCH path3 = (class)-[:EXTENDS|IMPLEMENTS]->(parent)
WITH d, f, class, parent, path1, path2, path3
OPTIONAL MATCH path4 = (class)-[:DEFINES]->(method:PHPMethod)
WITH d, f, class, parent, method, path1, path2, path3, path4
OPTIONAL MATCH path5 = (method)-[:CALLS]->(called)
RETURN path1, path2, path3, path4, path5
LIMIT 1000;

// ============================================================
// 8. 🎯 VISUAL VERIFICATION CHECKLIST
// ============================================================
// Run this to verify ALL components are connected:
MATCH (d:Directory) WITH COUNT(d) as total_dirs
MATCH (f:File) WITH total_dirs, COUNT(f) as total_files  
MATCH (c:PHPClass) WITH total_dirs, total_files, COUNT(c) as total_classes
MATCH (i:PHPInterface) WITH total_dirs, total_files, total_classes, COUNT(i) as total_interfaces
MATCH (t:PHPTrait) WITH total_dirs, total_files, total_classes, total_interfaces, COUNT(t) as total_traits
MATCH (m:PHPMethod) WITH total_dirs, total_files, total_classes, total_interfaces, total_traits, COUNT(m) as total_methods
MATCH ()-[r:CONTAINS]->() WITH total_dirs, total_files, total_classes, total_interfaces, total_traits, total_methods, COUNT(r) as contains_rels
MATCH ()-[r:EXTENDS]->() WITH total_dirs, total_files, total_classes, total_interfaces, total_traits, total_methods, contains_rels, COUNT(r) as extends_rels
MATCH ()-[r:IMPLEMENTS]->() WITH total_dirs, total_files, total_classes, total_interfaces, total_traits, total_methods, contains_rels, extends_rels, COUNT(r) as implements_rels
MATCH ()-[r:USES_TRAIT]->() 
RETURN 
  total_dirs as "📁 Directories",
  total_files as "📄 Files", 
  total_classes as "🏗️ Classes",
  total_interfaces as "📋 Interfaces",
  total_traits as "🧩 Traits",
  total_methods as "⚙️ Methods",
  contains_rels as "↪️ CONTAINS",
  extends_rels as "⬆️ EXTENDS",
  implements_rels as "🔗 IMPLEMENTS",
  COUNT(r) as "🔀 USES_TRAIT";

// ============================================================
// INSTRUCTIONS:
// 1. Set display limits first (run the :config commands)
// 2. Run Query #7 for the BEST complete visualization
// 3. Run Query #8 to verify all counts
// 4. Use Query #4 to see examples of each relationship type
// ============================================================