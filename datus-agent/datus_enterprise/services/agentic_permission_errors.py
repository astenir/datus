"""Safe user-facing formatting for downstream Agent permission denials."""

from __future__ import annotations

import re
from collections.abc import Iterator

_PERMISSION_DENIED_TOOL_RE = re.compile(
    r"PERMISSION_DENIED:\s*Tool\s+'(?P<tool>[^']+)'\s+\((?P<category>[^)]+)\)\s+"
    r"is blocked by the\s+'(?P<profile>[^']+)'\s+permission profile",
    re.IGNORECASE,
)
_PERMISSION_MODE_DENIED_RE = re.compile(
    r"Permission mode '(?P<mode>[^']+)' requires module\.chat\.permission_mode",
    re.IGNORECASE,
)
_FILESYSTEM_WRITE_TOOL_NAMES = {"write_file", "edit_file", "delete_file"}
_PERMISSION_PROFILE_LABELS = {
    "normal": "普通",
    "auto": "自动",
    "dangerous": "危险",
}


def is_permission_denied_error(exc: BaseException) -> bool:
    for current in _iter_exception_chain(exc):
        if type(current).__name__ == "PermissionDeniedException":
            return True
        if "PERMISSION_DENIED:" in str(current):
            return True
        if _PERMISSION_MODE_DENIED_RE.search(str(current)):
            return True
    return False


def format_permission_denied_error(exc: BaseException) -> str | None:
    for current in _iter_exception_chain(exc):
        text = str(current).strip()
        if not text:
            continue

        tool_match = _PERMISSION_DENIED_TOOL_RE.search(text)
        if tool_match:
            tool_name = tool_match.group("tool")
            category = tool_match.group("category")
            profile = _permission_profile_label(tool_match.group("profile"))
            if category == "filesystem_tools" and tool_name in _FILESYSTEM_WRITE_TOOL_NAMES:
                return (
                    "权限受限：当前 Agent 或会话的工具策略不允许直接修改文件。"
                    f"{tool_name} 已被“{profile}”权限模式拦截，换路径或重试不会绕过限制。"
                    "请联系管理员核对该 Agent 的工具策略。"
                )
            return (
                f"权限受限：当前账号没有执行工具 {tool_name} 的权限，"
                f"已被“{profile}”权限模式拦截，换参数或重试不会绕过限制。"
            )

        mode_match = _PERMISSION_MODE_DENIED_RE.search(text)
        if mode_match:
            mode = _permission_profile_label(mode_match.group("mode"))
            return (
                f"权限受限：当前账号不能切换到 {mode} 对话模式。"
                "如确需使用自动或危险工具权限，请联系管理员授予“高危对话模式”权限。"
            )

    return None


def _iter_exception_chain(exc: BaseException) -> Iterator[BaseException]:
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def _permission_profile_label(profile: str) -> str:
    return _PERMISSION_PROFILE_LABELS.get(profile, profile)
