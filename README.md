# Code Graph System

> Transform source code into a queryable knowledge graph for AI-assisted code analysis

## 🎯 Why This Exists

**Problem:** Traditional code search (grep, ripgrep) can't answer relationship questions like "What components call this API?" or "What's the impact of changing this interface?"

**Solution:** Parse code into a Neo4j graph database where relationships are first-class citizens, enabling 50-100x faster complex queries and AI agents to understand code structure instantly.

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start Neo4j
docker run -d \
  --name neo4j-code \
  -p 7474:7474 -p 7688:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest

# 3. Parse your codebase
python src/indexer/main.py --config your-project.yaml

# 4. Import to Neo4j
python tools/ultra_fast_neo4j_import.py --config your-project.yaml --bolt-parallel

# 5. Query your code
# Open http://localhost:7474 and run:
MATCH (c:ReactComponent)-[:RENDERS]->(e) RETURN c, e LIMIT 50
```

## 📊 What It Does

1. **Scans** your TypeScript/React/PHP codebase
2. **Extracts** symbols, relationships, and dependencies using Tree-sitter
3. **Stages** data in SQLite for efficient processing
4. **Imports** to Neo4j for graph queries
5. **Enables** queries impossible with text search

### Supported Languages
- ✅ TypeScript/TSX (React, Next.js)
- ✅ JavaScript/JSX
- ✅ PHP (EspoCRM optimized)
- 🚧 Python (coming soon)
- 🚧 Java (coming soon)

## 🏗️ Architecture

```
Source Code → Tree-sitter Parser → SQLite Staging → Neo4j Import → Cypher Queries
```

### Key Components
- **Indexer**: Orchestrates parsing and symbol extraction
- **Language Analyzers**: Tree-sitter based parsers for each language
- **Plugin System**: Extensible framework-specific analysis (NextJS, etc.)
- **Import Pipeline**: High-performance Neo4j data loading

## 📈 Performance

| Query Type | grep/ripgrep | Neo4j | Improvement |
|------------|--------------|-------|-------------|
| Find components rendering Button | Failed | 24ms | ∞ |
| Component dependency analysis | Not feasible | 50ms | N/A |
| Circular import detection | Custom script | 30ms | 100x |

## 🔍 Example Queries

```cypher
# Find unused React components
MATCH (c:ReactComponent)
WHERE NOT EXISTS(()-[:IMPORTS]->(c))
RETURN c.name, c.file_path

# Find API routes and their consumers
MATCH (api:APIRoute)<-[:CALLS*1..3]-(comp:ReactComponent)
RETURN api.name, collect(comp.name)

# Detect high-coupling components
MATCH (c:ReactComponent)
WITH c, COUNT {(c)-[:RENDERS|USES|CALLS]->()} as deps
WHERE deps > 15
RETURN c.name, deps ORDER BY deps DESC
```

## 📚 Documentation

- [Architecture Overview](docs/ARCHITECTURE.md)
- [Data Model Reference](docs/DATA_MODEL.md)
- [Configuration Guide](docs/CONFIGURATION.md)
- [Adding New Languages](docs/EXTENDING.md)
- [Performance Tuning](docs/PERFORMANCE.md)

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## 📄 License

MIT - See [LICENSE](LICENSE) for details.

---

Built with ❤️ for developers and AI agents who need to understand code relationships instantly.