# EspoCRM Code Graph System - Project Context
Date Created: 2025-08-26T10:00:00Z
Project: EspoCRM Code Graph Analysis System

## Project Overview
A sophisticated code analysis system that builds comprehensive knowledge graphs of EspoCRM installations, tracking relationships between PHP classes, JavaScript modules, and cross-language connections.

## Technology Stack
- Backend: Python with Neo4j graph database
- PHP Analysis: PHP AST parser with nikic/php-parser
- JavaScript Analysis: Tree-sitter parser
- Database: Neo4j for graph storage
- Cross-language: Custom linking system

## Architecture Components
- PHP Plugin: AST extraction and analysis
- JavaScript Plugin: Tree-sitter based parsing
- Cross-linker: Frontend-to-backend relationship detection
- Graph Store: Neo4j storage and querying
- Schema: Relationship and node type definitions

## Current Issues Identified
- Missing IMPLEMENTS relationships (Found 0, should find many)
- Missing USES_TRAIT relationships (Found 0, PHP uses many traits)
- Missing CALLS relationships (Found 0, JS makes API calls)
- Incomplete method call tracking within PHP
- Insufficient type hints and parameter capture

## Investigation Status
- Phase: Investigation COMPLETE
- Focus: Missing relationship detection and parser completeness

## Recent Updates
- 2025-08-26: Code Investigator completed comprehensive analysis of missing relationships
  - Report: .claude/memories/research/2025-08-26_code_graph_investigation.md
  - Found 4 critical bugs preventing relationship creation
  - Success rate currently only 30%, can improve to 90% with fixes
  - Priority fixes identified for JavaScript API calls and PHP trait usage