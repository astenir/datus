"""Downstream tests for the vendored dashboard renderer."""

from pathlib import Path


def test_vendored_dashboard_renderer_supports_optional_message_transport():
    """The bundled renderer owns the nested-frame transport implementation.

    The HTML template merely selects it through an optional global. Keeping
    these assertions beside the template tests prevents a vendor refresh from
    silently restoring the old frontend ``srcdoc`` rewrite dependency.
    """
    bundle_path = (
        Path(__file__).parents[4]
        / "datus"
        / "agent"
        / "node"
        / "visual_artifact"
        / "vendor"
        / "web_artifact_render_dist"
        / "index.umd.js"
    )
    bundle = bundle_path.read_text(encoding="utf-8")

    assert 'e.provider.mode==="post-message"' in bundle
    assert "DatusPostMessageQueryProvider" in bundle
    assert "queryTransport" in bundle
    assert "datus-artifact/query-result" in bundle
