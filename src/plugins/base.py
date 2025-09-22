"""Plugin interfaces and context objects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence, Dict

from src.pipeline import PipelineConfig
from src.core.symbol_table import SymbolTable


@dataclass
class PluginContext:
    """Context passed to plugin hooks."""

    config: PipelineConfig
    project_root: Path
    symbol_table: SymbolTable
    modules: Sequence[object]
    stats: Dict[str, int]


class PipelinePlugin(Protocol):
    """Hook interface for pipeline extensions."""

    name: str

    def before_collect(self, context: PluginContext) -> None:
        """Run before language modules collect symbols."""

    def after_collect(self, context: PluginContext) -> None:
        """Run after all modules collected symbols."""

    def after_resolve(self, context: PluginContext) -> None:
        """Run after references are resolved and before export."""
