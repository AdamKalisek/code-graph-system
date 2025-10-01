# Python App Example

A simple Python application demonstrating the Code Graph System's Python language support.

## Structure

```
python-app/
├── src/
│   ├── __init__.py     # Package initialization
│   ├── database.py     # Database and repository classes
│   ├── models.py       # Data models (User, Post)
│   ├── services.py     # Business logic services
│   └── app.py          # Main application
└── README.md
```

## Code Relationships

```
app.py (Application)
├── uses Database (from database.py)
├── uses UserService (from services.py)
└── uses PostService (from services.py)
    ├── uses UserService
    └── uses Repository (from database.py)
        └── uses Database

models.py
├── User (dataclass)
└── Post (dataclass)

database.py
├── Database (class)
└── Repository (class)
    └── uses Database

services.py
├── UserService (class)
│   └── uses Database, Repository, User
└── PostService (class)
    └── uses Database, Repository, UserService, Post
```

## Expected Graph Nodes

When parsed, this should create:

**Classes:**
- `Database` (in database.py)
- `Repository` (in database.py)
- `User` (in models.py)
- `Post` (in models.py)
- `UserService` (in services.py)
- `PostService` (in services.py)
- `Application` (in app.py)

**Functions:**
- `main` (in app.py)
- Various methods in each class

**Relationships:**
- `Repository` uses `Database` (constructor parameter)
- `UserService` uses `Database` and `Repository`
- `PostService` uses `Database`, `Repository`, and `UserService`
- `Application` uses `Database`, `UserService`, and `PostService`
- Multiple `CALLS` relationships between methods
- `EXTENDS` relationships for dataclasses

## How to Test

```bash
# From repository root

# 1. Install dependencies (includes tree-sitter-python)
make install

# 2. Parse the example
make parse CONFIG=examples/python-app.yaml

# or directly:
python src/indexer/main.py --config examples/python-app.yaml

# 3. Check SQLite output
sqlite3 data/python-app.db "SELECT name, type FROM symbols WHERE type='class';"
# Should show: Database, Repository, User, Post, UserService, PostService, Application

# 4. Import to Neo4j (if Neo4j is running)
make import CONFIG=examples/python-app.yaml

# 5. Query in Neo4j browser
# Open http://localhost:7474 and run:
```

## Example Queries

```cypher
// Find all Python classes
MATCH (c) WHERE c.type = 'class'
RETURN c.name, c.file_path

// Show class dependencies
MATCH (source)-[r:USES]->(target)
WHERE source.type = 'class' AND target.type = 'class'
RETURN source.name, type(r), target.name

// Find the Application class and what it uses
MATCH (app {name: 'Application'})-[:USES]->(dep)
RETURN app.name, dep.name, dep.type

// Find service layer classes
MATCH (c) WHERE c.name ENDS WITH 'Service'
RETURN c.name, c.file_path

// Find dataclass models
MATCH (m) WHERE m.name IN ['User', 'Post']
RETURN m.name, m.file_path
```

## Expected Output

After successful parsing and import, you should see:

- **7 Python class nodes**: Database, Repository, User, Post, UserService, PostService, Application
- **20+ method nodes**: Various methods from each class
- **Several USES relationships**: Showing dependencies between classes
- **Multiple CALLS relationships**: Method invocations
- **IMPORTS relationships**: Between modules
- **File nodes**: 4 files (database.py, models.py, services.py, app.py)

## Features Demonstrated

This example shows Python-specific features:
- **Class definitions**: Regular classes and dataclasses
- **Type hints**: Function parameters and return types
- **Imports**: Both absolute and relative imports
- **Inheritance**: Dataclass inheritance
- **Method calls**: Between classes and within classes
- **Decorators**: @dataclass decorator
- **Module structure**: Proper Python package layout

## Troubleshooting

**No symbols found:**
- Check that `python` is in the languages list in config
- Verify the `root` path points to examples/python-app

**Import fails:**
- Make sure Neo4j is running: `make neo4j-start`
- Check Neo4j credentials in config match your setup

**Parser errors:**
- Ensure tree-sitter-python is installed: `pip install tree-sitter-python`
- Check Python syntax is valid in example files
