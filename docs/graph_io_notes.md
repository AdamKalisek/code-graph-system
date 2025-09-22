# Neo4j Import/Export Mechanics (Current State)

## Export Scripts

- **`src/export/neo4j_exporter.py`**
  - Reads the SQLite cache (`.cache/complete_espocrm.db`) and generates `espocrm_complete_with_files.cypher`.
  - Features:
    - Explicit Directory/File nodes with deterministic IDs (`md5(path)`), enabling quick lookups.
    - Emits hierarchy relationships (`Directory-[:CONTAINS]->Directory`, `Directory-[:CONTAINS]->File`).
    - Adds `File-[:DEFINES]->Symbol` edges for fast per-file queries.
    - Escapes Cypher strings correctly; writes indices prior to data import.
    - Treats every code file (PHP, JS, JSON, YAML, etc.) uniformly and filters out vendor/node_modules.
  - Performs a single sequential pass over the symbols table; complexity mainly bound by disk I/O when writing large Cypher files.

- **`src/export/neo4j_final_export.py`**
  - Simpler variant that writes `espocrm_complete_graph.cypher` without file system elements.
  - Uses `Symbol` as base label and adds extra labels per type (Class/Method/etc.).
  - Includes summary comments with relationship counts at the end for quick debugging.

## Import Scripts

- **`src/import/optimized_neo4j_import_fixed.py`** (fastest path)
  - Connects directly to Neo4j via bolt and streams data using `UNWIND`.
  - Key performance traits:
    - Drops existing data in 10k batches to avoid memory spikes.
    - Creates a rich set of constraints and indexes before ingest, eliminating duplicates and supporting quick lookups.
    - Imports nodes in configurable batch sizes (default 10k) grouped by label combinations to minimise MetaGraph churn.
    - Imports relationships per type, also using `UNWIND`, and tracks failures per relationship type for debugging.
    - Supports retries for failed batches with smaller chunk sizes.
  - Emits stats: total nodes/relationships, import duration, failed counts.

- **`src/import/neo4j_importer.py`**
  - Consumes the large Cypher file produced by `neo4j_exporter.py`.
  - Splits statements into logical categories (indexes, directories, files, symbols, relationships) to provide detailed progress output.
  - Executes statements sequentially with periodic transactions/commits to avoid transaction bloat.
  - Provides user-facing analytics (counts per stage, throughput) for manual supervision.
  - Useful when bolt access is restricted or when a human-friendly step-by-step import is preferred.

- **`src/import/fast_importer.py`**
  - Similar philosophy to `neo4j_importer.py` but operates on pre-generated batch files (`batch_nodes_*.cypher`, `batch_rels_*.cypher`).
  - Optimised for streaming batches while retaining manual control.

- **`src/import/fast_cypher_import.py`**
  - Generates Cypher scripts containing `UNWIND` blocks per label/relationship type.
  - Acts as an intermediate solution: produce Cypher once, then pipe it through `cypher-shell` for fast headless imports.

- **`src/import/final_complete_import.py`**
  - Hybrid strategy:
    - Reads SQLite directly and uses bolt driver.
    - Prioritises critical relationships first (`EXTENDS`, `IMPLEMENTS`, `USES_TRAIT`) before others.
    - Performs verification queries at the end (counts, sample email references).
  - Serves as a scripted, reproducible end-to-end import with built-in validation.

## Observations & Requirements for Unified Tooling

1. **Performance Musts**
   - Preserve the `UNWIND`-based streaming import because it is the only path that avoids row-by-row execution overhead.
   - Maintain pre-creation of constraints and indexes to guarantee fast MATCH/CREATE operations.
   - Keep batching logic configurable (batch size, relationship chunking) to support large graphs.

2. **Operational Flexibility**
   - Support both direct bolt ingestion (fast) and Cypher file generation (offline/air-gapped scenarios).
   - Provide optional safeguards (dry-run, progress logging) akin to the current verbose importer scripts.

3. **Configurability Gaps**
   - Paths, credentials, and database names are hard-coded; new tooling must consume `PipelineConfig`/`Neo4jConfig`.
   - Current scripts assume EspoCRM-specific database filenames; the new system should target the active project cache (`config.storage.sqlite_path`).

4. **Reusable Logic to Extract**
   - Directory/file ID hashing (`md5(path)`), directory hierarchy construction, and symbol export mapping.
   - Label mapping logic for PHP vs. JS symbols.
   - Relationship grouping and batching by type.
   - Verification routines (post-import stats, orphaned nodes) for confidence checks.

These findings will guide the design of a consolidated `GraphExporter`/`GraphImporter` module that honours existing performance characteristics while making the process fully configuration-driven.
