"""
Plugin Manager for the Universal Code Graph System.

Handles dynamic loading, lifecycle management, and orchestration of plugins.
"""

import importlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import yaml
import logging

from .plugin_interface import (
    IPlugin, ILanguagePlugin, IFrameworkPlugin, 
    ISystemPlugin, IAnalysisPlugin, PluginMetadata,
    PluginType
)
from .schema import CoreNode, Relationship


logger = logging.getLogger(__name__)


class PluginProcess:
    """Manages a plugin running in a separate process for sandboxing"""
    
    def __init__(self, plugin_path: str, plugin_id: str):
        self.plugin_path = plugin_path
        self.plugin_id = plugin_id
        self.process = None
        self.is_running = False
        
    def start(self):
        """Start the plugin process"""
        if self.is_running:
            return
            
        # Start plugin in subprocess for isolation
        self.process = subprocess.Popen(
            [sys.executable, '-m', 'code_graph_system.plugin_runner', self.plugin_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        self.is_running = True
        logger.info(f"Started plugin process: {self.plugin_id}")
        
    def stop(self):
        """Stop the plugin process"""
        if self.process and self.is_running:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.is_running = False
            logger.info(f"Stopped plugin process: {self.plugin_id}")
            
    def call_method(self, method: str, *args, **kwargs) -> Any:
        """Call a method on the plugin via IPC"""
        if not self.is_running:
            self.start()
            
        # Send request as JSON
        request = {
            'method': method,
            'args': args,
            'kwargs': kwargs
        }
        
        self.process.stdin.write(json.dumps(request) + '\n')
        self.process.stdin.flush()
        
        # Read response
        response_line = self.process.stdout.readline()
        if response_line:
            response = json.loads(response_line)
            if 'error' in response:
                raise Exception(f"Plugin error: {response['error']}")
            return response.get('result')
        return None


class PluginManager:
    """Manages all plugins in the system"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.plugins: Dict[str, IPlugin] = {}
        self.plugin_processes: Dict[str, PluginProcess] = {}
        self.language_plugins: Dict[str, List[str]] = {}
        self.framework_plugins: Dict[str, List[str]] = {}
        self.system_plugins: Dict[str, List[str]] = {}
        self.analysis_plugins: List[str] = []
        
        # Plugin directories
        self.plugin_dirs = self.config.get('plugin_directories', [
            './plugins/builtin',
            './plugins/community',
            Path.home() / '.cgs/plugins'
        ])
        
        # Sandboxing configuration
        self.use_sandboxing = self.config.get('security', {}).get('plugin_sandboxing', True)
        
    def discover_plugins(self) -> List[str]:
        """Auto-discover plugins in configured directories"""
        discovered = []
        
        for plugin_dir in self.plugin_dirs:
            plugin_path = Path(plugin_dir)
            if not plugin_path.exists():
                continue
                
            # Look for plugin.yaml or plugin.json files
            for config_file in plugin_path.glob('*/plugin.{yaml,yml,json}'):
                plugin_id = self._load_plugin_config(config_file)
                if plugin_id:
                    discovered.append(plugin_id)
                    
        logger.info(f"Discovered {len(discovered)} plugins")
        return discovered
        
    def _load_plugin_config(self, config_file: Path) -> Optional[str]:
        """Load plugin configuration from file"""
        try:
            with open(config_file) as f:
                if config_file.suffix in ['.yaml', '.yml']:
                    config = yaml.safe_load(f)
                else:
                    config = json.load(f)
                    
            plugin_id = config.get('id')
            if not plugin_id:
                logger.warning(f"Plugin config missing ID: {config_file}")
                return None
                
            # Store configuration
            self.config[f'plugin.{plugin_id}'] = config
            return plugin_id
            
        except Exception as e:
            logger.error(f"Failed to load plugin config {config_file}: {e}")
            return None
            
    def load_plugin(self, plugin_id: str) -> bool:
        """Load a specific plugin"""
        try:
            config = self.config.get(f'plugin.{plugin_id}')
            if not config:
                logger.error(f"No configuration found for plugin: {plugin_id}")
                return False
                
            plugin_path = config.get('path')
            if not plugin_path:
                # Try to find plugin in directories
                for plugin_dir in self.plugin_dirs:
                    potential_path = Path(plugin_dir) / plugin_id / 'plugin.py'
                    if potential_path.exists():
                        plugin_path = str(potential_path)
                        break
                        
            if not plugin_path or not Path(plugin_path).exists():
                logger.error(f"Plugin file not found: {plugin_id}")
                return False
                
            if self.use_sandboxing:
                # Load plugin in separate process
                plugin_process = PluginProcess(plugin_path, plugin_id)
                plugin_process.start()
                self.plugin_processes[plugin_id] = plugin_process
                
                # Get metadata via IPC
                metadata = plugin_process.call_method('get_metadata')
            else:
                # Load plugin in-process (less secure but faster)
                plugin = self._load_plugin_module(plugin_path, plugin_id)
                if not plugin:
                    return False
                    
                self.plugins[plugin_id] = plugin
                metadata = plugin.get_metadata()
                
            # Register plugin by type
            self._register_plugin(plugin_id, metadata)
            
            logger.info(f"Loaded plugin: {plugin_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_id}: {e}")
            return False
            
    def _load_plugin_module(self, plugin_path: str, plugin_id: str) -> Optional[IPlugin]:
        """Load plugin module directly (non-sandboxed)"""
        try:
            spec = importlib.util.spec_from_file_location(plugin_id, plugin_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find plugin class
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, IPlugin) and attr != IPlugin:
                    return attr()
                    
            logger.error(f"No IPlugin implementation found in {plugin_path}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to load plugin module {plugin_path}: {e}")
            return None
            
    def _register_plugin(self, plugin_id: str, metadata: Dict[str, Any]):
        """Register plugin by its capabilities"""
        plugin_type = metadata.get('type', 'language')
        
        if plugin_type == 'language':
            for lang in metadata.get('supported_languages', []):
                if lang not in self.language_plugins:
                    self.language_plugins[lang] = []
                self.language_plugins[lang].append(plugin_id)
                
        elif plugin_type == 'framework':
            for fw in metadata.get('supported_frameworks', []):
                if fw not in self.framework_plugins:
                    self.framework_plugins[fw] = []
                self.framework_plugins[fw].append(plugin_id)
                
        elif plugin_type == 'system':
            for sys in metadata.get('supported_systems', []):
                if sys not in self.system_plugins:
                    self.system_plugins[sys] = []
                self.system_plugins[sys].append(plugin_id)
                
        elif plugin_type == 'analysis':
            self.analysis_plugins.append(plugin_id)
            
    def get_language_handler(self, file_path: str) -> Optional[Any]:
        """Get appropriate language plugin for a file"""
        # Determine language from extension
        ext = Path(file_path).suffix[1:]  # Remove dot
        
        language_map = {
            'php': 'php',
            'js': 'javascript',
            'jsx': 'javascript',
            'ts': 'typescript',
            'tsx': 'typescript',
            'py': 'python',
            'java': 'java',
            'go': 'go',
            'rs': 'rust',
            'rb': 'ruby',
            'cs': 'csharp',
            'cpp': 'cpp',
            'c': 'c',
            'h': 'c',
            'hpp': 'cpp'
        }
        
        language = language_map.get(ext)
        if not language:
            return None
            
        plugin_ids = self.language_plugins.get(language, [])
        if not plugin_ids:
            return None
            
        # Return first available plugin
        plugin_id = plugin_ids[0]
        
        if self.use_sandboxing:
            return self.plugin_processes.get(plugin_id)
        else:
            return self.plugins.get(plugin_id)
            
    def get_framework_handlers(self, project_root: str) -> List[Any]:
        """Get all applicable framework plugins for a project"""
        handlers = []
        
        for fw_name, plugin_ids in self.framework_plugins.items():
            for plugin_id in plugin_ids:
                if self.use_sandboxing:
                    plugin = self.plugin_processes.get(plugin_id)
                    if plugin and plugin.call_method('detect_framework', project_root):
                        handlers.append(plugin)
                else:
                    plugin = self.plugins.get(plugin_id)
                    if plugin and plugin.detect_framework(project_root):
                        handlers.append(plugin)
                        
        return handlers
        
    def shutdown(self):
        """Shutdown all plugin processes"""
        for plugin_process in self.plugin_processes.values():
            plugin_process.stop()
            
        self.plugin_processes.clear()
        self.plugins.clear()
        logger.info("Plugin manager shutdown complete")