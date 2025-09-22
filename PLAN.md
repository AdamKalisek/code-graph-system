# Refactoring Plan

## Objectives
- Treat EspoCRM support as one plugin among many, allowing the indexer to handle arbitrary PHP/JS projects.
- Consolidate the ingestion → graph export pipeline into configurable stages with minimal duplication.
- Retire or quarantine dead code paths left by previous iterations and replace hard-coded credentials/paths with configuration.
- Provide a foundation for automated testing that distinguishes core behavior from Espo-specific extensions.

## Current Pain Points
- `src/indexer/main.py` couples the pipeline to EspoCRM via hard-coded project roots, Espo-specific parsers, and bespoke cross-language logic.
- `src/core/symbol_table.py` bakes EspoCRM heuristics (partial namespace matching) into generic resolution logic.
- Parsers in `parsers/` are written around EspoCRM conventions (Ajax helpers, metadata layouts) with no abstraction for other stacks.
- Multiple Neo4j import/export scripts under `src/import/` and `src/export/` repeat the same responsibilities with different credentials and filenames.
- Legacy scripts and node_modules in `archive/` contribute noise and hide the canonical workflows.
- Tests mix core guarantees with EspoCRM fixtures, making it hard to validate a generalized build.

## Target Architecture
1. **Config-driven Pipeline**
   - CLI entry point accepts a project descriptor (YAML/JSON) describing source roots, languages, and plugin hooks.
   - Core pipeline (scan → collect → resolve → link → export) orchestrated by dependency-injected strategies.
2. **Plugin System**
   - Language Modules: provide symbol collectors/reference resolvers per language (PHP, JS, etc.).
   - Domain Plugins: optional modules for product-specific metadata (e.g., EspoCRM metadata, Salesforce metadata) and cross-language linkers.
   - Plugins register additional relationships, heuristics, or post-processing passes without modifying core code.
3. **Unified Graph Export**
   - Single exporter/importer pair with swappable drivers (SQLite, Neo4j) and consistent configuration (URI, auth, batch size).
   - Export format versioning to ensure compatibility as schema evolves.
4. **Testing Strategy**
   - Core unit/integration tests run against synthetic fixtures.
   - Plugin-specific test suites reside with each plugin and exercise product heuristics separately.

## Work Plan

### Phase 0 – Baseline & Cleanup
- Document the existing end-to-end flow and delete or archive redundant scripts (`src/import/*`, `archive/indexing_scripts/*`) retaining only a reference implementation.
- Add smoke tests that exercise the current pipeline to protect against regressions during refactor.

### Phase 1 – Core Pipeline Extraction
- Introduce a `PipelineConfig` object describing source roots, enabled languages, database targets, and plugin set.
- Create a `CodebaseIndexer` class that encapsulates the current run sequence (`_index_file_structure`, symbol collection, reference resolution, linking, export) but delegates implementation details to injected components.
- Move statistics tracking to an instrumentation module so it can be reused by different indexers.

### Phase 2 – Language Module Boundary
- Define interfaces (`LanguageCollector`, `ReferenceResolver`) that the PHP and JS implementations must satisfy.
- Refactor `parsers/php_enhanced.py` and `parsers/php_reference_resolver.py` into a `languages/php` package that implements those interfaces with no Espo-specific logic.
- Extract EspoCRM JS heuristics (`parsers/js_espocrm_parser.py`) into a plugin subclass while creating a baseline JS parser for generic projects.

### Phase 3 – Domain Pluginization
- Establish a plugin registry (`plugins/`) with lifecycle hooks (`before_collect`, `after_resolve`, `cross_language_links`, etc.).
- Move EspoCRM-specific pieces into `plugins/espocrm/`:
  - Metadata parser and configuration edge creation.
  - Controller/action endpoint mapping logic.
  - Espo namespace fallback currently embedded in `SymbolTable.resolve`.
- Ensure core code only depends on plugin interfaces (e.g., `NamespaceFallbackStrategy`).

### Phase 4 – Export/Import Consolidation
- Merge the divergent Neo4j import scripts into a configurable `GraphExporter` and `GraphImporter` supporting:
  - Single point of credential configuration.
  - Standard batching/retry strategy.
  - Optional drivers (direct bolt vs. Cypher file generation) selected via config.
- Update CLI commands to target these unified components and deprecate legacy scripts.

### Phase 5 – Configuration & CLI
- Provide a `memory.yaml` schema (project root, include/exclude globs, enabled plugins, graph options).
- Implement CLI (`python -m memory index --config memory.yaml`) that loads the config, instantiates the pipeline, runs index/export/import steps, and reports metrics.
- Support environment-based overrides for secrets (Neo4j credentials).

### Phase 6 – Testing & Quality Gates
- Split existing tests into:
  - Core: run against generic fixtures (rename or duplicate Espo fixtures as neutral data where possible).
  - Plugin: run Espo-specific behavior when the plugin is enabled.
- Add regression tests for the plugin registry to ensure disabled plugins cannot leak behavior into the core pipeline.
- Configure CI targets (lint, unit, integration, plugin).

### Phase 7 – Documentation & Samples
- Update README/docs to describe the plugin model, configuration file, and how to add a new plugin.
- Provide sample configs for EspoCRM and a generic PHP/JS project.

### Phase 8 – Post-refactor Cleanup
- Remove or relocate `archive/` assets that are superseded by the new architecture.
- Replace hard-coded strings (e.g., `bolt://localhost:7688`) with configuration-driven defaults and document environment variables.
- Audit logging to ensure consistent structure and log levels across modules.

## Risk & Mitigation Notes
- **Regression Risk:** Preserve current behavior behind an EspoCRM plugin until tests demonstrate feature parity.
- **Performance:** Monitor SQLite and Neo4j ingest performance after abstraction; extract shared batching utilities rather than duplicating logic per importer.
- **Adoption:** Deliver migration docs so existing automation (scripts referencing `CompleteEspoCRMIndexer`) can switch to the new CLI with minimal changes.

## Immediate Next Steps
1. Create design sketches for the plugin interface and pipeline configuration objects.
2. Spike a prototype where `CompleteEspoCRMIndexer` delegates to a configuration-driven pipeline while still using the current components.
3. Identify quick deletions (unused import scripts, dormant archive modules) that can be removed before deeper refactor.
