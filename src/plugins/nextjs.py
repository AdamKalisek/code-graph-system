"""Next.js / TypeScript plugin leveraging the shared TypeScript analyzer."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

from os import walk as os_walk

from src.core.symbol_table import Symbol, SymbolTable, SymbolType
from src.pipeline.typescript import ModuleAnalysis, TypeScriptAnalyzer
from src.plugins.base import PipelinePlugin, PluginContext

logger = logging.getLogger(__name__)


class NextJsPlugin(PipelinePlugin):
    name = "nextjs"

    def __init__(self) -> None:
        self._analyzer = TypeScriptAnalyzer()

    # ------------------------------------------------------------------
    # Plugin lifecycle
    # ------------------------------------------------------------------

    def before_collect(self, context: PluginContext) -> None:
        logger.debug("NextJsPlugin before_collect for %s", context.project_root)

    def after_collect(self, context: PluginContext) -> None:
        logger.debug("NextJsPlugin after_collect scanning TypeScript sources")

        project_root = context.project_root
        symbol_table = context.symbol_table

        ts_files = 0
        component_count = 0
        api_route_count = 0
        interface_count = 0
        type_alias_count = 0
        imports_total = 0
        exports_total = 0
        relationships_total = 0

        files = list(self._discover_ts_files(project_root))
        for ts_path in files:
            analysis = self._analyzer.analyze(ts_path, project_root)
            if analysis is None:
                continue

            ts_files += 1
            component_count += self._count_components(analysis)
            api_route_count += len(analysis.api_routes)
            interface_count += len(analysis.interfaces)
            type_alias_count += len(analysis.type_aliases)
            imports_total += len(analysis.imports)
            exports_total += self._estimate_exports(analysis)

            relationships_total += self._materialize(symbol_table, analysis)

        symbol_table.conn.commit()

        stats = context.stats
        stats["next_ts_files"] = ts_files
        stats["next_react_components"] = component_count
        stats["next_api_routes"] = api_route_count
        stats["next_ts_interfaces"] = interface_count
        stats["next_ts_type_aliases"] = type_alias_count
        stats["next_module_imports"] = imports_total
        stats["next_module_exports"] = exports_total
        stats["next_ts_relationships"] = relationships_total

    def after_resolve(self, context: PluginContext) -> None:
        logger.debug("NextJsPlugin after_resolve noop for %s", context.project_root)

    # ------------------------------------------------------------------
    # Core persistence logic
    # ------------------------------------------------------------------

    def _materialize(self, symbol_table: SymbolTable, analysis: ModuleAnalysis) -> int:
        relationships = 0
        file_id = self._file_symbol_id(analysis.path)

        imports_by_local: Dict[str, str] = {}
        interfaces_by_name: Dict[str, str] = {}
        types_by_name: Dict[str, str] = {}
        classes_by_name: Dict[str, str] = {}
        functions_by_name: Dict[str, str] = {}
        components_by_name: Dict[str, str] = {}
        jsx_symbol_cache: Dict[Tuple[str, str], str] = {}
        prop_symbol_cache: Dict[Tuple[str, str], str] = {}
        state_symbol_cache: Dict[Tuple[str, str], str] = {}
        synthetic_types: Dict[str, str] = {}

        # Imports --------------------------------------------------------
        for imp in analysis.imports:
            key = imp.local_name or imp.imported_name or imp.module
            symbol_id = self._make_symbol_id(
                "import",
                analysis.path,
                key,
                imp.location.line,
                imp.location.column,
            )
            metadata = {
                "module": imp.module,
                "import_kind": imp.kind,
                "imported_name": imp.imported_name,
                "local_name": imp.local_name,
                "is_type_only": imp.is_type_only,
            }
            symbol_table.add_symbol(
                Symbol(
                    id=symbol_id,
                    name=key,
                    type=SymbolType.IMPORT,
                    file_path=str(analysis.path),
                    line_number=imp.location.line,
                    column_number=imp.location.column,
                    metadata=metadata,
                )
            )
            relationships += self._add_reference(
                symbol_table,
                source_id=file_id,
                target_id=symbol_id,
                reference_type="IMPORTS",
                line=imp.location.line,
                column=imp.location.column,
                context=f"imports {imp.module}",
            )
            if imp.local_name:
                imports_by_local.setdefault(imp.local_name, symbol_id)

        # Interfaces -----------------------------------------------------
        for interface in analysis.interfaces:
            symbol_id = self._make_symbol_id(
                "interface",
                analysis.path,
                interface.name,
                interface.location.line,
                interface.location.column,
            )
            metadata = {
                "export_type": interface.export_type,
                "extends": interface.extends,
                "members": interface.members,
                "module_is_client": analysis.is_client_module,
            }
            symbol_table.add_symbol(
                Symbol(
                    id=symbol_id,
                    name=interface.name,
                    type=SymbolType.TS_INTERFACE,
                    file_path=str(analysis.path),
                    line_number=interface.location.line,
                    column_number=interface.location.column,
                    metadata=metadata,
                )
            )
            interfaces_by_name[interface.name] = symbol_id
            relationships += self._add_export_reference(
                symbol_table,
                file_id,
                symbol_id,
                interface.location.line,
                interface.location.column,
                interface.export_type,
                label=f"interface {interface.name}",
            )

        # Type aliases ---------------------------------------------------
        for alias in analysis.type_aliases:
            symbol_id = self._make_symbol_id(
                "type",
                analysis.path,
                alias.name,
                alias.location.line,
                alias.location.column,
            )
            metadata = {
                "export_type": alias.export_type,
                "type_value": alias.value,
                "module_is_client": analysis.is_client_module,
            }
            symbol_table.add_symbol(
                Symbol(
                    id=symbol_id,
                    name=alias.name,
                    type=SymbolType.TS_TYPE,
                    file_path=str(analysis.path),
                    line_number=alias.location.line,
                    column_number=alias.location.column,
                    metadata=metadata,
                )
            )
            types_by_name[alias.name] = symbol_id
            relationships += self._add_export_reference(
                symbol_table,
                file_id,
                symbol_id,
                alias.location.line,
                alias.location.column,
                alias.export_type,
                label=f"type {alias.name}",
            )

        # Classes --------------------------------------------------------
        for cls in analysis.classes:
            symbol_id = self._make_symbol_id(
                "class",
                analysis.path,
                cls.name,
                cls.location.line,
                cls.location.column,
            )
            metadata = {
                "export_type": cls.export_type,
                "extends": cls.extends,
                "implements": cls.implements,
                "react_component": cls.is_component,
                "renders": [render.name for render in cls.jsx],
                "module_is_client": analysis.is_client_module,
            }
            symbol_table.add_symbol(
                Symbol(
                    id=symbol_id,
                    name=cls.name,
                    type=SymbolType.TS_CLASS,
                    file_path=str(analysis.path),
                    line_number=cls.location.line,
                    column_number=cls.location.column,
                    metadata=metadata,
                )
            )
            classes_by_name[cls.name] = symbol_id
            if cls.is_component:
                components_by_name.setdefault(cls.name, symbol_id)
            relationships += self._add_export_reference(
                symbol_table,
                file_id,
                symbol_id,
                cls.location.line,
                cls.location.column,
                cls.export_type,
                label=f"class {cls.name}",
            )

        # Functions / components ----------------------------------------
        for func in analysis.functions:
            prefix = "component" if func.is_component else "function"
            symbol_id = self._make_symbol_id(
                prefix,
                analysis.path,
                func.name,
                func.location.line,
                func.location.column,
            )
            symbol_type = SymbolType.REACT_COMPONENT if func.is_component else SymbolType.TS_FUNCTION
            metadata = {
                "export_type": func.export_type,
                "is_default_export": func.is_default_export,
                "is_async": func.is_async,
                "is_generator": func.is_generator,
                "hooks": [hook.name for hook in func.hooks],
                "calls": [call.name for call in func.calls],
                "props_type": func.props_type,
                "props": [prop.name for prop in func.props],
                "state": [state.name for state in func.state],
                "renders": [render.name for render in func.jsx],
                "component_kind": func.component_kind,
                "module_is_client": analysis.is_client_module,
            }
            if func.metadata:
                metadata.update(func.metadata)
            symbol_table.add_symbol(
                Symbol(
                    id=symbol_id,
                    name=func.name,
                    type=symbol_type,
                    file_path=str(analysis.path),
                    line_number=func.location.line,
                    column_number=func.location.column,
                    return_type=func.return_type,
                    metadata=metadata,
                )
            )
            functions_by_name[func.name] = symbol_id
            if func.is_component:
                components_by_name.setdefault(func.name, symbol_id)
            relationships += self._add_export_reference(
                symbol_table,
                file_id,
                symbol_id,
                func.location.line,
                func.location.column,
                func.export_type,
                label=f"function {func.name}",
            )

        # API routes -----------------------------------------------------
        for route in analysis.api_routes:
            symbol_id = self._make_symbol_id(
                "api_route",
                analysis.path,
                route.handler_name,
                route.location.line,
                route.location.column,
            )
            metadata = {
                "http_method": route.method,
                "export_type": route.export_type,
                "is_async": route.is_async,
                "route_path": route.route_path,
            }
            symbol_table.add_symbol(
                Symbol(
                    id=symbol_id,
                    name=route.handler_name,
                    type=SymbolType.API_ROUTE,
                    file_path=str(analysis.path),
                    line_number=route.location.line,
                    column_number=route.location.column,
                    metadata=metadata,
                )
            )
            relationships += self._add_export_reference(
                symbol_table,
                file_id,
                symbol_id,
                route.location.line,
                route.location.column,
                route.export_type,
                label=f"api route {route.method}",
            )

        # Relationships --------------------------------------------------
        relationships += self._link_class_relationships(
            symbol_table,
            analysis,
            classes_by_name,
            interfaces_by_name,
            imports_by_local,
            functions_by_name,
            components_by_name,
            jsx_symbol_cache,
        )
        relationships += self._link_interface_relationships(
            symbol_table,
            analysis,
            file_id,
            interfaces_by_name,
            imports_by_local,
        )
        relationships += self._link_function_relationships(
            symbol_table,
            analysis,
            functions_by_name,
            components_by_name,
            classes_by_name,
            interfaces_by_name,
            types_by_name,
            imports_by_local,
            jsx_symbol_cache,
            prop_symbol_cache,
            state_symbol_cache,
            synthetic_types,
        )
        relationships += self._handle_export_clauses(
            symbol_table,
            analysis,
            file_id,
            functions_by_name,
            components_by_name,
            classes_by_name,
            interfaces_by_name,
            types_by_name,
            imports_by_local,
        )

        return relationships

    # ------------------------------------------------------------------
    # Relationship helpers
    # ------------------------------------------------------------------

    def _link_function_relationships(
        self,
        symbol_table: SymbolTable,
        analysis: ModuleAnalysis,
        functions_by_name: Dict[str, str],
        components_by_name: Dict[str, str],
        classes_by_name: Dict[str, str],
        interfaces_by_name: Dict[str, str],
        types_by_name: Dict[str, str],
        imports_by_local: Dict[str, str],
        jsx_symbol_cache: Dict[Tuple[str, str], str],
        prop_symbol_cache: Dict[Tuple[str, str], str],
        state_symbol_cache: Dict[Tuple[str, str], str],
        synthetic_types: Dict[str, str],
    ) -> int:
        relationships = 0

        def resolve_target(name: str, *maps: Dict[str, str]) -> Optional[str]:
            for mapping in maps:
                if name in mapping:
                    return mapping[name]
            return None

        for func in analysis.functions:
            source_id = functions_by_name.get(func.name)
            if not source_id:
                continue

            # CALLS relationships
            for call in func.calls:
                target_id = resolve_target(
                    call.name,
                    functions_by_name,
                    components_by_name,
                    classes_by_name,
                    imports_by_local,
                )
                if target_id:
                    relationships += self._add_reference(
                        symbol_table,
                        source_id,
                        target_id,
                        "CALLS",
                        call.location.line,
                        call.location.column,
                        context=f"{func.name} calls {call.name}",
                    )

            # Component-specific relationships
            if func.is_component:
                relationships += self._link_component_renderings(
                    symbol_table,
                    source_id,
                    func.name,
                    func.jsx,
                    analysis,
                    functions_by_name,
                    components_by_name,
                    classes_by_name,
                    imports_by_local,
                    jsx_symbol_cache,
                )
                relationships += self._link_props(
                    symbol_table,
                    source_id,
                    func,
                    analysis,
                    interfaces_by_name,
                    types_by_name,
                    imports_by_local,
                    prop_symbol_cache,
                )
                relationships += self._link_state(
                    symbol_table,
                    source_id,
                    func,
                    analysis,
                    state_symbol_cache,
                )

            # RETURN type relationships
            if func.return_type:
                target_id = resolve_target(
                    func.return_type,
                    types_by_name,
                    interfaces_by_name,
                    imports_by_local,
                )
                if target_id is None:
                    target_id = synthetic_types.get(func.return_type)
                    if target_id is None:
                        target_id = self._make_symbol_id(
                            "return_type",
                            analysis.path,
                            f"{func.name}:{func.return_type}",
                            func.location.line,
                            func.location.column,
                        )
                        symbol_table.add_symbol(
                            Symbol(
                                id=target_id,
                                name=func.return_type,
                                type=SymbolType.TS_TYPE,
                                file_path=str(analysis.path),
                                line_number=func.location.line,
                                column_number=func.location.column,
                                metadata={
                                    "synthetic": True,
                                    "kind": "return",
                                    "origin": func.name,
                                },
                            )
                        )
                        synthetic_types[func.return_type] = target_id
                relationships += self._add_reference(
                    symbol_table,
                    source_id,
                    target_id,
                    "RETURNS",
                    func.location.line,
                    func.location.column,
                    context=f"{func.name} returns {func.return_type}",
                )

        return relationships

    def _link_class_relationships(
        self,
        symbol_table: SymbolTable,
        analysis: ModuleAnalysis,
        classes_by_name: Dict[str, str],
        interfaces_by_name: Dict[str, str],
        imports_by_local: Dict[str, str],
        functions_by_name: Dict[str, str],
        components_by_name: Dict[str, str],
        jsx_symbol_cache: Dict[Tuple[str, str], str],
    ) -> int:
        relationships = 0

        def resolve(name: str) -> Optional[str]:
            return (
                classes_by_name.get(name)
                or interfaces_by_name.get(name)
                or imports_by_local.get(name)
            )

        for cls in analysis.classes:
            source_id = classes_by_name.get(cls.name)
            if not source_id:
                continue

            for base in cls.extends:
                target_id = resolve(base)
                if target_id:
                    relationships += self._add_reference(
                        symbol_table,
                        source_id,
                        target_id,
                        "EXTENDS",
                        cls.location.line,
                        cls.location.column,
                        context=f"{cls.name} extends {base}",
                    )

            for iface in cls.implements:
                target_id = interfaces_by_name.get(iface) or imports_by_local.get(iface)
                if target_id:
                    relationships += self._add_reference(
                        symbol_table,
                        source_id,
                        target_id,
                        "IMPLEMENTS",
                        cls.location.line,
                        cls.location.column,
                        context=f"{cls.name} implements {iface}",
                    )

            if cls.is_component:
                relationships += self._link_component_renderings(
                    symbol_table,
                    source_id,
                    cls.name,
                    cls.jsx,
                    analysis,
                    functions_by_name,
                    components_by_name,
                    classes_by_name,
                    imports_by_local,
                    jsx_symbol_cache,
                )

        return relationships

    def _link_interface_relationships(
        self,
        symbol_table: SymbolTable,
        analysis: ModuleAnalysis,
        file_id: str,
        interfaces_by_name: Dict[str, str],
        imports_by_local: Dict[str, str],
    ) -> int:
        relationships = 0
        for interface in analysis.interfaces:
            source_id = interfaces_by_name.get(interface.name)
            if not source_id:
                continue
            for base in interface.extends:
                target_id = interfaces_by_name.get(base) or imports_by_local.get(base)
                if target_id:
                    relationships += self._add_reference(
                        symbol_table,
                        source_id,
                        target_id,
                        "EXTENDS",
                        interface.location.line,
                        interface.location.column,
                        context=f"{interface.name} extends {base}",
                    )
        return relationships

    def _link_component_renderings(
        self,
        symbol_table: SymbolTable,
        source_id: str,
        component_name: str,
        jsx_elements,
        analysis: ModuleAnalysis,
        functions_by_name: Dict[str, str],
        components_by_name: Dict[str, str],
        classes_by_name: Dict[str, str],
        imports_by_local: Dict[str, str],
        jsx_symbol_cache: Dict[Tuple[str, str], str],
    ) -> int:
        relationships = 0

        def resolve(name: str) -> Optional[str]:
            return (
                functions_by_name.get(name)
                or components_by_name.get(name)
                or classes_by_name.get(name)
                or imports_by_local.get(name)
            )

        for render in jsx_elements:
            if render.is_component:
                target_id = resolve(render.name)
                if target_id:
                    relationships += self._add_reference(
                        symbol_table,
                        source_id,
                        target_id,
                        "USES",
                        render.location.line,
                        render.location.column,
                        context=f"{component_name} uses {render.name}",
                    )
            jsx_key = (component_name, render.name)
            jsx_symbol = jsx_symbol_cache.get(jsx_key)
            if jsx_symbol is None:
                jsx_symbol = self._make_symbol_id(
                    "jsx",
                    analysis.path,
                    f"{component_name}:{render.name}",
                    render.location.line,
                    render.location.column,
                )
                symbol_table.add_symbol(
                    Symbol(
                        id=jsx_symbol,
                        name=render.name,
                        type=SymbolType.JSX_ELEMENT,
                        file_path=str(analysis.path),
                        line_number=render.location.line,
                        column_number=render.location.column,
                        metadata={
                            "component": component_name,
                            "is_component": render.is_component,
                        },
                    )
                )
                jsx_symbol_cache[jsx_key] = jsx_symbol
            relationships += self._add_reference(
                symbol_table,
                source_id,
                jsx_symbol,
                "RENDERS",
                render.location.line,
                render.location.column,
                context=f"{component_name} renders {render.name}",
            )

        return relationships

    def _link_props(
        self,
        symbol_table: SymbolTable,
        source_id: str,
        func,
        analysis: ModuleAnalysis,
        interfaces_by_name: Dict[str, str],
        types_by_name: Dict[str, str],
        imports_by_local: Dict[str, str],
        prop_symbol_cache: Dict[Tuple[str, str], str],
    ) -> int:
        relationships = 0

        if func.props_type:
            target_id = (
                interfaces_by_name.get(func.props_type)
                or types_by_name.get(func.props_type)
                or imports_by_local.get(func.props_type)
            )
            if target_id:
                relationships += self._add_reference(
                    symbol_table,
                    source_id,
                    target_id,
                    "HAS_PROP",
                    func.location.line,
                    func.location.column,
                    context=f"{func.name} props type {func.props_type}",
                )

        for prop in func.props:
            key = (func.name, prop.name)
            prop_symbol = prop_symbol_cache.get(key)
            if prop_symbol is None:
                prop_symbol = self._make_symbol_id(
                    "prop",
                    analysis.path,
                    f"{func.name}.{prop.name}",
                    prop.location.line,
                    prop.location.column,
                )
                symbol_table.add_symbol(
                    Symbol(
                        id=prop_symbol,
                        name=prop.name,
                        type=SymbolType.PROPERTY,
                        file_path=str(analysis.path),
                        line_number=prop.location.line,
                        column_number=prop.location.column,
                        metadata={
                            "component": func.name,
                            "type": prop.type_annotation,
                        },
                    )
                )
                prop_symbol_cache[key] = prop_symbol
            relationships += self._add_reference(
                symbol_table,
                source_id,
                prop_symbol,
                "HAS_PROP",
                prop.location.line,
                prop.location.column,
                context=f"{func.name} prop {prop.name}",
            )

        return relationships

    def _link_state(
        self,
        symbol_table: SymbolTable,
        source_id: str,
        func,
        analysis: ModuleAnalysis,
        state_symbol_cache: Dict[Tuple[str, str], str],
    ) -> int:
        relationships = 0
        for state in func.state:
            key = (func.name, state.name)
            state_symbol = state_symbol_cache.get(key)
            if state_symbol is None:
                state_symbol = self._make_symbol_id(
                    "state",
                    analysis.path,
                    f"{func.name}.{state.name}",
                    state.location.line,
                    state.location.column,
                )
                symbol_table.add_symbol(
                    Symbol(
                        id=state_symbol,
                        name=state.name,
                        type=SymbolType.VARIABLE,
                        file_path=str(analysis.path),
                        line_number=state.location.line,
                        column_number=state.location.column,
                        metadata={
                            "component": func.name,
                            "hook": state.hook,
                        },
                    )
                )
                state_symbol_cache[key] = state_symbol
            relationships += self._add_reference(
                symbol_table,
                source_id,
                state_symbol,
                "HAS_STATE",
                state.location.line,
                state.location.column,
                context=f"{func.name} state {state.name}",
            )
        return relationships

    def _handle_export_clauses(
        self,
        symbol_table: SymbolTable,
        analysis: ModuleAnalysis,
        file_id: str,
        functions_by_name: Dict[str, str],
        components_by_name: Dict[str, str],
        classes_by_name: Dict[str, str],
        interfaces_by_name: Dict[str, str],
        types_by_name: Dict[str, str],
        imports_by_local: Dict[str, str],
    ) -> int:
        relationships = 0

        def resolve(name: str) -> Optional[str]:
            return (
                functions_by_name.get(name)
                or components_by_name.get(name)
                or classes_by_name.get(name)
                or interfaces_by_name.get(name)
                or types_by_name.get(name)
                or imports_by_local.get(name)
            )

        for export in analysis.exports:
            export_name = export.alias or export.name or (
                "*" if export.export_type == "all_from" else export.source_module or "default"
            )
            symbol_id = self._make_symbol_id(
                "export",
                analysis.path,
                export_name,
                export.location.line,
                export.location.column,
            )
            metadata = {
                "export_type": export.export_type,
                "source_module": export.source_module,
                "alias": export.alias,
            }
            symbol_table.add_symbol(
                Symbol(
                    id=symbol_id,
                    name=export_name,
                    type=SymbolType.VARIABLE,
                    file_path=str(analysis.path),
                    line_number=export.location.line,
                    column_number=export.location.column,
                    metadata=metadata,
                )
            )
            relationships += self._add_reference(
                symbol_table,
                file_id,
                symbol_id,
                "EXPORTS",
                export.location.line,
                export.location.column,
                context="module export",
            )
            if export.name:
                target_id = resolve(export.name)
                if target_id:
                    relationships += self._add_reference(
                        symbol_table,
                        symbol_id,
                        target_id,
                        "EXPORTS",
                        export.location.line,
                        export.location.column,
                        context="re-exports symbol",
                    )
        return relationships

    # ------------------------------------------------------------------
    # Discovery helpers
    # ------------------------------------------------------------------

    def _discover_ts_files(self, root: Path) -> Iterable[Path]:
        exts = {".ts", ".tsx"}
        skip_dirs = {"node_modules", ".next", "dist", "build", "out"}
        for current_root, dirs, files in os_walk(root):
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
            for filename in files:
                if Path(filename).suffix.lower() in exts:
                    yield Path(current_root) / filename

    # ------------------------------------------------------------------
    # Small utilities
    # ------------------------------------------------------------------

    def _count_components(self, analysis: ModuleAnalysis) -> int:
        function_components = sum(1 for func in analysis.functions if func.is_component)
        class_components = sum(1 for cls in analysis.classes if cls.is_component)
        return function_components + class_components

    def _estimate_exports(self, analysis: ModuleAnalysis) -> int:
        direct = sum(
            1
            for seq in (
                analysis.functions,
                analysis.classes,
                analysis.interfaces,
                analysis.type_aliases,
                analysis.api_routes,
            )
            for item in seq
            if getattr(item, "export_type", None)
        )
        return direct + len(analysis.exports)

    def _add_export_reference(
        self,
        symbol_table: SymbolTable,
        file_id: str,
        target_id: str,
        line: int,
        column: int,
        export_type: Optional[str],
        *,
        label: str,
    ) -> int:
        if not export_type:
            return 0
        context = f"{label} ({export_type})"
        return self._add_reference(
            symbol_table,
            source_id=file_id,
            target_id=target_id,
            reference_type="EXPORTS",
            line=line,
            column=column,
            context=context,
        )

    def _add_reference(
        self,
        symbol_table: SymbolTable,
        source_id: str,
        target_id: str,
        reference_type: str,
        line: int,
        column: int,
        *,
        context: str,
    ) -> int:
        symbol_table.add_reference(
            source_id=source_id,
            target_id=target_id,
            reference_type=reference_type,
            line=line,
            column=column,
            context=context,
        )
        return 1

    @staticmethod
    def _make_symbol_id(prefix: str, path: Path, name: str, line: int, column: int) -> str:
        raw = f"{path}:{name}:{line}:{column}:{prefix}".encode()
        return f"next_{prefix}_{hashlib.md5(raw).hexdigest()}"

    @staticmethod
    def _file_symbol_id(path: Path) -> str:
        return f"file_{hashlib.md5(str(path).encode()).hexdigest()}"
