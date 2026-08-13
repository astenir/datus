# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Static import/export checks that catch React #130-style runtime failures.

React error #130 ("Element type is invalid: expected a string ... but got:
undefined") is thrown at mount time when a JSX tag resolves to ``undefined``.
The two dominant authored causes are:

* a default/named import mixup — ``import Foo from './x'`` when ``x`` only
  exports named bindings (or vice versa), so the binding is ``undefined``;
* a JSX tag identifier that was never imported or defined in its file.

``validate_render`` cannot execute the render tree, but both causes are
statically verifiable from the module sources alone. This module adds:

1. FATAL issues — default/named import specifiers that do not exist in the
   target module's export surface.
2. NON-FATAL warnings — capitalized JSX tags that are not in scope
   (imports + top-level definitions + function parameters).
3. FATAL issues — a ``style={name}`` prop where ``name`` resolves to a
   same-file function declaration or arrow-const assignment (passing the
   function itself to ``style`` throws React #62 at mount time).

The checks are deliberately conservative: ``export * from`` targets are
skipped (their surface is unknowable statically), the JSX-tag check is a
warning so heuristic misses never block a legitimate render tree, and the
style check only fires when a local function definition proves the binding
is a function.

Shared between the report and dashboard validators so the two kinds can't
drift on what counts as an import contract violation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

# Bare specifiers an authored render module is allowed to import. Keep in
# lockstep with the module map inside the iframe runtime
# (``@datus/web-artifact-render``). Importing from a bare specifier is not
# statically checkable here, so the scan skips them.
ALLOWED_BARE_MODULES: frozenset[str] = frozenset(
    {
        "react",
        "recharts",
        "lucide-react",
        "d3-format",
        "dayjs",
        "@datus/web-artifact",
    }
)

# Public export surface of the pinned ``@datus/web-artifact-render`` runtime
# (verified against the vendored 0.1.7 UMD bundle and unpkg 0.1.8). Unlike
# the other bare modules, this is the repo's own contract, so a named import
# outside this set is statically provable to be ``undefined`` at runtime and
# throws React #130 at mount — ``BlockHandle`` is the historical example:
# the system prompt advertised it while no published 0.1.x bundle exported it.
WEB_ARTIFACT_EXPORTS: frozenset[str] = frozenset(
    {
        "useDatusArtifact",
        "DatusArtifactProvider",
        "BundledQueryArtifactProvider",
        "RemoteQueryArtifactProvider",
        "normalizeSqlId",
        "AnimateOnVisible",
        "ChartCard",
        "ChartEntryMore",
        "Skeleton",
        "ErrorBlock",
        "bootstrap",
        "React",
        "ReactDOM",
        "Recharts",
        "LucideReact",
        "d3Format",
        "dayjs",
    }
)

_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)

# ``import <bindings> from '<spec>'`` — bindings may be a default name, a
# ``* as NS`` namespace binding, a ``{ A, B as C }`` list, or default + list
# combinations. Newlines are allowed so multi-line named-import lists are
# parsed. Side-effect imports (``import './x'``) have no ``from`` and are
# left to the existing path walker.
_IMPORT_STMT_RE = re.compile(
    r"\bimport\s+(?P<bindings>[^'\"]+?)\s+from\s+['\"](?P<spec>[^'\"]+)['\"]",
    re.DOTALL,
)
_NAMESPACE_BINDING_RE = re.compile(r"\*\s*as\s+([A-Za-z_$][\w$]*)")
_NAMED_LIST_RE = re.compile(r"\{([^}]*)\}")
_NAMED_ITEM_RE = re.compile(r"([A-Za-z_$][\w$]*)\s*(?:as\s+([A-Za-z_$][\w$]*))?")
_IDENT_RE = re.compile(r"[A-Za-z_$][\w$]*")

# Export surface extraction (on block-comment-stripped source).
_NAMED_CONST_EXPORT_RE = re.compile(r"\bexport\s+(?:const|let|var)\s+([A-Za-z_$][\w$]*|\{[^}]*\})")
_NAMED_FN_EXPORT_RE = re.compile(r"\bexport\s+(?:async\s+)?function\s+([A-Za-z_$][\w$]*)")
_NAMED_CLASS_EXPORT_RE = re.compile(r"\bexport\s+class\s+([A-Za-z_$][\w$]*)")
_EXPORT_LIST_RE = re.compile(r"\bexport\s+\{([^}]*)\}\s*(?:from\s*['\"][^'\"]+['\"])?")
_EXPORT_STAR_RE = re.compile(r"\bexport\s+\*\s+from")
_DEFAULT_EXPORT_ANY_RE = re.compile(r"\bexport\s+default\b")

