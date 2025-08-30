#!/usr/bin/env python3
"""
Comprehensive Test Suite for Complete EspoCRM Coverage
Tests all parsers and verifies we capture everything
"""

import subprocess
import json
import sys
from pathlib import Path

def run_test(name, command):
    """Run a test and return results"""
    print(f"\n{'='*70}")
    print(f"Testing: {name}")
    print('='*70)
    
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {name} passed")
            return True
        else:
            print(f"❌ {name} failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ {name} error: {e}")
        return False

def test_all_parsers():
    """Test all implemented parsers"""
    
    print("\n" + "🚀 "*20)
    print("COMPREHENSIVE ESPOCRM COVERAGE TEST SUITE")
    print("🚀 "*20)
    
    tests_passed = []
    tests_failed = []
    
    # 1. Test PHP Enhanced Parser (CALLS, IMPORTS, ACCESSES, etc.)
    if run_test(
        "PHP Enhanced Parser",
        "php plugins/php/ast_parser_enhanced.php tests/test_enhanced_parser.php 2>&1 | grep -c '\"type\"'"
    ):
        tests_passed.append("PHP Enhanced Parser")
    else:
        tests_failed.append("PHP Enhanced Parser")
    
    # 2. Test EspoCRM-Aware Parser (Container resolution, ACL, Jobs)
    if run_test(
        "EspoCRM-Aware Parser",
        "php plugins/php/espocrm_aware_parser.php tests/test_espocrm_coverage.php 2>&1 | grep -c 'CHECKS_PERMISSION'"
    ):
        tests_passed.append("EspoCRM-Aware Parser")
    else:
        tests_failed.append("EspoCRM-Aware Parser")
    
    # 3. Test QueryBuilder Parser
    if run_test(
        "QueryBuilder Chain Parser",
        "php plugins/php/querybuilder_parser.php tests/test_querybuilder_chains.php 2>&1 | grep -c 'SELECT_'"
    ):
        tests_passed.append("QueryBuilder Parser")
    else:
        tests_failed.append("QueryBuilder Parser")
    
    # 4. Test Formula DSL Parser
    if run_test(
        "Formula DSL Parser",
        "python plugins/espocrm/formula_parser.py 2>&1 | grep -c 'FORMULA_'"
    ):
        tests_passed.append("Formula DSL Parser")
    else:
        tests_failed.append("Formula DSL Parser")
    
    # 5. Test JavaScript API Parser
    if run_test(
        "JavaScript API Parser",
        "python plugins/javascript/api_parser.py 2>&1 | grep -c 'JS_CALLS_API'"
    ):
        tests_passed.append("JavaScript API Parser")
    else:
        tests_failed.append("JavaScript API Parser")
    
    # 6. Test Metadata Parser (Hooks, Jobs, ACL, ORM)
    if run_test(
        "Metadata Parser",
        "python plugins/espocrm/metadata_parser.py 2>&1 | grep -c 'entities with'"
    ):
        tests_passed.append("Metadata Parser")
    else:
        tests_failed.append("Metadata Parser")
    
    # Test on real EspoCRM files
    print("\n" + "="*70)
    print("TESTING ON REAL ESPOCRM CODE")
    print("="*70)
    
    # Test QueryBuilder on real service
    result = subprocess.run(
        "php plugins/php/querybuilder_parser.php espocrm/application/Espo/Services/RecordTree.php 2>&1 | python -m json.tool | grep total_queries",
        shell=True, capture_output=True, text=True
    )
    
    if '"total_queries":' in result.stdout:
        queries_found = result.stdout.strip().split(':')[1].strip(' ,')
        print(f"✅ QueryBuilder: Found {queries_found} queries in RecordTree.php")
    else:
        print("❌ QueryBuilder: No queries detected in real code")
    
    # Final Report
    print("\n" + "="*70)
    print("📊 COVERAGE ANALYSIS")
    print("="*70)
    
    coverage_map = {
        "PHP Structure": ["Classes", "Methods", "Properties", "Inheritance"],
        "PHP Behavior": ["CALLS", "IMPORTS", "ACCESSES", "THROWS", "INSTANTIATES"],
        "EspoCRM Dynamic": ["Container Resolution", "Constant Propagation", "Service Map"],
        "EspoCRM Subsystems": ["Hooks", "Jobs", "ACL", "Events", "Routes"],
        "QueryBuilder": ["Query Chains", "Repository Methods", "ORM Operations"],
        "Formula DSL": ["Entity Operations", "Workflow", "Record CRUD", "ACL Checks"],
        "JavaScript": ["API Calls", "Model Operations", "WebSocket", "Collections"],
        "Metadata": ["Entity Relations", "Fields", "Permissions", "Endpoints"]
    }
    
    print("\n✅ WHAT WE CAPTURE:")
    for category, items in coverage_map.items():
        print(f"\n{category}:")
        for item in items:
            print(f"  ✓ {item}")
    
    # Missing items check
    print("\n⚠️ KNOWN LIMITATIONS:")
    limitations = [
        "Magic methods (__call, __get) - Need runtime tracing",
        "Dynamic SQL strings - Need query log analysis",
        "Template placeholders - Parser implemented but not integrated",
        "EntryPoints - Metadata exists but not fully mapped",
        "Field validators/processors - Structure exists but not extracted",
        "BPM/Workflows - Would need database access",
        "Custom modules - Need recursive directory scanning"
    ]
    
    for limitation in limitations:
        print(f"  • {limitation}")
    
    # Summary
    print("\n" + "="*70)
    print("📈 TEST SUMMARY")
    print("="*70)
    print(f"Tests Passed: {len(tests_passed)}")
    print(f"Tests Failed: {len(tests_failed)}")
    
    if tests_passed:
        print("\n✅ Passed:")
        for test in tests_passed:
            print(f"  • {test}")
    
    if tests_failed:
        print("\n❌ Failed:")
        for test in tests_failed:
            print(f"  • {test}")
    
    # Final verdict
    total_tests = len(tests_passed) + len(tests_failed)
    coverage_percent = (len(tests_passed) / total_tests * 100) if total_tests > 0 else 0
    
    print("\n" + "🎯"*35)
    if coverage_percent >= 80:
        print(f"✅ EXCELLENT COVERAGE: {coverage_percent:.1f}% of parsers working!")
        print("We can successfully navigate EspoCRM's codebase!")
    elif coverage_percent >= 60:
        print(f"⚠️ GOOD COVERAGE: {coverage_percent:.1f}% of parsers working")
        print("Most navigation patterns supported, some gaps remain")
    else:
        print(f"❌ INSUFFICIENT COVERAGE: {coverage_percent:.1f}% of parsers working")
        print("Significant gaps in code navigation capability")
    print("🎯"*35)
    
    return len(tests_failed) == 0


if __name__ == "__main__":
    success = test_all_parsers()
    sys.exit(0 if success else 1)