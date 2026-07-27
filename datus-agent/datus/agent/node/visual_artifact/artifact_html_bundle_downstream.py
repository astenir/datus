"""Downstream helpers for bundled visual-artifact renderer assets."""

from __future__ import annotations

import base64
from pathlib import Path

from datus.utils.loggings import get_logger

logger = get_logger(__name__)

DIST_CSS_NAME = "index.css"
DIST_JS_NAME = "index.umd.js"
BUNDLED_DIST_DIR = Path(__file__).parent / "vendor" / "web_artifact_render_dist"


def resolve_dist(dist: Path | None) -> Path | None:
    """Resolve an explicit dist, then the bundled dist, then CDN fallback."""

    if dist:
        return _validate_dist(Path(dist), warn=True)
    return _validate_dist(BUNDLED_DIST_DIR, warn=False)


def inline_offline_assets(dist_dir: Path) -> tuple[str, str]:
    return (
        _dist_asset_data_url(dist_dir, DIST_CSS_NAME, "text/css"),
        _dist_asset_data_url(dist_dir, DIST_JS_NAME, "text/javascript"),
    )


def _validate_dist(dist: Path, *, warn: bool) -> Path | None:
    resolved = dist.expanduser().resolve()
    if not resolved.is_dir():
        if warn:
            logger.warning("artifact dist %s is not a directory; falling back to CDN.", resolved)
        return None

    missing = [name for name in (DIST_CSS_NAME, DIST_JS_NAME) if not (resolved / name).is_file()]
    if missing:
        if warn:
            logger.warning(
                "artifact dist %s is missing required assets %s; falling back to CDN.",
                resolved,
                missing,
            )
        return None
    return resolved


def _dist_asset_data_url(dist_dir: Path, filename: str, mime_type: str) -> str:
    encoded = base64.b64encode((dist_dir / filename).read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"
