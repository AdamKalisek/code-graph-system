"""TypeScript/TSX structural analysis helpers for Next.js parsing."""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from ctypes import c_void_p, cdll

from tree_sitter import Language, Node, Parser
import tree_sitter_languages

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data containers exposed to plugins
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Location:
    """Concrete source location (1-based line/column)."""

    line: int
    column: int


@dataclass(frozen=True)
class ImportEntry:
    local_name: Optional[str]
    imported_name: Optional[str]
    module: str
    kind: str  # default | named | namespace | side-effect
    is_type_only: bool
    location: Location


@dataclass(frozen=True)
class ExportEntry:
    name: Optional[str]
    export_type: str  # default | named | all_from | from
    source_module: Optional[str]
    alias: Optional[str]
    location: Location


@dataclass(frozen=True)
class JSXRender:
    name: str
    location: Location
    is_component: bool


@dataclass(frozen=True)
class CallSite:
    name: str
    location: Location


@dataclass(frozen=True)
class HookUsage:
    name: str
    location: Location


@dataclass(frozen=True)
class ComponentState:
    name: str
    hook: str
    location: Location


@dataclass(frozen=True)
class ComponentProp:
    name: str
    type_annotation: Optional[str]
    location: Location


@dataclass
class TSFunction:
    name: str
    location: Location
    export_type: Optional[str]
    is_default_export: bool
    is_async: bool
    is_generator: bool
    return_type: Optional[str]
    calls: List[CallSite] = field(default_factory=list)
    hooks: List[HookUsage] = field(default_factory=list)
    jsx: List[JSXRender] = field(default_factory=list)
    props_type: Optional[str] = None
    props: List[ComponentProp] = field(default_factory=list)
    state: List[ComponentState] = field(default_factory=list)
    is_component: bool = False
    component_kind: Optional[str] = None  # function | arrow | class_method
    metadata: Dict[str, object] = field(default_factory=dict)


@dataclass
class TSClass:
    name: str
    location: Location
    export_type: Optional[str]
    is_default_export: bool
    extends: List[str] = field(default_factory=list)
    implements: List[str] = field(default_factory=list)
    is_component: bool = False
    jsx: List[JSXRender] = field(default_factory=list)


@dataclass
class TSInterface:
    name: str
    location: Location
    export_type: Optional[str]
    extends: List[str] = field(default_factory=list)
    members: List[str] = field(default_factory=list)


@dataclass
class TSTypeAlias:
    name: str
    location: Location
    export_type: Optional[str]
    value: str


@dataclass
class APIRoute:
    method: str
    handler_name: str
    location: Location
    export_type: Optional[str]
    is_async: bool
    route_path: Optional[str]


@dataclass
class ModuleAnalysis:
    path: Path
    imports: List[ImportEntry]
    exports: List[ExportEntry]
    functions: List[TSFunction]
    classes: List[TSClass]
    interfaces: List[TSInterface]
    type_aliases: List[TSTypeAlias]
    api_routes: List[APIRoute]
    is_client_module: bool
    route_path: Optional[str]


# ---------------------------------------------------------------------------
# Tree-sitter helpers
# ---------------------------------------------------------------------------


class _TreeSitterLoader:
    """Lazily loads TypeScript/TSX grammars from the bundled languages."""

    def __init__(self) -> None:
        package_dir = Path(tree_sitter_languages.__file__).resolve().parent
        self._library_path = package_dir / "languages.so"
        self._lib = cdll.LoadLibrary(str(self._library_path))
        self._languages: Dict[str, Language] = {}
        self._parsers: Dict[str, Parser] = {}

    def parser_for_suffix(self, suffix: str) -> Optional[Parser]:
        lang_key = "tsx" if suffix.lower() in {".tsx", ".jsx"} else "typescript"
        if lang_key not in {"typescript", "tsx"}:
            return None
        if lang_key not in self._parsers:
            parser = Parser()
            parser.language = self._language(lang_key)
            self._parsers[lang_key] = parser
        return self._parsers[lang_key]

    def _language(self, name: str) -> Language:
        if name not in self._languages:
            func = getattr(self._lib, f"tree_sitter_{name}")
            func.restype = c_void_p
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message="int argument support is deprecated",
                    category=DeprecationWarning,
                )
                pointer = func()
            self._languages[name] = Language(pointer)  # type: ignore[arg-type]
        return self._languages[name]


