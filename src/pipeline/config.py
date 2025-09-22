"""Configuration helpers for the indexing pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # Optional dependency - documented in requirements
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - exercised when PyYAML is missing
    yaml = None  # type: ignore


@dataclass
class ProjectConfig:
    """Describe the project that should be analysed."""

    name: str
    root: Path
    languages: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], base_dir: Path) -> "ProjectConfig":
        raw_root = data.get("root", ".")
        root = Path(raw_root)
        if not root.is_absolute():
            root = (base_dir / root).resolve()

        name = data.get("name") or root.name
        languages = data.get("languages") or []
        return cls(name=name, root=root, languages=languages)


@dataclass
class StorageConfig:
    """Local storage configuration (SQLite, caches, etc.)."""

    sqlite_path: Path

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        project_name: str,
        base_dir: Path,
    ) -> "StorageConfig":
        raw_sqlite = data.get("sqlite") or f"data/{project_name}.db"
        sqlite_path = Path(raw_sqlite)
        if not sqlite_path.is_absolute():
            sqlite_path = (base_dir / sqlite_path).resolve()
        return cls(sqlite_path=sqlite_path)


@dataclass
class Neo4jConfig:
    """Remote graph database configuration."""

    uri: str = "bolt://localhost:7688"
    username: str = "neo4j"
    password: str = "password123"
    database: str = "neo4j"
    wipe_before_import: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any], project_name: str) -> "Neo4jConfig":
        return cls(
            uri=data.get("uri", "bolt://localhost:7688"),
            username=data.get("username", "neo4j"),
            password=data.get("password", "password123"),
            database=data.get("database", project_name),
            wipe_before_import=bool(data.get("wipe_before_import", False)),
        )


@dataclass
class PipelineConfig:
    """Top-level configuration for the indexing pipeline."""

    project: ProjectConfig
    storage: StorageConfig
    neo4j: Neo4jConfig
    plugins: List[str] = field(default_factory=list)
    extras: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], base_dir: Path) -> "PipelineConfig":
        project_cfg = ProjectConfig.from_dict(data.get("project", {}), base_dir)
        storage_cfg = StorageConfig.from_dict(
            data.get("storage", {}), project_cfg.name, base_dir
        )
        neo4j_cfg = Neo4jConfig.from_dict(data.get("neo4j", {}), project_cfg.name)
        plugins = data.get("plugins") or []
        extras = {k: v for k, v in data.items() if k not in {"project", "storage", "neo4j", "plugins"}}
        return cls(project=project_cfg, storage=storage_cfg, neo4j=neo4j_cfg, plugins=plugins, extras=extras)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the configuration to a basic dictionary (useful for debugging)."""
        return {
            "project": {
                "name": self.project.name,
                "root": str(self.project.root),
                "languages": self.project.languages,
            },
            "storage": {"sqlite": str(self.storage.sqlite_path)},
            "neo4j": {
                "uri": self.neo4j.uri,
                "username": self.neo4j.username,
                "password": self.neo4j.password,
                "database": self.neo4j.database,
                "wipe_before_import": self.neo4j.wipe_before_import,
            },
            "plugins": list(self.plugins),
            "extras": self.extras,
        }


def load_pipeline_config(path: Path | str) -> PipelineConfig:
    """Load a pipeline configuration from JSON or YAML."""

    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    raw_text = config_path.read_text()
    suffix = config_path.suffix.lower()

    if suffix in {".yaml", ".yml"}:
        if yaml is None:
            raise RuntimeError(
                "PyYAML is required to parse YAML configuration files. "
                "Install it via `pip install PyYAML`."
            )
        data = yaml.safe_load(raw_text) or {}
    elif suffix == ".json":
        data = json.loads(raw_text or "{}")
    else:
        raise ValueError(
            f"Unsupported configuration format '{suffix}'. Use .yaml, .yml, or .json."
        )

    base_dir = config_path.parent.resolve()
    if not isinstance(data, dict):
        raise ValueError("Configuration file must contain a JSON/YAML object at the top level.")
    return PipelineConfig.from_dict(data, base_dir)
