# Universal Code Graph System

A plugin-based, language-agnostic code analysis platform for creating knowledge graphs of any codebase.

## Quick Start

```bash
# Install
pip install code-graph-system

# Analyze a codebase
cgs analyze ./my-project --type=espocrm

# Query the graph
cgs query impact --target="MyClass::myMethod"
```

## Architecture

### Core Principles
- **Plugin-based**: Language, framework, and system support via plugins
- **Incremental**: Only re-analyze changed files
- **Scalable**: Handles millions of files via sharding
- **Universal**: Works with any programming language

### Key Components
1. **Core Engine**: Orchestrates analysis pipeline
2. **Plugin System**: Dynamic loading of language/framework analyzers
3. **Graph Store**: Neo4j-backed knowledge graph
4. **Query Engine**: Cross-language impact analysis

## Supported Technologies

### Languages (via plugins)
- PHP
- JavaScript/TypeScript
- Python
- Java
- Go
- Rust

### Frameworks (via plugins)
- Laravel, Symfony
- React, Vue, Angular
- Django, Flask
- Spring Boot

### Systems (via plugins)
- EspoCRM
- WordPress
- Drupal
- Magento

## Development

```bash
# Setup development environment
git clone https://github.com/yourusername/code-graph-system
cd code-graph-system
pip install -e ".[dev]"

# Run tests
pytest

# Build a plugin
cgs plugin create my-language-plugin
```

## License

MIT