# In-file scope for the JSX-tag warning: imports (collected separately),
# top-level definitions, assignments, and function parameters.
_FN_DEF_RE = re.compile(r"\b(?:function|class)\s+([A-Z]\w*)")
_CONST_DEF_RE = re.compile(r"\b(?:const|let|var)\s+([A-Z]\w*)")
_DESTRUCTURED_DEF_RE = re.compile(r"\b(?:const|let|var)\s*\{([^}]*)\}")
_ASSIGN_RE = re.compile(r"\b([A-Z]\w*)\s*=")
_ARROW_PARAMS_RE = re.compile(r"\(\s*([^()]*?)\s*\)\s*=>")
_NAMED_FN_PARAMS_RE = re.compile(r"\bfunction\s+[A-Za-z_$][\w$]*\s*\(\s*([^()]*?)\s*\)")

# Capitalized JSX tags: ``<ChartCard ...>`` / ``<ChartCard.Section ...>``.
_JSX_TAG_RE = re.compile(r"<\s*([A-Z][A-Za-z0-9_$]*)")

# ``style={name}`` with a bare identifier — the only way to statically prove
# a React #62 crash is when ``name`` resolves to a same-file function
# declaration or arrow-const assignment (passing the function itself, not
# its result, to the style prop).
_STYLE_BARE_IDENT_RE = re.compile(r"\bstyle\s*=\s*\{\s*([A-Za-z_$][\w$]*)\s*\}")
_FUNCTION_DECL_RE = re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(")
_ARROW_ASSIGN_RE = re.compile(
    r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\[[^\]]*\]|\([^()]*\)|[A-Za-z_$][\w$]*)\s*=>"
)


@dataclass
class _ImportBinding:
    spec: str
    default: Optional[str] = None
    namespace: Optional[str] = None
    named: List[Tuple[str, str]] = field(default_factory=list)  # (local, imported)


def _strip_block_comments(source: str) -> str:
    return _BLOCK_COMMENT_RE.sub("", source)


def resolve_relative_import(caller_key: str, spec: str, module_keys: Set[str]) -> Optional[str]:
    """Resolve a relative import spec to a module key (or None when it doesn't).

    Mirrors the iframe runtime's resolution so static validation can refuse
    references the renderer would also reject. ``caller_key`` is the
    importing module (e.g. ``"app"`` or ``"charts/trend"``); ``spec`` is the
    relative path (``"./kpi-banner"``, ``"../shared/util"``). Returns the
    resolved module key on success.
    """
    parts: List[str] = caller_key.split("/")[:-1] if "/" in caller_key else []
    spec_segments = spec.split("/")
    # The renderer accepts both extension-less and extension-full imports.
    if spec_segments:
        spec_segments[-1] = re.sub(r"\.(jsx|js)$", "", spec_segments[-1])

    for seg in spec_segments:
        if seg in ("", "."):
            continue
        if seg == "..":
            if not parts:
                return None  # escape attempt outside render/
            parts.pop()
        else:
            parts.append(seg)

    candidate = "/".join(parts)
    if not candidate:
        return None  # someone wrote `import './'` — meaningless

    if candidate in module_keys:
        return candidate
    indexed = f"{candidate}/index"
    if indexed in module_keys:
        return indexed
    return None


def _iter_imports(source: str) -> List[_ImportBinding]:
    """Parse the import statements of one module source."""
    imports: List[_ImportBinding] = []
    for match in _IMPORT_STMT_RE.finditer(source):
        spec = match.group("spec")
        bindings = match.group("bindings")
        imp = _ImportBinding(spec=spec)

        namespace = _NAMESPACE_BINDING_RE.search(bindings)
        if namespace:
            imp.namespace = namespace.group(1)

        named_list = _NAMED_LIST_RE.search(bindings)
        if named_list:
            for item in named_list.group(1).split(","):
                parsed = _NAMED_ITEM_RE.match(item.strip())
                if not parsed:
                    continue
                local, imported = parsed.group(1), parsed.group(2) or parsed.group(1)
                imp.named.append((local, imported))

        # A default binding is the first bare identifier of the clause
        # (everything that isn't ``*`` or a brace list).
        head = bindings.strip()
        if not head.startswith(("{", "*")):
            first = _IDENT_RE.match(head)
            if first:
                imp.default = first.group(0)

        imports.append(imp)
    return imports


def _extract_exports(source: str) -> Tuple[Set[str], bool, bool]:
    """Return ``(named_exports, has_default_export, has_export_star)``."""
    stripped = _strip_block_comments(source)
    named: Set[str] = set()

    for match in _NAMED_CONST_EXPORT_RE.finditer(stripped):
        captured = match.group(1)
        if captured.startswith("{"):
            named.update(_IDENT_RE.findall(captured))
        else:
            named.add(captured)
    for match in _NAMED_FN_EXPORT_RE.finditer(stripped):
        named.add(match.group(1))
    for match in _NAMED_CLASS_EXPORT_RE.finditer(stripped):
        named.add(match.group(1))
    for match in _EXPORT_LIST_RE.finditer(stripped):
        for item in match.group(1).split(","):
            parsed = _NAMED_ITEM_RE.match(item.strip())
            if parsed:
                # ``export { A as B }`` exports B.
                named.add(parsed.group(2) or parsed.group(1))

    has_default = bool(_DEFAULT_EXPORT_ANY_RE.search(stripped))
    has_star = bool(_EXPORT_STAR_RE.search(stripped))
    return named, has_default, has_star


