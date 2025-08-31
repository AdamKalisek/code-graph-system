"""Laravel Framework Plugin - Pass 3: Detect Laravel-specific patterns"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
import logging

from symbol_table import SymbolTable, Symbol, SymbolType

logger = logging.getLogger(__name__)


class LaravelPlugin:
    """Detects and adds Laravel-specific relationships"""
    
    def __init__(self, symbol_table: SymbolTable):
        self.symbol_table = symbol_table
        self.project_root = None
        self.routes = []
        self.service_providers = []
        self.middleware = []
        self.models = []
        self.controllers = []
        self.events = []
        self.listeners = []
        
    def analyze_project(self, project_root: str) -> None:
        """Analyze a Laravel project for framework-specific patterns"""
        self.project_root = Path(project_root)
        
        logger.info(f"Analyzing Laravel project at {project_root}")
        
        # Start transaction
        self.symbol_table.begin_transaction()
        
        try:
            # Detect Laravel structure
            if not self._is_laravel_project():
                logger.warning("Not a Laravel project")
                return
            
            # Analyze different Laravel components
            self._analyze_routes()
            self._analyze_service_providers()
            self._analyze_middleware()
            self._analyze_models()
            self._analyze_controllers()
            self._analyze_events_and_listeners()
            self._analyze_dependency_injection()
            self._analyze_facades()
            self._analyze_blade_templates()
            self._analyze_migrations()
            
            # Commit all changes
            self.symbol_table.commit()
            
            logger.info("Laravel analysis complete")
            
        except Exception as e:
            logger.error(f"Error analyzing Laravel project: {e}")
            self.symbol_table.rollback()
            raise
    
    def _is_laravel_project(self) -> bool:
        """Check if this is a Laravel project"""
        markers = [
            'artisan',
            'composer.json',
            'app/Http/Kernel.php',
            'bootstrap/app.php'
        ]
        
        for marker in markers:
            if not (self.project_root / marker).exists():
                return False
        
        # Check composer.json for Laravel
        composer_file = self.project_root / 'composer.json'
        try:
            with open(composer_file) as f:
                composer = json.load(f)
                require = composer.get('require', {})
                return 'laravel/framework' in require
        except:
            return False
    
    def _analyze_routes(self) -> None:
        """Analyze route definitions"""
        routes_path = self.project_root / 'routes'
        
        if not routes_path.exists():
            return
        
        logger.info("Analyzing routes...")
        
        route_files = ['web.php', 'api.php', 'console.php', 'channels.php']
        
        for route_file in route_files:
            file_path = routes_path / route_file
            if not file_path.exists():
                continue
            
            with open(file_path) as f:
                content = f.read()
            
            # Find route definitions
            # Route::get('/path', [Controller::class, 'method'])
            pattern = r"Route::(get|post|put|patch|delete|any)\s*\(\s*['\"]([^'\"]+)['\"].*?(?:\[([^,\]]+)::class\s*,\s*['\"]([^'\"]+)['\"]\]|['\"]([^'\"]+)['\"])"
            
            for match in re.finditer(pattern, content):
                method = match.group(1)
                path = match.group(2)
                controller_class = match.group(3)
                controller_method = match.group(4)
                closure = match.group(5)
                
                if controller_class and controller_method:
                    # Resolve controller
                    controller_symbol = self._resolve_class(controller_class)
                    if controller_symbol:
                        # Find method in controller
                        methods = self.symbol_table.get_children(controller_symbol.id)
                        for method_symbol in methods:
                            if method_symbol.type == SymbolType.METHOD and method_symbol.name == controller_method:
                                # Add route relationship
                                self._add_route_edge(
                                    path=path,
                                    http_method=method.upper(),
                                    controller_id=controller_symbol.id,
                                    method_id=method_symbol.id,
                                    file_path=str(file_path)
                                )
                                break
    
    def _analyze_service_providers(self) -> None:
        """Analyze service providers for dependency injection"""
        providers_path = self.project_root / 'app' / 'Providers'
        
        if not providers_path.exists():
            return
        
        logger.info("Analyzing service providers...")
        
        for provider_file in providers_path.glob('*.php'):
            # Get symbols in this file
            symbols = self.symbol_table.get_symbols_in_file(str(provider_file))
            
            for symbol in symbols:
                if symbol.type == SymbolType.CLASS and 'ServiceProvider' in symbol.name:
                    # Look for register and boot methods
                    methods = self.symbol_table.get_children(symbol.id)
                    
                    for method in methods:
                        if method.name == 'register':
                            # Analyze bindings in register method
                            self._analyze_service_bindings(method)
                        elif method.name == 'boot':
                            # Analyze boot operations
                            self._analyze_boot_operations(method)
    
    def _analyze_middleware(self) -> None:
        """Analyze middleware classes"""
        middleware_path = self.project_root / 'app' / 'Http' / 'Middleware'
        
        if not middleware_path.exists():
            return
        
        logger.info("Analyzing middleware...")
        
        for middleware_file in middleware_path.glob('*.php'):
            symbols = self.symbol_table.get_symbols_in_file(str(middleware_file))
            
            for symbol in symbols:
                if symbol.type == SymbolType.CLASS:
                    # Look for handle method
                    methods = self.symbol_table.get_children(symbol.id)
                    
                    for method in methods:
                        if method.name == 'handle':
                            # Mark as middleware
                            self._add_framework_metadata(
                                symbol.id,
                                'laravel_type',
                                'middleware'
                            )
                            self.middleware.append(symbol)
    
    def _analyze_models(self) -> None:
        """Analyze Eloquent models"""
        models_path = self.project_root / 'app' / 'Models'
        
        # Fallback to app directory if Models doesn't exist
        if not models_path.exists():
            models_path = self.project_root / 'app'
        
        logger.info("Analyzing models...")
        
        for model_file in models_path.glob('**/*.php'):
            symbols = self.symbol_table.get_symbols_in_file(str(model_file))
            
            for symbol in symbols:
                if symbol.type == SymbolType.CLASS:
                    # Check if it extends Model
                    if symbol.extends and 'Model' in symbol.extends:
                        self._add_framework_metadata(
                            symbol.id,
                            'laravel_type',
                            'model'
                        )
                        self.models.append(symbol)
                        
                        # Analyze relationships
                        self._analyze_model_relationships(symbol)
    
    def _analyze_model_relationships(self, model: Symbol) -> None:
        """Analyze Eloquent relationships in a model"""
        methods = self.symbol_table.get_children(model.id)
        
        relationship_types = [
            'hasOne', 'hasMany', 'belongsTo', 'belongsToMany',
            'morphTo', 'morphOne', 'morphMany', 'morphToMany'
        ]
        
        for method in methods:
            if method.type == SymbolType.METHOD:
                # Check if method returns a relationship
                # This would need actual code analysis in practice
                for rel_type in relationship_types:
                    if rel_type.lower() in method.name.lower():
                        # Add relationship edge
                        self._add_model_relationship(
                            source_model_id=model.id,
                            relationship_type=rel_type,
                            method_id=method.id
                        )
    
    def _analyze_controllers(self) -> None:
        """Analyze controller classes"""
        controllers_path = self.project_root / 'app' / 'Http' / 'Controllers'
        
        if not controllers_path.exists():
            return
        
        logger.info("Analyzing controllers...")
        
        for controller_file in controllers_path.glob('**/*.php'):
            symbols = self.symbol_table.get_symbols_in_file(str(controller_file))
            
            for symbol in symbols:
                if symbol.type == SymbolType.CLASS and 'Controller' in symbol.name:
                    self._add_framework_metadata(
                        symbol.id,
                        'laravel_type',
                        'controller'
                    )
                    self.controllers.append(symbol)
                    
                    # Analyze dependency injection in constructor
                    self._analyze_constructor_injection(symbol)
    
    def _analyze_constructor_injection(self, class_symbol: Symbol) -> None:
        """Analyze constructor dependency injection"""
        methods = self.symbol_table.get_children(class_symbol.id)
        
        for method in methods:
            if method.name == '__construct' and method.parameters:
                for param in method.parameters:
                    if 'type' in param and param['type']:
                        # Resolve the type
                        injected_type = self._resolve_class(param['type'])
                        if injected_type:
                            self.symbol_table.add_reference(
                                source_id=class_symbol.id,
                                target_id=injected_type.id,
                                reference_type='INJECTS',
                                line=method.line_number,
                                column=method.column_number,
                                context=f"Constructor injection of {param['type']}"
                            )
    
    def _analyze_events_and_listeners(self) -> None:
        """Analyze events and listeners"""
        events_path = self.project_root / 'app' / 'Events'
        listeners_path = self.project_root / 'app' / 'Listeners'
        
        # Analyze events
        if events_path.exists():
            logger.info("Analyzing events...")
            for event_file in events_path.glob('**/*.php'):
                symbols = self.symbol_table.get_symbols_in_file(str(event_file))
                for symbol in symbols:
                    if symbol.type == SymbolType.CLASS:
                        self._add_framework_metadata(
                            symbol.id,
                            'laravel_type',
                            'event'
                        )
                        self.events.append(symbol)
        
        # Analyze listeners
        if listeners_path.exists():
            logger.info("Analyzing listeners...")
            for listener_file in listeners_path.glob('**/*.php'):
                symbols = self.symbol_table.get_symbols_in_file(str(listener_file))
                for symbol in symbols:
                    if symbol.type == SymbolType.CLASS:
                        self._add_framework_metadata(
                            symbol.id,
                            'laravel_type',
                            'listener'
                        )
                        self.listeners.append(symbol)
                        
                        # Check handle method for event type
                        methods = self.symbol_table.get_children(symbol.id)
                        for method in methods:
                            if method.name == 'handle' and method.parameters:
                                # First parameter is usually the event
                                if method.parameters[0].get('type'):
                                    event_type = self._resolve_class(method.parameters[0]['type'])
                                    if event_type:
                                        self.symbol_table.add_reference(
                                            source_id=symbol.id,
                                            target_id=event_type.id,
                                            reference_type='LISTENS_TO',
                                            line=method.line_number,
                                            column=method.column_number,
                                            context=f"Listens to {method.parameters[0]['type']}"
                                        )
    
    def _analyze_dependency_injection(self) -> None:
        """Analyze Laravel's dependency injection container"""
        # This would analyze app()->bind(), app()->singleton(), etc.
        # For now, focusing on constructor injection which is handled elsewhere
        pass
    
    def _analyze_facades(self) -> None:
        """Analyze facade usage"""
        # Would need to track static calls to facade classes
        # and resolve them to their underlying services
        pass
    
    def _analyze_blade_templates(self) -> None:
        """Analyze Blade template relationships"""
        views_path = self.project_root / 'resources' / 'views'
        
        if not views_path.exists():
            return
        
        logger.info("Analyzing Blade templates...")
        
        for blade_file in views_path.glob('**/*.blade.php'):
            # Would need to parse Blade syntax for:
            # - @extends relationships
            # - @include relationships
            # - Component usage
            pass
    
    def _analyze_migrations(self) -> None:
        """Analyze database migrations"""
        migrations_path = self.project_root / 'database' / 'migrations'
        
        if not migrations_path.exists():
            return
        
        logger.info("Analyzing migrations...")
        
        for migration_file in migrations_path.glob('*.php'):
            symbols = self.symbol_table.get_symbols_in_file(str(migration_file))
            
            for symbol in symbols:
                if symbol.type == SymbolType.CLASS:
                    self._add_framework_metadata(
                        symbol.id,
                        'laravel_type',
                        'migration'
                    )
                    
                    # Analyze up/down methods for table operations
                    methods = self.symbol_table.get_children(symbol.id)
                    for method in methods:
                        if method.name in ['up', 'down']:
                            # Would parse Schema:: calls to understand
                            # table creation/modification
                            pass
    
    def _analyze_service_bindings(self, register_method: Symbol) -> None:
        """Analyze service container bindings in a register method"""
        # Would need to parse the method body for:
        # - $this->app->bind()
        # - $this->app->singleton()
        # - $this->app->instance()
        pass
    
    def _analyze_boot_operations(self, boot_method: Symbol) -> None:
        """Analyze boot operations in a service provider"""
        # Would parse for:
        # - Route model binding
        # - View composers
        # - Event listeners
        pass
    
    def _add_route_edge(self, path: str, http_method: str, 
                       controller_id: str, method_id: str, file_path: str) -> None:
        """Add a route relationship"""
        # Create a virtual node for the route
        route_id = f"route_{http_method}_{path}".replace('/', '_')
        
        route_symbol = Symbol(
            id=route_id,
            name=f"{http_method} {path}",
            type=SymbolType.CONSTANT,  # Use constant type for routes
            file_path=file_path,
            line_number=0,
            column_number=0,
            metadata={
                'laravel_type': 'route',
                'http_method': http_method,
                'path': path
            }
        )
        
        self.symbol_table.add_symbol(route_symbol)
        
        # Add edges
        self.symbol_table.add_reference(
            source_id=route_id,
            target_id=controller_id,
            reference_type='ROUTES_TO_CONTROLLER',
            line=0,
            column=0,
            context=f"Route {http_method} {path} to controller"
        )
        
        self.symbol_table.add_reference(
            source_id=route_id,
            target_id=method_id,
            reference_type='ROUTES_TO_METHOD',
            line=0,
            column=0,
            context=f"Route {http_method} {path} to method"
        )
    
    def _add_model_relationship(self, source_model_id: str, 
                               relationship_type: str, method_id: str) -> None:
        """Add a model relationship edge"""
        self.symbol_table.add_reference(
            source_id=source_model_id,
            target_id=method_id,
            reference_type=f'HAS_RELATIONSHIP_{relationship_type.upper()}',
            line=0,
            column=0,
            context=f"Eloquent relationship: {relationship_type}"
        )
    
    def _add_framework_metadata(self, symbol_id: str, key: str, value: str) -> None:
        """Add framework-specific metadata to a symbol"""
        # Would update the symbol's metadata field
        # For now, we'll track it separately
        pass
    
    def _resolve_class(self, class_name: str) -> Optional[Symbol]:
        """Resolve a class name to a symbol"""
        # Simple resolution - would need proper namespace handling
        return self.symbol_table.resolve(class_name, "", {})