# ---------------------------------------------------------------------------
# High-level analyzer
# ---------------------------------------------------------------------------


class TypeScriptAnalyzer:
    """Produces a structured module analysis for TypeScript / TSX sources."""

    _HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}

    def __init__(self) -> None:
        self._loader = _TreeSitterLoader()
        self._source: bytes = b""
        self._path: Path = Path()
        self._project_root: Path = Path()
        self._analysis: Optional[ModuleAnalysis] = None
        self._is_api_route_file: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, path: Path, project_root: Path) -> Optional[ModuleAnalysis]:
        parser = self._loader.parser_for_suffix(path.suffix)
        if parser is None:
            logger.debug("Skipping non-TypeScript file: %s", path)
            return None

        try:
            source = path.read_bytes()
        except OSError as exc:  # pragma: no cover - filesystem errors
            logger.warning("Unable to read %s: %s", path, exc)
            return None

        tree = parser.parse(source)
        self._source = source
        self._path = path
        self._project_root = project_root

        route_path = self._compute_route_path(path, project_root)
        analysis = ModuleAnalysis(
            path=path,
            imports=[],
            exports=[],
            functions=[],
            classes=[],
            interfaces=[],
            type_aliases=[],
            api_routes=[],
            is_client_module=False,
            route_path=route_path,
        )
        self._analysis = analysis
        self._is_api_route_file = self._detect_api_route(path, project_root)

        if tree.root_node is None:
            return analysis

        analysis.is_client_module = self._detect_use_client(tree.root_node)
        self._walk(tree.root_node, export_ctx=None)
        return analysis

    # ------------------------------------------------------------------
    # Traversal
    # ------------------------------------------------------------------

    def _walk(self, node: Node, export_ctx: Optional[str]) -> None:
        if node.type == "import_statement":
            self._handle_import(node)
            return

        if node.type == "export_statement":
            ctx = self._extract_export_context(node)
            declaration = node.child_by_field_name("declaration")
            if declaration is not None:
                self._walk(declaration, ctx)
            else:
                self._handle_export_clause(node, ctx)
            return

        handler = {
            "function_declaration": self._handle_function_declaration,
            "class_declaration": self._handle_class_declaration,
            "interface_declaration": self._handle_interface_declaration,
            "type_alias_declaration": self._handle_type_alias_declaration,
            "lexical_declaration": self._handle_lexical_declaration,
        }.get(node.type)

        if handler:
            handler(node, export_ctx)
            return

        for child in node.children:
            self._walk(child, None)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _handle_import(self, node: Node) -> None:
        module_node = node.child_by_field_name("source")
        module_text = self._text(module_node) if module_node else ""
        module = module_text.strip('"\'')
        is_type_only = any(child.type == "type" for child in node.children)
        clause = next((child for child in node.children if child.type == "import_clause"), None)

        if clause is None:
            self._analysis.imports.append(
                ImportEntry(
                    local_name=None,
                    imported_name=None,
                    module=module,
                    kind="side-effect",
                    is_type_only=is_type_only,
                    location=self._loc(node),
                )
            )
            return

        for child in clause.named_children:
            if child.type == "named_imports":
                for spec in child.named_children:
                    name_node = spec.child_by_field_name("name")
                    alias_node = spec.child_by_field_name("alias")
                    imported = self._text(name_node) if name_node else None
                    local = self._text(alias_node) if alias_node else imported
                    self._analysis.imports.append(
                        ImportEntry(
                            local_name=local,
                            imported_name=imported,
                            module=module,
                            kind="named",
                            is_type_only=is_type_only,
                            location=self._loc(spec),
                        )
                    )
            elif child.type == "identifier":
                self._analysis.imports.append(
                    ImportEntry(
                        local_name=self._text(child),
                        imported_name="default",
                        module=module,
                        kind="default",
                        is_type_only=is_type_only,
                        location=self._loc(child),
                    )
                )
            elif child.type == "namespace_import":
                alias_node = child.child_by_field_name("name") or child.child_by_field_name("alias")
                alias = self._text(alias_node) if alias_node else "*"
                self._analysis.imports.append(
                    ImportEntry(
                        local_name=alias,
                        imported_name="*",
                        module=module,
                        kind="namespace",
                        is_type_only=is_type_only,
                        location=self._loc(child),
                    )
                )

    def _handle_export_clause(self, node: Node, export_ctx: Optional[str]) -> None:
        clause = next((child for child in node.children if child.type == "export_clause"), None)
        source_node = node.child_by_field_name("source")
        source_module = self._text(source_node).strip('"\'') if source_node else None

        if any(child.type == "*" for child in node.children):
            self._analysis.exports.append(
                ExportEntry(
                    name=None,
                    export_type="all_from",
                    source_module=source_module,
                    alias=None,
                    location=self._loc(node),
                )
            )
            return

        if clause is None:
            return

        for spec in clause.named_children:
            name_node = spec.child_by_field_name("name")
            alias_node = spec.child_by_field_name("alias")
            self._analysis.exports.append(
                ExportEntry(
                    name=self._text(name_node) if name_node else None,
                    export_type="from" if source_module else "named",
                    source_module=source_module,
                    alias=self._text(alias_node) if alias_node else None,
                    location=self._loc(spec),
                )
            )

    def _handle_function_declaration(self, node: Node, export_ctx: Optional[str]) -> None:
        if not self._is_top_level(node):
            return

        name_node = node.child_by_field_name("name")
        if name_node is None:
            return

        func = self._build_function(node, name=self._text(name_node), kind="function", export_ctx=export_ctx)

        if func:
            self._analysis.functions.append(func)
            self._register_api_route(func.name, func.location, func.export_type, func.is_async)

    def _handle_class_declaration(self, node: Node, export_ctx: Optional[str]) -> None:
        if not self._is_top_level(node):
            return

        name_node = node.child_by_field_name("name") or node.child_by_field_name("identifier")
        if name_node is None:
            return

        class_info = TSClass(
            name=self._text(name_node),
            location=self._loc(node),
            export_type=export_ctx,
            is_default_export=export_ctx == "default",
        )

        heritage = node.child_by_field_name("heritage") or next(
            (child for child in node.children if child.type == "class_heritage"),
            None,
        )
        if heritage:
            for child in heritage.named_children:
                if child.type == "extends_clause":
                    class_info.extends.extend(self._extract_identifier_list(child))
                elif child.type == "implements_clause":
                    class_info.implements.extend(self._extract_identifier_list(child))

        class_body = node.child_by_field_name("body")
        if class_body:
            class_info.jsx = self._collect_jsx_usages(class_body)
            class_info.is_component = any(
                name.startswith("React.Component") or name.endswith("Component")
                for name in class_info.extends
            ) or self._contains_jsx(class_body)

        self._analysis.classes.append(class_info)

    def _handle_interface_declaration(self, node: Node, export_ctx: Optional[str]) -> None:
        if not self._is_top_level(node):
            return
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return

        interface = TSInterface(
            name=self._text(name_node),
            location=self._loc(node),
            export_type=export_ctx,
        )

        for child in node.children:
            if child.type == "extends_clause" or child.type == "extends_type_clause":
                interface.extends.extend(self._extract_identifier_list(child))
            elif child.type == "object_type":
                for member in child.named_children:
                    member_name = member.child_by_field_name("name")
                    if member_name:
                        interface.members.append(self._text(member_name))

        self._analysis.interfaces.append(interface)

    def _handle_type_alias_declaration(self, node: Node, export_ctx: Optional[str]) -> None:
        if not self._is_top_level(node):
            return
        name_node = node.child_by_field_name("name")
        value_node = node.child_by_field_name("value")
        if name_node is None or value_node is None:
            return

        self._analysis.type_aliases.append(
            TSTypeAlias(
                name=self._text(name_node),
                location=self._loc(node),
                export_type=export_ctx,
                value=self._text(value_node).strip(),
            )
        )

    def _handle_lexical_declaration(self, node: Node, export_ctx: Optional[str]) -> None:
        for child in node.named_children:
            if child.type == "variable_declarator":
                self._handle_variable_declarator(child, export_ctx)

    def _handle_variable_declarator(self, node: Node, export_ctx: Optional[str]) -> None:
        if not self._is_top_level(node):
            return

        name_node = node.child_by_field_name("name")
        value_node = node.child_by_field_name("value")
        if name_node is None or value_node is None:
            return

        name = self._text(name_node)
        if value_node.type in {"arrow_function", "function"}:
            func = self._build_function(value_node, name=name, kind=value_node.type, export_ctx=export_ctx)
            if func:
                self._analysis.functions.append(func)
                self._register_api_route(name, func.location, export_ctx, func.is_async)
            return

        if value_node.type == "call_expression":
            func = self._build_wrapped_component(value_node, name=name, export_ctx=export_ctx)
            if func:
                self._analysis.functions.append(func)
                self._register_api_route(name, func.location, export_ctx, func.is_async)
                return
            self._register_api_route(name, self._loc(node), export_ctx, self._is_async_function_like(value_node))

    # ------------------------------------------------------------------
    # Builders
    # ------------------------------------------------------------------

    def _build_function(self, node: Node, *, name: str, kind: str, export_ctx: Optional[str]) -> Optional[TSFunction]:
        body = node.child_by_field_name("body")
        if body is None:
            return None

        loc = self._loc(node)
        return_type = self._extract_return_type(node)
        calls, hooks, jsx, state = self._collect_function_body_semantics(body)
        props_type, props = self._extract_props(node)

        is_component = self._looks_like_component(name) or bool(jsx)
        if not is_component and any(hook.name.startswith("use") for hook in hooks):
            is_component = True

        component_kind = {
            "function": "function",
            "function_declaration": "function",
            "arrow_function": "arrow",
        }.get(node.type, kind)

        return TSFunction(
            name=name,
            location=loc,
            export_type=export_ctx,
            is_default_export=export_ctx == "default",
            is_async=self._has_child(node, "async"),
            is_generator=self._has_child(node, "*") or self._has_child(node, "yield"),
            return_type=return_type,
            calls=calls,
            hooks=hooks,
            jsx=jsx,
            props_type=props_type,
            props=props,
            state=state,
            is_component=is_component,
            component_kind=component_kind,
            metadata={},
        )

    def _build_wrapped_component(self, node: Node, *, name: str, export_ctx: Optional[str]) -> Optional[TSFunction]:
        function_expr = node.child_by_field_name("function")
        arguments = node.child_by_field_name("arguments")
        if arguments is None or not arguments.named_children:
            return None

        first_arg = arguments.named_children[0]
        if first_arg.type not in {"arrow_function", "function"}:
            return None

        func = self._build_function(first_arg, name=name, kind=first_arg.type, export_ctx=export_ctx)
        if func is None:
            return None

        wrapper_name = self._expression_to_string(function_expr)
        if wrapper_name:
            func.metadata["wrapped_by"] = wrapper_name
            func.component_kind = wrapper_name.split(".")[-1]
        func.is_component = True
        return func

    def _register_api_route(
        self,
        name: str,
        location: Location,
        export_ctx: Optional[str],
        is_async: bool,
    ) -> None:
        if not self._is_api_route_file:
            return
        method = name.upper()
        if method not in self._HTTP_METHODS:
            return
        self._analysis.api_routes.append(
            APIRoute(
                method=method,
                handler_name=name,
                location=location,
                export_type=export_ctx or "named",
                is_async=is_async,
                route_path=self._analysis.route_path,
            )
        )

    # ------------------------------------------------------------------
    # Extraction helpers
    # ------------------------------------------------------------------

    def _collect_function_body_semantics(
        self, body: Node
    ) -> Tuple[List[CallSite], List[HookUsage], List[JSXRender], List[ComponentState]]:
        calls: Dict[str, CallSite] = {}
        hooks: Dict[str, HookUsage] = {}
        jsx: Dict[str, JSXRender] = {}
        state: Dict[str, ComponentState] = {}

        def visit(node: Node) -> None:
            if node.type in {"function_declaration", "arrow_function", "function", "method_definition"} and node is not body:
                # Avoid descending into nested function bodies; they will be handled separately.
                return

            if node.type == "call_expression":
                function_node = node.child_by_field_name("function")
                name = self._expression_to_string(function_node)
                if name:
                    calls.setdefault(name, CallSite(name=name, location=self._loc(node)))
                    hook_name = name.split(".")[-1]
                    if hook_name.startswith("use") and len(hook_name) > 3 and hook_name[3].isupper():
                        hooks.setdefault(
                            hook_name,
                            HookUsage(name=hook_name, location=self._loc(node)),
                        )

            if node.type in {"jsx_element", "jsx_self_closing_element", "jsx_fragment"}:
                for render in self._collect_jsx_usages(node):
                    jsx.setdefault(render.name, render)

            if node.type == "lexical_declaration":
                for declarator in node.named_children:
                    if declarator.type != "variable_declarator":
                        continue
                    value = declarator.child_by_field_name("value")
                    pattern = declarator.child_by_field_name("name")
                    if value is None or pattern is None:
                        continue
                    call_name = self._expression_to_string(value.child_by_field_name("function") if value.type == "call_expression" else value)
                    if not call_name:
                        continue
                    if call_name in {"useState", "React.useState", "useReducer", "React.useReducer"}:
                        if pattern.type == "array_pattern" and pattern.named_children:
                            state_name_node = pattern.named_children[0]
                            state_name = self._text(state_name_node)
                        else:
                            state_name = self._text(pattern)
                        state.setdefault(
                            state_name,
                            ComponentState(
                                name=state_name,
                                hook=call_name.split(".")[-1],
                                location=self._loc(pattern),
                            ),
                        )

            for child in node.children:
                visit(child)

        visit(body)

        return (list(calls.values()), list(hooks.values()), list(jsx.values()), list(state.values()))

    def _collect_jsx_usages(self, node: Node) -> List[JSXRender]:
        jsx_usages: Dict[str, JSXRender] = {}

        def visit(n: Node) -> None:
            if n.type in {"jsx_opening_element", "jsx_self_closing_element"}:
                name_node = n.child_by_field_name("name")
                if name_node is None:
                    return
                name = self._jsx_name(name_node)
                is_component = bool(name) and name[0].isupper()
                if name:
                    jsx_usages.setdefault(name, JSXRender(name=name, location=self._loc(n), is_component=is_component))
            for child in n.children:
                visit(child)

        visit(node)
        return list(jsx_usages.values())

    def _extract_props(self, node: Node) -> Tuple[Optional[str], List[ComponentProp]]:
        params = node.child_by_field_name("parameters")
        if params is None:
            return None, []

        for param in params.named_children:
            param_node = param
            if param_node.type == "required_parameter":
                param_node = next((child for child in param_node.children if child.is_named), None) or param_node

            type_node = param_node.child_by_field_name("type") or param_node.child_by_field_name("type_annotation")
            props_type = None
            if type_node is not None:
                type_text = self._text(type_node)
                if type_text.startswith(":"):
                    type_text = type_text[1:].strip()
                props_type = type_text.strip()
            else:
                props_type = None

            props: List[ComponentProp] = []
            name_node = param_node.child_by_field_name("name") or param_node
            if name_node.type == "object_pattern":
                for prop in name_node.named_children:
                    if prop.type in {"pair", "shorthand_property_identifier_pattern"}:
                        identifier_node = prop.child_by_field_name("value") or prop.child_by_field_name("key") or prop
                        props.append(
                            ComponentProp(
                                name=self._text(identifier_node),
                                type_annotation=None,
                                location=self._loc(identifier_node),
                            )
                        )
            elif name_node.type == "identifier":
                props.append(
                    ComponentProp(
                        name=self._text(name_node),
                        type_annotation=props_type,
                        location=self._loc(name_node),
                    )
                )

            return props_type, props

        return None, []

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    def _extract_export_context(self, node: Node) -> Optional[str]:
        if node.type != "export_statement":
            return None
        if any(child.type == "default" for child in node.children):
            return "default"
        return "named"

    def _extract_identifier_list(self, node: Node) -> List[str]:
        identifiers: List[str] = []

        def visit(n: Node) -> None:
            if n.type in {"identifier", "type_identifier", "property_identifier"}:
                identifiers.append(self._text(n))
            for child in n.children:
                visit(child)

        visit(node)
        return identifiers

    def _extract_return_type(self, node: Node) -> Optional[str]:
        return_node = node.child_by_field_name("return_type")
        if return_node is None:
            return None
        text = self._text(return_node)
        if text.startswith(":"):
            text = text[1:].strip()
        return text.strip() or None

    def _loc(self, node: Node) -> Location:
        return Location(line=node.start_point[0] + 1, column=node.start_point[1] + 1)

    def _text(self, node: Optional[Node]) -> str:
        if node is None:
            return ""
        return self._source[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")

    def _jsx_name(self, node: Node) -> str:
        if node.type in {"identifier", "jsx_identifier", "type_identifier", "property_identifier"}:
            return self._text(node)
        if node.type == "jsx_member_expression":
            object_node = node.child_by_field_name("object")
            property_node = node.child_by_field_name("property")
            if object_node and property_node:
                return f"{self._jsx_name(object_node)}.{self._jsx_name(property_node)}"
        return self._text(node)

    def _expression_to_string(self, node: Optional[Node]) -> str:
        if node is None:
            return ""
        if node.type in {"identifier", "type_identifier", "property_identifier"}:
            return self._text(node)
        if node.type == "member_expression":
            object_node = node.child_by_field_name("object")
            property_node = node.child_by_field_name("property")
            if object_node and property_node:
                return f"{self._expression_to_string(object_node)}.{self._expression_to_string(property_node)}"
        if node.type == "call_expression":
            return self._expression_to_string(node.child_by_field_name("function"))
        return self._text(node)

    def _contains_jsx(self, node: Node) -> bool:
        found = False

        def visit(n: Node) -> None:
            nonlocal found
            if found:
                return
            if n.type in {"jsx_element", "jsx_self_closing_element", "jsx_fragment"}:
                found = True
                return
            for child in n.children:
                visit(child)

        visit(node)
        return found

    def _has_child(self, node: Node, needle: str) -> bool:
        return any(child.type == needle for child in node.children)

    def _looks_like_component(self, name: str) -> bool:
        if not name:
            return False
        if self._is_api_route_file and name.upper() in self._HTTP_METHODS:
            return False
        if len(name) <= 3 and name.isupper():
            return False
        return name[0].isupper()

    def _detect_use_client(self, root: Node) -> bool:
        for child in root.children:
            if child.type == "expression_statement":
                for expr in child.named_children:
                    if expr.type == "string" and self._text(expr).strip('"\'') == "use client":
                        return True
        return False

    def _is_top_level(self, node: Node) -> bool:
        current = node
        while current.parent is not None:
            parent = current.parent
            if parent.type == "program":
                return True
            if parent.type in {"export_statement", "lexical_declaration", "variable_declaration"}:
                current = parent
                continue
            return False
        return True

    def _is_async_function_like(self, node: Node) -> bool:
        if node is None:
            return False
        if node.type in {"function", "arrow_function"}:
            return any(child.type == "async" for child in node.children)
        if node.type == "call_expression":
            arguments = node.child_by_field_name("arguments")
            if arguments:
                return any(self._is_async_function_like(child) for child in arguments.named_children)
        return False

    def _compute_route_path(self, path: Path, project_root: Path) -> Optional[str]:
        try:
            relative = path.relative_to(project_root)
        except ValueError:
            relative = path

        parts = list(relative.parts)
        if "app" in parts:
            idx = parts.index("app")
            parts = parts[idx + 1 :]
            filtered: List[str] = []
            skip = {"page.tsx", "page.ts", "layout.tsx", "layout.ts", "route.ts", "route.tsx"}
            for segment in parts:
                if segment in skip:
                    continue
                if segment.startswith("(") and segment.endswith(")"):
                    continue
                if not filtered and segment == "api":
                    continue
                filtered.append(segment)
            if filtered:
                return "/" + "/".join(filtered).rstrip("/")
        if "pages" in parts:
            idx = parts.index("pages")
            parts = parts[idx + 1 :]
            if parts and parts[0] == "api":
                url_parts = parts[1:]
                if url_parts:
                    name = "/" + "/".join(p.rsplit(".", 1)[0] for p in url_parts)
                    return name
        return None

    def _detect_api_route(self, path: Path, project_root: Path) -> bool:
        try:
            relative = path.relative_to(project_root)
        except ValueError:
            relative = path

        parts = list(relative.parts)
        for idx, part in enumerate(parts):
            if part == "app":
                remainder = parts[idx + 1 :]
                for segment in remainder:
                    if segment.startswith("(") and segment.endswith(")"):
                        continue
                    return segment == "api"
                return False
            if part == "pages":
                remainder = parts[idx + 1 :]
                return bool(remainder and remainder[0] == "api")
        return False


__all__ = [
    "APIRoute",
    "CallSite",
    "ComponentProp",
    "ComponentState",
    "ExportEntry",
    "HookUsage",
    "ImportEntry",
    "JSXRender",
    "Location",
    "ModuleAnalysis",
    "TSClass",
    "TSFunction",
    "TSInterface",
    "TSTypeAlias",
    "TypeScriptAnalyzer",
]
