"""Generic indexing pipeline orchestrator."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Protocol, TYPE_CHECKING

from src.core.symbol_table import Symbol, SymbolTable, SymbolType
from src.pipeline.config import PipelineConfig

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from src.plugins.registry import PluginRegistry

logger = logging.getLogger(__name__)


class LanguageModule(Protocol):
    """Interface for language-specific indexing steps."""

    name: str

    def collect(self) -> None:
        """Collect symbols for the language."""

    def resolve(self) -> None:
        """Resolve references for the language."""

    def stats(self) -> Dict[str, int]:  # pragma: no cover - simple delegation
        """Return statistics gathered during collection/resolution."""


@dataclass
class CodebaseIndexer:
    """Configuration-driven indexer orchestrating language modules."""

    config: PipelineConfig
    symbol_table_override: Optional[SymbolTable] = None
    plugin_registry: Optional["PluginRegistry"] = None
    symbol_table: SymbolTable = field(init=False)
    project_root: Path = field(init=False)
    modules: List[LanguageModule] = field(init=False, default_factory=list)
    stats: Dict[str, int] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self.project_root = self.config.project.root
        if self.symbol_table_override is not None:
            self.symbol_table = self.symbol_table_override
        else:
            sqlite_path = self.config.storage.sqlite_path
            sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            self.symbol_table = SymbolTable(str(sqlite_path))
        self.modules = list(self._build_language_modules())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> Dict[str, int]:
        logger.info("Starting indexing pipeline for %s", self.project_root)
        self.stats.clear()

        plugin_context = None
        if self.plugin_registry:
            from src.plugins.base import PluginContext  # local import to avoid cycles

            plugin_context = PluginContext(
                config=self.config,
                project_root=self.project_root,
                symbol_table=self.symbol_table,
                modules=self.modules,
                stats=self.stats,
            )
            self.plugin_registry.before_collect(plugin_context)

        self._index_file_structure()

        for module in self.modules:
            logger.info("Collecting symbols for %s", module.name)
            module.collect()
            self._merge_stats(module.stats())

        if self.plugin_registry and plugin_context:
            self.plugin_registry.after_collect(plugin_context)

        for module in self.modules:
            logger.info("Resolving references for %s", module.name)
            module.resolve()
            self._merge_stats(module.stats())

        if self.plugin_registry and plugin_context:
            self.plugin_registry.after_resolve(plugin_context)

        self.stats.setdefault("total_symbols", self.symbol_table.get_stats().get("total_symbols", 0))
        return dict(self.stats)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _merge_stats(self, module_stats: Dict[str, int]) -> None:
        for key, value in module_stats.items():
            self.stats[key] = self.stats.get(key, 0) + value

    def _build_language_modules(self) -> Iterable[LanguageModule]:
        languages = {lang.lower() for lang in self.config.project.languages} or {"php", "javascript"}

        if "php" in languages:
            yield PHPLanguageModule(self.project_root, self.symbol_table)
        if "javascript" in languages:
            yield JavaScriptLanguageModule(self.project_root, self.symbol_table)

    def _index_file_structure(self) -> None:
        logger.info("Indexing file structure under %s", self.project_root)
        dir_count = 0
        file_count = 0
        seen_dirs: set[str] = set()

        for root, dirs, files in self._walk_project_root():
            root_path = Path(root)
            dir_id = f"dir_{hashlib.md5(str(root_path).encode()).hexdigest()}"

            if str(root_path) not in seen_dirs:
                dir_sym = Symbol(
                    id=dir_id,
                    name=root_path.name or str(self.project_root),
                    type=SymbolType.DIRECTORY,
                    file_path=str(root_path),
                    line_number=0,
                    column_number=0,
                    metadata={"node_type": "directory", "path": str(root_path)},
                )
                self.symbol_table.add_symbol(dir_sym)
                seen_dirs.add(str(root_path))
                dir_count += 1

                parent_path = root_path.parent
                if str(parent_path) in seen_dirs and str(parent_path) != str(root_path):
                    parent_id = f"dir_{hashlib.md5(str(parent_path).encode()).hexdigest()}"
                    self.symbol_table.add_reference(
                        source_id=parent_id,
                        target_id=dir_id,
                        reference_type="CONTAINS",
                        line=0,
                        column=0,
                        context="directory_structure",
                    )

            for file_name in files:
                if not self._is_indexable_file(file_name):
                    continue
                file_path = root_path / file_name
                file_id = f"file_{hashlib.md5(str(file_path).encode()).hexdigest()}"

                file_sym = Symbol(
                    id=file_id,
                    name=file_name,
                    type=SymbolType.FILE,
                    file_path=str(file_path),
                    line_number=0,
                    column_number=0,
                    metadata={"node_type": "file", "extension": file_path.suffix},
                )
                self.symbol_table.add_symbol(file_sym)
                file_count += 1

                self.symbol_table.add_reference(
                    source_id=dir_id,
                    target_id=file_id,
                    reference_type="CONTAINS",
                    line=0,
                    column=0,
                    context="file_in_directory",
                )

        self.symbol_table.conn.commit()
        self.stats["directories"] = dir_count
        self.stats["files"] = file_count

    def _walk_project_root(self):
        for root, dirs, files in os_walk(self.project_root):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {'vendor', 'node_modules'}]
            yield root, dirs, files

    def _is_indexable_file(self, filename: str) -> bool:
        return any(
            filename.endswith(ext)
            for ext in ['.php', '.js', '.jsx', '.ts', '.tsx', '.json', '.yml', '.yaml', '.xml', '.html', '.css', '.scss']
        )


# ----------------------------------------------------------------------
# Language modules (initial implementation; more abstraction forthcoming)
# ----------------------------------------------------------------------

import os
from typing import Tuple

from parsers.php_enhanced import PHPSymbolCollector
from parsers.php_reference_resolver import PHPReferenceResolver
from parsers.js_parser import JavaScriptParser, JSSymbol, JSReference


def os_walk(root: Path):  # pragma: no cover - passthrough helper for testability
    return os.walk(root)


@dataclass
class PHPLanguageModule:
    project_root: Path
    symbol_table: SymbolTable
    name: str = "php"
    _stats: Dict[str, int] = field(default_factory=dict)

    def collect(self) -> None:
        collector = PHPSymbolCollector(self.symbol_table)
        php_files = list(self.project_root.rglob("*.php"))
        self._stats["php_files"] = len(php_files)

        for idx, file_path in enumerate(php_files, 1):
            try:
                collector.parse_file(str(file_path))
            except Exception as exc:  # pragma: no cover - passthrough logging
                logger.debug("PHP symbol collection failed for %s: %s", file_path, exc)
            if idx % 200 == 0:
                logger.debug("Collected PHP symbols from %s/%s files", idx, len(php_files))

    def resolve(self) -> None:
        resolver = PHPReferenceResolver(self.symbol_table)
        php_files = list(self.project_root.rglob("*.php"))
        for idx, file_path in enumerate(php_files, 1):
            try:
                resolver.resolve_file(str(file_path))
            except Exception as exc:  # pragma: no cover - passthrough logging
                logger.debug("PHP reference resolution failed for %s: %s", file_path, exc)
            if idx % 200 == 0:
                logger.debug("Resolved PHP references for %s/%s files", idx, len(php_files))

        stats = self.symbol_table.get_stats()
        self._stats["php_symbols"] = stats.get("total_symbols", 0)
        self._stats["php_references"] = stats.get("total_references", 0)

    def stats(self) -> Dict[str, int]:
        return dict(self._stats)


@dataclass
class JavaScriptLanguageModule:
    project_root: Path
    symbol_table: SymbolTable
    name: str = "javascript"
    _stats: Dict[str, int] = field(default_factory=dict)
    parser: JavaScriptParser = field(default_factory=JavaScriptParser)
    api_calls: List[Dict[str, object]] = field(default_factory=list)
    processed_files: List[Path] = field(default_factory=list)

    def collect(self) -> None:
        js_files = self._discover_files()
        self._stats["js_files"] = len(js_files)

        total_symbols = 0
        total_references = 0
        self.api_calls.clear()
        self.processed_files = list(js_files)

        for idx, file_path in enumerate(js_files, 1):
            try:
                symbols, references = self.parser.parse_file(str(file_path))
            except Exception as exc:  # pragma: no cover - passthrough logging
                logger.debug("JS parse failed for %s: %s", file_path, exc)
                continue

            for symbol in symbols:
                symbol_id = f"js_{symbol.id}"
                sym = Symbol(
                    id=symbol_id,
                    name=symbol.name,
                    type=self._map_symbol_type(symbol.type),
                    file_path=str(file_path),
                    line_number=symbol.line,
                    column_number=symbol.column,
                    namespace=None,
                    parent_id=None,
                    metadata={"js_type": symbol.type, "js_metadata": symbol.metadata},
                )
                self.symbol_table.add_symbol(sym)

                if symbol.type == 'api_call':
                    self.api_calls.append(
                        {
                            'symbol_id': symbol_id,
                            'endpoint': symbol.metadata.get('endpoint'),
                            'method': symbol.metadata.get('method'),
                            'php_controller': symbol.metadata.get('php_controller'),
                            'php_method': symbol.metadata.get('php_method'),
                            'file': str(file_path),
                            'line': symbol.line,
                        }
                    )

            for ref in references:
                source_id = ref.source_id if ref.source_id.startswith("js_") else f"js_{ref.source_id}"
                target_id = ref.target_id if ref.target_id.startswith("js_") else f"js_{ref.target_id}"
                self.symbol_table.add_reference(
                    source_id=source_id,
                    target_id=target_id,
                    reference_type=ref.type,
                    line=ref.line,
                    column=ref.column,
                    context=ref.context,
                )

            total_symbols += len(symbols)
            total_references += len(references)

            if idx % 100 == 0:
                logger.debug("Processed JS symbols for %s/%s files", idx, len(js_files))

        self.symbol_table.conn.commit()
        self._stats["js_symbols"] = total_symbols
        self._stats["js_references"] = total_references

    def resolve(self) -> None:
        # JS module currently resolves relationships during collection.
        return None

    def stats(self) -> Dict[str, int]:
        return dict(self._stats)

    def _discover_files(self) -> List[Path]:
        patterns = ["*.js", "*.jsx", "*.mjs", "*.ts", "*.tsx"]
        files: List[Path] = []
        for pattern in patterns:
            files.extend(self.project_root.rglob(pattern))
        return [f for f in files if "node_modules" not in f.parts and "vendor" not in f.parts]

    def _map_symbol_type(self, js_type: str) -> SymbolType:
        mapping = {
            'class': SymbolType.CLASS,
            'function': SymbolType.FUNCTION,
            'method': SymbolType.METHOD,
            'property': SymbolType.PROPERTY,
            'variable': SymbolType.VARIABLE,
            'import': SymbolType.IMPORT,
            'constant': SymbolType.CONSTANT,
        }
        return mapping.get(js_type, SymbolType.VARIABLE)
