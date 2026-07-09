import { beforeEach, describe, expect, it, vi } from "vitest";

const listAgents = vi.fn();
const getAgent = vi.fn();
const createAgent = vi.fn();
const editAgent = vi.fn();
const deleteAgent = vi.fn();
const agentTools = vi.fn();
const agentUseTools = vi.fn();
const listDatasources = vi.fn();
const listArtifacts = vi.fn();
const listMcpServers = vi.fn();
const listMcpTools = vi.fn();
const fetchPermissions = vi.fn();
const toastError = vi.fn();
const toastSuccess = vi.fn();
const grantedPermissions = new Set<string>();

function permissionMatches(required: string, granted: string) {
  if (granted === "*" || granted === required) return true;
  if (!granted.endsWith("*")) return false;
  return required.startsWith(granted.slice(0, -1));
}

vi.mock("@/lib/api", () => ({
  agentApi: {
    list: listAgents,
    get: getAgent,
    create: createAgent,
    edit: editAgent,
    delete: deleteAgent,
    tools: agentTools,
    useTools: agentUseTools,
  },
  adminDatasourceApi: {
    listDatasources,
  },
  adminArtifactApi: {
    listArtifacts,
  },
  mcpApi: {
    listServers: listMcpServers,
    listTools: listMcpTools,
  },
}));

vi.mock("@/composables/useConnection", () => ({
  useConnection: () => ({
    effectiveBase: () => "http://api.test",
  }),
}));

vi.mock("@/composables/usePermission", () => ({
  usePermission: () => ({
    isLoaded: { value: true },
    fetchPermissions,
    hasPermission: (permissionCode: string) =>
      [...grantedPermissions].some((permission) => permissionMatches(permissionCode, permission)),
  }),
}));

vi.mock("vue-sonner", () => ({
  toast: {
    error: toastError,
    success: toastSuccess,
  },
}));

