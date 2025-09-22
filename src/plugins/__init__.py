"""Plugin registry and built-in plugins."""

from __future__ import annotations

from typing import Dict

from src.pipeline import PipelineConfig

from .base import PipelinePlugin, PluginContext
from .registry import PluginRegistry
from .espocrm import EspoCrmPlugin, EspoApiScanner
from .nextjs import NextJsPlugin

# Built-in plugins keyed by configuration name.
_BUILTIN_PLUGINS: Dict[str, type[PipelinePlugin]] = {
    "espocrm": EspoCrmPlugin,
    "nextjs": NextJsPlugin,
}


def create_registry(config: PipelineConfig) -> PluginRegistry:
    registry = PluginRegistry(config, available_plugins=_BUILTIN_PLUGINS)
    registry.load()
    return registry


__all__ = [
    "PipelinePlugin",
    "PluginContext",
    "PluginRegistry",
    "create_registry",
    "EspoApiScanner",
    "NextJsPlugin",
]
