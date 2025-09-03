Debug logic and neo4j search

## ✅ GOAL COMPLETED

### Problem Identified:
Neo4j queries gave incorrect information about login hook registration, telling user hooks were auto-discovered when they actually require explicit JSON registration.

### Root Cause:
- Neo4j graph only contained PHP code structure (classes, interfaces)
- Missing JSON configuration metadata that controls runtime behavior
- Static code analysis can't see dynamic string-based loading from config files

### Solution Implemented:
1. ✅ Created metadata parser to extract config references from JSON files
2. ✅ Added 678 configuration references to SQLite database
3. ✅ Imported config data to Neo4j with new node/relationship types:
   - `ConfigFile` nodes for JSON files
   - `REGISTERED_IN` relationships for hook registration
   - `LOADS_VIA_CONFIG` relationships for dynamic loading
   - `requires_registration` property on hooks

### Verification:
Neo4j now correctly shows:
- All 3 login hooks are properly registered in authentication.json
- Manager loads hooks via metadata configuration, not filesystem
- Clear distinction between auto-discovered entity hooks and registered login hooks

### Impact:
Future Neo4j queries will accurately reflect actual runtime behavior, preventing incorrect advice about hook registration and other configuration-driven features in EspoCRM.
