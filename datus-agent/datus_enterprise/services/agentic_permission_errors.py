"""Safe user-facing formatting for downstream Agent permission denials."""

from __future__ import annotations

import re
from collections.abc import Iterator

from datus.tools.business_datasource_policy import business_datasource_read_only_message

_BUSINESS_DATASOURCE_READ_ONLY_RE = re.compile(
    r"ENTERPRISE_BUSINESS_DATASOURCE_READ_ONLY:\s*operation='(?P<operation>[^']+)'",
    re.IGNORECASE,
)
_PERMISSION_DENIED_TOOL_RE = re.compile(
    r"PERMISSION_DENIED:\s*Tool\s+'(?P<tool>[^']+)'\s+\((?P<category>[^)]+)\)\s+"
    r"is blocked by the\s+'(?P<profile>[^']+)'\s+permission profile",
    re.IGNORECASE,
)
_PERMISSION_MODE_DENIED_RE = re.compile(
    r"Permission mode '(?P<mode>[^']+)' requires module\.chat\.permission_mode",
    re.IGNORECASE,
)

# Structured ``deny_reason`` tags carried by ``PermissionDeniedException``
# (see ``datus.tools.permission.permission_hooks``). These route the message
# to copy that names the concrete blocker (rule / statement kind / path)
# without relying on message-text regexes, which silently missed several
# raise sites and left users with a generic fallback. The regexes above
# remain as the fallback for exceptions that predate or bypass the tag.
_REASON_USER_REJECTED = "user_rejected"
_REASON_USER_REJECTED_FS = "user_rejected_fs"
_REASON_NON_INTERACTIVE = "non_interactive"
_REASON_NON_INTERACTIVE_FS = "non_interactive_fs"
_REASON_NON_INTERACTIVE_BASH = "non_interactive_bash"
_REASON_SQL_STATEMENTS_DENIED = "sql_statements_denied"
_REASON_BASH_DENIED = "bash_denied"

# Extraction helpers for the structured copy above; each matches the exact
# raise-site wording in ``permission_hooks.py``.
_PROFILE_UNDER_RE = re.compile(r"under the\s+'([^']+)'\s+(?:permission\s+)?profile", re.IGNORECASE)
_PROFILE_BLOCKED_BY_RE = re.compile(r"blocked by the\s+'([^']+)'\s+permission profile", re.IGNORECASE)
_SQL_KIND_RE = re.compile(r"SQL statement kind\s+'([^']+)'\s+\(class\s+'([^']+)'\)", re.IGNORECASE)
_BASH_RULE_RE = re.compile(r"blocked by rule\s+'([^']+)'", re.IGNORECASE)
_FS_PATH_RE = re.compile(r"filesystem path\s+'([^']+)'", re.IGNORECASE)
_FS_REJECTED_PATH_RE = re.compile(r"external filesystem access to\s+(.+)$", re.IGNORECASE)
_TOOL_EXECUTION_RE = re.compile(r"execution of\s+'([^']+)'", re.IGNORECASE)
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

        structured = _format_structured_denial(current, text)
        if structured is not None:
            return structured

        datasource_match = _BUSINESS_DATASOURCE_READ_ONLY_RE.search(text)
        if datasource_match:
            return f"权限受限：{business_datasource_read_only_message(datasource_match.group('operation'))}"

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


def _format_structured_denial(exc: BaseException, text: str) -> str | None:
    """Format a denial carrying the structured ``deny_reason`` tag.

    Returns ``None`` when the exception carries no tag, so the legacy
    message-regex path below keeps covering every other denial.
    """
    reason = getattr(exc, "deny_reason", None)
    if not isinstance(reason, str) or not reason:
        return None

    if reason == _REASON_USER_REJECTED:
        tool = _exception_tool(exc, text)
        label = "bash 命令" if tool == "bash" else (f"工具 {tool}" if tool else "该操作")
        return f"权限受限：{label} 的执行未获得确认，已取消。如需执行，请重新发起并在确认弹窗中选择允许。"

    if reason == _REASON_USER_REJECTED_FS:
        match = _FS_REJECTED_PATH_RE.search(text)
        path = match.group(1).strip() if match else ""
        if path:
            return f"权限受限：外部路径 {path} 的访问未获得确认，已取消。如需访问，请重新发起并在确认弹窗中选择允许。"
        return "权限受限：外部路径访问未获得确认，已取消。如需访问，请重新发起并在确认弹窗中选择允许。"

    if reason == _REASON_NON_INTERACTIVE:
        tool = _exception_tool(exc, text)
        profile = _profile_under(text) or "auto"
        return (
            f"权限受限：工具 {tool} 需要用户确认，但当前流程以非交互模式运行"
            f"（{profile} 权限模式），因此被拦截。换参数不会绕过限制，"
            "请改用交互式对话，或由管理员调整权限规则。"
        )

    if reason == _REASON_NON_INTERACTIVE_FS:
        path = _fs_path(text) or ""
        profile = _profile_under(text) or "auto"
        return (
            f"权限受限：路径 {path} 位于项目根目录之外，需要用户确认，但当前流程"
            f"以非交互模式运行（{profile} 权限模式），因此被拦截。"
            "请改用项目内路径，或由管理员调整权限规则。"
        )

    if reason == _REASON_NON_INTERACTIVE_BASH:
        profile = _profile_under(text) or "auto"
        return (
            f"权限受限：bash 命令需要用户确认，但当前流程以非交互模式运行"
            f"（{profile} 权限模式），因此被拦截。请改用交互式对话，"
            "或由管理员调整权限规则。"
        )

    if reason == _REASON_SQL_STATEMENTS_DENIED:
        kind_match = _SQL_KIND_RE.search(text)
        kind = kind_match.group(1) if kind_match else "未知"
        profile = _profile_blocked_by(text) or "unknown"
        return (
            f"权限受限：{kind} 类 SQL 语句被 {profile} 权限模式的 sql_statements 规则拦截，"
            "换写法不会绕过限制。如需放行，请管理员在 agent.yml 的"
            " permissions.sql_statements 中调整规则。"
        )

    if reason == _REASON_BASH_DENIED:
        rule_match = _BASH_RULE_RE.search(text)
        rule = rule_match.group(1) if rule_match else "未知"
        profile = _profile_under(text) or "unknown"
        return (
            f"权限受限：bash 命令被规则 {rule} 拦截（{profile} 权限模式），"
            "换写法不会绕过限制。如需放行，请管理员在 agent.yml 的"
            " permissions.bash_commands 中调整规则。"
        )

    return None


def _exception_tool(exc: BaseException, text: str) -> str:
    tool = getattr(exc, "tool_name", "") or ""
    if tool:
        return tool
    match = _TOOL_EXECUTION_RE.search(text)
    return match.group(1) if match else ""


def _profile_under(text: str) -> str:
    match = _PROFILE_UNDER_RE.search(text)
    return match.group(1) if match else ""


def _profile_blocked_by(text: str) -> str:
    match = _PROFILE_BLOCKED_BY_RE.search(text)
    return match.group(1) if match else ""


def _fs_path(text: str) -> str:
    match = _FS_PATH_RE.search(text)
    return match.group(1) if match else ""


def _iter_exception_chain(exc: BaseException) -> Iterator[BaseException]:
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def _permission_profile_label(profile: str) -> str:
    return _PERMISSION_PROFILE_LABELS.get(profile, profile)
