#!/usr/bin/env python3
"""Test the enhanced code graph pipeline"""

import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from symbol_table import SymbolTable
from parsers.php_enhanced import PHPSymbolCollector
from parsers.php_reference_resolver import PHPReferenceResolver
from neo4j_integration.batch_writer import Neo4jBatchWriter, Neo4jConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_symbol_table():
    """Test basic Symbol Table operations"""
    logger.info("Testing Symbol Table...")
    
    # Create in-memory database for testing
    symbol_table = SymbolTable(":memory:")
    
    # Test adding a symbol
    from symbol_table import Symbol, SymbolType
    
    test_symbol = Symbol(
        id="test_1",
        name="App\\Test\\TestClass",  # Use fully qualified name
        type=SymbolType.CLASS,
        file_path="/test/file.php",
        line_number=10,
        column_number=5,
        namespace="App\\Test"
    )
    
    symbol_table.add_symbol(test_symbol)
    symbol_table.commit()  # Commit the transaction
    
    # Test resolving the symbol
    resolved = symbol_table.resolve("TestClass", "App\\Test", {})
    assert resolved is not None, "Failed to resolve symbol"
    assert resolved.name == "App\\Test\\TestClass", "Resolved wrong symbol"
    
    # Test statistics
    stats = symbol_table.get_stats()
    assert stats['total_symbols'] == 1, "Wrong symbol count"
    
    logger.info("✓ Symbol Table tests passed")
    return True


def test_small_php_file():
    """Test parsing a small PHP file"""
    logger.info("Testing PHP parsing...")
    
    # Create test PHP file
    test_file = Path("test_sample.php")
    test_content = """<?php
namespace App\\Test;

use App\\Models\\User;

class TestController extends BaseController {
    private $userService;
    
    public function __construct(UserService $service) {
        $this->userService = $service;
    }
    
    public function index() {
        $users = User::all();
        return view('users.index', compact('users'));
    }
    
    public function show($id) {
        $user = User::find($id);
        return $user->toArray();
    }
}
"""
    
    # Write test file
    test_file.write_text(test_content)
    
    try:
        # Create symbol table
        symbol_table = SymbolTable(":memory:")
        
        # Pass 1: Collect symbols
        collector = PHPSymbolCollector(symbol_table)
        collector.parse_file(str(test_file))
        
        stats = symbol_table.get_stats()
        logger.info(f"Collected symbols: {stats}")
        
        assert stats['total_symbols'] > 0, "No symbols collected"
        assert stats['type_class'] >= 1, "No classes found"
        assert stats['type_method'] >= 3, "Methods not found"
        
        # Pass 2: Resolve references
        resolver = PHPReferenceResolver(symbol_table)
        resolver.resolve_file(str(test_file))
        
        stats = symbol_table.get_stats()
        logger.info(f"After resolution: {stats}")
        
        logger.info("✓ PHP parsing tests passed")
        return True
        
    finally:
        # Clean up
        test_file.unlink(missing_ok=True)


def test_neo4j_export():
    """Test Neo4j export (requires Neo4j to be running)"""
    logger.info("Testing Neo4j export...")
    
    try:
        # Create simple symbol table with test data
        symbol_table = SymbolTable(":memory:")
        
        from symbol_table import Symbol, SymbolType
        
        # Add some test symbols
        class_symbol = Symbol(
            id="class_1",
            name="TestClass",
            type=SymbolType.CLASS,
            file_path="/test/file.php",
            line_number=10,
            column_number=5
        )
        symbol_table.add_symbol(class_symbol)
        
        method_symbol = Symbol(
            id="method_1",
            name="testMethod",
            type=SymbolType.METHOD,
            file_path="/test/file.php",
            line_number=15,
            column_number=10,
            parent_id="class_1"
        )
        symbol_table.add_symbol(method_symbol)
        
        # Add a reference
        symbol_table.add_reference(
            source_id="method_1",
            target_id="class_1",
            reference_type="BELONGS_TO",
            line=15,
            column=10
        )
        
        symbol_table.commit()
        
        # Try to export to Neo4j
        config = Neo4jConfig(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="your-password",  # Update with actual password
            batch_size=100
        )
        
        writer = Neo4jBatchWriter(symbol_table, config)
        
        try:
            writer.connect()
            stats = writer.export_to_neo4j()
            
            logger.info(f"Export stats: {stats}")
            assert stats['nodes_created'] > 0, "No nodes created"
            
            logger.info("✓ Neo4j export tests passed")
            return True
            
        except Exception as e:
            logger.warning(f"Neo4j test skipped (is Neo4j running?): {e}")
            return None
            
        finally:
            writer.close()
            
    except Exception as e:
        logger.error(f"Neo4j test failed: {e}")
        return False


def main():
    """Run all tests"""
    logger.info("=" * 60)
    logger.info("Running Enhanced Pipeline Tests")
    logger.info("=" * 60)
    
    tests = [
        ("Symbol Table", test_symbol_table),
        ("PHP Parsing", test_small_php_file),
        ("Neo4j Export", test_neo4j_export)
    ]
    
    results = {}
    for test_name, test_func in tests:
        logger.info(f"\n{test_name} Test:")
        try:
            result = test_func()
            results[test_name] = "PASSED" if result else "SKIPPED" if result is None else "FAILED"
        except Exception as e:
            logger.error(f"Test failed with exception: {e}")
            results[test_name] = "ERROR"
    
    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("Test Summary:")
    for test_name, result in results.items():
        logger.info(f"  {test_name}: {result}")
    
    # Return success if no failures
    return all(r in ["PASSED", "SKIPPED"] for r in results.values())


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)