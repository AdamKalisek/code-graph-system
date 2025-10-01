.PHONY: help install test clean parse import neo4j-start neo4j-stop neo4j-clean query

# Default target - show help
help:
	@echo "Code Graph System - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install        Install Python dependencies with uv"
	@echo "  make install-dev    Install with dev dependencies"
	@echo "  make update         Update all dependencies"
	@echo "  make neo4j-start    Start Neo4j Docker container"
	@echo ""
	@echo "Development:"
	@echo "  make test           Run all tests"
	@echo "  make lint           Lint code with ruff"
	@echo "  make format         Format code with black"
	@echo "  make parse          Parse codebase (requires CONFIG=path/to/config.yaml)"
	@echo "  make import         Import to Neo4j (requires CONFIG=path/to/config.yaml)"
	@echo "  make clean          Clean SQLite databases"
	@echo ""
	@echo "Neo4j Management:"
	@echo "  make neo4j-stop     Stop Neo4j container"
	@echo "  make neo4j-clean    Stop and remove Neo4j container and data"
	@echo "  make query          Open Neo4j browser"
	@echo ""
	@echo "Example workflow:"
	@echo "  make install"
	@echo "  make neo4j-start"
	@echo "  make parse CONFIG=memory.yaml"
	@echo "  make import CONFIG=memory.yaml"
	@echo "  make query"

# Install Python dependencies with uv
install:
	@echo "Installing dependencies with uv..."
	uv sync
	@echo "✅ Dependencies installed"

# Install with development dependencies
install-dev:
	@echo "Installing dependencies with dev tools..."
	uv sync --extra dev
	@echo "✅ Dev dependencies installed"

# Update dependencies
update:
	@echo "Updating dependencies..."
	uv lock --upgrade
	uv sync
	@echo "✅ Dependencies updated"

# Run tests
test:
	@echo "Running tests..."
	uv run pytest tests/ -v
	@echo "✅ Tests complete"

# Run tests with coverage
test-coverage:
	@echo "Running tests with coverage..."
	uv run pytest tests/ -v --cov=src --cov-report=term-missing
	@echo "✅ Tests complete with coverage report"

# Clean generated files
clean:
	@echo "Cleaning databases and generated files..."
	rm -rf data/*.db data/*.db-shm data/*.db-wal
	rm -f *.cypher
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "✅ Cleaned"

# Parse codebase (requires CONFIG variable)
parse:
ifndef CONFIG
	@echo "❌ Error: CONFIG variable required"
	@echo "Usage: make parse CONFIG=your-project.yaml"
	@exit 1
endif
	@echo "Parsing codebase with config: $(CONFIG)"
	uv run python src/indexer/main.py --config $(CONFIG)
	@echo "✅ Parsing complete"

# Import to Neo4j (requires CONFIG variable)
import:
ifndef CONFIG
	@echo "❌ Error: CONFIG variable required"
	@echo "Usage: make import CONFIG=your-project.yaml"
	@exit 1
endif
	@echo "Importing to Neo4j with config: $(CONFIG)"
	uv run python tools/ultra_fast_neo4j_import.py --config $(CONFIG) --bolt-parallel
	@echo "✅ Import complete"

# Full pipeline: parse + import
pipeline:
ifndef CONFIG
	@echo "❌ Error: CONFIG variable required"
	@echo "Usage: make pipeline CONFIG=your-project.yaml"
	@exit 1
endif
	@echo "Running full pipeline for $(CONFIG)..."
	$(MAKE) parse CONFIG=$(CONFIG)
	$(MAKE) import CONFIG=$(CONFIG)
	@echo "✅ Pipeline complete"

# Start Neo4j in Docker
neo4j-start:
	@echo "Starting Neo4j..."
	@docker ps -a | grep neo4j-code > /dev/null 2>&1 && \
		(echo "Container exists, starting..." && docker start neo4j-code) || \
		(echo "Creating new container..." && docker run -d \
			--name neo4j-code \
			-p 7474:7474 -p 7688:7687 \
			-e NEO4J_AUTH=neo4j/password \
			neo4j:latest)
	@echo "⏳ Waiting for Neo4j to be ready..."
	@sleep 5
	@echo "✅ Neo4j started at http://localhost:7474"
	@echo "   Username: neo4j"
	@echo "   Password: password"

# Stop Neo4j
neo4j-stop:
	@echo "Stopping Neo4j..."
	@docker stop neo4j-code || true
	@echo "✅ Neo4j stopped"

# Clean Neo4j (stop, remove container and data)
neo4j-clean:
	@echo "Cleaning Neo4j..."
	@docker stop neo4j-code || true
	@docker rm neo4j-code || true
	@echo "✅ Neo4j removed"

# Open Neo4j browser
query:
	@echo "Opening Neo4j browser..."
	@command -v open > /dev/null && open http://localhost:7474 || \
	 command -v xdg-open > /dev/null && xdg-open http://localhost:7474 || \
	 echo "Please open http://localhost:7474 in your browser"

# Lint code
lint:
	@echo "Linting code..."
	uv run ruff check src/ tests/ parsers/

# Format code
format:
	@echo "Formatting code..."
	uv run black src/ tests/ parsers/

# Type check
typecheck:
	@echo "Type checking..."
	uv run mypy src/ --ignore-missing-imports || echo "⚠️  mypy not installed"