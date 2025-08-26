#!/bin/bash
# Run Neo4j in Docker with web interface
# Web interface: http://localhost:7475
# Bolt connection: bolt://localhost:7688

set -e

echo "=========================================="
echo "  Neo4j Graph Database Runner"
echo "=========================================="

# Check if container exists
if docker ps -a | grep -q "neo4j-memory"; then
    echo "✓ Container 'neo4j-memory' exists"
    
    # Check if running
    if docker ps | grep -q "neo4j-memory"; then
        echo "✓ Neo4j is already running"
    else
        echo "→ Starting existing container..."
        docker start neo4j-memory
        echo "✓ Container started"
    fi
else
    echo "→ Creating new Neo4j container..."
    docker run -d \
        --name neo4j-memory \
        -p 7475:7474 \
        -p 7688:7687 \
        -e NEO4J_AUTH=neo4j/password123 \
        -e NEO4J_dbms_memory_pagecache_size=512m \
        -e NEO4J_dbms_memory_heap_initial__size=512m \
        -e NEO4J_dbms_memory_heap_max__size=2G \
        -v $(pwd)/neo4j_data:/data \
        -v $(pwd)/neo4j_logs:/logs \
        neo4j:latest
    
    echo "✓ Container created and started"
fi

echo ""
echo "=========================================="
echo "  Neo4j is ready!"
echo "=========================================="
echo ""
echo "📊 Web Interface: http://localhost:7475"
echo "🔌 Bolt URL: bolt://localhost:7688"
echo "👤 Username: neo4j"
echo "🔑 Password: password123"
echo ""
echo "To view logs: docker logs -f neo4j-memory"
echo "To stop: docker stop neo4j-memory"
echo "To remove: docker rm -f neo4j-memory"
echo ""

# Wait for Neo4j to be ready
echo "→ Waiting for Neo4j to be ready..."
for i in {1..30}; do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:7475 | grep -q "200"; then
        echo "✓ Neo4j web interface is accessible"
        break
    fi
    sleep 1
done

# Open browser if available
if command -v xdg-open > /dev/null; then
    echo "→ Opening Neo4j Browser..."
    xdg-open http://localhost:7475 2>/dev/null &
elif command -v open > /dev/null; then
    echo "→ Opening Neo4j Browser..."
    open http://localhost:7475 2>/dev/null &
fi

echo ""
echo "✨ Neo4j is running and ready for connections!"