"""Artifact filesystem scope adapters for ACL-authorized edit sessions."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

from datus.schemas.action_history import ActionHistory, ActionRole, ActionStatus
from datus.tools.func_tool.base import FuncToolResult
from datus.tools.func_tool.fs_path_policy import PathZone, ResolvedPath

_PROTECTED_ARTIFACT_ROOTS = frozenset({"reports", "dashboards"})
_ARTIFACT_BOUND_NODES = frozenset({"gen_visual_report", "gen_visual_dashboard", "ask_report", "ask_dashboard"})

ArtifactAccessMode = Literal["legacy", "create", "edit"]


def resolve_artifact_access_mode(
    agent_config: Any,
    node_config: Mapping[str, Any],
) -> ArtifactAccessMode:
    if not bool(getattr(agent_config, "_enterprise_enabled", False)):
        return "legacy"
    if node_config.get("_acl_authorized_artifact_edit"):
        if not node_config.get("edit_locked") or not node_config.get("artifact_slug"):
            raise ValueError("ACL-authorized artifact edit is missing its locked artifact slug.")
        return "edit"
    if node_config.get("edit_locked"):
        raise ValueError("Enterprise artifact edit requires an ACL-authorized edit session.")
    return "create"


def resolve_locked_artifact_slug(
    node_config: Mapping[str, Any],
    *,
    access_mode: ArtifactAccessMode,
) -> str | None:
    if access_mode == "edit" or (access_mode == "legacy" and node_config.get("edit_locked")):
        value = node_config.get("artifact_slug")
        return str(value) if value else None
    return None


def bind_node_authorized_artifact(filesystem_tool: Any, artifact_slug: str) -> None:
    if filesystem_tool is None:
        return
    bind = getattr(filesystem_tool, "bind_authorized_artifact", None)
    if bind is not None:
        bind(artifact_slug)


def bind_locked_artifact(
    node_config: Mapping[str, Any],
    artifact_tools: Any,
    *,
    artifact_kind: str,
    artifact_root_dir_name: str,
) -> str | None:
    if not node_config.get("edit_locked"):
        return None
    artifact_slug = node_config.get("artifact_slug")
    if not artifact_slug or artifact_tools is None:
        return None
    bind_tool = getattr(artifact_tools, f"bind_existing_{artifact_kind}", None)
    if bind_tool is None:
        return None
    result = bind_tool(artifact_slug)
    if getattr(result, "success", 0) != 1:
        raise ValueError(
            f"Failed to bind locked {artifact_kind} artifact "
            f"{artifact_root_dir_name}/{artifact_slug}: {getattr(result, 'error', None) or result}"
        )
    return str(artifact_slug)


def auto_validate_locked_artifact(
    node_config: Mapping[str, Any],
    artifact_slug: str | None,
    artifact_tools: Any,
    action_history_manager: Any,
) -> ActionHistory | None:
    """Validate a locked edit artifact and append the synthetic tool action."""

    if not node_config.get("edit_locked") or not artifact_slug or artifact_tools is None:
        return None
    validate_render = getattr(artifact_tools, "validate_render", None)
    if validate_render is None:
        return None

    validate_result = validate_render()
    output_data = validate_result.model_dump() if hasattr(validate_result, "model_dump") else validate_result
    validate_action = ActionHistory.create_action(
        role=ActionRole.TOOL,
        action_type="validate_render",
        messages="Auto validate locked artifact before finalizing.",
        input_data={"function_name": "validate_render", "arguments": "{}"},
        output_data={
            "success": getattr(validate_result, "success", 0) == 1,
            "raw_output": output_data,
            "summary": "Auto validate locked artifact",
        },
        status=ActionStatus.SUCCESS if getattr(validate_result, "success", 0) == 1 else ActionStatus.FAILED,
    )
    action_history_manager.add_action(validate_action)
    return validate_action


def apply_global_skills_read_only(
    resolved: ResolvedPath,
    *,
    enabled: bool,
    datus_home: Path | None,
) -> ResolvedPath:
    if not enabled or resolved.zone != PathZone.WHITELIST:
        return resolved

    effective_datus_home = datus_home or (Path.home() / ".datus").resolve(strict=False)
    global_skills = (effective_datus_home / "skills").resolve(strict=False)
    if resolved.resolved.is_relative_to(global_skills):
        return replace(resolved, read_only=True)
    return resolved


def generic_artifact_protection_active(*, enabled: bool, current_node: str | None) -> bool:
    return enabled and current_node not in _ARTIFACT_BOUND_NODES


def is_generic_protected_artifact_path(
    resolved: ResolvedPath,
    *,
    active: bool,
    root_path: Path,
) -> bool:
    if not active or resolved.zone not in (PathZone.INTERNAL, PathZone.WHITELIST):
        return False
    try:
        rel = resolved.resolved.relative_to(root_path).as_posix()
    except ValueError:
        return False
    return rel.split("/", 1)[0] in _PROTECTED_ARTIFACT_ROOTS


def generic_artifact_not_found(resolved: ResolvedPath) -> FuncToolResult:
    return FuncToolResult(success=0, error=f"File not found: {resolved.display}")


def generic_artifact_mutation_reject(resolved: ResolvedPath) -> FuncToolResult:
    return FuncToolResult(
        success=0,
        error=(
            f"Artifact path is protected by report/dashboard ACLs: {resolved.display}. "
            "Use the report/dashboard artifact APIs or an ACL-bound artifact agent."
        ),
    )


def generic_artifact_visibility_filtered() -> FuncToolResult:
    return FuncToolResult(
        result={
            "files": [],
            "truncated": False,
            "visibility_filtered": True,
            "visibility_reason": "artifact_acl",
            "message": (
                "Artifact directory is protected by Artifact ACLs and cannot be "
                "enumerated from the current Chat authorization scope; an empty "
                "list does not prove that no artifact exists on disk."
            ),
        }
    )


def decorate_generic_artifact_glob_result(result: FuncToolResult) -> FuncToolResult:
    """Explain ACL pruning when a generic workspace walk crosses artifacts.

    A generic Chat ``glob`` may start at the project root and therefore cannot
    reject the seed up front. The walk still prunes ``reports/`` and
    ``dashboards/`` entries, though; preserve the successful, possibly
    non-empty result while making that policy filtering explicit to the model.
    """

    if result.success != 1 or not isinstance(result.result, dict):
        return result

    scoped_result = dict(result.result)
    scoped_result["visibility_filtered"] = True
    scoped_result["visibility_reason"] = "artifact_acl"
    scoped_result["message"] = (
        "Artifact ACLs omitted protected report/dashboard paths from this Glob result. "
        "The returned files only cover the current Chat authorization scope; absence "
        "of an artifact path does not prove that it is missing on disk."
    )
    result.result = scoped_result
    return result


def initialize_artifact_scope(
    tool: Any,
    *,
    locked_artifact_slug: str | None,
    require_authorized_artifact: bool,
) -> None:
    tool._locked_artifact_slug = locked_artifact_slug if locked_artifact_slug else None
    tool._require_authorized_artifact = require_authorized_artifact


def bind_authorized_artifact(tool: Any, artifact_slug: str) -> None:
    """Bind filesystem mutations to one server-authorized artifact slug."""

    if not tool._require_authorized_artifact:
        return
    if tool._locked_artifact_slug and tool._locked_artifact_slug != artifact_slug:
        raise ValueError(
            f"Artifact filesystem is already locked to {tool.ARTIFACT_ROOT_DIR_NAME}/{tool._locked_artifact_slug}."
        )
    tool._locked_artifact_slug = artifact_slug


def reject_artifact_mutation(tool: Any, path: str) -> FuncToolResult | None:
    slug = _artifact_slug_for_path(tool, path)
    if tool._require_authorized_artifact and not (tool._locked_artifact_slug and slug == tool._locked_artifact_slug):
        return FuncToolResult(
            success=0,
            error=(
                "Artifact filesystem writes require an ACL-authorized binding under "
                f"{tool.ARTIFACT_ROOT_DIR_NAME}/<slug>/; cannot modify {path}."
            ),
        )
    if _violates_locked_artifact(tool, slug):
        return FuncToolResult(
            success=0,
            error=(
                "Artifact edit session is locked to "
                f"{tool.ARTIFACT_ROOT_DIR_NAME}/{tool._locked_artifact_slug}/; cannot modify {path}."
            ),
        )
    return None


def reject_artifact_read(tool: Any, path: str) -> FuncToolResult | None:
    if _violates_locked_artifact(tool, _artifact_slug_for_path(tool, path)):
        return FuncToolResult(success=0, error=f"File not found: {path}")
    return None


def decorate_artifact_glob_result(
    tool: Any,
    pattern: str,
    path: str,
    result: FuncToolResult,
) -> FuncToolResult:
    normalized_pattern = pattern.replace("\\", "/").lstrip("./")
    normalized_path = path.replace("\\", "/").strip("./")
    targets_artifact_tree = normalized_pattern == tool.ARTIFACT_ROOT_DIR_NAME or normalized_pattern.startswith(
        f"{tool.ARTIFACT_ROOT_DIR_NAME}/"
    )
    targets_artifact_tree = (
        targets_artifact_tree
        or normalized_path == tool.ARTIFACT_ROOT_DIR_NAME
        or normalized_path.startswith(f"{tool.ARTIFACT_ROOT_DIR_NAME}/")
    )
    if result.success != 1 or not isinstance(result.result, dict):
        return result
    if not targets_artifact_tree or not (tool._require_authorized_artifact or tool._locked_artifact_slug):
        return result

    scoped_result = dict(result.result)
    scoped_result["visibility_filtered"] = True
    scoped_result["visibility_reason"] = "artifact_acl"
    if tool._locked_artifact_slug:
        scoped_result["message"] = (
            f"Artifact ACL limits results to the authorized {tool.ARTIFACT_KIND} "
            f"{tool.ARTIFACT_ROOT_DIR_NAME}/{tool._locked_artifact_slug}."
        )
    else:
        scoped_result["message"] = (
            f"No {tool.ARTIFACT_KIND} is bound yet; Artifact ACLs prevent this session from "
            f"enumerating existing {tool.ARTIFACT_ROOT_DIR_NAME}/ paths. An empty list does not "
            "prove that no artifact exists on disk."
        )
    result.result = scoped_result
    return result


def filter_artifact_walk(tool: Any, paths: Iterable[Path]) -> Iterator[Path]:
    for path in paths:
        if tool._require_authorized_artifact or tool._locked_artifact_slug:
            slug = _artifact_slug_for_resolved_path(tool, path)
            if slug is not None and slug != tool._locked_artifact_slug:
                continue
        yield path


def _artifact_slug_for_path(tool: Any, path: str) -> str | None:
    try:
        resolved = tool._classify(path)
    except Exception:  # pragma: no cover - defensive
        return None
    try:
        rel = resolved.resolved.relative_to(tool._root_resolved).as_posix()
    except ValueError:
        return None
    match = tool._ARTIFACT_PATH_RE.match(rel)
    return match.group(1) if match else None


def _artifact_slug_for_resolved_path(tool: Any, path: Path) -> str | None:
    try:
        rel = path.resolve(strict=False).relative_to(tool._root_resolved).as_posix()
    except ValueError:
        return None
    match = tool._ARTIFACT_PATH_RE.match(rel)
    return match.group(1) if match else None


def _violates_locked_artifact(tool: Any, slug: str | None) -> bool:
    if slug is None:
        return False
    if tool._require_authorized_artifact:
        return slug != tool._locked_artifact_slug
    return bool(tool._locked_artifact_slug and slug != tool._locked_artifact_slug)