def _file_scope(source: str, imports: List[_ImportBinding]) -> Set[str]:
    """Identifiers in scope for JSX tags: imports + definitions + params."""
    stripped = _strip_block_comments(source)
    scope: Set[str] = set()
    for imp in imports:
        if imp.default:
            scope.add(imp.default)
        if imp.namespace:
            scope.add(imp.namespace)
        for local, _ in imp.named:
            scope.add(local)

    scope.update(_FN_DEF_RE.findall(stripped))
    scope.update(_CONST_DEF_RE.findall(stripped))
    for match in _DESTRUCTURED_DEF_RE.finditer(stripped):
        for ident in _IDENT_RE.findall(match.group(1)):
            if ident[:1].isupper():
                scope.add(ident)
    scope.update(_ASSIGN_RE.findall(stripped))

    for pattern in (_ARROW_PARAMS_RE, _NAMED_FN_PARAMS_RE):
        for match in pattern.finditer(stripped):
            for ident in _IDENT_RE.findall(match.group(1)):
                if ident[:1].isupper():
                    scope.add(ident)
    return scope


def _jsx_tags(source: str) -> Set[str]:
    return set(_JSX_TAG_RE.findall(_strip_block_comments(source)))


def scan_render_imports(modules: Dict[str, Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    """Return ``(issues, warnings)`` for import/export mismatches and
    out-of-scope JSX tags across the render tree.

    ``modules`` uses the validator's canonical shape: key → ``{rel, source,
    ...}``. FATAL issues cover specifiers that provably resolve to
    ``undefined`` (the #130 root cause); warnings cover JSX tags the scan
    cannot prove are in scope, so false positives never block a build.
    """
    issues: List[str] = []
    warnings: List[str] = []
    module_keys: Set[str] = set(modules.keys())

    export_surface: Dict[str, Tuple[Set[str], bool, bool]] = {
        key: _extract_exports(mod["source"]) for key, mod in modules.items()
    }

    for key, mod in modules.items():
        rel = mod["rel"]
        source = mod["source"]
        imports = _iter_imports(source)

        for imp in imports:
            if imp.spec in ALLOWED_BARE_MODULES:
                if imp.spec == "@datus/web-artifact":
                    for local, imported in imp.named:
                        if imported not in WEB_ARTIFACT_EXPORTS:
                            issues.append(
                                f"render/{rel}: import {{ {imported} }} from '@datus/web-artifact' but "
                                "the pinned runtime (0.1.x) does not export it — the binding is "
                                "undefined at runtime and throws React #130 at mount time. Known "
                                f"exports: {sorted(WEB_ARTIFACT_EXPORTS)}."
                            )
                    if imp.default:
                        issues.append(
                            f"render/{rel}: default import {imp.default!r} from '@datus/web-artifact' "
                            "but the runtime module has no default export — the binding is "
                            "undefined at runtime and throws React #130 at mount time. "
                            "Import the named exports instead."
                        )
                continue
            if not (imp.spec.startswith("./") or imp.spec.startswith("../")):
                continue  # disallowed bare specifiers are reported elsewhere
            target = resolve_relative_import(key, imp.spec, module_keys)
            if target is None:
                continue  # unresolved paths are reported elsewhere
            named, has_default, has_star = export_surface[target]
            if has_star:
                continue  # export surface is unknowable statically
            target_rel = modules[target]["rel"]

            if imp.default and not has_default:
                issues.append(
                    f"render/{rel}: default import {imp.default!r} from {imp.spec!r} but "
                    f"render/{target_rel} has no default export — the binding is undefined at "
                    "runtime and renders as React error #130 (Element type is invalid). "
                    "Switch to a named import or add `export default`."
                )
            for local, imported in imp.named:
                if imported not in named:
                    issues.append(
                        f"render/{rel}: import {{ {imported} }} from {imp.spec!r} but "
                        f"render/{target_rel} does not export {imported!r} "
                        f"(named exports: {sorted(named) or 'none'}) — the binding is undefined "
                        "at runtime and renders as React error #130 (Element type is invalid)."
                    )

        scope = _file_scope(source, imports)
        for tag in sorted(_jsx_tags(source) - scope):
            warnings.append(
                f"render/{rel}: <{tag}/> is used but {tag} is not imported or defined in this "
                "file — if the binding is undefined this throws React error #130 at mount time. "
                "Check the import statement (default vs named export) or define the component."
            )

        # ---- style prop receiving a same-file function reference (React #62)
        local_functions = set(_FUNCTION_DECL_RE.findall(_strip_block_comments(source)))
        local_functions.update(_ARROW_ASSIGN_RE.findall(_strip_block_comments(source)))
        for match in _STYLE_BARE_IDENT_RE.finditer(_strip_block_comments(source)):
            name = match.group(1)
            if name in local_functions:
                issues.append(
                    f"render/{rel}: style={{ {name} }} passes the function {name} itself as the "
                    "style prop — React throws #62 at mount time (style expects an object "
                    f"mapping). Call it instead: style={{{name}()}}."
                )

    return issues, warnings
