# Contributing to Code Graph System

Thanks for your interest in contributing! This guide will help you get started.

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/yourusername/code-graph-system.git
cd code-graph-system
make install

# 2. Start Neo4j for testing
make neo4j-start

# 3. Run tests
make test

# 4. Try the minimal example
make parse CONFIG=examples/mini-app.yaml
make import CONFIG=examples/mini-app.yaml
```

## Development Setup

### Prerequisites
- Python 3.8+
- Docker (for Neo4j)
- Git

### Install Development Dependencies
```bash
pip install -r requirements.txt

# Optional: Install development tools
pip install black ruff pytest-cov
```

## Project Structure

```
code-graph-system/
├── src/
│   ├── core/          # Symbol table, type definitions
│   ├── indexer/       # Main parsing orchestrator
│   ├── pipeline/      # Language-specific modules
│   ├── plugins/       # Framework-specific analyzers
│   ├── export/        # Neo4j export logic
│   └── import/        # Neo4j import strategies
├── parsers/           # Language parsers (PHP, JS)
├── tools/             # Utility scripts
├── tests/             # Test suite
└── examples/          # Example projects
```

## Making Changes

### 1. Create a Branch
```bash
git checkout -b feature/your-feature-name
```

### 2. Make Your Changes
- Follow existing code style (see Style Guide below)
- Add tests for new functionality
- Update documentation if needed

### 3. Run Tests
```bash
# Run all tests
make test

# Run with coverage
make test-coverage

# Run specific test
pytest tests/test_specific.py -v
```

### 4. Commit Your Changes
```bash
git add .
git commit -m "Add feature: your feature description"
```

## Adding a New Language Parser

To add support for a new programming language:

### 1. Create Language Module
Create `src/pipeline/your_language.py`:

```python
from src.pipeline.base import LanguageModule

class YourLanguageModule(LanguageModule):
    def get_file_extensions(self):
        return ['.yourlang']

    def parse_file(self, file_path: str):
        # Parse file and extract symbols
        pass
```

### 2. Create Parser
Create `parsers/your_language_parser.py`:

```python
from tree_sitter import Language, Parser
import tree_sitter_yourlanguage

class YourLanguageParser:
    def __init__(self):
        language = Language(tree_sitter_yourlanguage.language())
        self.parser = Parser(language)

    def parse_file(self, file_path: str):
        # Return symbols and references
        pass
```

### 3. Register in Pipeline
Add to `src/pipeline/indexer.py`:

```python
from src.pipeline.your_language import YourLanguageModule

# In CodebaseIndexer.__init__:
language_modules['yourlanguage'] = YourLanguageModule(config, symbol_table)
```

### 4. Add Tests
Create `tests/test_your_language_parser.py`:

```python
def test_parse_basic_file():
    parser = YourLanguageParser()
    symbols, refs = parser.parse_file('tests/fixtures/sample.yourlang')
    assert len(symbols) > 0
```

### 5. Update Documentation
- Add language to README.md
- Document in CLAUDE.md
- Add example to examples/

## Adding a Framework Plugin

To add support for a specific framework (like React, Vue, etc.):

### 1. Create Plugin
Create `src/plugins/your_framework.py`:

```python
from src.plugins.base import BasePlugin

class YourFrameworkPlugin(BasePlugin):
    def analyze_file(self, file_path: str, ast, symbol_table):
        # Extract framework-specific patterns
        # e.g., API routes, components, hooks
        pass
```

### 2. Register Plugin
Add to `src/plugins/registry.py`:

```python
from src.plugins.your_framework import YourFrameworkPlugin

def create_registry(config):
    plugins = {}
    if 'your_framework' in config.plugins:
        plugins['your_framework'] = YourFrameworkPlugin(config)
    return plugins
```

### 3. Add Configuration
Update `docs/CONFIGURATION.md` with plugin options.

## Testing Guidelines

### Running Tests
```bash
# All tests
pytest tests/

# Specific test file
pytest tests/test_parser.py

# With verbose output
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=term-missing
```

### Writing Tests
- Place tests in `tests/` directory
- Name test files `test_*.py`
- Name test functions `test_*`
- Use fixtures in `tests/fixtures/` for sample code

Example:
```python
def test_parse_typescript_function():
    """Test parsing a simple TypeScript function"""
    parser = TypeScriptParser()
    symbols, refs = parser.parse_file('tests/fixtures/simple.ts')

    assert len(symbols) == 1
    assert symbols[0].type == 'function'
    assert symbols[0].name == 'myFunction'
```

## Style Guide

### Python Code Style
- Follow PEP 8
- Use type hints where possible
- Keep functions focused and small (<50 lines)
- Add docstrings to public functions

Example:
```python
def parse_file(file_path: str) -> Tuple[List[Symbol], List[Reference]]:
    """
    Parse a source file and extract symbols and references.

    Args:
        file_path: Absolute path to source file

    Returns:
        Tuple of (symbols, references) extracted from file
    """
    pass
```

### Formatting
```bash
# Format code with black
black src/ tests/

# Lint with ruff
ruff check src/ tests/
```

## Debugging Tips

### Enable Debug Logging
```python
# In your script or test
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

### Inspect SQLite Database
```bash
sqlite3 data/your-project.db

# Check symbols
SELECT COUNT(*), type FROM symbols GROUP BY type;

# Check relationships
SELECT COUNT(*), reference_type FROM symbol_references GROUP BY reference_type;
```

### Debug Neo4j Queries
```cypher
// Open http://localhost:7474

// Check what was imported
MATCH (n) RETURN labels(n), COUNT(*) GROUP BY labels(n)

// Find specific symbol
MATCH (s {name: 'YourSymbol'}) RETURN s
```

## Common Issues

### Import Errors
If you see "ModuleNotFoundError":
```bash
# Make sure you're in the project root
pip install -r requirements.txt
python -c "import src.core.symbol_table"
```

### Tests Fail
- Ensure Neo4j is running: `make neo4j-start`
- Check test fixtures exist
- Run with `-v` flag for more details

### Parser Not Working
- Verify tree-sitter language bindings installed
- Check file extensions registered correctly
- Add debug logging to see what's being parsed

## Questions?

- Open an issue on GitHub
- Check existing issues for similar questions
- Review documentation in `docs/`

## License

By contributing, you agree that your contributions will be licensed under the MIT License.