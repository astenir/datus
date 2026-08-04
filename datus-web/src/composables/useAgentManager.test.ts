import { beforeEach, describe, expect, it, vi } from "vitest";

const listAgents = vi.fn();
const getAgent = vi.fn();
const createAgent = vi.fn();
const editAgent = vi.fn();
const deleteAgent = vi.fn();
const agentNodeTypes = vi.fn();
const agentAclUsers = vi.fn();
const agentAclRoles = vi.fn();
const agentTools = vi.fn();
const agentUseTools = vi.fn();
const updateAgentStatus = vi.fn();
const updateAgentAcl = vi.fn();
const updateAgentPolicy = vi.fn();
const agentDefaultUsers = vi.fn();
const updateAgentDefaultUsers = vi.fn();
const enterpriseDefault = vi.fn();
const updateEnterpriseDefault = vi.fn();
const listPromptVersions = vi.fn();
const getPromptVersion = vi.fn();
const createPromptVersion = vi.fn();
const activatePromptVersion = vi.fn();
const listDatasources = vi.fn();
const listArtifacts = vi.fn();
const listMcpServers = vi.fn();
const listMcpTools = vi.fn();
const fetchPermissions = vi.fn();
const toastError = vi.fn();
const toastSuccess = vi.fn();
const grantedPermissions = new Set<string>();

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function flushPendingPromises() {
  return new Promise<void>((resolve) => {
    setTimeout(resolve, 0);
  });
}

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
    nodeTypes: agentNodeTypes,
    aclUsers: agentAclUsers,
    aclRoles: agentAclRoles,
    tools: agentTools,
    useTools: agentUseTools,
    updateStatus: updateAgentStatus,
    updateAcl: updateAgentAcl,
    updatePolicy: updateAgentPolicy,
    defaultUsers: agentDefaultUsers,
    updateDefaultUsers: updateAgentDefaultUsers,
    enterpriseDefault,
    updateEnterpriseDefault,
    promptVersions: listPromptVersions,
    promptVersion: getPromptVersion,
    createPromptVersion,
    activatePromptVersion,
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
      acl: {
        visibility: "role",
        allowed_roles: ["analyst"],
        allowed_user_ids: ["alice"],
      },
    });
    createAgent.mockResolvedValue({ agent_id: "analyst", name: "analyst" });
    editAgent.mockResolvedValue({});
    deleteAgent.mockResolvedValue({});
    updateAgentStatus.mockResolvedValue({});
    updateAgentAcl.mockResolvedValue({});
    updateAgentPolicy.mockResolvedValue({});
    agentDefaultUsers.mockResolvedValue([]);
    updateAgentDefaultUsers.mockResolvedValue([]);
    enterpriseDefault.mockResolvedValue({ default_agent_id: "chat", source: "enterprise" });
    updateEnterpriseDefault.mockResolvedValue({ default_agent_id: "chat", source: "enterprise" });
    listPromptVersions.mockResolvedValue({ active_version_id: null, versions: [] });
    getPromptVersion.mockResolvedValue(null);
    createPromptVersion.mockResolvedValue(null);
    activatePromptVersion.mockResolvedValue(null);
    agentNodeTypes.mockResolvedValue([
      {
        node_class: "gen_sql",
        label: "SQL 分析",
        description: "生成和执行只读 SQL。",
        supports_mcp: true,
      },
      {
        node_class: "ask_metrics",
        label: "指标问答",
        description: "围绕指标、维度和归因分析问答。",
        supports_mcp: false,
      },
    ]);
    agentAclUsers.mockResolvedValue([
      {
        user_id: "alice",
        display_name: "Alice Chen",
        email: "alice@example.com",
        department: "Finance",
        title: "Analyst",
      },
      {
        user_id: "bob",
        display_name: null,
        email: "bob@example.com",
        department: null,
        title: null,
      },
    ]);
    agentAclRoles.mockResolvedValue([
      { role_id: "analyst", name: "Analyst", description: "Read-only analysts" },
      { role_id: "fund_researcher", name: "Fund Researcher", description: null },
    ]);
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
        { name: "fund_pg", display_name: "基金分析库", type: "postgres", is_default: true },
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

  it("defaults newly created enterprise agents to enterprise visibility", async () => {
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    expect(manager.form.value).toMatchObject({
      visibility: "enterprise",
      allowedRoleIds: [],
      allowedUserIds: [],
    });
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

  it("does not expose unrecognized backend errors in Agent feedback", async () => {
    const { ApiResultError } = await import("@/lib/chat");
    listAgents.mockRejectedValue(new ApiResultError(
      "RuntimeError: https://private.example/agents failed at /srv/agent.py",
      "INTERNAL_ERROR",
    ));
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.loadAgents();

    expect(manager.error.value).toBe("读取 Agent 列表失败");
    expect(toastError).toHaveBeenCalledWith("读取 Agent 列表失败");
    expect(JSON.stringify(toastError.mock.calls)).not.toContain("private.example");
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
      promptVersion: "1.0",
      toolsText: "read_query",
      visibility: "role",
      allowedRoleIds: ["analyst"],
      allowedUserIds: ["alice"],
    });
    expect(manager.selectedUseToolCount.value).toBe(2);
    expect(listPromptVersions).toHaveBeenCalledWith("http://api.test", "analyst");
  });

  it("does not keep the main detail loader waiting for prompt versions", async () => {
    const versionRequest = deferred<{
      active_version_id: string | null;
      versions: [];
    }>();
    listPromptVersions.mockReturnValueOnce(versionRequest.promise);
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.selectAgent("analyst");

    expect(manager.detailLoading.value).toBe(false);
    expect(manager.selectedAgent.value?.agent_id).toBe("analyst");
    expect(manager.promptVersions.loading.value).toBe(true);

    versionRequest.resolve({ active_version_id: null, versions: [] });
    await flushPendingPromises();
    expect(manager.promptVersions.loading.value).toBe(false);
  });

  it("loads edit dependencies in parallel while keeping detail loading active", async () => {
    const defaultUsersRequest = deferred<string[]>();
    const useToolsRequest = deferred<{
      default_tools: string[];
      tool_types: Record<string, { tools: string[] }>;
    }>();
    agentDefaultUsers.mockReturnValueOnce(defaultUsersRequest.promise);
    agentUseTools.mockReturnValueOnce(useToolsRequest.promise);
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    const selection = manager.selectAgent("analyst");

    expect(manager.detailLoading.value).toBe(true);
    await flushPendingPromises();
    expect(agentDefaultUsers).toHaveBeenCalledWith("http://api.test", "analyst");
    expect(agentUseTools).toHaveBeenCalledWith("http://api.test", "gen_sql");
    expect(manager.detailLoading.value).toBe(true);

    defaultUsersRequest.resolve(["alice"]);
    useToolsRequest.resolve({
      default_tools: ["read_query"],
      tool_types: { analytics: { tools: ["explain_query"] } },
    });
    await selection;

    expect(manager.detailLoading.value).toBe(false);
    expect(manager.form.value.defaultUserIds).toEqual(["alice"]);
  });

  it("does not let a stale edit request overwrite a newly started form", async () => {
    const detailRequest = deferred<null>();
    getAgent.mockReturnValueOnce(detailRequest.promise);
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    const selection = manager.selectAgent("analyst");
    expect(manager.detailLoading.value).toBe(true);

    manager.startCreate();
    detailRequest.resolve(null);
    await selection;

    expect(manager.detailLoading.value).toBe(false);
    expect(manager.detailError.value).toBeNull();
    expect(manager.formMode.value).toBe("create");
    expect(manager.selectedAgent.value).toBeNull();
    expect(manager.form.value.name).toBe("");
  });

  it("keeps existing agents private when the detail payload has no ACL", async () => {
    getAgent.mockResolvedValue({
      agent_id: "legacy",
      name: "legacy",
      node_class: "gen_sql",
      status: "published",
      source: "enterprise",
      tools: [],
      mcp: [],
      skills: [],
      scoped_context: {},
      rules: [],
      max_turns: 30,
    });
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.selectAgent("legacy");

    expect(manager.form.value.visibility).toBe("private");
  });

  it("distinguishes default tool patterns from saved catalog fallbacks", async () => {
    getAgent.mockResolvedValue({
      agent_id: "analyst",
      name: "analyst",
      node_class: "gen_sql",
      status: "draft",
      source: "custom",
      tools: ["db_tools.*", "legacy_tools.old_method", "db_tools.list_tables"],
      mcp: [],
      skills: [],
      scoped_context: {},
      rules: [],
      max_turns: 30,
    });
    agentUseTools.mockResolvedValue({
      default_tools: ["db_tools.*"],
      tool_types: {
        db_tools: { tools: ["list_tables"] },
      },
    });
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.selectAgent("analyst");

    expect(manager.toolOptions.value).toEqual([
      { value: "legacy_tools.old_method", label: "当前配置：legacy_tools.old_method" },
      { value: "db_tools.*", label: "默认：db_tools.*" },
      { value: "db_tools.list_tables", label: "list_tables", description: "db_tools" },
    ]);
    expect(manager.toolOptions.value.filter(option => option.value === "db_tools.*")).toHaveLength(1);
    expect(manager.selectedTools.value).toEqual([
      "db_tools.*",
      "legacy_tools.old_method",
      "db_tools.list_tables",
    ]);
  });

  it("keeps the bash policy pattern available only in the deny picker", async () => {
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.selectAgent("analyst");

    expect(manager.toolOptions.value.map(option => option.value)).not.toContain("bash_tools.*");
    expect(manager.deniedToolOptions.value).toContainEqual({
      value: "bash_tools.*",
      label: "服务端 Bash",
      description: "策略拒绝规则；Web 和企业会话同时由后端强制禁用",
    });
  });

  it("can add the bash deny rule again after removing it", async () => {
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    manager.toggleListFieldValue("deniedToolsText", "bash_tools.*");
    expect(manager.deniedTools.value).not.toContain("bash_tools.*");
    expect(manager.deniedToolOptions.value.map(option => option.value)).toContain("bash_tools.*");

    manager.toggleListFieldValue("deniedToolsText", "bash_tools.*");
    expect(manager.deniedTools.value).toContain("bash_tools.*");
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
    expect(manager.canSubmitForm.value).toBe(true);
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
    agentNodeTypes.mockResolvedValue([
      {
        node_class: "chat",
        label: "通用聊天",
        description: "面向普通问答、规划和多工具协作。",
        supports_mcp: true,
      },
    ]);
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.loadAgents();
    await manager.loadNodeTypes();
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
      visibility: "enterprise",
      allowedRoleIds: [],
      allowedUserIds: [],
    });
    expect(toastSuccess).toHaveBeenCalledWith("已复制为企业 Agent 草稿，可选择 MCP 后保存。");
  });

  it("does not clone an internal builtin without an enterprise node capability", async () => {
    getAgent.mockResolvedValue({
      agent_id: "gen_semantic_model",
      name: "gen_semantic_model",
      node_class: "gen_semantic_model",
      status: "published",
      source: "builtin",
      tools: [],
      mcp: [],
      skills: [],
      scoped_context: {},
      rules: [],
      max_turns: 30,
    });
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.loadNodeTypes();
    await manager.selectAgent("gen_semantic_model");

    expect(manager.selectedCanCloneBuiltin.value).toBe(false);
    expect(manager.startCreateFromSelectedBuiltin()).toBe(false);
    expect(toastError).toHaveBeenCalledWith("当前系统内置 Agent 不支持复制为企业 Agent。");
  });

  it("loads available agent tool catalogs", async () => {
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.loadToolCatalog();

    expect(agentTools).toHaveBeenCalledWith("http://api.test");
    expect(manager.toolCategoryCount.value).toBe(1);
    expect(manager.toolCount.value).toBe(2);
  });

  it("loads node class options from the enterprise API in response order", async () => {
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.loadNodeTypes();

    expect(agentNodeTypes).toHaveBeenCalledWith("http://api.test");
    expect(manager.nodeClassOptions.value).toEqual([
      {
        value: "gen_sql",
        label: "SQL 分析",
        description: "生成和执行只读 SQL。",
      },
      {
        value: "ask_metrics",
        label: "指标问答",
        description: "围绕指标、维度和归因分析问答。",
      },
    ]);
    expect(manager.nodeTypesLoading.value).toBe(false);
    expect(manager.nodeTypesError.value).toBeNull();
  });

  it("keeps only the selected node class when the node type catalog fails", async () => {
    agentNodeTypes.mockRejectedValue(new Error("unavailable"));
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();
    manager.form.value.nodeClass = "legacy_type";

    await manager.loadNodeTypes();

    expect(manager.nodeClassOptions.value).toEqual([
      { value: "legacy_type", label: "当前：legacy_type" },
    ]);
    expect(manager.nodeTypesError.value).toBe("读取 Agent 节点类型失败");
    expect(toastError).toHaveBeenCalledWith("读取 Agent 节点类型失败");
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

  it("surfaces and removes an Agent MCP binding whose Server no longer exists", async () => {
    listMcpServers.mockResolvedValue({
      servers: [{ name: "remote_api", type: "http", url: "https://api.example.test/mcp" }],
    });
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.selectAgent("analyst");
    await manager.loadMcpCatalog();

    expect(manager.mcpServerOptions.value).toContainEqual({
      name: "filesystem",
      type: "missing",
      target: "Server 已不存在，请解除绑定",
      tools: [],
      selected: true,
      missing: true,
    });

    manager.toggleMcpServer("filesystem");

    expect(manager.form.value.mcpText).toBe("");
    expect(manager.mcpServerOptions.value.some(server => server.name === "filesystem")).toBe(false);
  });

  it("loads datasource and artifact option catalogs for picker fields", async () => {
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.loadResourceCatalogs();

    expect(listDatasources).toHaveBeenCalled();
    expect(listArtifacts).toHaveBeenCalled();
    expect(manager.datasourceOptions.value.map(option => option.value)).toEqual(["fund_pg", "warehouse"]);
    expect(manager.datasourceOptions.value[0]?.label).toContain("默认");
    expect(manager.datasourceOptions.value[0]?.label).toContain("基金分析库 (fund_pg)");
    expect(manager.artifactOptions.value.map(option => option.value)).toEqual(["risk_dashboard", "weekly_report"]);
  });

  it("loads searchable ACL user and role options and toggles selections", async () => {
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.loadAclDirectory();
    manager.toggleAclRole("analyst");
    manager.toggleAclUser("alice");

    expect(agentAclUsers).toHaveBeenCalledWith("http://api.test");
    expect(agentAclRoles).toHaveBeenCalledWith("http://api.test");
    expect(manager.aclUserOptions.value).toContainEqual({
      value: "alice",
      label: "Alice Chen",
      description: "alice · alice@example.com · Finance · Analyst",
    });
    expect(manager.aclRoleOptions.value).toContainEqual({
      value: "analyst",
      label: "Analyst",
      description: "Read-only analysts",
    });
    expect(manager.form.value.allowedRoleIds).toEqual(["analyst"]);
    expect(manager.form.value.allowedUserIds).toEqual(["alice"]);

    manager.toggleAclRole("analyst");
    manager.toggleAclUser("alice");

    expect(manager.form.value.allowedRoleIds).toEqual([]);
    expect(manager.form.value.allowedUserIds).toEqual([]);
  });

  it("loads and updates the enterprise default Agent", async () => {
    updateEnterpriseDefault.mockResolvedValue({
      default_agent_id: "analyst",
      source: "enterprise",
    });
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.loadEnterpriseDefault();
    expect(manager.enterpriseDefaultAgentId.value).toBe("chat");

    await manager.setEnterpriseDefault("analyst");

    expect(updateEnterpriseDefault).toHaveBeenCalledWith("http://api.test", "analyst");
    expect(manager.enterpriseDefaultAgentId.value).toBe("analyst");
    expect(toastSuccess).toHaveBeenCalledWith("企业默认 Agent 已更新");
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
      promptTemplate: "\n  Answer carefully\n",
      promptVersion: "2.1",
      toolsText: "read_query, explain_query",
      mcpText: "filesystem",
      skillsText: "fund-analyst",
      datasourceId: "fund_pg",
      artifactSlug: "risk_dashboard",
      catalogsText: "fund",
      subjectsText: "portfolio\nrisk",
      rulesText: "",
      maxTurns: "8",
      visibility: "role",
      allowedRoleIds: ["analyst", "fund_researcher"],
      allowedUserIds: ["alice", "bob"],
      toolPolicyMode: "allowlist",
      deniedToolsText: "filesystem_tools.*",
      allowSubagentDelegation: false,
      allowedSubagentIds: [],
      defaultUserIds: [],
    };

    await manager.saveForm();

    expect(createAgent).toHaveBeenCalledWith("http://api.test", "researcher", {
      name: "researcher",
      node_class: "gen_sql",
      status: "draft",
      datasource_id: "fund_pg",
      artifact_slug: "risk_dashboard",
      description: "Research agent",
      prompt_template: "\n  Answer carefully\n",
      prompt_language: "en",
      prompt_version: "2.1",
      tools: ["read_query", "explain_query"],
      mcp: ["filesystem"],
      skills: ["fund-analyst"],
      scoped_context: {
        catalogs: ["fund"],
        subjects: ["portfolio", "risk"],
      },
      rules: undefined,
      max_turns: 8,
      acl: {
        visibility: "role",
        allowed_roles: ["analyst", "fund_researcher"],
        allowed_user_ids: ["alice", "bob"],
      },
      tool_policy: {
        mode: "allowlist",
        allowed: ["explain_query", "mcp.filesystem.*", "read_query"],
        denied: ["filesystem_tools.*"],
      },
      runtime_policy: {
        allow_subagent_delegation: false,
        allowed_subagents: [],
      },
    });
    expect(toastSuccess).toHaveBeenCalledWith("Agent 已创建");
  });

  it("does not persist stale MCP bindings for node types without MCP runtime support", async () => {
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();
    await manager.loadNodeTypes();
    manager.form.value.name = "metrics_reader";
    manager.form.value.nodeClass = "ask_metrics";
    manager.form.value.toolsText = "semantic_tools.list_metrics";
    manager.form.value.mcpText = "filesystem";

    expect(manager.selectedNodeSupportsMcp.value).toBe(false);
    expect(manager.selectedMcpCount.value).toBe(0);

    await manager.saveForm();

    expect(createAgent).toHaveBeenCalledWith(
      "http://api.test",
      "metrics_reader",
      expect.objectContaining({
        node_class: "ask_metrics",
        mcp: undefined,
        tool_policy: expect.objectContaining({
          allowed: ["semantic_tools.list_metrics"],
        }),
      }),
    );
  });

  it("explicitly publishes new enterprise agents with enterprise visibility", async () => {
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();
    manager.form.value.name = "company_assistant";
    manager.form.value.status = "published";

    await manager.saveForm();

    expect(createAgent).toHaveBeenCalledWith(
      "http://api.test",
      "company_assistant",
      expect.objectContaining({
        status: "published",
        acl: {
          visibility: "enterprise",
          allowed_roles: [],
          allowed_user_ids: [],
        },
      }),
    );
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
      acl: {
        visibility: "role",
        allowed_roles: ["analyst"],
        allowed_user_ids: ["alice"],
      },
      tool_policy: expect.objectContaining({
        denied: [],
      }),
    }));
  });

  it("persists an explicitly selected bash deny rule", async () => {
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();
    await manager.selectAgent("analyst");
    manager.toggleListFieldValue("deniedToolsText", "bash_tools.*");

    await manager.saveForm();

    expect(editAgent).toHaveBeenCalledWith(
      "http://api.test",
      "analyst",
      expect.objectContaining({
        tool_policy: expect.objectContaining({
          denied: ["bash_tools.*"],
        }),
      }),
    );
  });

  it("saves builtin enterprise policy but does not mutate or delete its definition", async () => {
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
    expect(updateAgentStatus).toHaveBeenCalledWith("http://api.test", "gen_sql", "published");
    expect(updateAgentAcl).toHaveBeenCalled();
    expect(updateAgentPolicy).toHaveBeenCalled();
    expect(updateAgentDefaultUsers).toHaveBeenCalledWith("http://api.test", "gen_sql", []);
    expect(deleteAgent).not.toHaveBeenCalled();
    expect(toastSuccess).toHaveBeenCalledWith("内置 Agent 企业策略已保存");
    expect(toastError).toHaveBeenCalledWith("系统内置 Agent 为只读，不能删除。");
  });

  it("publishes a disabled builtin before assigning its default users", async () => {
    listAgents.mockResolvedValue([
      { agent_id: "gen_sql", name: "gen_sql", node_class: "gen_sql", status: "disabled", source: "builtin" },
    ]);
    getAgent.mockResolvedValue({
      agent_id: "gen_sql",
      name: "gen_sql",
      description: "SQL assistant",
      node_class: "gen_sql",
      status: "disabled",
      source: "builtin",
      tools: [],
      scoped_context: {},
      rules: [],
      max_turns: 30,
    });
    agentDefaultUsers.mockResolvedValue(["alice"]);
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.loadAgents();
    await manager.selectAgent("gen_sql");
    manager.form.value.status = "published";
    await manager.saveForm();

    expect(updateAgentStatus).toHaveBeenCalledWith("http://api.test", "gen_sql", "published");
    expect(updateAgentDefaultUsers).toHaveBeenCalledWith("http://api.test", "gen_sql", ["alice"]);
    expect(updateAgentStatus.mock.invocationCallOrder[0]).toBeLessThan(
      updateAgentDefaultUsers.mock.invocationCallOrder[0] ?? Number.POSITIVE_INFINITY,
    );
  });

  it("clears default user assignments when a builtin remains disabled", async () => {
    listAgents.mockResolvedValue([
      { agent_id: "gen_sql", name: "gen_sql", node_class: "gen_sql", status: "disabled", source: "builtin" },
    ]);
    getAgent.mockResolvedValue({
      agent_id: "gen_sql",
      name: "gen_sql",
      description: "SQL assistant",
      node_class: "gen_sql",
      status: "disabled",
      source: "builtin",
      tools: [],
      scoped_context: {},
      rules: [],
      max_turns: 30,
    });
    agentDefaultUsers.mockResolvedValue(["alice"]);
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.loadAgents();
    await manager.selectAgent("gen_sql");
    await manager.saveForm();

    expect(updateAgentStatus).toHaveBeenCalledWith("http://api.test", "gen_sql", "disabled");
    expect(updateAgentDefaultUsers).toHaveBeenCalledWith("http://api.test", "gen_sql", []);
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
