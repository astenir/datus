"""Safe enterprise Agent permission error formatting."""

from datus.tools.permission.permission_hooks import PermissionDeniedException
from datus_enterprise.services.agentic_permission_errors import format_permission_denied_error


def test_formats_business_datasource_delete_denial_with_exact_user_copy() -> None:
    exc = PermissionDeniedException(
        "PERMISSION_DENIED: ENTERPRISE_BUSINESS_DATASOURCE_READ_ONLY: operation='DELETE' kind='delete'. STOP retrying.",
        tool_category="db_tools",
        tool_name="execute_sql",
    )

    assert format_permission_denied_error(exc) == (
        "权限受限：企业模式下业务数据源仅支持只读查询，DELETE 操作未执行。"
        "如需删除业务数据，请通过受控的数据维护流程联系管理员。"
    )


def test_formats_sql_statements_denial_via_structured_reason() -> None:
    exc = PermissionDeniedException(
        "PERMISSION_DENIED: SQL statement kind 'insert' (class 'write') is blocked by the "
        "'normal' permission profile's sql_statements rules. STOP retrying — rewording "
        "the SQL will not change the outcome. The user can adjust "
        "`permissions.sql_statements` in agent.yml.",
        tool_category="db_tools",
        tool_name="execute_sql",
        deny_reason="sql_statements_denied",
    )

    assert format_permission_denied_error(exc) == (
        "权限受限：insert 类 SQL 语句被 normal 权限模式的 sql_statements 规则拦截，"
        "换写法不会绕过限制。如需放行，请管理员在 agent.yml 的"
        " permissions.sql_statements 中调整规则。"
    )


def test_formats_bash_rule_denial_via_structured_reason() -> None:
    exc = PermissionDeniedException(
        "PERMISSION_DENIED: Bash command blocked by rule 'rm:*' under the 'normal' permission "
        "profile. STOP retrying this command — rewording it will not change the outcome. "
        "The user can adjust `permissions.bash_commands` in agent.yml.",
        tool_category="bash_tools",
        tool_name="bash",
        deny_reason="bash_denied",
    )

    assert format_permission_denied_error(exc) == (
        "权限受限：bash 命令被规则 rm:* 拦截（normal 权限模式），"
        "换写法不会绕过限制。如需放行，请管理员在 agent.yml 的"
        " permissions.bash_commands 中调整规则。"
    )


def test_formats_non_interactive_ask_denial_via_structured_reason() -> None:
    exc = PermissionDeniedException(
        "PERMISSION_DENIED: Tool 'bash' (bash_tools) requires user confirmation but this flow "
        "runs non-interactively under the 'auto' profile. The tool is outside that profile's "
        "scope. STOP retrying — different parameters will not change the outcome.",
        tool_category="bash_tools",
        tool_name="bash",
        deny_reason="non_interactive",
    )

    assert format_permission_denied_error(exc) == (
        "权限受限：工具 bash 需要用户确认，但当前流程以非交互模式运行"
        "（auto 权限模式），因此被拦截。换参数不会绕过限制，"
        "请改用交互式对话，或由管理员调整权限规则。"
    )


def test_formats_non_interactive_external_fs_denial_via_structured_reason() -> None:
    exc = PermissionDeniedException(
        "PERMISSION_DENIED: filesystem path '/srv/private/data.csv' is outside the project "
        "root and requires user confirmation, but this flow runs non-interactively under "
        "the 'normal' profile. STOP retrying — choose a path inside the project root or "
        "surface the failure.",
        tool_category="filesystem_tools",
        tool_name="read_file",
        deny_reason="non_interactive_fs",
    )

    assert format_permission_denied_error(exc) == (
        "权限受限：路径 /srv/private/data.csv 位于项目根目录之外，需要用户确认，但当前流程"
        "以非交互模式运行（normal 权限模式），因此被拦截。"
        "请改用项目内路径，或由管理员调整权限规则。"
    )


def test_formats_user_rejected_denial_via_structured_reason() -> None:
    exc = PermissionDeniedException(
        "User rejected execution of 'write_file'",
        tool_category="filesystem_tools",
        tool_name="write_file",
        deny_reason="user_rejected",
    )

    assert format_permission_denied_error(exc) == (
        "权限受限：工具 write_file 的执行未获得确认，已取消。"
        "如需执行，请重新发起并在确认弹窗中选择允许。"
    )


def test_formats_user_rejected_bash_via_structured_reason() -> None:
    exc = PermissionDeniedException(
        "User rejected execution of bash command",
        tool_category="bash_tools",
        tool_name="bash",
        deny_reason="user_rejected",
    )

    assert format_permission_denied_error(exc) == (
        "权限受限：bash 命令 的执行未获得确认，已取消。"
        "如需执行，请重新发起并在确认弹窗中选择允许。"
    )


def test_formats_user_rejected_external_fs_via_structured_reason() -> None:
    exc = PermissionDeniedException(
        "User rejected external filesystem access to /srv/private/data.csv",
        tool_category="filesystem_tools",
        tool_name="read_file",
        deny_reason="user_rejected_fs",
    )

    assert format_permission_denied_error(exc) == (
        "权限受限：外部路径 /srv/private/data.csv 的访问未获得确认，已取消。"
        "如需访问，请重新发起并在确认弹窗中选择允许。"
    )
