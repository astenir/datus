"""Enterprise extensions for the upstream dashboard service."""

import asyncio
import json
from pathlib import Path
from typing import List, Optional

from datus.api.models.base_models import Result
from datus.api.services.dashboard_service import DashboardService, _resolve_dashboard_dir
from datus.configuration.agent_config import AgentConfig
from datus.schemas.artifact_manifest import ArtifactManifest
from datus.schemas.gen_visual_dashboard_models import DASHBOARD_SLUG_RE
from datus.utils.loggings import get_logger

logger = get_logger(__name__)


def _configured_dashboard_dist(agent_config: Optional[AgentConfig]) -> Optional[Path]:
    if agent_config is None:
        return None

    agentic_nodes = getattr(agent_config, "agentic_nodes", None)
    if isinstance(agentic_nodes, dict):
        node_config = agentic_nodes.get("gen_visual_dashboard")
        if isinstance(node_config, dict):
            dashboard_dist = node_config.get("dashboard_dist")
            if dashboard_dist:
                return Path(str(dashboard_dist)).expanduser()

    cli_override = getattr(agent_config, "report_dist_cli_override", None)
    if cli_override:
        return Path(str(cli_override)).expanduser()

    return None


class EnterpriseDashboardService(DashboardService):
    """Add downstream dashboard listing and offline HTML rendering."""

    async def list_dashboards(
        self,
        *,
        project_files_root: Path,
    ) -> Result[List[ArtifactManifest]]:
        """Enumerate valid dashboard manifests, sorted by recency."""
        dashboards_root = project_files_root / "dashboards"
        if not await asyncio.to_thread(dashboards_root.is_dir):
            return Result(success=True, data=[])

        def _scan() -> List[Path]:
            return sorted(
                (path for path in dashboards_root.iterdir() if path.is_dir()),
                key=lambda path: path.name,
            )

        subdirs = await asyncio.to_thread(_scan)

        manifests: List[ArtifactManifest] = []
        for subdir in subdirs:
            manifest_path = subdir / "manifest.json"
            if not await asyncio.to_thread(manifest_path.is_file):
                continue
            try:
                text = await asyncio.to_thread(manifest_path.read_text, "utf-8")
                manifests.append(ArtifactManifest.model_validate(json.loads(text)))
            except Exception as exc:
                logger.warning("Skipping dashboard %s: corrupt manifest.json (%s)", subdir.name, exc)

        manifests.sort(key=lambda manifest: manifest.updated_at or manifest.created_at or "", reverse=True)
        return Result(success=True, data=manifests)

    async def render_html(
        self,
        *,
        project_files_root: Path,
        dashboard_slug: str,
        query_endpoint: str,
    ) -> Result[str]:
        """Compile the dashboard HTML string for iframe rendering."""
        from datus.agent.node.visual_artifact.dashboard_html_renderer import render_dashboard_html_str

        dashboard_dir = _resolve_dashboard_dir(project_files_root, dashboard_slug)
        if dashboard_dir is None:
            return Result(
                success=False,
                errorCode="INVALID_DASHBOARD_SLUG",
                errorMessage=f"dashboard_slug must match {DASHBOARD_SLUG_RE.pattern}",
            )

        try:
            html_str = await asyncio.to_thread(
                render_dashboard_html_str,
                project_root=project_files_root,
                dashboard_slug=dashboard_slug,
                query_endpoint=query_endpoint,
                dashboard_dist=_configured_dashboard_dist(self.agent_config),
            )
        except FileNotFoundError:
            return Result(
                success=False,
                errorCode="DASHBOARD_NOT_FOUND",
                errorMessage=f"dashboard {dashboard_slug!r} not found or missing render/app.jsx",
            )
        except ValueError as exc:
            return Result(
                success=False,
                errorCode="INVALID_DASHBOARD_SLUG",
                errorMessage=str(exc),
            )
        except Exception as exc:
            logger.exception("Failed to render HTML for %s: %s", dashboard_slug, exc)
            return Result(
                success=False,
                errorCode="DASHBOARD_NOT_FOUND",
                errorMessage=str(exc),
            )

        return Result(success=True, data=html_str)
