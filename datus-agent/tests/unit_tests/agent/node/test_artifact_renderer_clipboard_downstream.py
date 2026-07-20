# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""Downstream regression coverage for the vendored artifact renderer patch."""

from __future__ import annotations

from pathlib import Path

_VENDOR_DIR = (
    Path(__file__).parents[4] / "datus" / "agent" / "node" / "visual_artifact" / "vendor" / "web_artifact_render_dist"
)


def test_fix_prompt_copy_has_clipboard_fallback():
    bundle = (_VENDOR_DIR / "index.umd.js").read_text(encoding="utf-8")

    assert "async function datusCopyText" in bundle
    assert 'document.execCommand("copy")' in bundle
    assert "await datusCopyText(W)" in bundle
    assert 'navigator.clipboard.writeText(W),uc.success("Fix prompt copied")' not in bundle


def test_renderer_patch_recipe_includes_clipboard_fix():
    patcher = (_VENDOR_DIR / "patch-post-message-transport.mjs").read_text(encoding="utf-8")

    assert 'replaceOnce("copy helper"' in patcher
    assert 'replaceOnce("copy fix action"' in patcher
