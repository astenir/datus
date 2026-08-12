"""Canonical capabilities for Agent node classes.

This module is intentionally declarative and dependency-light so runtime,
enterprise API, CLI, and editor tool catalogs can share the same source of
truth without importing one another.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentNodeCapability:
    """Product and editor capabilities for one runtime Agent node class."""

    node_class: str
    label: str
    description: str
    customizable: bool = False
    enterprise_visible: bool = False
    cli_visible: bool = False
    cli_label: str | None = None
    prompt_template: str | None = None
    module_permission: str | None = None
    supports_mcp: bool = False
    #: Runtime fallback ``max_turns`` for the node class when neither
    #: ``agent.yml`` nor an enterprise Agent record overrides it. Mirrors
    #: the node class constructors' defaults; kept here so enterprise
    #: built-in Agent summaries can align with the same value.
    default_max_turns: int = 50
    default_tools: tuple[str, ...] = ()
    tool_categories: tuple[str, ...] = ()
    tool_method_allowlists: tuple[tuple[str, tuple[str, ...]], ...] = ()

    def allowed_tool_methods(self, category: str) -> tuple[str, ...] | None:
        for configured_category, methods in self.tool_method_allowlists:
            if configured_category == category:
                return methods
        return None


_USER_FACING_TOOL_CATEGORIES: tuple[str, ...] = (
    "db_tools",
    "context_search_tools",
    "semantic_tools",
    "reference_template_tools",
    "date_parsing_tools",
    "filesystem_tools",
)

_ANALYSIS_TOOL_CATEGORIES: tuple[str, ...] = (
    "db_tools",
    "semantic_tools",
    "context_search_tools",
)

_REPORT_TOOL_CATEGORIES: tuple[str, ...] = (
    "db_tools",
    "semantic_tools",
    "context_search_tools",
    "date_parsing_tools",
    "reference_template_tools",
)

_INTERACTION_TOOL_CATEGORIES: tuple[str, ...] = ("tools",)

REPORT_ARTIFACT_TOOL_METHODS: tuple[str, ...] = (
    "start_new_report",
    "bind_existing_report",
    "save_query",
    "validate_render",
)

DASHBOARD_ARTIFACT_TOOL_METHODS: tuple[str, ...] = (
    "start_new_dashboard",
    "bind_existing_dashboard",
    "save_query_template",
    "validate_render",
)

ARTIFACT_TOOL_METHODS: tuple[str, ...] = tuple(
    sorted(set(REPORT_ARTIFACT_TOOL_METHODS + DASHBOARD_ARTIFACT_TOOL_METHODS))
)

_STANDARD_FILESYSTEM_METHODS: tuple[str, ...] = (
    "read_file",
    "write_file",
    "edit_file",
    "delete_file",
    "glob",
    "grep",
)

_VISUAL_REPORT_DEFAULT_TOOLS: tuple[str, ...] = (
    "semantic_tools.*",
    "db_tools.*",
    "context_search_tools.*",
    *tuple(f"filesystem_tools.{method}" for method in _STANDARD_FILESYSTEM_METHODS),
    *tuple(f"artifact_tools.{method}" for method in REPORT_ARTIFACT_TOOL_METHODS),
    "tools.*",
)

_VISUAL_DASHBOARD_DEFAULT_TOOLS: tuple[str, ...] = (
    "semantic_tools.*",
    "db_tools.*",
    "context_search_tools.*",
    *tuple(f"filesystem_tools.{method}" for method in _STANDARD_FILESYSTEM_METHODS),
    *tuple(f"artifact_tools.{method}" for method in DASHBOARD_ARTIFACT_TOOL_METHODS),
    "tools.*",
)

_ARTIFACT_ASK_TOOL_CATEGORIES: tuple[str, ...] = (
    "db_tools",
    "semantic_tools",
    "context_search_tools",
    "reference_template_tools",
    "date_parsing_tools",
    "filesystem_tools",
)

_ASK_AGENT_FILESYSTEM_READ_ONLY: tuple[str, ...] = ("glob", "grep", "read_file")
_EXPLORE_FILESYSTEM_READ_ONLY: tuple[str, ...] = ("read_file", "glob", "grep")

_ARTIFACT_ASK_DEFAULT_TOOLS: tuple[str, ...] = (
    "db_tools.list_databases",
    "db_tools.list_schemas",
    "db_tools.list_tables",
    "db_tools.describe_table",
    "db_tools.search_table",
    "db_tools.execute_sql",
    "semantic_tools.*",
    "context_search_tools.*",
    "reference_template_tools.*",
    "date_parsing_tools.*",
    "filesystem_tools.read_file",
    "filesystem_tools.glob",
    "filesystem_tools.grep",
    "tools.*",
)


AGENT_NODE_CAPABILITIES: tuple[AgentNodeCapability, ...] = (
    AgentNodeCapability(
        node_class="chat",
        label="通用聊天",
        description="面向普通问答、规划和多工具协作。",
        customizable=True,
        enterprise_visible=True,
        prompt_template="chat_system",
        supports_mcp=True,
        default_tools=(
            "db_tools.*",
            "context_search_tools.*",
            "reference_template_tools.*",
            "date_parsing_tools.*",
            "filesystem_tools.*",
            "memory_tools.*",
            "platform_doc_tools.*",
            "tools.*",
        ),
        tool_categories=(
            _USER_FACING_TOOL_CATEGORIES + ("memory_tools", "platform_doc_tools") + _INTERACTION_TOOL_CATEGORIES
        ),
    ),
    AgentNodeCapability(
        node_class="gen_sql",
        label="SQL 分析",
        description="生成和执行只读 SQL。",
        customizable=True,
        enterprise_visible=True,
        cli_visible=True,
        cli_label="gen_sql - SQL generation (default)",
        prompt_template="gen_sql_system",
        module_permission="module.sql_executor",
        supports_mcp=True,
        default_tools=("db_tools.*", "semantic_tools.*", "context_search_tools.*", "tools.*"),
        tool_categories=_ANALYSIS_TOOL_CATEGORIES + _INTERACTION_TOOL_CATEGORIES,
    ),
    AgentNodeCapability(
        node_class="gen_report",
        label="报表生成",
        description="创建或更新报表产物。",
        customizable=True,
        enterprise_visible=True,
        cli_visible=True,
        cli_label="gen_report - Report/analysis generation",
        prompt_template="gen_report_system",
        module_permission="module.report.query",
        default_tools=(
            "semantic_tools.*",
            "context_search_tools.list_subject_tree",
            *tuple(f"filesystem_tools.{method}" for method in _STANDARD_FILESYSTEM_METHODS),
            "tools.*",
        ),
        tool_categories=_REPORT_TOOL_CATEGORIES + ("filesystem_tools",) + _INTERACTION_TOOL_CATEGORIES,
        tool_method_allowlists=(("filesystem_tools", _STANDARD_FILESYSTEM_METHODS),),
    ),
    AgentNodeCapability(
        node_class="gen_visual_report",
        label="可视化报表",
        description="生成带清单、查询和可视化页面的结构化报表产物。",
        customizable=True,
        enterprise_visible=True,
        cli_visible=True,
        cli_label="gen_visual_report - Structured report artifact (manifest + queries)",
        prompt_template="gen_visual_report_system",
        module_permission="module.report.query",
        default_max_turns=80,
        default_tools=_VISUAL_REPORT_DEFAULT_TOOLS,
        tool_categories=_ANALYSIS_TOOL_CATEGORIES
        + ("filesystem_tools", "artifact_tools")
        + _INTERACTION_TOOL_CATEGORIES,
        tool_method_allowlists=(
            ("filesystem_tools", _STANDARD_FILESYSTEM_METHODS),
            ("artifact_tools", REPORT_ARTIFACT_TOOL_METHODS),
        ),
    ),
    AgentNodeCapability(
        node_class="gen_visual_dashboard",
        label="可视化仪表盘",
        description="生成支持参数化查询的结构化仪表盘产物。",
        customizable=True,
        enterprise_visible=True,
        cli_visible=True,
        cli_label="gen_visual_dashboard - Parameterized dashboard artifact (Jinja2 SQL templates)",
        prompt_template="gen_visual_dashboard_system",
        module_permission="module.dashboard.query",
        default_max_turns=80,
        default_tools=_VISUAL_DASHBOARD_DEFAULT_TOOLS,
        tool_categories=_ANALYSIS_TOOL_CATEGORIES
        + ("filesystem_tools", "artifact_tools")
        + _INTERACTION_TOOL_CATEGORIES,
        tool_method_allowlists=(
            ("filesystem_tools", _STANDARD_FILESYSTEM_METHODS),
            ("artifact_tools", DASHBOARD_ARTIFACT_TOOL_METHODS),
        ),
    ),
    AgentNodeCapability(
        node_class="ask_metrics",
        label="指标问答",
        description="围绕指标、维度和归因分析问答。",
        customizable=True,
        enterprise_visible=True,
        prompt_template="ask_metrics_system",
        default_tools=(
            "context_search_tools.search_metrics",
            "context_search_tools.get_metrics",
            "semantic_tools.list_metrics",
            "semantic_tools.get_dimensions",
            "semantic_tools.query_metrics",
            "semantic_tools.attribution_analyze",
            "context_search_tools.list_subject_tree",
        ),
        tool_categories=_USER_FACING_TOOL_CATEGORIES,
    ),
    AgentNodeCapability(
        node_class="ask_report",
        label="报表问答",
        description="围绕一个已存在报表做只读问答。",
        customizable=True,
        enterprise_visible=True,
        prompt_template="ask_report_system",
        module_permission="module.report.query",
        default_tools=_ARTIFACT_ASK_DEFAULT_TOOLS,
        tool_categories=_ARTIFACT_ASK_TOOL_CATEGORIES + _INTERACTION_TOOL_CATEGORIES,
        tool_method_allowlists=(("filesystem_tools", _ASK_AGENT_FILESYSTEM_READ_ONLY),),
    ),
    AgentNodeCapability(
        node_class="ask_dashboard",
        label="仪表盘问答",
        description="围绕一个已存在仪表盘做只读问答。",
        customizable=True,
        enterprise_visible=True,
        prompt_template="ask_dashboard_system",
        module_permission="module.dashboard.query",
        default_tools=_ARTIFACT_ASK_DEFAULT_TOOLS,
        tool_categories=_ARTIFACT_ASK_TOOL_CATEGORIES + _INTERACTION_TOOL_CATEGORIES,
        tool_method_allowlists=(("filesystem_tools", _ASK_AGENT_FILESYSTEM_READ_ONLY),),
    ),
    AgentNodeCapability(
        node_class="gen_table",
        label="宽表生成",
        description="从关联 SQL 生成宽表。",
        customizable=True,
        prompt_template="gen_table_system",
    ),
    AgentNodeCapability(
        node_class="gen_dashboard",
        label="BI 仪表盘生成",
        description="在已配置的 BI 服务中创建和管理仪表盘。",
        customizable=True,
        prompt_template="gen_dashboard_system",
        module_permission="module.dashboard.query",
    ),
    AgentNodeCapability(
        node_class="gen_skill",
        label="技能生成",
        description="创建和优化 Agent 技能。",
        customizable=True,
        prompt_template="skill_creator_system",
    ),
    AgentNodeCapability(
        node_class="scheduler",
        label="调度管理",
        description="管理和监控外部任务调度服务。",
        customizable=True,
        prompt_template="scheduler_system",
    ),
    AgentNodeCapability(
        node_class="explore",
        label="数据探索",
        description="以只读方式探索数据和收集上下文。",
        customizable=True,
        enterprise_visible=True,
        prompt_template="explore_system",
        default_tools=(
            "db_tools.*",
            "context_search_tools.*",
            "date_parsing_tools.*",
            "filesystem_tools.read_file",
            "filesystem_tools.glob",
            "filesystem_tools.grep",
        ),
        tool_categories=(
            "db_tools",
            "context_search_tools",
            "date_parsing_tools",
            "filesystem_tools",
        ),
        tool_method_allowlists=(("filesystem_tools", _EXPLORE_FILESYSTEM_READ_ONLY),),
    ),
    AgentNodeCapability(
        node_class="gen_semantic_model",
        label="语义模型生成",
        description="内部语义模型初始化和生成节点。",
        prompt_template="gen_semantic_model_system",
    ),
    AgentNodeCapability(
        node_class="gen_metrics",
        label="指标生成",
        description="内部指标初始化和生成节点。",
        prompt_template="gen_metrics_system",
    ),
    AgentNodeCapability(
        node_class="gen_sql_summary",
        label="SQL 摘要生成",
        description="内部 SQL 摘要生成节点。",
        prompt_template="gen_sql_summary_system",
    ),
    AgentNodeCapability(
        node_class="gen_job",
        label="数据任务生成",
        description="内部数据任务生成节点。",
        prompt_template="gen_job_system",
    ),
    AgentNodeCapability(
        node_class="feedback",
        label="反馈分析",
        description="内部会话反馈分析和知识归档节点。",
        prompt_template="feedback_system",
    ),
)

AGENT_NODE_CAPABILITY_BY_CLASS = {capability.node_class: capability for capability in AGENT_NODE_CAPABILITIES}

if len(AGENT_NODE_CAPABILITY_BY_CLASS) != len(AGENT_NODE_CAPABILITIES):
    raise RuntimeError("Agent node capability registry contains duplicate node_class values.")


def get_agent_node_capability(node_class: str) -> AgentNodeCapability | None:
    """Return one registered node capability by canonical class name."""

    return AGENT_NODE_CAPABILITY_BY_CLASS.get(node_class)


def enterprise_agent_node_capabilities() -> tuple[AgentNodeCapability, ...]:
    """Return customizable node classes supported by enterprise Agent management."""

    return tuple(
        capability
        for capability in AGENT_NODE_CAPABILITIES
        if capability.customizable and capability.enterprise_visible
    )


def cli_agent_node_capabilities() -> tuple[AgentNodeCapability, ...]:
    """Return customizable node classes offered by the local CLI wizard."""

    return tuple(
        capability for capability in AGENT_NODE_CAPABILITIES if capability.customizable and capability.cli_visible
    )


def tool_editor_node_capabilities() -> tuple[AgentNodeCapability, ...]:
    """Return node classes with a complete editor tool-selection profile."""

    return tuple(capability for capability in AGENT_NODE_CAPABILITIES if capability.tool_categories)
