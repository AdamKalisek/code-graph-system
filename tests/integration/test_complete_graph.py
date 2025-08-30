#!/usr/bin/env python3
"""
Complete Graph Test - Creates a realistic code graph with all node types and relationships
This represents what our indexing SHOULD create
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from code_graph_system.core.graph_store import FederatedGraphStore
from code_graph_system.core.schema import Symbol, File, Relationship, Endpoint
from datetime import datetime

def clean_database(graph):
    """Completely clean the database"""
    print("🧹 Cleaning database...")
    graph.graph.run("MATCH (n) DETACH DELETE n")
    result = graph.query("MATCH (n) RETURN count(n) as count")[0]['count']
    print(f"   Nodes remaining: {result}")

def create_complete_graph():
    """Create a complete graph with all node types and relationships"""
    print("\n" + "="*70)
    print("COMPLETE CODE GRAPH TEST")
    print("Creating realistic graph with all relationship types")
    print("="*70)
    
    # Connect to Neo4j
    print("\n1. Connecting to Neo4j...")
    graph = FederatedGraphStore(
        'bolt://localhost:7688',
        ('neo4j', 'password123'),
        {'federation': {'mode': 'unified'}}
    )
    
    # Clean database
    clean_database(graph)
    
    # ==========================================
    # DIRECTORY STRUCTURE
    # ==========================================
    print("\n2. Creating directory structure...")
    directories = {
        'root': Symbol(name="app", qualified_name="app", kind="directory", plugin_id="filesystem"),
        'controllers': Symbol(name="controllers", qualified_name="app/controllers", kind="directory", plugin_id="filesystem"),
        'models': Symbol(name="models", qualified_name="app/models", kind="directory", plugin_id="filesystem"),
        'services': Symbol(name="services", qualified_name="app/services", kind="directory", plugin_id="filesystem"),
        'client': Symbol(name="client", qualified_name="app/client", kind="directory", plugin_id="filesystem"),
        'views': Symbol(name="views", qualified_name="app/client/views", kind="directory", plugin_id="filesystem"),
        'js_models': Symbol(name="models", qualified_name="app/client/models", kind="directory", plugin_id="filesystem"),
        'js_services': Symbol(name="services", qualified_name="app/client/services", kind="directory", plugin_id="filesystem"),
    }
    
    dir_relationships = [
        Relationship(source_id=directories['root'].id, target_id=directories['controllers'].id, type="CONTAINS"),
        Relationship(source_id=directories['root'].id, target_id=directories['models'].id, type="CONTAINS"),
        Relationship(source_id=directories['root'].id, target_id=directories['services'].id, type="CONTAINS"),
        Relationship(source_id=directories['root'].id, target_id=directories['client'].id, type="CONTAINS"),
        Relationship(source_id=directories['client'].id, target_id=directories['views'].id, type="CONTAINS"),
        Relationship(source_id=directories['client'].id, target_id=directories['js_models'].id, type="CONTAINS"),
        Relationship(source_id=directories['client'].id, target_id=directories['js_services'].id, type="CONTAINS"),
    ]
    
    # ==========================================
    # PHP FILES
    # ==========================================
    print("\n3. Creating PHP files...")
    php_files = {
        'user_controller': File(
            path="app/controllers/UserController.php",
            language="php",
            name="UserController.php",
            plugin_id="php"
        ),
        'base_controller': File(
            path="app/controllers/BaseController.php",
            language="php",
            name="BaseController.php",
            plugin_id="php"
        ),
        'user_model': File(
            path="app/models/User.php",
            language="php",
            name="User.php",
            plugin_id="php"
        ),
        'user_service': File(
            path="app/services/UserService.php",
            language="php",
            name="UserService.php",
            plugin_id="php"
        ),
    }
    
    # File to Directory relationships
    file_dir_relationships = [
        Relationship(source_id=php_files['user_controller'].id, target_id=directories['controllers'].id, type="IN_DIRECTORY"),
        Relationship(source_id=php_files['base_controller'].id, target_id=directories['controllers'].id, type="IN_DIRECTORY"),
        Relationship(source_id=php_files['user_model'].id, target_id=directories['models'].id, type="IN_DIRECTORY"),
        Relationship(source_id=php_files['user_service'].id, target_id=directories['services'].id, type="IN_DIRECTORY"),
    ]
    
    # ==========================================
    # PHP CLASSES
    # ==========================================
    print("\n4. Creating PHP classes...")
    php_classes = {
        'UserController': Symbol(
            name="UserController",
            qualified_name="App\\Controllers\\UserController",
            kind="class",
            plugin_id="php",
            metadata={"namespace": "App\\Controllers"}
        ),
        'BaseController': Symbol(
            name="BaseController",
            qualified_name="App\\Controllers\\BaseController",
            kind="class",
            plugin_id="php",
            metadata={"namespace": "App\\Controllers"}
        ),
        'User': Symbol(
            name="User",
            qualified_name="App\\Models\\User",
            kind="class",
            plugin_id="php",
            metadata={"namespace": "App\\Models"}
        ),
        'UserService': Symbol(
            name="UserService",
            qualified_name="App\\Services\\UserService",
            kind="class",
            plugin_id="php",
            metadata={"namespace": "App\\Services"}
        ),
        'ControllerInterface': Symbol(
            name="ControllerInterface",
            qualified_name="App\\Interfaces\\ControllerInterface",
            kind="interface",
            plugin_id="php",
            metadata={"namespace": "App\\Interfaces"}
        ),
    }
    
    # PHP Methods
    php_methods = {
        'list': Symbol(name="list", qualified_name="UserController::list", kind="method", plugin_id="php"),
        'create': Symbol(name="create", qualified_name="UserController::create", kind="method", plugin_id="php"),
        'delete': Symbol(name="delete", qualified_name="UserController::delete", kind="method", plugin_id="php"),
        'getAllUsers': Symbol(name="getAllUsers", qualified_name="UserService::getAllUsers", kind="method", plugin_id="php"),
        'saveUser': Symbol(name="saveUser", qualified_name="UserService::saveUser", kind="method", plugin_id="php"),
        'deleteUser': Symbol(name="deleteUser", qualified_name="UserService::deleteUser", kind="method", plugin_id="php"),
    }
    
    # ==========================================
    # JAVASCRIPT FILES
    # ==========================================
    print("\n5. Creating JavaScript files...")
    js_files = {
        'user_view': File(
            path="app/client/views/UserView.js",
            language="javascript",
            name="UserView.js",
            plugin_id="javascript"
        ),
        'base_view': File(
            path="app/client/views/BaseView.js",
            language="javascript",
            name="BaseView.js",
            plugin_id="javascript"
        ),
        'user_model_js': File(
            path="app/client/models/UserModel.js",
            language="javascript",
            name="UserModel.js",
            plugin_id="javascript"
        ),
        'user_service_js': File(
            path="app/client/services/UserService.js",
            language="javascript",
            name="UserService.js",
            plugin_id="javascript"
        ),
    }
    
    # JS File to Directory relationships
    js_file_dir_relationships = [
        Relationship(source_id=js_files['user_view'].id, target_id=directories['views'].id, type="IN_DIRECTORY"),
        Relationship(source_id=js_files['base_view'].id, target_id=directories['views'].id, type="IN_DIRECTORY"),
        Relationship(source_id=js_files['user_model_js'].id, target_id=directories['js_models'].id, type="IN_DIRECTORY"),
        Relationship(source_id=js_files['user_service_js'].id, target_id=directories['js_services'].id, type="IN_DIRECTORY"),
    ]
    
    # ==========================================
    # JAVASCRIPT CLASSES
    # ==========================================
    print("\n6. Creating JavaScript classes...")
    js_classes = {
        'UserView': Symbol(
            name="UserView",
            qualified_name="UserView",
            kind="class",
            plugin_id="javascript",
            metadata={"_language": "javascript"}
        ),
        'BaseView': Symbol(
            name="BaseView",
            qualified_name="BaseView",
            kind="class",
            plugin_id="javascript",
            metadata={"_language": "javascript"}
        ),
        'UserModel': Symbol(
            name="UserModel",
            qualified_name="UserModel",
            kind="class",
            plugin_id="javascript",
            metadata={"_language": "javascript"}
        ),
        'UserServiceJS': Symbol(
            name="UserService",
            qualified_name="UserService",
            kind="class",
            plugin_id="javascript",
            metadata={"_language": "javascript"}
        ),
    }
    
    # JavaScript Methods
    js_methods = {
        'loadUsers': Symbol(name="loadUsers", qualified_name="UserView.loadUsers", kind="function", plugin_id="javascript"),
        'createUser': Symbol(name="createUser", qualified_name="UserView.createUser", kind="function", plugin_id="javascript"),
        'deleteUser': Symbol(name="deleteUser", qualified_name="UserView.deleteUser", kind="function", plugin_id="javascript"),
        'fetchUsers': Symbol(name="fetchUsers", qualified_name="UserService.fetchUsers", kind="function", plugin_id="javascript"),
    }
    
    # ==========================================
    # API ENDPOINTS
    # ==========================================
    print("\n7. Creating API endpoints...")
    endpoints = {
        'get_users': Endpoint(
            path="/api/users",
            method="GET",
            name="GET /api/users",
            plugin_id="api"
        ),
        'post_users': Endpoint(
            path="/api/users",
            method="POST",
            name="POST /api/users",
            plugin_id="api"
        ),
        'delete_user': Endpoint(
            path="/api/users/:id",
            method="DELETE",
            name="DELETE /api/users/:id",
            plugin_id="api"
        ),
    }
    
    # ==========================================
    # RELATIONSHIPS
    # ==========================================
    print("\n8. Creating code relationships...")
    
    # Class relationships
    class_relationships = [
        # PHP inheritance
        Relationship(source_id=php_classes['UserController'].id, target_id=php_classes['BaseController'].id, type="EXTENDS"),
        Relationship(source_id=php_classes['UserController'].id, target_id=php_classes['ControllerInterface'].id, type="IMPLEMENTS"),
        
        # JS inheritance
        Relationship(source_id=js_classes['UserView'].id, target_id=js_classes['BaseView'].id, type="EXTENDS"),
        
        # Class to File
        Relationship(source_id=php_classes['UserController'].id, target_id=php_files['user_controller'].id, type="DEFINED_IN"),
        Relationship(source_id=php_classes['BaseController'].id, target_id=php_files['base_controller'].id, type="DEFINED_IN"),
        Relationship(source_id=php_classes['User'].id, target_id=php_files['user_model'].id, type="DEFINED_IN"),
        Relationship(source_id=php_classes['UserService'].id, target_id=php_files['user_service'].id, type="DEFINED_IN"),
        
        Relationship(source_id=js_classes['UserView'].id, target_id=js_files['user_view'].id, type="DEFINED_IN"),
        Relationship(source_id=js_classes['BaseView'].id, target_id=js_files['base_view'].id, type="DEFINED_IN"),
        Relationship(source_id=js_classes['UserModel'].id, target_id=js_files['user_model_js'].id, type="DEFINED_IN"),
        Relationship(source_id=js_classes['UserServiceJS'].id, target_id=js_files['user_service_js'].id, type="DEFINED_IN"),
        
        # Class has Methods
        Relationship(source_id=php_classes['UserController'].id, target_id=php_methods['list'].id, type="HAS_METHOD"),
        Relationship(source_id=php_classes['UserController'].id, target_id=php_methods['create'].id, type="HAS_METHOD"),
        Relationship(source_id=php_classes['UserController'].id, target_id=php_methods['delete'].id, type="HAS_METHOD"),
        Relationship(source_id=php_classes['UserService'].id, target_id=php_methods['getAllUsers'].id, type="HAS_METHOD"),
        Relationship(source_id=php_classes['UserService'].id, target_id=php_methods['saveUser'].id, type="HAS_METHOD"),
        Relationship(source_id=php_classes['UserService'].id, target_id=php_methods['deleteUser'].id, type="HAS_METHOD"),
        
        Relationship(source_id=js_classes['UserView'].id, target_id=js_methods['loadUsers'].id, type="HAS_METHOD"),
        Relationship(source_id=js_classes['UserView'].id, target_id=js_methods['createUser'].id, type="HAS_METHOD"),
        Relationship(source_id=js_classes['UserView'].id, target_id=js_methods['deleteUser'].id, type="HAS_METHOD"),
        Relationship(source_id=js_classes['UserServiceJS'].id, target_id=js_methods['fetchUsers'].id, type="HAS_METHOD"),
    ]
    
    # Dependencies and Calls
    dependency_relationships = [
        # PHP dependencies
        Relationship(source_id=php_classes['UserController'].id, target_id=php_classes['UserService'].id, type="USES"),
        Relationship(source_id=php_classes['UserController'].id, target_id=php_classes['User'].id, type="USES"),
        
        # JS dependencies
        Relationship(source_id=js_classes['UserView'].id, target_id=js_classes['UserModel'].id, type="USES"),
        Relationship(source_id=js_classes['UserView'].id, target_id=js_classes['UserServiceJS'].id, type="USES"),
        
        # Method calls
        Relationship(source_id=php_methods['list'].id, target_id=php_methods['getAllUsers'].id, type="CALLS"),
        Relationship(source_id=php_methods['create'].id, target_id=php_methods['saveUser'].id, type="CALLS"),
        Relationship(source_id=php_methods['delete'].id, target_id=php_methods['deleteUser'].id, type="CALLS"),
        
        Relationship(source_id=js_methods['loadUsers'].id, target_id=js_methods['fetchUsers'].id, type="CALLS"),
        
        # File imports
        Relationship(source_id=php_files['user_controller'].id, target_id=php_files['user_service'].id, type="IMPORTS"),
        Relationship(source_id=php_files['user_controller'].id, target_id=php_files['user_model'].id, type="IMPORTS"),
        
        Relationship(source_id=js_files['user_view'].id, target_id=js_files['base_view'].id, type="IMPORTS"),
        Relationship(source_id=js_files['user_view'].id, target_id=js_files['user_model_js'].id, type="IMPORTS"),
        Relationship(source_id=js_files['user_view'].id, target_id=js_files['user_service_js'].id, type="IMPORTS"),
    ]
    
    # Endpoint relationships
    endpoint_relationships = [
        # Endpoints handled by PHP controllers
        Relationship(source_id=endpoints['get_users'].id, target_id=php_methods['list'].id, type="HANDLES"),
        Relationship(source_id=endpoints['post_users'].id, target_id=php_methods['create'].id, type="HANDLES"),
        Relationship(source_id=endpoints['delete_user'].id, target_id=php_methods['delete'].id, type="HANDLES"),
        
        # JS methods call endpoints
        Relationship(source_id=js_methods['loadUsers'].id, target_id=endpoints['get_users'].id, type="CALLS_API"),
        Relationship(source_id=js_methods['createUser'].id, target_id=endpoints['post_users'].id, type="CALLS_API"),
        Relationship(source_id=js_methods['deleteUser'].id, target_id=endpoints['delete_user'].id, type="CALLS_API"),
    ]
    
    # ==========================================
    # STORE ALL NODES AND RELATIONSHIPS
    # ==========================================
    print("\n9. Storing all nodes and relationships...")
    
    # Store directories
    all_directories = list(directories.values())
    n1, r1 = graph.store_batch(all_directories, dir_relationships, 'filesystem')
    print(f"   Directories: {n1} nodes, {r1} relationships")
    
    # Store PHP files and classes
    all_php_files = list(php_files.values())
    all_php_symbols = list(php_classes.values()) + list(php_methods.values())
    n2, r2 = graph.store_batch(all_php_files + all_php_symbols, file_dir_relationships, 'php')
    print(f"   PHP: {n2} nodes, {r2} relationships")
    
    # Store JS files and classes
    all_js_files = list(js_files.values())
    all_js_symbols = list(js_classes.values()) + list(js_methods.values())
    n3, r3 = graph.store_batch(all_js_files + all_js_symbols, js_file_dir_relationships, 'javascript')
    print(f"   JavaScript: {n3} nodes, {r3} relationships")
    
    # Store endpoints
    all_endpoints = list(endpoints.values())
    n4, r4 = graph.store_batch(all_endpoints, [], 'api')
    print(f"   Endpoints: {n4} nodes")
    
    # Store all relationships
    all_relationships = class_relationships + dependency_relationships + endpoint_relationships
    r5 = graph.store_relationships(all_relationships)
    print(f"   Code relationships: {r5}")
    
    # ==========================================
    # VERIFY GRAPH STRUCTURE
    # ==========================================
    print("\n10. Verifying graph structure...")
    
    stats = {
        'Total Nodes': graph.query("MATCH (n) RETURN count(n) as c")[0]['c'],
        'Directories': graph.query("MATCH (n:Directory) RETURN count(n) as c")[0]['c'],
        'PHP Files': graph.query("MATCH (n:File {language: 'php'}) RETURN count(n) as c")[0]['c'],
        'JS Files': graph.query("MATCH (n:File {language: 'javascript'}) RETURN count(n) as c")[0]['c'],
        'PHP Classes': graph.query("MATCH (n:Class) WHERE n.plugin_id = 'php' RETURN count(n) as c")[0]['c'],
        'JS Classes': graph.query("MATCH (n:Class) WHERE n.metadata__language = 'javascript' RETURN count(n) as c")[0]['c'],
        'Methods': graph.query("MATCH (n:Method) RETURN count(n) as c")[0]['c'],
        'Functions': graph.query("MATCH (n:Function) RETURN count(n) as c")[0]['c'],
        'Endpoints': graph.query("MATCH (n:Endpoint) RETURN count(n) as c")[0]['c'],
        'Interfaces': graph.query("MATCH (n:Interface) RETURN count(n) as c")[0]['c'],
    }
    
    print("\n📊 Node Statistics:")
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    relationships = {
        'CONTAINS': graph.query("MATCH ()-[r:CONTAINS]->() RETURN count(r) as c")[0]['c'],
        'IN_DIRECTORY': graph.query("MATCH ()-[r:IN_DIRECTORY]->() RETURN count(r) as c")[0]['c'],
        'DEFINED_IN': graph.query("MATCH ()-[r:DEFINED_IN]->() RETURN count(r) as c")[0]['c'],
        'EXTENDS': graph.query("MATCH ()-[r:EXTENDS]->() RETURN count(r) as c")[0]['c'],
        'IMPLEMENTS': graph.query("MATCH ()-[r:IMPLEMENTS]->() RETURN count(r) as c")[0]['c'],
        'HAS_METHOD': graph.query("MATCH ()-[r:HAS_METHOD]->() RETURN count(r) as c")[0]['c'],
        'USES': graph.query("MATCH ()-[r:USES]->() RETURN count(r) as c")[0]['c'],
        'CALLS': graph.query("MATCH ()-[r:CALLS]->() RETURN count(r) as c")[0]['c'],
        'CALLS_API': graph.query("MATCH ()-[r:CALLS_API]->() RETURN count(r) as c")[0]['c'],
        'HANDLES': graph.query("MATCH ()-[r:HANDLES]->() RETURN count(r) as c")[0]['c'],
        'IMPORTS': graph.query("MATCH ()-[r:IMPORTS]->() RETURN count(r) as c")[0]['c'],
    }
    
    print("\n🔗 Relationship Statistics:")
    for key, value in relationships.items():
        if value > 0:
            print(f"   {key}: {value}")
    
    # Test some paths
    print("\n🛤️ Testing Graph Traversal:")
    
    # Directory hierarchy
    dir_path = graph.query("""
        MATCH path = (root:Directory {name: 'app'})-[:CONTAINS*]->(leaf:Directory {name: 'views'})
        RETURN length(path) as depth
    """)
    if dir_path:
        print(f"   ✓ Directory path depth: {dir_path[0]['depth']}")
    
    # File in directory
    file_in_dir = graph.query("""
        MATCH (f:File {name: 'UserController.php'})-[:IN_DIRECTORY]->(d:Directory)
        RETURN d.name as dir
    """)
    if file_in_dir:
        print(f"   ✓ UserController.php is in: {file_in_dir[0]['dir']}")
    
    # Class inheritance
    inheritance = graph.query("""
        MATCH (child:Class {name: 'UserController'})-[:EXTENDS]->(parent:Class)
        RETURN parent.name as parent
    """)
    if inheritance:
        print(f"   ✓ UserController extends: {inheritance[0]['parent']}")
    
    # Endpoint to handler
    endpoint_handler = graph.query("""
        MATCH (e:Endpoint {path: '/api/users', method: 'GET'})-[:HANDLES]->(m:Method)
        RETURN m.name as handler
    """)
    if endpoint_handler:
        print(f"   ✓ GET /api/users handled by: {endpoint_handler[0]['handler']}")
    
    # Cross-language connection
    cross_lang = graph.query("""
        MATCH (js:Function {name: 'loadUsers'})-[:CALLS_API]->(api:Endpoint)-[:HANDLES]->(php:Method)
        RETURN js.name as js_func, api.path as endpoint, php.name as php_method
    """)
    if cross_lang:
        print(f"   ✓ Cross-language: {cross_lang[0]['js_func']} -> {cross_lang[0]['endpoint']} -> {cross_lang[0]['php_method']}")
    
    print("\n" + "="*70)
    print("✅ COMPLETE GRAPH CREATED SUCCESSFULLY!")
    print("="*70)
    print("\n📌 You can now view this in Neo4j Browser at http://localhost:7474")
    print("   Try these queries:")
    print("   - MATCH (n) RETURN n LIMIT 100")
    print("   - MATCH p=()-[:EXTENDS|IMPLEMENTS|USES|CALLS]->() RETURN p")
    print("   - MATCH p=(js)-[:CALLS_API]->(api)-[:HANDLES]->(php) RETURN p")
    
    return True

if __name__ == "__main__":
    success = create_complete_graph()
    sys.exit(0 if success else 1)