"""Plugin registry for managing pipeline extensions."""

from __future__ import annotations

import logging
from typing import Dict, List, Sequence

from src.pipeline import PipelineConfig

from .base import PipelinePlugin, PluginContext

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Instantiate and execute configured plugins."""

    def __init__(self, config: PipelineConfig, available_plugins: Dict[str, type[PipelinePlugin]]):
        self.config = config
        self.available_plugins = available_plugins
        self._plugins: List[PipelinePlugin] = []

    def load(self) -> None:
        self._plugins = []
        for name in self.config.plugins:
            plugin_cls = self.available_plugins.get(name)
            if not plugin_cls:
                logger.warning("Plugin '%s' is not registered; skipping.", name)
                continue
            plugin = plugin_cls()  # type: ignore[call-arg]
            logger.debug("Loaded plugin %s", plugin.name)
            self._plugins.append(plugin)

    @property
    def plugins(self) -> Sequence[PipelinePlugin]:
        return tuple(self._plugins)

    # Hook dispatch helpers -------------------------------------------------

    def before_collect(self, context: PluginContext) -> None:
        for plugin in self._plugins:
            plugin.before_collect(context)

    def after_collect(self, context: PluginContext) -> None:
        for plugin in self._plugins:
            plugin.after_collect(context)

    def after_resolve(self, context: PluginContext) -> None:
        for plugin in self._plugins:
            plugin.after_resolve(context)
