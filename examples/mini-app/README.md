# Mini App Example

A minimal TypeScript/React application for testing the Code Graph System.

## Structure

```
mini-app/
├── src/
│   ├── App.tsx           # Main app component
│   └── components/
│       ├── Button.tsx     # Reusable button component
│       └── UserCard.tsx   # User display card
└── README.md
```

## Component Relationships

```
App
├── renders UserCard (2 instances via map)
└── UserCard
    └── renders Button
```

## Expected Graph Nodes

When parsed, this should create:

**React Components:**
- `App` (in src/App.tsx)
- `UserCard` (in src/components/UserCard.tsx)
- `Button` (in src/components/Button.tsx)

**TypeScript Types:**
- `User` interface (defined in both App.tsx and UserCard.tsx)
- `ButtonProps` interface (in Button.tsx)
- `UserCardProps` interface (in UserCard.tsx)

**Relationships:**
- `App` IMPORTS `UserCard`
- `UserCard` IMPORTS `Button`
- `App` RENDERS `UserCard`
- `UserCard` RENDERS `Button`
- `App` CALLS `handleEditUser` function
- `UserCard` CALLS `handleEdit` function
- `UserCard` USES `User` type
- `Button` USES `ButtonProps` type

## How to Test

```bash
# From repository root

# 1. Parse the example
make parse CONFIG=examples/mini-app.yaml

# or directly:
python src/indexer/main.py --config examples/mini-app.yaml

# 2. Check SQLite output
sqlite3 data/mini-app.db "SELECT COUNT(*) FROM symbols;"
# Should show ~10-15 symbols

# 3. Import to Neo4j (if Neo4j is running)
make import CONFIG=examples/mini-app.yaml

# 4. Query in Neo4j browser
# Open http://localhost:7474 and run:
```

## Example Queries

```cypher
// Find all React components
MATCH (c:ReactComponent)
RETURN c.name, c.file_path

// Show component hierarchy
MATCH (parent:ReactComponent)-[:RENDERS]->(child)
RETURN parent.name, child.name

// Find the Button component and what renders it
MATCH (c:ReactComponent {name: 'Button'})
MATCH (parent)-[:RENDERS]->(c)
RETURN parent.name, c.name

// Find all TypeScript interfaces
MATCH (i:TSInterface)
RETURN i.name, i.file_path
```

## Expected Output

After successful parsing and import, you should see:

- **3 ReactComponent nodes**: App, UserCard, Button
- **4-5 TSInterface nodes**: User, ButtonProps, UserCardProps
- **2 RENDERS relationships**: App→UserCard, UserCard→Button
- **2 IMPORTS relationships**: App→UserCard, UserCard→Button
- **File nodes**: 3 files (App.tsx, UserCard.tsx, Button.tsx)

## Troubleshooting

**No symbols found:**
- Check that TypeScript is in the languages list in config
- Verify the `root` path points to examples/mini-app

**Import fails:**
- Make sure Neo4j is running: `make neo4j-start`
- Check Neo4j credentials in config match your setup

**Wrong node types:**
- If you see PHPClass instead of ReactComponent, the TypeScript parser isn't being used
- Check that parser selection is working correctly