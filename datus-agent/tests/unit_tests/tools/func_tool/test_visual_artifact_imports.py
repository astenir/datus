# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Unit tests for the static import/export scanner behind React #130 checks.

The scanner runs inside ``validate_render``: the FATAL issues fail the
subagent's terminal action, so a false positive blocks a perfectly good
artifact. The warning path (out-of-scope JSX tags) is deliberately non-fatal
but should still stay quiet on legitimate code — the bulk of this file is
therefore negative cases grouped by the hazard they exercise.
"""

from __future__ import annotations

from datus.tools.func_tool._visual_artifact_imports import scan_render_imports


def scan(files: dict[str, str]) -> tuple[list[str], list[str]]:
    modules = {key: {"rel": f"{key}.jsx", "source": source} for key, source in files.items()}
    return scan_render_imports(modules)


# --------------------------------------------------------------------------- #
# Fatal issues — import specifiers that provably resolve to undefined         #
# --------------------------------------------------------------------------- #


class TestImportContractIssues:
    def test_named_import_not_exported_by_target(self):
        issues, _ = scan(
            {
                "app": 'import { Trend, MISSING } from "./charts/trend";\nexport default function App() { return <Trend/>; }',
                "charts/trend": "export function Trend() { return null; }",
            }
        )
        assert len(issues) == 1
        assert "MISSING" in issues[0] and "React error #130" in issues[0]

    def test_default_import_from_named_only_module(self):
        issues, _ = scan(
            {
                "app": 'import KpiBanner from "./kpi-banner";\nexport default function App() { return <KpiBanner/>; }',
                "kpi-banner": "export const KpiBanner = () => null;",
            }
        )
        assert len(issues) == 1
        assert "no default export" in issues[0]

    def test_import_mismatch_reported_per_file_and_binding(self):
        issues, _ = scan(
            {
                "app": (
                    'import { A } from "./one";\nimport { B } from "./two";\n'
                    "export default function App() { return <A/>; }"
                ),
                "one": "export const A = 1;",
                "two": "export const Other = 2;",
            }
        )
        assert len(issues) == 1
        assert "B" in issues[0] and "does not export" in issues[0]


# --------------------------------------------------------------------------- #
# Guards — export surfaces the scanner must recognise                          #
# --------------------------------------------------------------------------- #


class TestExportSurfaceGuards:
    def test_export_star_target_is_skipped(self):
        issues, _ = scan(
            {
                "app": 'import Thing from "./star";\nexport default function App() { return <Thing/>; }',
                "star": "export * from './inner';",
            }
        )
        assert issues == []

    def test_reexport_list_counts_as_named_export(self):
        issues, _ = scan(
            {
                "app": 'import { ReExp } from "./reexp";\nexport default function App() { return <ReExp/>; }',
                "reexp": "export { ReExp } from './inner';",
            }
        )
        assert issues == []

    def test_export_default_function_name_is_not_a_named_export(self):
        issues, _ = scan(
            {
                "app": 'import { App } from "./named-only";\nexport default function Wrapper() { return <App/>; }',
                "named-only": "export default function App() { return null; }",
            }
        )
        assert len(issues) == 1
        assert "does not export" in issues[0]

    def test_destructured_const_exports_are_named_exports(self):
        issues, _ = scan(
            {
                "app": 'import { COLORS, SPACING } from "./shared/constants";\nexport default function App() { return <div/>; }',
                "shared/constants": "export const { COLORS, SPACING } = theme;",
            }
        )
        assert issues == []

    def test_block_commented_exports_do_not_count(self):
        issues, _ = scan(
            {
                "app": 'import Fake from "./commented";\nexport default function App() { return <Fake/>; }',
                "commented": "/* export default () => null; */ export const nope = 1;",
            }
        )
        assert len(issues) == 1
        assert "no default export" in issues[0]

    def test_bare_specifier_imports_are_skipped(self):
        issues, _ = scan(
            {
                "app": (
                    'import { ChartCard, useDatusArtifact } from "@datus/web-artifact";\n'
                    "export default function App() { return <ChartCard/>; }"
                ),
            }
        )
        assert issues == []

    def test_web_artifact_default_import_is_rejected(self):
        # The runtime module has no default export — a default import is an
        # undefined binding that crashes with React #130 at mount.
        issues, _ = scan(
            {
                "app": (
                    'import DatusArtifact from "@datus/web-artifact";\n'
                    "export default function App() { return <DatusArtifact/>; }"
                ),
            }
        )
        assert len(issues) == 1
        assert "no default export" in issues[0] and "#130" in issues[0]

    def test_web_artifact_unknown_named_import_is_rejected(self):
        issues, _ = scan(
            {
                "app": (
                    'import { BlockHandle } from "@datus/web-artifact";\n'
                    "export default function App() { return <BlockHandle><div/></BlockHandle>; }"
                ),
            }
        )
        assert len(issues) == 1
        assert "BlockHandle" in issues[0] and "does not export" in issues[0]

    def test_multiline_named_imports_are_parsed(self):
        issues, warnings = scan(
            {
                "app": (
                    "import {\n"
                    "  LineChart,\n"
                    "  Line,\n"
                    "  XAxis,\n"
                    "} from 'recharts';\n"
                    "export default function App() { return <LineChart><Line/></LineChart>; }"
                ),
            }
        )
        assert issues == []
        assert warnings == []


# --------------------------------------------------------------------------- #
# Warnings — JSX tags not provably in scope                                    #
# --------------------------------------------------------------------------- #


class TestJsxTagWarnings:
    def test_unimported_tag_is_warned(self):
        _, warnings = scan(
            {
                "app": "export default function App() { return <Ghost/>; }",
            }
        )
        assert len(warnings) == 1
        assert "Ghost" in warnings[0] and "React error #130" in warnings[0]

    def test_lowercase_intrinsics_are_ignored(self):
        _, warnings = scan(
            {
                "app": "export default function App() { return <div><span>ok</span></div>; }",
            }
        )
        assert warnings == []

    def test_imported_and_defined_tags_stay_quiet(self):
        _, warnings = scan(
            {
                "app": (
                    'import Default from "./d";\nimport { Named } from "./n";\nimport * as NS from "./ns";\n'
                    "const Local = () => null;\n"
                    "function FnDecl() { return null; }\n"
                    "export default function App({ Section }) {"
                    " return <div><Default/><Named/><NS.Widget/><Local/><FnDecl/><Section/></div>; }"
                ),
                "d": "export default () => null;",
                "n": "export const Named = () => null;",
                "ns": "export const Widget = () => null;",
            }
        )
        assert warnings == []

    def test_callback_params_are_in_scope(self):
        _, warnings = scan(
            {
                "app": (
                    'import DataTable from "./table";\n'
                    "export default function App({ rows }) {"
                    " return rows.map((Item) => <Item/>); }"
                ),
                "table": "export default function DataTable() { return null; }",
            }
        )
        assert warnings == []

    def test_member_expression_tags_resolve_via_base_identifier(self):
        _, warnings = scan(
            {
                "app": 'import Cards from "./cards";\nexport default function App() { return <Cards.Kpi/>; }',
                "cards": "export default { Kpi: () => null };",
            }
        )
        assert warnings == []

    def test_tags_inside_block_comments_are_ignored(self):
        _, warnings = scan(
            {
                "app": "/* <Ghost/> */\nexport default function App() { return <div/>; }",
            }
        )
        assert warnings == []

    def test_closing_tags_do_not_duplicate_warnings(self):
        _, warnings = scan(
            {
                "app": "export default function App() { return <div><Ghost></Ghost></div>; }",
            }
        )
        assert len(warnings) == 1


# --------------------------------------------------------------------------- #
# React #62 — style prop receiving a function reference                       #
# --------------------------------------------------------------------------- #


class TestStylePropIssues:
    def test_style_receives_same_file_function_declaration(self):
        issues, _ = scan(
            {
                "app": (
                    "function labelStyle() { return { fontSize: 12 }; }\n"
                    "export default function App() { return <span style={labelStyle}>x</span>; }"
                ),
            }
        )
        assert len(issues) == 1
        assert "style={labelStyle()}" in issues[0] and "React throws #62" in issues[0]

    def test_style_receives_same_file_arrow_const(self):
        issues, _ = scan(
            {
                "app": (
                    "const selectStyle = () => ({ border: 'none' });\n"
                    "export default function App() { return <select style={selectStyle} />; }"
                ),
            }
        )
        assert len(issues) == 1
        assert "selectStyle()" in issues[0]

    def test_style_function_called_inline_is_fine(self):
        issues, _ = scan(
            {
                "app": (
                    "function chipStyle(active) { return { color: active ? 'red' : 'blue' }; }\n"
                    "export default function App() { return <button style={chipStyle(true)}>x</button>; }"
                ),
            }
        )
        assert issues == []

    def test_style_object_literal_and_object_const_are_fine(self):
        issues, _ = scan(
            {
                "app": (
                    "const boxStyle = { padding: 8 };\n"
                    "export default function App() { return <div style={{ color: 'red' }} /><span style={boxStyle} />; }"
                ),
            }
        )
        assert issues == []

    def test_style_from_unknown_import_or_member_is_skipped(self):
        # labelStyle comes from an import and helper.labelStyle from an object
        # literal — neither is provably a function, so the scan must stay quiet.
        issues, _ = scan(
            {
                "app": (
                    "import { labelStyle } from './styles';\n"
                    "const helper = { labelStyle: () => ({}) };\n"
                    "export default function App() { return <div style={labelStyle} /><span style={helper.labelStyle} />; }"
                ),
                "styles": "export const labelStyle = { fontSize: 12 };",
            }
        )
        assert issues == []
