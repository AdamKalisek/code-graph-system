# Configuration Guide

## Configuration File Format

The system uses YAML configuration files to define project settings, database connections, and parsing options.

## Basic Configuration

Create a `your-project.yaml` file:

```yaml
# Project settings
project:
  name: my-app
  root: /path/to/your/codebase
  languages:
    - typescript
    - javascript
    - php

# SQLite staging database
storage:
  sqlite: data/my-app.db

# Neo4j connection
neo4j:
  uri: bolt://localhost:7688
  username: neo4j
  password: password
  database: neo4j
  wipe_before_import: false

# Plugins to enable
plugins:
  - nextjs
  - espocrm

# Parsing options (optional)
parsing:
  ignore_patterns:
    - "*.test.ts"
    - "*.spec.js"
    - "node_modules/"
    - "vendor/"
  follow_symlinks: false
  max_file_size: 10485760  # 10MB

# Import options (optional)
import:
  strategy: bolt-parallel  # admin-export, apoc-parallel, bolt-parallel
  batch_size: 1000
  parallel_workers: 8
  node_batch: 500
  relationship_batch: 2000
```

## Configuration Options

### Project Section

#### `project.name`
- **Type:** String
- **Required:** Yes
- **Description:** Unique identifier for your project

#### `project.root`
- **Type:** String (Path)
- **Required:** Yes
- **Description:** Absolute path to codebase root directory

#### `project.languages`
- **Type:** Array of strings
- **Required:** Yes
- **Valid values:** `typescript`, `javascript`, `php`, `python`, `java`
- **Description:** Languages to parse in the codebase

### Storage Section

#### `storage.sqlite`
- **Type:** String (Path)
- **Required:** Yes
- **Description:** Path to SQLite staging database (created if not exists)

### Neo4j Section

#### `neo4j.uri`
- **Type:** String (URI)
- **Required:** Yes
- **Format:** `bolt://host:port` or `neo4j://host:port`
- **Description:** Neo4j connection URI

#### `neo4j.username`
- **Type:** String
- **Required:** Yes
- **Default:** `neo4j`
- **Description:** Neo4j username

#### `neo4j.password`
- **Type:** String
- **Required:** Yes
- **Description:** Neo4j password

#### `neo4j.database`
- **Type:** String
- **Default:** `neo4j`
- **Description:** Target database name (Neo4j 4.0+)

#### `neo4j.wipe_before_import`
- **Type:** Boolean
- **Default:** `false`
- **Description:** Clear database before import (WARNING: deletes all data)

### Plugins Section

#### `plugins`
- **Type:** Array of strings
- **Required:** No
- **Valid values:** `nextjs`, `espocrm`, `react`, `vue`, `angular`
- **Description:** Framework-specific plugins to enable

### Parsing Options

#### `parsing.ignore_patterns`
- **Type:** Array of strings (glob patterns)
- **Default:** `["node_modules/", "vendor/", "*.test.*", "*.spec.*"]`
- **Description:** Files/directories to skip during parsing

#### `parsing.follow_symlinks`
- **Type:** Boolean
- **Default:** `false`
- **Description:** Whether to follow symbolic links

#### `parsing.max_file_size`
- **Type:** Integer (bytes)
- **Default:** `10485760` (10MB)
- **Description:** Skip files larger than this size

### Import Options

#### `import.strategy`
- **Type:** String
- **Default:** `bolt-parallel`
- **Valid values:**
  - `admin-export`: Fastest, requires filesystem access to Neo4j
  - `apoc-parallel`: Fast, requires APOC plugin
  - `bolt-parallel`: Universal, works everywhere
- **Description:** Import strategy to use

#### `import.batch_size`
- **Type:** Integer
- **Default:** `1000`
- **Description:** General batch size for operations

#### `import.parallel_workers`
- **Type:** Integer
- **Default:** `8`
- **Description:** Number of parallel import workers

#### `import.node_batch`
- **Type:** Integer
- **Default:** `500`
- **Description:** Nodes per batch

#### `import.relationship_batch`
- **Type:** Integer
- **Default:** `2000`
- **Description:** Relationships per batch

## Environment Variables

You can override configuration with environment variables:

```bash
# Override Neo4j connection
export NEO4J_URI=bolt://prod-server:7687
export NEO4J_PASSWORD=secure_password

# Override import strategy
export IMPORT_STRATEGY=admin-export
export IMPORT_WORKERS=16

# Run with overrides
python src/indexer/main.py --config project.yaml
```

## Multiple Configurations

### Development Configuration
```yaml
# dev.yaml
project:
  name: myapp-dev
  root: ~/projects/myapp

neo4j:
  uri: bolt://localhost:7688
  password: dev_password
  wipe_before_import: true

import:
  strategy: bolt-parallel
  parallel_workers: 4
```

### Production Configuration
```yaml
# prod.yaml
project:
  name: myapp-prod
  root: /var/www/myapp

neo4j:
  uri: bolt://neo4j-cluster:7687
  password: ${NEO4J_PASSWORD}  # From environment
  wipe_before_import: false

import:
  strategy: admin-export
  parallel_workers: 16
  node_batch: 5000
```

## Plugin-Specific Configuration

### NextJS Plugin
```yaml
plugins:
  - nextjs

nextjs:
  app_directory: app  # or pages for older versions
  api_routes_path: app/api
  detect_server_components: true
  analyze_metadata: true
```

### EspoCRM Plugin
```yaml
plugins:
  - espocrm

espocrm:
  custom_path: custom/Espo/Custom
  modules_path: application/Espo/Modules
  analyze_metadata: true
  detect_relationships: true
```

## Performance Tuning

### For Large Codebases (>100k files)
```yaml
parsing:
  max_file_size: 5242880  # 5MB
  parallel_parsing: true
  parser_workers: 16

import:
  strategy: admin-export
  parallel_workers: 32
  node_batch: 10000
  relationship_batch: 50000

neo4j:
  connection_pool_size: 50
  connection_timeout: 30
```

### For Limited Memory (<4GB)
```yaml
parsing:
  streaming_mode: true
  cache_size: 100  # MB

import:
  strategy: bolt-parallel
  parallel_workers: 2
  node_batch: 100
  relationship_batch: 500
  use_streaming: true
```

## Validation

Validate your configuration:

```bash
python tools/validate_config.py project.yaml
```

This checks:
- File paths exist
- Neo4j connection works
- Required plugins are available
- No conflicting options