describe("useAgentManager", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    grantedPermissions.clear();
    grantedPermissions.add("module.admin.datasources");
    grantedPermissions.add("module.admin.artifacts");
    grantedPermissions.add("mcp.server.list");
    grantedPermissions.add("mcp.server.tools");
    listAgents.mockResolvedValue([
      { agent_id: "writer", name: "writer", node_class: "text", status: "published", source: "custom" },
      { agent_id: "analyst", name: "analyst", node_class: "gen_sql", status: "draft", source: "custom" },
    ]);
    getAgent.mockResolvedValue({
      agent_id: "analyst",
      name: "analyst",
      description: "Analysis helper",
      node_class: "gen_sql",
      status: "draft",
      source: "custom",
      prompt_template: "Analyze data",
      prompt_language: "en",
      prompt_version: "1.0",
      tools: ["read_query"],
      mcp: ["filesystem"],
      skills: ["fund-analyst"],
      scoped_context: {
        catalogs: ["fund"],
        subjects: ["portfolio"],
      },
      rules: ["cite sources"],
      max_turns: 30,
    });
    createAgent.mockResolvedValue({ agent_id: "analyst", name: "analyst" });
    editAgent.mockResolvedValue({});
    deleteAgent.mockResolvedValue({});
    agentTools.mockResolvedValue({
      tools: {
        sql: ["read_query", "explain_query"],
      },
    });
    agentUseTools.mockResolvedValue({
      default_tools: ["read_query"],
      tool_types: {
        analytics: { tools: ["explain_query"] },
      },
    });
    listDatasources.mockResolvedValue({
      data: [
        { name: "warehouse", type: "postgres", is_default: false },
        { name: "fund_pg", type: "postgres", is_default: true },
      ],
    });
    listArtifacts.mockResolvedValue({
      data: [
        {
          artifact_type: "dashboard",
          manifest: {
            slug: "risk_dashboard",
            name: "Risk Dashboard",
            description: "Risk overview",
            kind: "dashboard",
            created_at: "2026-01-01T00:00:00Z",
          },
        },
        {
          artifact_type: "report",
          manifest: {
            slug: "weekly_report",
            name: "Weekly Report",
            description: "Weekly summary",
            kind: "report",
            created_at: "2026-01-02T00:00:00Z",
          },
        },
      ],
    });
    listMcpServers.mockResolvedValue({
      servers: [
        { name: "remote_api", type: "http", url: "https://api.example.test/mcp" },
        { name: "filesystem", type: "stdio", command: "npx" },
      ],
    });
    listMcpTools.mockImplementation((_baseUrl: string, serverName: string) => Promise.resolve({
      tools: serverName === "filesystem"
        ? [{ name: "read_file" }, { name: "list_directory" }]
        : [{ name: "search" }],
    }));
  });

  it("loads and sorts agents from the active connection", async () => {
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.loadAgents();

    expect(listAgents).toHaveBeenCalledWith("http://api.test");
    expect(manager.agents.value.map(agent => agent.name)).toEqual(["analyst", "writer"]);
    expect(manager.agentCount.value).toBe(2);
  });

  it("surfaces enterprise disabled legacy agent routes explicitly", async () => {
    const { ApiResultError } = await import("@/lib/chat");
    listAgents.mockRejectedValue(new ApiResultError("legacy disabled", "ENTERPRISE_ROUTE_DISABLED"));
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.loadAgents();

    expect(manager.enterpriseRoutesUnavailable.value).toBe(true);
    expect(manager.error.value).toContain("企业 Agent 管理接口");
    expect(toastError).toHaveBeenCalledWith(expect.stringContaining("企业 Agent 管理接口"));
  });

  it("loads selected agent detail and its usable tools", async () => {
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.selectAgent("analyst");

    expect(getAgent).toHaveBeenCalledWith("http://api.test", "analyst");
    expect(agentUseTools).toHaveBeenCalledWith("http://api.test", "gen_sql");
    expect(manager.form.value).toMatchObject({
      id: "analyst",
      name: "analyst",
      promptTemplate: "Analyze data",
      toolsText: "read_query",
    });
    expect(manager.selectedUseToolCount.value).toBe(2);
  });

  it("hydrates builtin templates from the read-only detail payload", async () => {
    getAgent.mockResolvedValue({
      agent_id: "gen_sql",
      name: "gen_sql",
      description: "SQL assistant",
      node_class: "gen_sql",
      status: "published",
      source: "builtin",
      prompt_template: null,
      prompt_template_content: "builtin template body",
      prompt_template_name: "gen_sql_system",
      prompt_language: "en",
      prompt_version: "1.2",
      tools: [],
      mcp: [],
      skills: [],
      scoped_context: {},
      rules: [],
      max_turns: 30,
    });
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.selectAgent("gen_sql");

    expect(manager.form.value.promptTemplate).toBe("builtin template body");
    expect(manager.selectedIsBuiltin.value).toBe(true);
    expect(manager.canSubmitForm.value).toBe(false);
  });

  it("copies the builtin chat agent into an editable enterprise draft", async () => {
    listAgents.mockResolvedValue([
      { agent_id: "chat", name: "chat", node_class: "chat", status: "published", source: "builtin" },
      { agent_id: "chat_custom", name: "chat_custom", node_class: "chat", status: "draft", source: "enterprise" },
    ]);
    getAgent.mockResolvedValue({
      agent_id: "chat",
      name: "chat",
      description: "Default chat assistant",
      node_class: "chat",
      status: "published",
      source: "builtin",
      prompt_template: null,
      prompt_template_content: "builtin template body",
      prompt_template_name: "chat_system",
      prompt_language: "en",
      prompt_version: "1.2",
      tools: [],
      mcp: [],
      skills: [],
      scoped_context: {},
      rules: [],
      max_turns: 30,
    });
    agentUseTools.mockResolvedValue({
      default_tools: ["memory_tools.*"],
      tool_types: {},
    });
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.loadAgents();
    await manager.selectAgent("chat");
    const started = manager.startCreateFromSelectedBuiltin();

    expect(started).toBe(true);
    expect(manager.selectedAgent.value).toBeNull();
    expect(manager.selectedIsBuiltin.value).toBe(false);
    expect(manager.formMode.value).toBe("create");
    expect(manager.canSubmitForm.value).toBe(true);
    expect(manager.form.value).toMatchObject({
      id: "",
      name: "chat_custom_2",
      nodeClass: "chat",
      status: "draft",
      promptTemplate: "builtin template body",
      toolsText: "memory_tools.*",
      mcpText: "",
    });
    expect(toastSuccess).toHaveBeenCalledWith("已复制为企业 Agent 草稿，可选择 MCP 后保存。");
  });

  it("loads available agent tool catalogs", async () => {
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.loadToolCatalog();

    expect(agentTools).toHaveBeenCalledWith("http://api.test");
    expect(manager.toolCategoryCount.value).toBe(1);
    expect(manager.toolCount.value).toBe(2);
  });

  it("loads MCP servers and toggles agent server bindings", async () => {
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.loadMcpCatalog();

    expect(listMcpServers).toHaveBeenCalledWith("http://api.test");
    expect(listMcpTools).toHaveBeenCalledWith("http://api.test", "filesystem");
    expect(listMcpTools).toHaveBeenCalledWith("http://api.test", "remote_api");
    expect(manager.mcpServerOptions.value.map(server => server.name)).toEqual(["filesystem", "remote_api"]);
    expect(manager.mcpServerOptions.value[0]).toMatchObject({
      name: "filesystem",
      target: "npx",
      tools: ["list_directory", "read_file"],
      selected: false,
    });

    manager.toggleMcpServer("filesystem");

    expect(manager.form.value.mcpText).toBe("filesystem");
    expect(manager.selectedMcpCount.value).toBe(1);
    expect(manager.selectedMcpToolCount.value).toBe(2);
    expect(manager.mcpServerOptions.value[0]?.selected).toBe(true);
  });

  it("skips MCP catalog requests without MCP list permission", async () => {
    grantedPermissions.delete("mcp.server.list");
    grantedPermissions.delete("mcp.server.tools");
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.loadMcpCatalog();

    expect(listMcpServers).not.toHaveBeenCalled();
    expect(listMcpTools).not.toHaveBeenCalled();
    expect(manager.mcpServerOptions.value).toEqual([]);
    expect(toastError).not.toHaveBeenCalled();
  });

  it("loads MCP servers without tools when only server list is authorized", async () => {
    grantedPermissions.delete("mcp.server.tools");
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.loadMcpCatalog();

    expect(listMcpServers).toHaveBeenCalledWith("http://api.test");
    expect(listMcpTools).not.toHaveBeenCalled();
    expect(manager.mcpServerOptions.value.map(server => server.name)).toEqual(["filesystem", "remote_api"]);
    expect(manager.mcpServerOptions.value[0]?.tools).toEqual([]);
  });

  it("loads datasource and artifact option catalogs for picker fields", async () => {
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.loadResourceCatalogs();

    expect(listDatasources).toHaveBeenCalled();
    expect(listArtifacts).toHaveBeenCalled();
    expect(manager.datasourceOptions.value.map(option => option.value)).toEqual(["fund_pg", "warehouse"]);
    expect(manager.datasourceOptions.value[0]?.label).toContain("默认");
    expect(manager.artifactOptions.value.map(option => option.value)).toEqual(["risk_dashboard", "weekly_report"]);
  });

  it("skips optional resource catalogs without admin datasource or artifact permissions", async () => {
    grantedPermissions.delete("module.admin.datasources");
    grantedPermissions.delete("module.admin.artifacts");
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.loadResourceCatalogs();

    expect(listDatasources).not.toHaveBeenCalled();
    expect(listArtifacts).not.toHaveBeenCalled();
    expect(manager.datasourceOptions.value).toEqual([]);
    expect(manager.artifactOptions.value).toEqual([]);
    expect(toastError).not.toHaveBeenCalled();
  });

  it("loads only the authorized optional resource catalog", async () => {
    grantedPermissions.delete("module.admin.artifacts");
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.loadResourceCatalogs();

    expect(listDatasources).toHaveBeenCalled();
    expect(listArtifacts).not.toHaveBeenCalled();
    expect(manager.datasourceOptions.value.map(option => option.value)).toEqual(["fund_pg", "warehouse"]);
    expect(manager.artifactOptions.value).toEqual([]);
  });

  it("keeps selected values as fallback options when catalogs do not include them", async () => {
    listDatasources.mockResolvedValue({ data: [] });
    listArtifacts.mockResolvedValue({ data: [] });
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();
    manager.form.value.datasourceId = "legacy_ds";
    manager.form.value.artifactSlug = "legacy_report";

    await manager.loadResourceCatalogs();

    expect(manager.datasourceOptions.value).toEqual([{ value: "legacy_ds", label: "当前：legacy_ds" }]);
    expect(manager.artifactOptions.value).toEqual([{ value: "legacy_report", label: "当前：legacy_report" }]);
  });

  it("creates agents with normalized list fields", async () => {
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();
    manager.form.value = {
      id: "",
      name: "researcher",
      nodeClass: "gen_sql",
      status: "draft",
      description: "Research agent",
      promptTemplate: "Answer carefully",
      toolsText: "read_query, explain_query",
      mcpText: "filesystem",
      skillsText: "fund-analyst",
      datasourceId: "fund_pg",
      artifactSlug: "risk_dashboard",
      catalogsText: "fund",
      subjectsText: "portfolio\nrisk",
      rulesText: "",
      maxTurns: "8",
    };

    await manager.saveForm();

    expect(createAgent).toHaveBeenCalledWith("http://api.test", "researcher", {
      name: "researcher",
      node_class: "gen_sql",
      status: "draft",
      datasource_id: "fund_pg",
      artifact_slug: "risk_dashboard",
      description: "Research agent",
      prompt_template: "Answer carefully",
      prompt_language: "en",
      prompt_version: "1.0",
      tools: ["read_query", "explain_query"],
      mcp: ["filesystem"],
      skills: ["fund-analyst"],
      scoped_context: {
        catalogs: ["fund"],
        subjects: ["portfolio", "risk"],
      },
      rules: undefined,
      max_turns: 8,
    });
    expect(toastSuccess).toHaveBeenCalledWith("Agent 已创建");
  });

  it("edits agents through the enterprise upsert payload", async () => {
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();
    await manager.selectAgent("analyst");
    manager.form.value.promptTemplate = "Updated prompt";

    await manager.saveForm();

    expect(editAgent).toHaveBeenCalledWith("http://api.test", "analyst", expect.objectContaining({
      name: "analyst",
      node_class: "gen_sql",
      prompt_template: "Updated prompt",
    }));
  });

  it("does not save or delete builtin agents from the management surface", async () => {
    listAgents.mockResolvedValue([
      { agent_id: "gen_sql", name: "gen_sql", node_class: "gen_sql", status: "published", source: "builtin" },
    ]);
    getAgent.mockResolvedValue({
      agent_id: "gen_sql",
      name: "gen_sql",
      description: "SQL assistant",
      node_class: "gen_sql",
      status: "published",
      source: "builtin",
      prompt_template: "builtin template body",
      prompt_language: "en",
      prompt_version: "1.2",
      tools: [],
      scoped_context: {},
      rules: [],
      max_turns: 30,
    });
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.loadAgents();
    await manager.selectAgent("gen_sql");
    await manager.saveForm();
    await manager.deleteAgent("gen_sql");

    expect(editAgent).not.toHaveBeenCalled();
    expect(deleteAgent).not.toHaveBeenCalled();
    expect(toastError).toHaveBeenCalledWith("系统内置 Agent 为只读，不能在管理页保存。");
    expect(toastError).toHaveBeenCalledWith("系统内置 Agent 为只读，不能删除。");
  });

  it("rejects invalid max turn values before saving", async () => {
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();
    manager.form.value.name = "bad-agent";
    manager.form.value.maxTurns = "0";

    await manager.saveForm();

    expect(createAgent).not.toHaveBeenCalled();
    expect(toastError).toHaveBeenCalledWith("最大轮次必须是正整数");
  });

  it("updates list-like form fields through picker actions", async () => {
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    manager.toggleListFieldValue("toolsText", "db_tools.read_query");
    manager.addListFieldValue("skillsText", "fund-analyst");
    manager.toggleListFieldValue("toolsText", "semantic_tools.search_semantic_model");
    manager.toggleListFieldValue("toolsText", "db_tools.read_query");

    expect(manager.form.value.toolsText).toBe("semantic_tools.search_semantic_model");
    expect(manager.selectedTools.value).toEqual(["semantic_tools.search_semantic_model"]);
    expect(manager.form.value.skillsText).toBe("fund-analyst");
    expect(manager.selectedSkills.value).toEqual(["fund-analyst"]);
  });

  it("deletes agents and reloads the list", async () => {
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.deleteAgent("writer");

    expect(deleteAgent).toHaveBeenCalledWith("http://api.test", "writer");
    expect(listAgents).toHaveBeenCalledWith("http://api.test");
    expect(toastSuccess).toHaveBeenCalledWith("Agent 已删除");
  });
});

describe("agentManagerInternals", () => {
  it("normalizes comma and newline separated lists", async () => {
    const { agentManagerInternals } = await import("./useAgentManager");

    expect(agentManagerInternals.parseListText("a, b\nc")).toEqual(["a", "b", "c"]);
    expect(agentManagerInternals.parseListText(" ")).toBeUndefined();
  });
});
