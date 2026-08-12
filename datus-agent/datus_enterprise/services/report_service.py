"""Enterprise extensions for the upstream report service."""

import asyncio
import json
import shutil
from pathlib import Path
from typing import List, Optional

from datus.api.models.base_models import Result
from datus.api.services.report_service import REPORT_SLUG_RE, ReportService, _resolve_report_dir
from datus.configuration.agent_config import AgentConfig
from datus.schemas.artifact_manifest import ArtifactManifest
from datus.utils.loggings import get_logger

logger = get_logger(__name__)


def _configured_report_dist(agent_config: Optional[AgentConfig]) -> Optional[Path]:
    if agent_config is None:
        return None

    cli_override = getattr(agent_config, "report_dist_cli_override", None)
    if cli_override:
        return Path(str(cli_override)).expanduser()

    agentic_nodes = getattr(agent_config, "agentic_nodes", None)
    if not isinstance(agentic_nodes, dict):
        return None

    node_config = agentic_nodes.get("gen_visual_report")
    if not isinstance(node_config, dict):
        return None

    report_dist = node_config.get("report_dist")
    return Path(str(report_dist)).expanduser() if report_dist else None


class EnterpriseReportService(ReportService):
    """Add downstream report listing and offline HTML rendering."""

    async def list_reports(
        self,
        *,
        project_files_root: Path,
    ) -> Result[List[ArtifactManifest]]:
        """Enumerate valid report manifests, sorted by recency."""
        reports_root = project_files_root / "reports"
        if not await asyncio.to_thread(reports_root.is_dir):
            return Result(success=True, data=[])

        def _scan() -> List[Path]:
            return sorted(
                (path for path in reports_root.iterdir() if path.is_dir()),
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
                logger.warning("Skipping report %s: corrupt manifest.json (%s)", subdir.name, exc)

        manifests.sort(key=lambda manifest: manifest.updated_at or manifest.created_at or "", reverse=True)
        return Result(success=True, data=manifests)

    async def delete_report(
        self,
        *,
        project_files_root: Path,
        report_slug: str,
    ) -> Result[bool]:
        """Delete one report artifact directory from disk.

        ACL metadata cleanup is the caller's responsibility (the ACL store
        is an enterprise-extension hook, not part of the upstream service
        contract). Returns ``success=True`` only after the directory is gone.
        """

        report_dir = _resolve_report_dir(project_files_root, report_slug)
        if report_dir is None:
            return Result(
                success=False,
                errorCode="INVALID_REPORT_SLUG",
                errorMessage=f"report_slug must match {REPORT_SLUG_RE.pattern}",
            )
        if not await asyncio.to_thread(report_dir.is_dir):
            return Result(
                success=False,
                errorCode="REPORT_NOT_FOUND",
                errorMessage=f"report {report_slug!r} not found",
            )

        try:
            await asyncio.to_thread(shutil.rmtree, report_dir)
        except Exception as exc:
            logger.exception("Failed to delete report %s: %s", report_slug, exc)
            return Result(
                success=False,
                errorCode="DELETE_FAILED",
                errorMessage=f"failed to delete report {report_slug!r}",
            )

        return Result(success=True, data=True)

    async def render_html(
        self,
        *,
        project_files_root: Path,
        report_slug: str,
    ) -> Result[str]:
        """Compile the report HTML string for iframe rendering."""
        from datus.agent.node.visual_artifact.report_html_renderer import render_report_html_str

        report_dir = _resolve_report_dir(project_files_root, report_slug)
        if report_dir is None:
            return Result(
                success=False,
                errorCode="INVALID_REPORT_SLUG",
                errorMessage=f"report_slug must match {REPORT_SLUG_RE.pattern}",
            )

        try:
            html_str = await asyncio.to_thread(
                render_report_html_str,
                project_root=project_files_root,
                report_slug=report_slug,
                report_dist=_configured_report_dist(self.agent_config),
            )
        except FileNotFoundError:
            return Result(
                success=False,
                errorCode="REPORT_NOT_FOUND",
                errorMessage=f"report {report_slug!r} not found or missing render/app.jsx",
            )
        except ValueError as exc:
            return Result(
                success=False,
                errorCode="INVALID_REPORT_SLUG",
                errorMessage=str(exc),
            )
        except Exception as exc:
            logger.exception("Failed to render HTML for %s: %s", report_slug, exc)
            return Result(
                success=False,
                errorCode="REPORT_NOT_FOUND",
                errorMessage=str(exc),
            )

        return Result(success=True, data=html_str)
