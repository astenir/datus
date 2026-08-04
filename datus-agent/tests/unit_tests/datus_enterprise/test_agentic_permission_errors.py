"""Safe enterprise Agent permission error formatting."""

from datus.tools.permission.permission_hooks import PermissionDeniedException
from datus_enterprise.services.agentic_permission_errors import format_permission_denied_error


def test_formats_business_datasource_delete_denial_with_exact_user_copy() -> None:
    exc = PermissionDeniedException(
        "PERMISSION_DENIED: ENTERPRISE_BUSINESS_DATASOURCE_READ_ONLY: "
        "operation='DELETE' kind='delete'. STOP retrying.",
        tool_category="db_tools",
        tool_name="execute_sql",
    )

    assert format_permission_denied_error(exc) == (
        "权限受限：企业模式下业务数据源仅支持只读查询，DELETE 操作未执行。"
        "如需删除业务数据，请通过受控的数据维护流程联系管理员。"
    )
